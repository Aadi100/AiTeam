"""
Provider-agnostic LLM client that reports token usage.

chat(spec, system, prompt) -> (text, tokens_in, tokens_out)

A "spec" is resolved from a UI model string + the available keys:
    "ollama:llama3.2" -> local Ollama      "gemini-2.5-flash" -> Google
    "claude-sonnet-5-5" -> Anthropic       "gpt-4o"           -> OpenAI
If the requested provider has no key, we fall back to any provider that does,
and finally to local Ollama.
"""

import os
import re
import json
import time
import requests

DEFAULTS = {
    'gemini': 'gemini-2.5-flash',
    'claude': 'claude-sonnet-5-5',
    'openai': 'gpt-4o',
    'ollama': 'llama3.2',
}


class LLMError(Exception):
    pass


def effective_keys(keys):
    keys = keys or {}
    return {
        'gemini': keys.get('gemini') or os.getenv('GEMINI_API_KEY', ''),
        'claude': keys.get('claude') or os.getenv('CLAUDE_API_KEY', '') or os.getenv('ANTHROPIC_API_KEY', ''),
        'openai': keys.get('openai') or os.getenv('OPENAI_API_KEY', ''),
        'ollamaUrl': keys.get('ollamaUrl') or os.getenv('OLLAMA_URL', 'http://localhost:11434'),
    }


def _provider_of(model):
    m = (model or '').lower()
    if m.startswith('ollama'):
        return 'ollama'
    if m.startswith('gemini'):
        return 'gemini'
    if m.startswith('claude'):
        return 'claude'
    if m.startswith(('gpt', 'o1', 'o3', 'o4')):
        return 'openai'
    return None


def resolve(model, keys):
    """Return a spec dict {provider, model, key, label}."""
    k = effective_keys(keys)
    provider = _provider_of(model)
    if provider in ('gemini', 'claude', 'openai') and not k[provider]:
        provider = None  # requested provider unavailable
    if provider is None:
        for p in ('claude', 'gemini', 'openai'):
            if k[p]:
                provider, model = p, DEFAULTS[p]
                break
        else:
            provider = 'ollama'
    if provider == 'ollama':
        name = (model or '').split(':', 1)[1] if model and ':' in model else DEFAULTS['ollama']
        return {'provider': 'ollama', 'model': name or DEFAULTS['ollama'],
                'key': k['ollamaUrl'].rstrip('/'), 'label': f"ollama:{name or DEFAULTS['ollama']}"}
    return {'provider': provider, 'model': model, 'key': k[provider], 'label': model}


def _post(url, **kw):
    last = None
    for attempt in range(4):
        try:
            r = requests.post(url, timeout=300, **kw)
        except requests.exceptions.RequestException as e:
            last = f'network error: {e}'
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 529):
            last = f'HTTP {r.status_code}: {r.text[:200]}'
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise LLMError(f'HTTP {r.status_code}: {r.text[:300]}')
        return r.json()
    raise LLMError(last or 'request failed')


def chat(spec, system, prompt, json_mode=True, max_output=8192):
    p, model, key = spec['provider'], spec['model'], spec['key']

    if p == 'ollama':
        body = {
            'model': model, 'stream': False,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
            'options': {'temperature': 0.3, 'num_ctx': 16384},
        }
        if json_mode:
            body['format'] = 'json'
        try:
            d = _post(f'{key}/api/chat', json=body)
        except LLMError as e:
            raise LLMError(f'Ollama ({key}) failed: {e}. Is it running and is the model pulled?')
        return (d.get('message', {}).get('content', ''),
                d.get('prompt_eval_count', 0), d.get('eval_count', 0))

    if p == 'gemini':
        body = {
            'systemInstruction': {'parts': [{'text': system}]},
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.3, 'maxOutputTokens': max_output},
        }
        if json_mode:
            body['generationConfig']['responseMimeType'] = 'application/json'
        d = _post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                  headers={'x-goog-api-key': key}, json=body)
        try:
            text = ''.join(part.get('text', '') for part in d['candidates'][0]['content']['parts'])
        except (KeyError, IndexError):
            raise LLMError(f'Gemini returned no content: {str(d)[:200]}')
        u = d.get('usageMetadata', {})
        return text, u.get('promptTokenCount', 0), u.get('candidatesTokenCount', 0)

    if p == 'claude':
        body = {'model': model, 'max_tokens': max_output, 'system': system,
                'messages': [{'role': 'user', 'content': prompt}]}
        d = _post('https://api.anthropic.com/v1/messages',
                  headers={'x-api-key': key, 'anthropic-version': '2023-06-01'}, json=body)
        text = ''.join(b.get('text', '') for b in d.get('content', []) if b.get('type') == 'text')
        u = d.get('usage', {})
        return text, u.get('input_tokens', 0), u.get('output_tokens', 0)

    if p == 'openai':
        body = {'model': model, 'temperature': 0.3,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}
        if json_mode:
            body['response_format'] = {'type': 'json_object'}
        d = _post('https://api.openai.com/v1/chat/completions',
                  headers={'Authorization': f'Bearer {key}'}, json=body)
        text = d['choices'][0]['message']['content'] or ''
        u = d.get('usage', {})
        return text, u.get('prompt_tokens', 0), u.get('completion_tokens', 0)

    raise LLMError(f'unknown provider {p}')


def parse_json(text):
    """Parse a model reply that should be JSON; tolerate fences and prose around it."""
    if not text:
        return None
    t = re.sub(r'```(?:json|JSON)?', '', text).strip()
    try:
        return json.loads(t, strict=False)
    except json.JSONDecodeError:
        pass
    start = min([i for i in (t.find('{'), t.find('[')) if i != -1], default=-1)
    end = max(t.rfind('}'), t.rfind(']'))
    if start != -1 and end > start:
        try:
            return json.loads(t[start:end + 1], strict=False)
        except json.JSONDecodeError:
            return None
    return None
