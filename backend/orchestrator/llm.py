"""
LLM client for Adion. Two providers behind one interface:
  - DeepSeek (OpenAI-compatible API, https://platform.deepseek.com): cheap, the default.
  - Claude (Anthropic, official SDK): stronger, used when the owner adds a key and picks it (or the "mixed" setup).

chat(spec, system, prompt) -> (text, tokens_in, tokens_out)

Models:  "deepseek-chat" (default)  "deepseek-reasoner"  |  "claude-sonnet-5-5" (default Claude)  "claude-haiku-5-5"  "claude-opus-5-5"
The callers never know which provider answered: every function returns the same shapes.
"""

import os
import re
import json
import time
import requests

DEFAULT_MODEL = 'deepseek-chat'
API_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/')


class LLMError(Exception):
    pass


# ── token calculator ─────────────────────────────────────────────────────────
# USD per 1M tokens. DeepSeek bills cached input far below uncached input. Override with env vars if
# DeepSeek changes its prices (https://api-docs.deepseek.com/quick_start/pricing).
PRICE_HIT = float(os.getenv('DEEPSEEK_PRICE_HIT', '0.028'))
PRICE_MISS = float(os.getenv('DEEPSEEK_PRICE_MISS', '0.28'))
PRICE_OUT = float(os.getenv('DEEPSEEK_PRICE_OUT', '0.42'))


# Claude prices, USD per 1M tokens: (cached input, input, output). Override all of them with the env var
# ANTHROPIC_PRICES='{"claude-sonnet-5-5": [0.10, 2.0, 10.0]}' if Anthropic changes its prices.
CLAUDE_DEFAULT = 'claude-sonnet-5-5'
CLAUDE_PRICES = {'claude-sonnet-5-5': (0.10, 2.00, 10.00), 'claude-haiku-5-5': (0.01, 0.10, 0.50), 'claude-opus-5-5': (0.20, 4.00, 20.00)}
try:
    CLAUDE_PRICES.update({k: tuple(float(x) for x in v) for k, v in json.loads(os.getenv('ANTHROPIC_PRICES') or '{}').items()})
except (ValueError, TypeError):
    pass
CLAUDE_LABELS = {'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'claude-haiku-5-5': 'Claude Haiku 5.5', 'claude-opus-5-5': 'Claude Opus 5.5'}


def _prices(model):
    return CLAUDE_PRICES.get(model) or (PRICE_HIT, PRICE_MISS, PRICE_OUT)


def cost_usd(hit, miss, out, model=''):
    """Exact cost of one call from the usage the provider reports."""
    ph, pm, po = _prices(model)
    return (hit * ph + miss * pm + out * po) / 1_000_000


CODE_CHARS = set('{}[]()<>;=:,"_#$%&*|/') | {chr(92), chr(39)}


def count_tokens(text):
    """Offline estimate (no tokenizer download): ~4 chars/token for English, ~3 for code and JSON."""
    t = text or ''
    if not t:
        return 0
    symbols = sum(1 for c in t if c in CODE_CHARS)
    code_like = symbols / len(t) > 0.06
    return max(1, round(len(t) / (3.0 if code_like else 4.0)))


def record_usage(ctx, model, hit, miss, out):
    """Write the ledger row and roll the cost into the run. Never raises (accounting must not break a build)."""
    try:
        from models import UsageDocument, RunDocument
        c = cost_usd(hit, miss, out, model)
        ph, pm, _ = _prices(model)
        saved = hit * (pm - ph) / 1_000_000
        ctx = ctx or {}
        UsageDocument(owner=ctx.get('owner', ''), run_id=ctx.get('run_id', ''), task_id=ctx.get('task_id', ''),
                      purpose=ctx.get('purpose', 'other'), model=model, tokens_in=hit + miss, cache_hit=hit,
                      tokens_out=out, cost_usd=c, saved_usd=saved, client_id=ctx.get('client_id', ''), app_id=ctx.get('app_id', ''),
                      end_user=ctx.get('end_user', '')).save()
        if ctx.get('run_id'):
            RunDocument.objects(run_id=ctx['run_id']).update_one(inc__cost_usd=c, inc__cache_hit=hit)
    except Exception:  # noqa: BLE001
        pass


def effective_keys(keys):
    keys = keys or {}
    return {'deepseek': (keys.get('deepseek') or os.getenv('DEEPSEEK_API_KEY', '')).strip(),
            'anthropic': (keys.get('anthropic') or os.getenv('ANTHROPIC_API_KEY', '')).strip(),
            'brain': (keys.get('brain') or os.getenv('ADION_BRAIN', 'deepseek')).strip().lower()}


# Which jobs the owner's "mixed" setting gives to Claude: thinking and talking. Writing the files stays on the cheap model.
SMART_ROLES = ('planner', 'chat', 'apps', 'pc', 'assistant')
BRAINS = ('deepseek', 'claude', 'mixed')


def resolve(model, keys, role=''):
    """Return a spec dict {provider, model, key, label}.
    An explicit "claude-..." model is honoured when a Claude key exists. Otherwise the owner's brain setting decides:
    deepseek = everything on DeepSeek, claude = everything on Claude, mixed = Claude for SMART_ROLES, DeepSeek for the rest."""
    k = effective_keys(keys)
    m = (model or '').strip().lower()
    want_claude = False
    if m.startswith('claude'):
        want_claude = True
    elif not m.startswith('deepseek-reasoner'):
        want_claude = k['brain'] == 'claude' or (k['brain'] == 'mixed' and role in SMART_ROLES)
    if want_claude and k['anthropic']:
        cm = m if m in CLAUDE_PRICES else CLAUDE_DEFAULT
        return {'provider': 'anthropic', 'model': cm, 'key': k['anthropic'], 'label': cm}
    if not m.startswith('deepseek'):
        m = DEFAULT_MODEL
    return {'provider': 'deepseek', 'model': m, 'key': k['deepseek'], 'label': m}


def _post(url, **kw):
    last = None
    for attempt in range(4):
        try:
            r = requests.post(url, timeout=300, **kw)
        except requests.exceptions.RequestException as e:
            last = f'network error: {e}'
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503):
            last = f'HTTP {r.status_code}: {r.text[:200]}'
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 401:
            raise LLMError('DeepSeek rejected the API key (401). Check it in Models & keys.')
        if r.status_code == 402:
            raise LLMError('DeepSeek account has insufficient balance (402). Top up at platform.deepseek.com.')
        if r.status_code >= 400:
            raise LLMError(f'HTTP {r.status_code}: {r.text[:300]}')
        return r.json()
    raise LLMError(last or 'request failed')


def chat(spec, system, prompt, json_mode=True, max_output=8192, ctx=None):
    """ctx = {owner, run_id, task_id, purpose} labels the call in the usage ledger."""
    if spec.get('provider') == 'anthropic':
        from orchestrator import claude_llm
        return claude_llm.chat(spec, system, prompt, json_mode, max_output, ctx)
    model, key = spec['model'], spec['key']
    if not key:
        raise LLMError('No DeepSeek API key. Add one in "Models & keys" (get it at platform.deepseek.com) '
                       'or set DEEPSEEK_API_KEY in backend/.env.')
    # the reasoner spends part of max_tokens on its reasoning, so it needs far more headroom for the JSON itself
    body = {'model': model, 'temperature': 0.3, 'max_tokens': 24000 if model == 'deepseek-reasoner' else min(max_output, 8192),
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}
    if json_mode and model != 'deepseek-reasoner':
        body['response_format'] = {'type': 'json_object'}
        # DeepSeek's JSON mode requires the word "json" in the prompt.
        if 'json' not in (system + prompt).lower():
            body['messages'][0]['content'] += '\nRespond with valid JSON only.'
    d = _post(f'{API_URL}/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=body)
    try:
        text = d['choices'][0]['message'].get('content') or ''
    except (KeyError, IndexError):
        raise LLMError(f'DeepSeek returned no content: {str(d)[:200]}')
    u = d.get('usage', {})
    ti, to = u.get('prompt_tokens', 0), u.get('completion_tokens', 0)
    hit = u.get('prompt_cache_hit_tokens', 0)
    miss = u.get('prompt_cache_miss_tokens', max(0, ti - hit))
    record_usage(ctx, model, hit, miss, to)
    return text, ti, to


def chat_tools(spec, messages, tools=None, max_output=900, ctx=None):
    """One chat turn with function calling (OpenAI-style tools). messages = full list incl. the system message.
    Returns {'content', 'tool_calls': [{'id','name','arguments'}], 'tokens_in', 'tokens_out'}."""
    if spec.get('provider') == 'anthropic':
        from orchestrator import claude_llm
        return claude_llm.chat_tools(spec, messages, tools, max_output, ctx)
    model, key = spec['model'], spec['key']
    if not key:
        raise LLMError('No DeepSeek API key is configured on the server.')
    body = {'model': model, 'temperature': 0.3, 'max_tokens': min(max_output, 8192), 'messages': messages}
    if tools:
        body['tools'] = tools
        body['tool_choice'] = 'auto'
    d = _post(f'{API_URL}/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=body)
    try:
        msg = d['choices'][0]['message']
    except (KeyError, IndexError):
        raise LLMError(f'DeepSeek returned no content: {str(d)[:200]}')
    u = d.get('usage', {})
    ti, to = u.get('prompt_tokens', 0), u.get('completion_tokens', 0)
    hit = u.get('prompt_cache_hit_tokens', 0)
    record_usage(ctx, model, hit, u.get('prompt_cache_miss_tokens', max(0, ti - hit)), to)
    calls = [{'id': c.get('id') or f'call_{i}', 'name': (c.get('function') or {}).get('name', ''), 'arguments': (c.get('function') or {}).get('arguments', '{}')}
             for i, c in enumerate(msg.get('tool_calls') or [])]
    return {'content': msg.get('content') or '', 'tool_calls': calls, 'tokens_in': ti, 'tokens_out': to}


def chat_tools_stream(spec, messages, tools=None, max_output=900, ctx=None, on_delta=None):
    """Like chat_tools, but the text is streamed: on_delta(text_so_far) is called as words arrive (it may raise to stop the stream).
    Returns the same dict as chat_tools. Falls back to one normal call when streaming is switched off (ADION_STREAM=0) or fails before any output."""
    if os.getenv('ADION_STREAM', '1') == '0' or not on_delta:
        return chat_tools(spec, messages, tools, max_output, ctx)
    if spec.get('provider') == 'anthropic':
        from orchestrator import claude_llm
        return claude_llm.stream(spec, messages, tools, max_output, ctx, on_delta)
    model, key = spec['model'], spec['key']
    if not key:
        raise LLMError('No DeepSeek API key is configured on the server.')
    body = {'model': model, 'temperature': 0.3, 'max_tokens': min(max_output, 8192), 'messages': messages, 'stream': True, 'stream_options': {'include_usage': True}}
    if tools:
        body['tools'], body['tool_choice'] = tools, 'auto'
    text, calls, usage, got = '', {}, {}, False
    try:
        r = requests.post(f'{API_URL}/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=body, stream=True, timeout=(10, 90))
        if r.status_code == 401:
            raise LLMError('DeepSeek rejected the API key (401). Check the key on the Owner tab.')
        if r.status_code == 402:
            raise LLMError('DeepSeek account has insufficient balance (402). Top up at platform.deepseek.com.')
        if r.status_code >= 400:
            raise requests.exceptions.RequestException(f'HTTP {r.status_code}')
        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if chunk.get('usage'):
                    usage = chunk['usage']
                for ch in chunk.get('choices') or []:
                    d = ch.get('delta') or {}
                    if d.get('content'):
                        text, got = text + d['content'], True
                        on_delta(text)
                    for tc in d.get('tool_calls') or []:
                        c = calls.setdefault(tc.get('index', 0), {'id': '', 'name': '', 'arguments': ''})
                        c['id'] = tc.get('id') or c['id']
                        fn = tc.get('function') or {}
                        c['name'] = fn.get('name') or c['name']
                        c['arguments'] += fn.get('arguments') or ''
                        got = True
        finally:
            r.close()
    except LLMError:
        raise
    except requests.exceptions.RequestException as e:
        if got:
            raise LLMError(f'stream interrupted: {e}')
        return chat_tools(spec, messages, tools, max_output, ctx)      # nothing arrived yet: one normal call instead
    ti, to = usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)
    hit = usage.get('prompt_cache_hit_tokens', 0)
    record_usage(ctx, model, hit, usage.get('prompt_cache_miss_tokens', max(0, ti - hit)), to)
    out = [{'id': c['id'] or f'call_{i}', 'name': c['name'], 'arguments': c['arguments'] or '{}'} for i, c in sorted(calls.items())]
    return {'content': text, 'tool_calls': out, 'tokens_in': ti, 'tokens_out': to}


def chat_stream(spec, system, prompt, max_output=1200, ctx=None):
    """Streaming chat. Yields ('delta', text) as words arrive, then ('usage', (tokens_in, tokens_out)).
    Raises LLMError on any failure before or during the stream (callers fall back to chat())."""
    if spec.get('provider') == 'anthropic':
        from orchestrator import claude_llm
        yield from claude_llm.chat_stream(spec, system, prompt, max_output, ctx)
        return
    model, key = spec['model'], spec['key']
    if not key:
        raise LLMError('No DeepSeek API key. Add one in "Models & keys" or set DEEPSEEK_API_KEY in backend/.env.')
    body = {'model': model, 'temperature': 0.3, 'max_tokens': min(max_output, 8192), 'stream': True,
            'stream_options': {'include_usage': True},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]}
    try:
        r = requests.post(f'{API_URL}/chat/completions', headers={'Authorization': f'Bearer {key}'}, json=body,
                          stream=True, timeout=(10, 90))
    except requests.exceptions.RequestException as e:
        raise LLMError(f'network error: {e}')
    if r.status_code == 401:
        raise LLMError('DeepSeek rejected the API key (401). Check it in Models & keys.')
    if r.status_code == 402:
        raise LLMError('DeepSeek account has insufficient balance (402). Top up at platform.deepseek.com.')
    if r.status_code >= 400:
        raise LLMError(f'HTTP {r.status_code}: {r.text[:200]}')
    usage = {}
    try:
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get('usage'):
                usage = chunk['usage']
            for ch in chunk.get('choices') or []:
                piece = (ch.get('delta') or {}).get('content')
                if piece:
                    yield 'delta', piece
    except requests.exceptions.RequestException as e:
        raise LLMError(f'stream interrupted: {e}')
    finally:
        r.close()
    ti, to = usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)
    hit = usage.get('prompt_cache_hit_tokens', 0)
    record_usage(ctx, model, hit, usage.get('prompt_cache_miss_tokens', max(0, ti - hit)), to)
    yield 'usage', (ti, to)


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
