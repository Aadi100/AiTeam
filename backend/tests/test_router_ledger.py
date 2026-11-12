"""Offline test of router, ledger, calculator, small/answer/large paths. No real API calls (llm._post is faked)."""
import os, sys, json, time, tempfile
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, router
from models import RunDocument, AgentTaskDocument, UsageDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))

calls = []
def resp(text, pin, pout, hit=0):
    return {'choices': [{'message': {'content': text}}],
            'usage': {'prompt_tokens': pin, 'completion_tokens': pout, 'prompt_cache_hit_tokens': hit, 'prompt_cache_miss_tokens': pin - hit}}

seen_modules = {}
def fake_post(url, **kw):
    body = kw['json']; system = body['messages'][0]['content']; prompt = body['messages'][1]['content']
    if 'sharp personal assistant' in system:
        calls.append('answer'); return resp('Elon Musk is an entrepreneur.', 120, 30)
    if 'lead architect' in system:
        calls.append('plan')
        mods = [{"key": f"m{i}", "title": f"Build module {i}", "description": f"d{i}", "folder": f"f{i}", "depends_on": [],
                 "expects": [f"page{i}.html"]} for i in range(5)]
        return resp(json.dumps({"type": "build", "project_name": "CRM", "summary": "s",
                                "contract": {"stack": "html", "api": "none"}, "modules": mods}), 900, 700)
    if 'review a software plan' in system:
        calls.append('critic')
        return resp(json.dumps({"ok": False, "fixes": [{"key": "m1", "description": "better d1"}], "contract_add": "extra rule"}), 400, 80)
    if 'integration reviewer' in system:
        calls.append('review'); return resp(json.dumps({"summary": "ok", "files": [{"path": "README.md", "content": "# t"}]}), 300, 60, hit=200)
    if 'specialised engineer' in system:
        calls.append('agent')
        title = prompt.split('=== YOUR MODULE ===')[1].split('\n')[1]
        n = seen_modules.get(title, 0); seen_modules[title] = n + 1
        if 'module 2' in title and n == 0:   # forgets the required file on the first pass -> must be asked again
            return resp(json.dumps({"summary": "x", "files": [{"path": "other.html", "content": "<p>x</p>"}]}), 1500, 300, hit=1200)
        name = 'index.html' if 'calculator' in prompt.lower() else None
        if name is None:
            import re
            m = re.search(r'REQUIRED FILES.*?\n(\S+)', prompt, re.S)
            name = m.group(1) if m else 'index.html'
        return resp(json.dumps({"summary": "built", "files": [{"path": name, "content": "<p>ok</p>"}]}), 1500, 300, hit=1200)
    raise AssertionError('unexpected prompt: ' + system[:60])
llm._post = fake_post

def _no_stream(*a, **k):
    """These tests use the fake non-streaming transport: make chat_stream fail fast so answers fall back to it."""
    raise llm.LLMError('streaming disabled in this test')
    yield
llm.chat_stream = _no_stream


app = create_app()
auth.ensure_bootstrap_admin()
tok = auth.make_token('admin', 'admin')
H = {'Authorization': 'Bearer ' + tok}
KEYS = {'deepseek': 'sk-testtesttesttesttest'}
out_dir = tempfile.mkdtemp(prefix='adion_t3_')

def run(goal):
    calls.clear()
    r = engine.create_run(goal, out_dir, KEYS, owner='admin')
    for _ in range(120):
        time.sleep(0.25)
        d = RunDocument.objects.get(run_id=r.run_id)
        if d.status not in ('planning', 'running'):
            return d
    raise TimeoutError(goal)

# router
check('router: question -> chat', router.classify('who is elon musk') == 'chat')
check('router: how do I build -> chat', router.classify('how do I build a website') == 'chat')
check('router: simple calc -> small', router.classify('build a simple calculator') == 'small')
check('router: CRM -> large', router.classify('create a CRM with dashboard and auth') == 'large')

# 1. chat path
d = run('who is elon musk')
check('chat: completed with answer', d.status == 'completed' and d.answer.startswith('Elon'), d.error)
check('chat: ONE call, no planner', calls == ['answer'], str(calls))
check('chat: no agents', AgentTaskDocument.objects(run_id=d.run_id).count() == 0)
exp = llm.cost_usd(0, 120, 30)
check('chat: cost matches pricing', abs(d.cost_usd - exp) < 1e-9, f'{d.cost_usd} vs {exp}')
check('chat: forecast stored', d.estimate_tokens > 0)

# 2. small path
d = run('build a simple calculator')
tasks = list(AgentTaskDocument.objects(run_id=d.run_id))
check('small: completed', d.status == 'completed', d.error)
check('small: no planner/critic/review, one agent call', calls == ['agent'], str(calls))
check('small: exactly one task', len(tasks) == 1 and tasks[0].kind == 'module')
check('small: file written', any(f['path'].endswith('index.html') for f in tasks[0].files))
check('small: cache hit counted', d.cache_hit == 1200, str(d.cache_hit))

# 3. large path
seen_modules.clear()
d = run('create a CRM with dashboard and auth')
tasks = list(AgentTaskDocument.objects(run_id=d.run_id))
check('large: completed', d.status == 'completed', d.error)
check('large: planner + critic ran once', calls.count('plan') == 1 and calls.count('critic') == 1, str(calls))
check('large: critic fix applied', any(t.description == 'better d1' for t in tasks))
check('large: contract extended + structured text', 'extra rule' in d.contract and 'stack: html' in d.contract, d.contract)
check('large: review ran once', calls.count('review') == 1)
check('large: 5 modules + review', len([t for t in tasks if t.kind == 'module']) == 5 and any(t.kind == 'review' for t in tasks))
check('large: missing expected file re-requested (6 agent calls)', calls.count('agent') == 6, str(calls.count('agent')))
check('large: all expects satisfied', all(any(f['path'].endswith(e) for f in t.files) for t in tasks if t.kind == 'module' for e in t.expects))
check('large: estimate refined after plan', d.estimate_tokens > 0)
ledger = list(UsageDocument.objects(run_id=d.run_id))
check('large: ledger cost == run cost', abs(sum(u.cost_usd for u in ledger) - d.cost_usd) < 1e-9, f'{sum(u.cost_usd for u in ledger)} vs {d.cost_usd}')
check('large: ledger purposes', {u.purpose for u in ledger} == {'plan', 'critic', 'agent', 'review'}, str({u.purpose for u in ledger}))
check('large: run tokens == ledger tokens', d.tokens_in + d.tokens_out == sum(u.tokens_in + u.tokens_out for u in ledger))

# 4. HTTP: usage + estimate
c = app.test_client()
r = c.get('/api/usage?days=30', headers=H).get_json()
total = UsageDocument.objects.sum('cost_usd')
check('usage: totals', r['calls'] == UsageDocument.objects.count() and abs(r['cost'] - round(total, 5)) < 1e-5, str(r['cost']))
check('usage: cache saved > 0 and rate', r['saved'] > 0 and 0 < r['cacheRate'] < 1, f"{r['saved']} {r['cacheRate']}")
check('usage: purposes + runs + days present', len(r['byPurpose']) >= 4 and len(r['runs']) == 3 and len(r['byDay']) == 1)
e = c.post('/api/usage/estimate', headers=H, json={'goal': 'create a CRM with dashboard and auth'}).get_json()
check('estimate: shape', e['kind'] == 'large' and e['tokens'] > 5000 and e['low'] < e['tokens'] < e['high'] and e['cost'] > 0)
check('estimate: empty goal rejected', c.post('/api/usage/estimate', headers=H, json={'goal': ''}).status_code == 400)
vr = c.get('/api/runs/' + d.run_id, headers=H).get_json()
check('run api exposes cost/estimate/cacheHit', vr['run']['cost'] > 0 and vr['run']['estimateTokens'] > 0 and vr['run']['cacheHit'] > 0, str(vr['run'].keys()))

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
