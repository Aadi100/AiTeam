"""
LLM client for Adion. DeepSeek only (OpenAI-compatible API, https://platform.deepseek.com).

chat(spec, system, prompt) -> (text, tokens_in, tokens_out)

Models:  "deepseek-chat" (V3, fast, default)   "deepseek-reasoner" (R1, slower, thinks first)
Any other model string saved from an older version is mapped to the default.
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


def cost_usd(hit, miss, out):
    """Exact cost of one call from the usage DeepSeek reports."""
    return (hit * PRICE_HIT + miss * PRICE_MISS + out * PRICE_OUT) / 1_000_000


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
        c = cost_usd(hit, miss, out)
        saved = hit * (PRICE_MISS - PRICE_HIT) / 1_000_000
        ctx = ctx or {}
        UsageDocument(owner=ctx.get('owner', ''), run_id=ctx.get('run_id', ''), task_id=ctx.get('task_id', ''),
                      purpose=ctx.get('purpose', 'other'), model=model, tokens_in=hit + miss, cache_hit=hit,
                      tokens_out=out, cost_usd=c, saved_usd=saved).save()
        if ctx.get('run_id'):
            RunDocument.objects(run_id=ctx['run_id']).update_one(inc__cost_usd=c, inc__cache_hit=hit)
    except Exception:  # noqa: BLE001
        pass


def effective_keys(keys):
    keys = keys or {}
    return {'deepseek': (keys.get('deepseek') or os.getenv('DEEPSEEK_API_KEY', '')).strip()}


def resolve(model, keys):
    """Return a spec dict {provider, model, key, label}."""
    k = effective_keys(keys)
    m = (model or '').strip().lower()
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


def chat_stream(spec, system, prompt, max_output=1200, ctx=None):
    """Streaming chat. Yields ('delta', text) as words arrive, then ('usage', (tokens_in, tokens_out)).
    Raises LLMError on any failure before or during the stream (callers fall back to chat())."""
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
