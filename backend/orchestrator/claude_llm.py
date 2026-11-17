"""
Claude (Anthropic) behind Adion's one LLM interface.

The rest of Adion speaks OpenAI-style messages and tool calls (that is what DeepSeek speaks). These helpers translate to and from
Claude's Messages API with the official `anthropic` SDK, so no caller has to know which provider answered:
every function returns exactly the shapes orchestrator/llm.py returns.
"""

import os
import re
import json
import threading
from collections import OrderedDict

from orchestrator import llm as L

_clients = {}
_BLOCKS = OrderedDict()          # first tool-call id -> the assistant's raw content blocks (thinking blocks must be sent back unchanged)
_BLOCKS_LOCK = threading.Lock()
FALLBACK_BETA = 'server-side-fallback-2026-07-01'
NO_KEY = 'No Claude API key. The owner can add one on the Owner tab (console.anthropic.com).'


def client(key):
    c = _clients.get(key)
    if c is None:
        import anthropic
        c = _clients[key] = anthropic.Anthropic(api_key=key, max_retries=3, timeout=anthropic.Timeout(600.0, connect=10.0))
    return c


def to_llm_error(e):
    """An Anthropic SDK error as a short message a person can act on."""
    import anthropic
    msg = str(getattr(e, 'message', '') or e)
    if isinstance(e, anthropic.AuthenticationError):
        return L.LLMError('Claude rejected the API key (401). Check it on the Owner tab.')
    if 'credit balance' in msg.lower():
        return L.LLMError('The Anthropic account has no credit left. Add some at console.anthropic.com under Billing.')
    if isinstance(e, anthropic.RateLimitError):
        return L.LLMError('Claude is rate limiting requests (429). Try again in a moment.')
    if isinstance(e, anthropic.APIConnectionError):
        return L.LLMError(f'network error: {msg}')
    return L.LLMError(f'Claude error {getattr(e, "status_code", "")}: {msg[:300]}')


def _tools(tools):
    out = []
    for t in tools or []:
        f = t.get('function') or t
        out.append({'name': f['name'], 'description': f.get('description', ''),
                    'input_schema': f.get('parameters') or {'type': 'object', 'properties': {}}})
    return out


def _text(t):
    return {'type': 'text', 'text': t}


def to_claude_messages(messages):
    """OpenAI-style messages -> (system text, Claude messages). Consecutive tool results share one user turn."""
    system, out = [], []

    def push(role, blocks):
        if out and out[-1]['role'] == role:
            out[-1]['content'].extend(blocks)
        else:
            out.append({'role': role, 'content': list(blocks)})

    for m in messages:
        role, content = m.get('role'), m.get('content')
        if role == 'system':
            if content:
                system.append(str(content))
        elif role == 'tool':
            push('user', [{'type': 'tool_result', 'tool_use_id': m.get('tool_call_id', ''), 'content': str(content or '(no output)')}])
        elif role == 'assistant':
            calls = m.get('tool_calls') or []
            ids = {c['id'] for c in calls}
            raw = _BLOCKS.get(calls[0]['id']) if calls else None
            if raw:
                # the exact blocks Claude produced (thinking included), minus any tool call the agent decided not to run
                blocks = [b for b in raw if getattr(b, 'type', None) != 'tool_use' or b.id in ids]
            else:
                blocks = [_text(content)] if content and str(content).strip() else []
                for c in calls:
                    fn = c.get('function') or {}
                    try:
                        args = json.loads(fn.get('arguments') or '{}')
                    except json.JSONDecodeError:
                        args = {}
                    blocks.append({'type': 'tool_use', 'id': c['id'], 'name': fn.get('name', ''), 'input': args if isinstance(args, dict) else {}})
            push('assistant', blocks or [_text('(no reply)')])
        else:
            if isinstance(content, list):
                blocks = content
            else:
                blocks = [_text(str(content))] if content and str(content).strip() else [_text('(empty)')]
            push('user', blocks)
    if not out or out[0]['role'] != 'user':
        out.insert(0, {'role': 'user', 'content': [_text('(start)')]})
    return '\n\n'.join(system), out


def params(spec, system, messages, tools, max_output, loop):
    """Request arguments. loop=True is a tool loop: thinking is switched off where the model allows it (Sonnet, Haiku) because the
    conversation is rebuilt from Adion's own history. Single answers and plans think (adaptive) at higher effort."""
    model = spec['model']
    kw = {'model': model, 'max_tokens': min(max(int(max_output or 0) * 2, 4096), 16000), 'messages': messages,
          'cache_control': {'type': 'ephemeral'}}
    if system:
        kw['system'] = system
    if tools:
        kw['tools'] = _tools(tools)
    if loop and model == 'claude-sonnet-5-5':
        kw['thinking'] = {'type': 'between_tools'}
    elif loop and model == 'claude-haiku-5-5':
        kw['thinking'] = {'type': 'disabled'}
    kw['output_config'] = {'effort': 'high' if (not loop and model != 'claude-haiku-5-5') else 'medium'}
    if os.getenv('ANTHROPIC_FALLBACK', '1') != '0' and model != 'claude-haiku-5-5':
        kw['betas'], kw['fallbacks'] = [FALLBACK_BETA], 'default'
    else:
        kw['betas'] = []
    return kw


def finish(spec, msg, ctx):
    """A finished Claude message -> usage in the ledger, text, tool calls (raw blocks remembered for the next turn)."""
    u = msg.usage
    hit = getattr(u, 'cache_read_input_tokens', 0) or 0
    miss = (getattr(u, 'input_tokens', 0) or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0)
    to = getattr(u, 'output_tokens', 0) or 0
    L.record_usage(ctx, spec['model'], hit, miss, to)
    if msg.stop_reason == 'refusal':
        sd = getattr(msg, 'stop_details', None)
        cat = getattr(sd, 'category', None) if sd is not None else None
        raise L.LLMError('Claude declined this request' + (f' ({cat})' if cat else '') + '. Rephrase it or switch the model on the Owner tab.')
    text = ''.join(b.text for b in msg.content if b.type == 'text')
    uses = [b for b in msg.content if b.type == 'tool_use']
    if msg.stop_reason == 'max_tokens' and uses:
        raise L.LLMError('Claude ran out of room in the middle of a tool call. Try again with a shorter request.')
    calls = [{'id': b.id, 'name': b.name, 'arguments': json.dumps(b.input or {})} for b in uses]
    if calls:
        with _BLOCKS_LOCK:
            _BLOCKS[calls[0]['id']] = list(msg.content)
            while len(_BLOCKS) > 400:
                _BLOCKS.popitem(last=False)
    return {'content': text, 'tool_calls': calls, 'tokens_in': hit + miss, 'tokens_out': to}


def call(spec, system, messages, tools, max_output, ctx, loop):
    import anthropic
    if not spec.get('key'):
        raise L.LLMError(NO_KEY)
    try:
        msg = client(spec['key']).beta.messages.create(**params(spec, system, messages, tools, max_output, loop))
    except anthropic.APIError as e:
        raise to_llm_error(e)
    return finish(spec, msg, ctx)


def chat(spec, system, prompt, json_mode, max_output, ctx):
    """Same contract as llm.chat: (text, tokens_in, tokens_out). Claude has no JSON mode, so JSON is asked for in words (parse_json is tolerant)."""
    if json_mode:
        system += '\nRespond with valid JSON only, with no text before or after it.'
    r = call(spec, system, [{'role': 'user', 'content': [_text(prompt)]}], None, max_output, ctx, False)
    return r['content'], r['tokens_in'], r['tokens_out']


def chat_tools(spec, messages, tools, max_output, ctx):
    system, msgs = to_claude_messages(messages)
    return call(spec, system, msgs, tools, max_output, ctx, True)


def stream(spec, messages, tools, max_output, ctx, on_delta):
    """Same contract as llm.chat_tools_stream. on_delta(text_so_far) may raise to stop the stream; that exception is passed up untouched."""
    import anthropic
    if not spec.get('key'):
        raise L.LLMError(NO_KEY)
    system, msgs = to_claude_messages(messages)
    got = False
    try:
        with client(spec['key']).beta.messages.stream(**params(spec, system, msgs, tools, max_output, True)) as st:
            text = ''
            for ev in st:
                if ev.type == 'content_block_delta' and getattr(ev.delta, 'type', '') == 'text_delta':
                    text, got = text + ev.delta.text, True
                    on_delta(text)
                elif ev.type == 'content_block_start' and getattr(ev.content_block, 'type', '') == 'tool_use':
                    got = True
            final = st.get_final_message()
    except anthropic.APIConnectionError as e:
        if got:
            raise L.LLMError(f'stream interrupted: {e}')
        return call(spec, system, msgs, tools, max_output, ctx, True)      # nothing arrived yet: one normal call instead
    except anthropic.APIError as e:
        raise to_llm_error(e)
    return finish(spec, final, ctx)


def chat_stream(spec, system, prompt, max_output, ctx):
    """Same contract as llm.chat_stream: yields ('delta', piece) then ('usage', (tokens_in, tokens_out))."""
    import anthropic
    if not spec.get('key'):
        raise L.LLMError(NO_KEY)
    try:
        with client(spec['key']).beta.messages.stream(**params(spec, system, [{'role': 'user', 'content': [_text(prompt)]}], None, max_output, False)) as st:
            for piece in st.text_stream:
                if piece:
                    yield 'delta', piece
            final = st.get_final_message()
    except anthropic.APIError as e:
        raise to_llm_error(e)
    r = finish(spec, final, ctx)
    yield 'usage', (r['tokens_in'], r['tokens_out'])


def web_search(spec, query, ctx=None):
    """Claude's own built-in web search (a server-side tool: Anthropic runs the search, no Tavily key needed).
    -> ({'results': [{title, url, content}, ...]}, searches_made). The first result is Claude's short summary (flagged 'summary': it is not a page)."""
    import anthropic
    if not spec.get('key'):
        raise L.LLMError(NO_KEY)
    tool = {'type': 'web_search_20250305' if spec['model'] == 'claude-haiku-5-5' else 'web_search_20260209', 'name': 'web_search', 'max_uses': 3}
    msgs = [{'role': 'user', 'content': [_text(f'Search the web and report what you find for: {query}\n\n'
                                              'Answer in under 250 words with the key facts only. If nothing useful turns up, say so.')]}]
    kw = {'model': spec['model'], 'max_tokens': 4000, 'messages': msgs, 'tools': [tool], 'output_config': {'effort': 'low'}}
    n, sources, cited, text = 0, [], {}, ''
    for _ in range(3):                      # a long search can pause the turn: carry on from where it stopped
        try:
            msg = client(spec['key']).beta.messages.create(**kw)
        except anthropic.APIError as e:
            raise to_llm_error(e)
        u = msg.usage
        hit = getattr(u, 'cache_read_input_tokens', 0) or 0
        L.record_usage(dict(ctx or {}, purpose='search'), spec['model'], hit, (getattr(u, 'input_tokens', 0) or 0) + (getattr(u, 'cache_creation_input_tokens', 0) or 0), getattr(u, 'output_tokens', 0) or 0)
        if msg.stop_reason == 'refusal':
            raise L.LLMError('Claude declined to search for that.')
        for b in msg.content:
            if b.type == 'server_tool_use' and getattr(b, 'name', '') == 'web_search':
                n += 1
            elif b.type == 'web_search_tool_result':
                if isinstance(b.content, list):
                    sources += [r for r in b.content if getattr(r, 'type', '') == 'web_search_result']
                else:
                    raise L.LLMError('Claude web search failed: ' + str(getattr(b.content, 'error_code', 'unknown error')))
            elif b.type == 'text':
                text += b.text
                for c in getattr(b, 'citations', None) or []:
                    if getattr(c, 'url', None):
                        cited.setdefault(c.url, getattr(c, 'cited_text', '') or '')
        if msg.stop_reason != 'pause_turn':
            break
        msgs.append({'role': 'assistant', 'content': msg.content})
    res, seen = [], set()
    for r in sources:
        if r.url not in seen and len(res) < 5:
            seen.add(r.url)
            res.append({'title': (getattr(r, 'title', '') or r.url)[:120], 'url': r.url, 'content': re.sub(r'\s+', ' ', cited.get(r.url) or getattr(r, 'title', '') or '').strip()[:420]})
    summary = text.strip()
    if summary:
        res.insert(0, {'title': 'Search summary', 'url': res[0]['url'] if res else '', 'content': summary[:1800], 'summary': True})
    return {'results': res}, n
