"""Offline test of Tavily web search. llm._post and Tavily HTTP are faked: no real API calls, no credits."""
import os, sys, json, time, tempfile, types
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, search, router
from models import RunDocument, UsageDocument, UserDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))

llm_prompts = []
def fake_llm_post(url, **kw):
    msgs = kw['json']['messages']
    llm_prompts.append((msgs[0]['content'], msgs[1]['content']))
    if 'numbered WEB SOURCES' in msgs[0]['content']:
        text = 'Based on the sources, it is 42 [1].'
    elif 'Adion, the user' in msgs[0]['content']:
        text = json.dumps({'reply': 'The latest version is 42.', 'action': {'type': 'none'}})
    else:
        text = 'Built-in knowledge answer.'
    return {'choices': [{'message': {'content': text}}],
            'usage': {'prompt_tokens': 200, 'completion_tokens': 40, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 200}}
llm._post = fake_llm_post

def _no_stream(*a, **k):
    """These tests use the fake non-streaming transport: make chat_stream fail fast so answers fall back to it."""
    raise llm.LLMError('streaming disabled in this test')
    yield
llm.chat_stream = _no_stream


tavily_calls = []
tavily_mode = {'status': 200}
class Resp:
    def __init__(self, status, data): self.status_code, self._d, self.text = status, data, json.dumps(data)
    def json(self): return self._d
def fake_tavily_post(url, **kw):
    tavily_calls.append((url, kw['headers'].get('Authorization'), kw['json']))
    if tavily_mode['status'] != 200:
        return Resp(tavily_mode['status'], {'detail': 'x'})
    return Resp(200, {'results': [
        {'title': 'Release notes', 'url': 'https://example.com/a', 'content': 'Version 42 was released.  ' * 60},
        {'title': 'Blog', 'url': 'https://example.com/b', 'content': 'Another source about 42.'},
        {'title': 'Empty', 'url': 'https://example.com/c', 'content': ''}]})
search.requests = types.SimpleNamespace(post=fake_tavily_post, exceptions=requests.exceptions)

app = create_app()
auth.ensure_bootstrap_admin()
tok = auth.make_token('admin', 'admin')
H = {'Authorization': 'Bearer ' + tok}
c = app.test_client()
out_dir = tempfile.mkdtemp(prefix='adion_t4_')
KEYS = {'deepseek': 'sk-testtesttesttesttest', 'tavily': 'tvly-testtesttest'}

def run(goal, keys=KEYS, web=False):
    llm_prompts.clear(); tavily_calls.clear()
    r = engine.create_run(goal, out_dir, keys, owner='admin', web_search=web)
    for _ in range(80):
        time.sleep(0.25)
        d = RunDocument.objects.get(run_id=r.run_id)
        if d.status not in ('planning', 'running'):
            return d
    raise TimeoutError(goal)

# heuristics
for q, want in [('what is the latest version of react', True), ('bitcoin price today', True), ('who is the current president of france', True),
                ('who is elon musk', False), ('explain recursion', False), ('weather in london', True), ('what is docker', False)]:
    check(f'needs_search({q!r}) == {want}', search.needs_search(q) == want)

# recent question -> searches
d = run('what is the latest version of react?')
check('recent: completed with cited answer', d.status == 'completed' and '[1]' in d.answer, d.error + d.answer)
check('recent: exactly one Tavily call with bearer key', len(tavily_calls) == 1 and tavily_calls[0][1] == 'Bearer tvly-testtesttest' and tavily_calls[0][0].endswith('/search'), str(tavily_calls))
check('recent: sources saved, empty result dropped', [s['url'] for s in d.sources] == ['https://example.com/a', 'https://example.com/b'], str(d.sources))
sys_p, user_p = llm_prompts[0]
check('recent: model got numbered sources + question', user_p.startswith('WEB SOURCES (searched for:') and '[1] Release notes' in user_p and 'QUESTION:' in user_p)
check('recent: snippets trimmed (cheap prompt)', len(user_p) < 1200, str(len(user_p)))
rows = list(UsageDocument.objects(run_id=d.run_id))
check('recent: ledger has a search row and an answer row', {r.purpose for r in rows} == {'search', 'answer'}, str({r.purpose for r in rows}))

# plain question -> no search
d = run('explain recursion')
check('plain: no Tavily call', len(tavily_calls) == 0 and d.sources == [] and d.answer == 'Built-in knowledge answer.')

# forced
d = run('explain recursion', web=True)
check('forced: searched even though not recent', len(tavily_calls) == 1 and len(d.sources) == 2)

# Tavily down -> still answers, with a warning
tavily_mode['status'] = 401
d = run('bitcoin price today')
check('401: run still completes', d.status == 'completed', d.error)
check('401: warns the answer may be out of date', 'out of date' in d.answer and 'rejected' in d.answer and d.sources == [], d.answer)
tavily_mode['status'] = 429
d = run('bitcoin price today')
check('429: limit message', 'usage limit' in d.answer, d.answer)
tavily_mode['status'] = 200

# no key
d = run('bitcoin price today', keys={'deepseek': KEYS['deepseek']})
check('no key: no call, answered from knowledge', len(tavily_calls) == 0 and d.status == 'completed')
d = run('explain recursion', keys={'deepseek': KEYS['deepseek']}, web=True)
check('no key + switch on: tells the user to add a key', 'no Tavily key' in d.answer, d.answer)

# key storage endpoints
check('searchkey: initially unset', c.get('/api/auth/searchkey', headers=H).get_json()['set'] is False)
check('searchkey: junk rejected', c.put('/api/auth/searchkey', headers=H, json={'key': 'abc'}).status_code == 400)
r = c.put('/api/auth/searchkey', headers=H, json={'key': 'tvly-REALLYSECRET123456'}).get_json()
check('searchkey: saved with masked hint', r['ok'] and r['hint'] == 'tvly-…3456', str(r))
row = UserDocument.objects(username='admin').first()
check('searchkey: encrypted in DB (no plaintext)', row.tavily_enc and 'REALLYSECRET' not in row.tavily_enc)
check('searchkey: GET shows set, never the key', c.get('/api/auth/searchkey', headers=H).get_json() == {'set': True, 'hint': 'tvly-…3456', 'shared': False})
check('with_stored_key fills tavily', auth.with_stored_key({'deepseek': 'x'}, 'admin')['tavily'] == 'tvly-REALLYSECRET123456')
check('searchkey: viewer-less delete works', c.delete('/api/auth/searchkey', headers=H).get_json()['ok'] and not UserDocument.objects(username='admin').first().tavily_enc)

# voice assistant uses search for current questions
c.put('/api/auth/searchkey', headers=H, json={'key': 'tvly-REALLYSECRET123456'})
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
llm_prompts.clear(); tavily_calls.clear()
j = c.post('/api/assistant/chat', headers=H, json={'message': 'what is the latest version of react', 'history': []}).get_json()
check('assistant: replied', j.get('reply') == 'The latest version is 42.', str(j))
check('assistant: searched + sources in prompt', len(tavily_calls) == 1 and 'WEB SOURCES' in llm_prompts[0][1])
llm_prompts.clear(); tavily_calls.clear()
c.post('/api/assistant/chat', headers=H, json={'message': 'hello how are you', 'history': []})
check('assistant: no search for small talk', len(tavily_calls) == 0)

# API + calculator
r = c.post('/api/runs', headers=H, json={'goal': 'who is the current ceo of apple', 'targetPath': out_dir, 'webSearch': True}).get_json()
check('runs API accepts webSearch', r.get('id'))
f1 = router.forecast('who is the current ceo of apple'); f2 = router.forecast('explain recursion')
check('forecast: web question costs more than plain', f1['tokens'] > f2['tokens'] and 'web' in f1['parts'][0]['name'].lower(), f"{f1['tokens']} {f2['tokens']}")
u = c.get('/api/usage?days=30', headers=H).get_json()
check('usage: counts web searches', any(p['purpose'] == 'search' and p['calls'] >= 3 for p in u['byPurpose']), str(u['byPurpose']))

time.sleep(2)
print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
