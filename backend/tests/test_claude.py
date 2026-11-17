"""Offline tests: Claude as a second model provider (key, owner's switch, message translation, tools, streaming, cost). No network, no credits."""
import os, sys, types, json
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
os.environ['ADION_LEARN'] = '0'      # learning has its own tests (test_learn.py); here it would consume the scripted model replies
os.environ.pop('ANTHROPIC_API_KEY', None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import anthropic, httpx2
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import llm, claude_llm
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

NS = types.SimpleNamespace
K = {'deepseek': 'sk-ds', 'anthropic': 'sk-ant-testtesttesttest'}

# ───────── which model does a job get ─────────
def who(model, keys, role=''):
    s = llm.resolve(model, keys, role); return s['provider'], s['model']
check('R1: default is DeepSeek even when a Claude key exists', who('', dict(K, brain='deepseek')) == ('deepseek', 'deepseek-chat'))
check('R2: brain=claude puts every job on Claude', who('deepseek-chat', dict(K, brain='claude'), 'worker') == ('anthropic', 'claude-sonnet-5-5'))
check('R3: brain=mixed: planner/chat on Claude, the file-writing worker on DeepSeek', who('deepseek-chat', dict(K, brain='mixed'), 'planner') == ('anthropic', 'claude-sonnet-5-5') and who('deepseek-chat', dict(K, brain='mixed'), 'worker') == ('deepseek', 'deepseek-chat'))
check('R4: an explicit Claude model is honoured', who('claude-haiku-5-5', dict(K, brain='deepseek')) == ('anthropic', 'claude-haiku-5-5'))
check('R5: Claude chosen but no Claude key -> DeepSeek, never a broken call', who('claude-opus-5-5', {'deepseek': 'sk-ds', 'brain': 'claude'}) == ('deepseek', 'deepseek-chat') and who('', {'deepseek': 'sk-ds', 'brain': 'claude'}) == ('deepseek', 'deepseek-chat'))
check('R6: the deep-planning reasoner stays on DeepSeek', who('deepseek-reasoner', dict(K, brain='claude'), 'planner') == ('deepseek', 'deepseek-reasoner'))
check('R7: an unknown claude model name maps to the default Claude', who('claude-whatever', K) == ('anthropic', 'claude-sonnet-5-5'))
check('R8: the old call shape (no role) still works', llm.resolve('deepseek-chat', {'deepseek': 'k'})['provider'] == 'deepseek')

# ───────── price ─────────
check('C1: Claude costs use Claude prices (Sonnet 5.5: $2 in, $10 out, $0.10 cached per 1M)', abs(llm.cost_usd(1_000_000, 1_000_000, 1_000_000, 'claude-sonnet-5-5') - 12.10) < 1e-9)
check('C2: DeepSeek cost is unchanged', abs(llm.cost_usd(1_000_000, 0, 0) - llm.PRICE_HIT) < 1e-9)

# ───────── message translation ─────────
msgs = [{'role': 'system', 'content': 'You are Adion.'}, {'role': 'system', 'content': 'Be brief.'},
        {'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': 'Hello!'}, {'role': 'user', 'content': 'search cats'},
        {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 't1', 'type': 'function', 'function': {'name': 'web_search', 'arguments': '{"query": "cats"}'}},
                                                            {'id': 't2', 'type': 'function', 'function': {'name': 'recall', 'arguments': 'not json'}}]},
        {'role': 'tool', 'tool_call_id': 't1', 'content': 'result one'}, {'role': 'tool', 'tool_call_id': 't2', 'content': ''}]
system, out = claude_llm.to_claude_messages(msgs)
check('T1: system messages are joined and lifted out', system == 'You are Adion.\n\nBe brief.' and all(m['role'] != 'system' for m in out))
check('T2: roles alternate, starting with the user', [m['role'] for m in out] == ['user', 'assistant', 'user', 'assistant', 'user'], [m['role'] for m in out])
tu = [b for b in out[3]['content'] if b['type'] == 'tool_use']
check('T3: tool calls become tool_use blocks with parsed input (bad JSON becomes {})', [(b['id'], b['name'], b['input']) for b in tu] == [('t1', 'web_search', {'query': 'cats'}), ('t2', 'recall', {})] and out[3]['content'][0]['type'] == 'tool_use')
check('T4: both tool results ride in ONE user turn, in order; empty output gets a placeholder', [(b['type'], b['tool_use_id'], b['content']) for b in out[4]['content']] == [('tool_result', 't1', 'result one'), ('tool_result', 't2', '(no output)')])
s2, o2 = claude_llm.to_claude_messages([{'role': 'assistant', 'content': 'x'}])
check('T5: a conversation that starts with the assistant still starts with a user turn', o2[0]['role'] == 'user' and o2[1]['role'] == 'assistant')
check('T6: empty text never becomes an empty block', claude_llm.to_claude_messages([{'role': 'user', 'content': '  '}])[1][0]['content'][0]['text'] == '(empty)')
tl = claude_llm._tools([{'type': 'function', 'function': {'name': 'a', 'description': 'd', 'parameters': {'type': 'object', 'properties': {'q': {'type': 'string'}}}}}, {'type': 'function', 'function': {'name': 'b'}}])
check('T7: OpenAI tool schemas become Claude tools (missing parameters -> empty object)', tl[0] == {'name': 'a', 'description': 'd', 'input_schema': {'type': 'object', 'properties': {'q': {'type': 'string'}}}} and tl[1]['input_schema'] == {'type': 'object', 'properties': {}})

# ───────── request settings ─────────
son = claude_llm.params({'model': 'claude-sonnet-5-5'}, 'sys', [], None, 900, True)
check('P1: Sonnet in a tool loop: thinking off (between_tools), cache on, fallback to a safer model on, no temperature', son['thinking'] == {'type': 'between_tools'} and son['cache_control'] == {'type': 'ephemeral'} and son['fallbacks'] == 'default' and claude_llm.FALLBACK_BETA in son['betas'] and 'temperature' not in son, son)
hai = claude_llm.params({'model': 'claude-haiku-5-5'}, '', [], None, 900, True)
check('P2: Haiku in a tool loop: thinking disabled, no fallback option', hai['thinking'] == {'type': 'disabled'} and 'fallbacks' not in hai and hai['betas'] == [])
opu = claude_llm.params({'model': 'claude-opus-5-5'}, '', [], None, 900, True)
check('P3: Opus cannot turn thinking off, so none is sent', 'thinking' not in opu)
pl = claude_llm.params({'model': 'claude-sonnet-5-5'}, '', [], None, 6000, False)
check('P4: a plan (single answer) thinks at high effort and gets room for its thinking', 'thinking' not in pl and pl['output_config'] == {'effort': 'high'} and pl['max_tokens'] == 12000 and son['max_tokens'] == 4096, pl)
os.environ['ANTHROPIC_FALLBACK'] = '0'
check('P5: ANTHROPIC_FALLBACK=0 switches the fallback off', 'fallbacks' not in claude_llm.params({'model': 'claude-sonnet-5-5'}, '', [], None, 900, True))
os.environ.pop('ANTHROPIC_FALLBACK')

# ───────── a fake Claude ─────────
CALLS, REPLIES = [], []
def usage(i=100, o=20, hit=0): return NS(input_tokens=i, output_tokens=o, cache_read_input_tokens=hit, cache_creation_input_tokens=0)
def text_msg(t, stop='end_turn'): return NS(content=[NS(type='text', text=t)], usage=usage(), stop_reason=stop, stop_details=None)
class FakeMessages:
    def create(self, **kw):
        CALLS.append(kw); r = REPLIES.pop(0)
        if isinstance(r, Exception): raise r
        return r
    def stream(self, **kw):
        CALLS.append(kw); r = REPLIES.pop(0)
        if isinstance(r, Exception): raise r
        return FakeStream(r)
class FakeStream:
    def __init__(self, msg): self.msg = msg
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self):
        for b in self.msg.content:
            if b.type == 'text':
                for w in b.text.split(' '):
                    yield NS(type='content_block_delta', delta=NS(type='text_delta', text=w + ' '))
            elif b.type == 'tool_use':
                yield NS(type='content_block_start', content_block=b)
    @property
    def text_stream(self):
        for ev in self:
            if ev.type == 'content_block_delta': yield ev.delta.text
    def get_final_message(self): return self.msg
claude_llm.client = lambda key: NS(beta=NS(messages=FakeMessages()))
SPEC = {'provider': 'anthropic', 'model': 'claude-sonnet-5-5', 'key': 'sk-ant-testtesttesttest', 'label': 'x'}

REPLIES[:] = [text_msg('{"ok": true}')]
text, ti, to = llm.chat(SPEC, 'plan it', 'goal', json_mode=True, max_output=700)
check('A1: chat() returns text and tokens through Claude', text == '{"ok": true}' and (ti, to) == (100, 20) and llm.parse_json(text) == {'ok': True})
check('A2: JSON is requested in words (Claude has no JSON mode)', 'JSON' in CALLS[-1]['system'] and CALLS[-1]['messages'] == [{'role': 'user', 'content': [{'type': 'text', 'text': 'goal'}]}])

thinking = NS(type='thinking', thinking='', signature='sig123')
tool = NS(type='tool_use', id='toolu_1', name='web_search', input={'query': 'cats'})
tool2 = NS(type='tool_use', id='toolu_2', name='recall', input={'query': 'x'})
REPLIES[:] = [NS(content=[thinking, NS(type='text', text='Let me look.'), tool, tool2], usage=usage(), stop_reason='tool_use', stop_details=None), text_msg('Done.')]
r = llm.chat_tools(SPEC, [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'cats?'}], [{'type': 'function', 'function': {'name': 'web_search', 'parameters': {}}}])
check('A3: tool calls come back in the common shape', [(c['id'], c['name'], json.loads(c['arguments'])) for c in r['tool_calls']] == [('toolu_1', 'web_search', {'query': 'cats'}), ('toolu_2', 'recall', {'query': 'x'})] and r['content'] == 'Let me look.')
# the agent keeps only the first call; the next request must carry Claude's own blocks (thinking included) for that call only
history = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'cats?'},
           {'role': 'assistant', 'content': 'Let me look.', 'tool_calls': [{'id': 'toolu_1', 'type': 'function', 'function': {'name': 'web_search', 'arguments': '{"query": "cats"}'}}]},
           {'role': 'tool', 'tool_call_id': 'toolu_1', 'content': 'cats are great'}]
r2 = llm.chat_tools(SPEC, history, None)
sent = CALLS[-1]['messages']
a_blocks = sent[1]['content']
check('A4: the previous assistant turn is replayed with its thinking block, and the call the agent skipped is dropped', [getattr(b, 'type', None) or b.get('type') for b in a_blocks] == ['thinking', 'text', 'tool_use'] and sent[2]['content'][0]['tool_use_id'] == 'toolu_1', str(a_blocks))
check('A5: the final answer comes back as text with no tool calls', r2['content'] == 'Done.' and r2['tool_calls'] == [])

REPLIES[:] = [text_msg('Sorry.', stop='refusal')]
try: llm.chat(SPEC, 's', 'p', json_mode=False); ok = False
except llm.LLMError as e: ok = 'declined' in str(e)
check('A6: a refusal is a clear error, not an empty answer', ok)
REPLIES[:] = [NS(content=[tool], usage=usage(), stop_reason='max_tokens', stop_details=None)]
try: llm.chat_tools(SPEC, [{'role': 'user', 'content': 'x'}], None); ok = False
except llm.LLMError as e: ok = 'ran out of room' in str(e)
check('A7: a tool call cut off by the token limit is an error, never run half-formed', ok)

# streaming
REPLIES[:] = [text_msg('The answer is forty two')]
seen = []
res = llm.chat_tools_stream(SPEC, [{'role': 'user', 'content': 'q'}], None, 100, None, on_delta=seen.append)
check('S1: text streams word by word and the final result matches', seen[0] == 'The ' and seen[-1].strip() == 'The answer is forty two' and res['content'] == 'The answer is forty two', seen)
REPLIES[:] = [text_msg('one two three')]
class Stop(Exception): pass
def boom(t):
    if 'two' in t: raise Stop()
try: llm.chat_tools_stream(SPEC, [{'role': 'user', 'content': 'q'}], None, 100, None, on_delta=boom); ok = False
except Stop: ok = True
check('S2: an exception from the callback (the cancel button) stops the stream and is not swallowed', ok)
REPLIES[:] = [text_msg('a b')]
pieces = list(llm.chat_stream(SPEC, 'sys', 'prompt', 100))
check('S3: chat_stream yields deltas then usage', [p[0] for p in pieces] == ['delta', 'delta', 'usage'] and pieces[-1][1] == (100, 20), pieces)
REPLIES[:] = [NS(content=[tool], usage=usage(), stop_reason='tool_use', stop_details=None)]
res = llm.chat_tools_stream(SPEC, [{'role': 'user', 'content': 'q'}], None, 100, None, on_delta=lambda t: None)
check('S4: a streamed turn that only calls a tool returns the call', res['tool_calls'][0]['name'] == 'web_search')

# errors
req = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
def err(cls, status, msg): return cls(msg, response=httpx2.Response(status, request=req, json={'error': {'message': msg}}), body=None)
for name, e, want in [('bad key', err(anthropic.AuthenticationError, 401, 'invalid x-api-key'), 'rejected the API key'),
                      ('no credit', err(anthropic.BadRequestError, 400, 'Your credit balance is too low to access the API'), 'no credit left'),
                      ('rate limit', err(anthropic.RateLimitError, 429, 'slow down'), 'rate limiting'),
                      ('server', err(anthropic.InternalServerError, 500, 'oops'), 'Claude error 500')]:
    REPLIES[:] = [e]
    try: llm.chat(SPEC, 's', 'p', json_mode=False); got = ''
    except llm.LLMError as ex: got = str(ex)
    check(f'E: {name} -> a plain message', want in got, got)
try: llm.chat(dict(SPEC, key=''), 's', 'p'); got = ''
except llm.LLMError as ex: got = str(ex)
check('E5: no key -> tells the owner where to add it', 'Owner tab' in got)

# ───────── the owner's settings ─────────
app = create_app()
auth.ensure_bootstrap_admin()
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
HA = {'Authorization': 'Bearer ' + auth.make_token('admin', 'admin')}
HM = {'Authorization': 'Bearer ' + auth.make_token('mem', 'member')}
c = app.test_client()
check('O1: a member cannot set the Claude key', c.put('/api/auth/claudekey', headers=HM, json={'key': 'sk-ant-' + 'x' * 30}).status_code == 403)
check('O2: a member cannot switch the model setup', c.put('/api/auth/brain', headers=HM, json={'brain': 'claude'}).status_code == 403)
check('O3: junk is not accepted as a Claude key', c.put('/api/auth/claudekey', headers=HA, json={'key': 'short'}).status_code == 400)
check('O4: switching to Claude without a key is refused', c.put('/api/auth/brain', headers=HA, json={'brain': 'claude'}).status_code == 400)
r = c.put('/api/auth/claudekey', headers=HA, json={'key': 'sk-ant-api03-REALLYSECRETKEY123456'})
check('O5: the owner saves the key; only a hint comes back', r.status_code == 200 and 'REALLYSECRET' not in r.get_data(as_text=True))
g = c.get('/api/auth/claudekey', headers=HM).get_json()
check('O6: a member sees only that a shared key exists, not the key', g['set'] is False and g['shared'] is True and 'REALLY' not in json.dumps(g))
check('O7: the key is stored encrypted', 'REALLYSECRET' not in auth.UserDocument.objects(username='admin').first().anthropic_enc)
check('O8: the owner picks mixed', c.put('/api/auth/brain', headers=HA, json={'brain': 'mixed'}).get_json()['brain'] == 'mixed' and c.get('/api/auth/brain', headers=HM).get_json()['brain'] == 'mixed')
check('O9: an unknown setup is refused', c.put('/api/auth/brain', headers=HA, json={'brain': 'gpt'}).status_code == 400)
k = auth.with_stored_key({}, 'mem')
check('O10: every request now carries the Claude key and the setup (so any member gets the owner\'s choice)', k['anthropic'] == 'sk-ant-api03-REALLYSECRETKEY123456' and k['brain'] == 'mixed')
check('O11: ...and a planner job for a member lands on Claude, a worker on DeepSeek', llm.resolve('deepseek-chat', k, 'planner')['provider'] == 'anthropic' and llm.resolve('deepseek-chat', dict(k, deepseek='sk-ds'), 'worker')['provider'] == 'deepseek')
c.delete('/api/auth/claudekey', headers=HA)
check('O12: removing the key puts everything back on DeepSeek', auth.stored_brain() == 'deepseek' and llm.resolve('', auth.with_stored_key({'deepseek': 'sk'}, 'admin'), 'planner')['provider'] == 'deepseek')

# ───────── web search: Claude searches by itself, Tavily stays for DeepSeek ─────────
from orchestrator import search, agent, engine as oe
from models import UsageDocument
def srv(name='web_search'): return NS(type='server_tool_use', name=name, id='srvtoolu_1', input={'query': 'q'})
def res_block(items): return NS(type='web_search_tool_result', content=[NS(type='web_search_result', title=t, url=u, page_age=None) for t, u in items])
def cited_text(t, url, cited): return NS(type='text', text=t, citations=[NS(url=url, cited_text=cited, title='x')])
SEARCH_REPLY = NS(content=[srv(), res_block([('Nvidia - Wikipedia', 'https://en.wikipedia.org/wiki/Nvidia'), ('Nvidia leadership', 'https://nvidia.com/leadership'), ('Nvidia - Wikipedia', 'https://en.wikipedia.org/wiki/Nvidia')]),
                              cited_text('Jensen Huang is the CEO of Nvidia.', 'https://nvidia.com/leadership', 'Jensen Huang, founder and CEO')],
                  usage=usage(300, 60), stop_reason='end_turn', stop_details=None)
NOKEY = {'deepseek': 'sk-ds', 'anthropic': 'sk-ant-testtesttesttest'}
check('W1: Claude can search with no Tavily key; DeepSeek cannot without one', search.available(SPEC, '') and not search.available({'provider': 'deepseek', 'key': 'k'}, '') and search.available({'provider': 'deepseek', 'key': 'k'}, 'tvly-x'))
REPLIES[:] = [SEARCH_REPLY]
out = search.search_for(SPEC, 'who is the ceo of nvidia', '', ctx={'owner': 'admin', 'run_id': ''})
rs = out['results']
check('W2: the answer is a short summary first, then the pages (duplicates dropped), each with the text Claude cited', rs[0].get('summary') and 'Jensen Huang' in rs[0]['content'] and [r['url'] for r in rs[1:]] == ['https://en.wikipedia.org/wiki/Nvidia', 'https://nvidia.com/leadership'] and rs[2]['content'] == 'Jensen Huang, founder and CEO', rs)
check('W3: the summary is not shown to the user as a source', [x['url'] for x in search.source_links(rs)] == ['https://en.wikipedia.org/wiki/Nvidia', 'https://nvidia.com/leadership'])
check('W4: the prompt block carries the summary and the pages', 'Search summary' in search.format_sources(rs) and 'nvidia.com/leadership' in search.format_sources(rs))
tool = CALLS[-1]['tools'][0]
check('W5: Sonnet uses the current server-side search tool, capped at 3 searches', tool['type'] == 'web_search_20260209' and tool['max_uses'] == 3 and tool['name'] == 'web_search', tool)
REPLIES[:] = [SEARCH_REPLY]; search.search_for(dict(SPEC, model='claude-haiku-5-5'), 'x', '')
check('W6: Haiku uses the basic variant of the tool', CALLS[-1]['tools'][0]['type'] == 'web_search_20250305')
UsageDocument.objects(model='claude-web-search').delete()
REPLIES[:] = [SEARCH_REPLY]; search.search_for(SPEC, 'x', '', ctx={'owner': 'admin', 'run_id': ''})
row = UsageDocument.objects(model='claude-web-search').first()
check('W7: each search is billed in the ledger at the search price, on top of the tokens', row is not None and abs(row.cost_usd - search.CLAUDE_PRICE_PER_SEARCH) < 1e-9 and UsageDocument.objects(purpose='search', model='claude-sonnet-5-5').count() >= 1)
paused = NS(content=[srv()], usage=usage(), stop_reason='pause_turn', stop_details=None)
REPLIES[:] = [paused, SEARCH_REPLY]
rs = search.search_for(SPEC, 'x', '')['results']
check('W8: a paused search is carried on to the end', len(CALLS[-1]['messages']) == 2 and CALLS[-1]['messages'][1]['role'] == 'assistant' and rs[0].get('summary'))
REPLIES[:] = [NS(content=[srv(), NS(type='web_search_tool_result', content=NS(error_code='too_many_requests'))], usage=usage(), stop_reason='end_turn', stop_details=None)]
try: search.search_for(SPEC, 'x', ''); got = ''
except search.SearchError as e: got = str(e)
check('W9: a failed search is a SearchError the callers already handle', 'too_many_requests' in got, got)
st = agent.State('admin', '', NOKEY, lambda t: None, SPEC)
REPLIES[:] = [SEARCH_REPLY]
txt = agent._tool(st, 'web_search', {'query': 'who is the ceo of nvidia'})
check('W10: the agent web_search tool works for Claude without Tavily, with real sources only', txt.startswith('WEB RESULTS') and [x['url'] for x in st.sources] == ['https://en.wikipedia.org/wiki/Nvidia', 'https://nvidia.com/leadership'], (txt[:80], st.sources))
st2 = agent.State('admin', '', {'deepseek': 'sk'}, lambda t: None, {'provider': 'deepseek', 'key': 'k', 'model': 'deepseek-chat'})
check('W11: for DeepSeek with no Tavily key the old message stays', 'no Tavily key' in agent._tool(st2, 'web_search', {'query': 'x'}))
REPLIES[:] = [SEARCH_REPLY]
blk, srcs, note = oe._web_context(NS(web_search=True, goal='who is the ceo of nvidia'), SPEC, {}, NOKEY, None)
check('W12: the classic answer path also searches with Claude and needs no Tavily key', 'WEB SOURCES' in blk and len(srcs) == 2 and note == '', (blk[:80], srcs, note))

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
