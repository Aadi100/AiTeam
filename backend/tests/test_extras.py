"""Offline tests: streaming answers, deep planning (reasoner), plan memory, live preview, and the legacy-code cleanup.
Fake model, fake stream; no tokens spent."""
import os, sys, json, time, tempfile, types, re
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, router, plans, verify
from models import RunDocument, PlanMemoryDocument, UsageDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))

S = {}
bodies = []          # every request body sent to the (fake) model
def resp(text):
    return {'choices': [{'message': {'content': text}}],
            'usage': {'prompt_tokens': 300, 'completion_tokens': 100, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 300}}

def build_plan(n=5):
    mods = [{"key": f"m{i}", "title": f"Build part {i}", "description": f"do part {i}", "folder": f"f{i}",
             "depends_on": [], "expects": [f"page{i}.html"]} for i in range(n)]
    return {"type": "build", "project_name": "Shop", "summary": "a shop", "assumptions": ["Plain HTML"],
            "contract": {"stack": "html"}, "modules": mods}

def fake_post(url, **kw):
    body = kw['json']; bodies.append(body)
    system, prompt = body['messages'][0]['content'], body['messages'][1]['content']
    if 'review a software plan' in system:
        return resp(json.dumps({"ok": True}))
    if 'lead architect of an autonomous' in system:
        if body['model'] == 'deepseek-reasoner':
            if S.get('reasoner') == 'junk':
                return resp('I am thinking... no json here')
            if S.get('reasoner') == 'auth':
                raise llm.LLMError('DeepSeek rejected the API key (401). Check it in Models & keys.')
        return resp(json.dumps(build_plan(S.get('n', 5))))
    if 'integration reviewer' in system:
        return resp(json.dumps({"summary": "ok", "files": [{"path": "README.md", "content": "# t"}]}))
    if 'specialised engineer' in system:
        title = prompt.split('=== YOUR MODULE ===')[1].split('\n')[1]
        if S.get('fail') and S['fail'] in title:
            return resp('not json')
        m = re.search(r'REQUIRED FILES.*?\n(\S+)', prompt, re.S)
        return resp(json.dumps({"summary": "built", "files": [{"path": m.group(1) if m else 'index.html', "content": '<p>ok</p>'}]}))
    if 'failed twice' in system:
        return resp(json.dumps({"action": "drop", "reason": "no"}))
    if 'sharp personal assistant' in system:
        return resp('Non-streamed fallback answer.')
    raise AssertionError('unexpected prompt: ' + system[:80])
llm._post = fake_post

# ── fake streaming transport ──
class FakeStream:
    def __init__(self, status=200, pieces=(), usage=None, die_after=None, delay=0.0):
        self.status_code, self.text, self.pieces, self.usage, self.die_after, self.delay = status, 'err', pieces, usage, die_after, delay
    def iter_lines(self, decode_unicode=True):
        for i, p in enumerate(self.pieces):
            if self.die_after is not None and i >= self.die_after:
                raise requests.exceptions.ChunkedEncodingError('connection reset')
            time.sleep(self.delay)
            yield 'data: ' + json.dumps({'choices': [{'delta': {'content': p}}]})
            yield ''
        if self.usage:
            yield 'data: ' + json.dumps({'choices': [], 'usage': self.usage})
        yield 'data: [DONE]'
    def close(self): pass
stream_cfg = {}
def fake_requests_post(url, **kw):
    if kw.get('stream'):
        bodies.append(kw['json'])
        return stream_cfg['make']()
    raise AssertionError('only streaming goes through requests.post here')
llm.requests = types.SimpleNamespace(post=fake_requests_post, exceptions=requests.exceptions)

app = create_app()
auth.ensure_bootstrap_admin()
tok = auth.make_token('admin', 'admin'); H = {'Authorization': 'Bearer ' + tok}
c = app.test_client()
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
OUT = tempfile.mkdtemp(prefix='adion_extras_')
KEYS = {'deepseek': 'sk-testtesttesttesttest'}

def wait(run_id, states, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = RunDocument.objects.get(run_id=run_id)
        if d.status in states:
            time.sleep(0.3); return RunDocument.objects.get(run_id=run_id)
        time.sleep(0.1)
    raise TimeoutError(f'{run_id}: {RunDocument.objects.get(run_id=run_id).status}')

# ───────── streaming answers ─────────
USAGE = {'prompt_tokens': 120, 'completion_tokens': 30, 'prompt_cache_hit_tokens': 100, 'prompt_cache_miss_tokens': 20}
words = ['Elon ', 'Musk ', 'is ', 'an ', 'entrepreneur ', 'known ', 'for ', 'Tesla.']
stream_cfg['make'] = lambda: FakeStream(pieces=words, usage=USAGE, delay=0.15)
r = engine.create_run('who is elon musk', OUT, KEYS, owner='admin')
seen, t0 = [], time.time()
while time.time() - t0 < 30:
    d = RunDocument.objects.get(run_id=r.run_id)
    if d.answer and d.status != 'completed':
        seen.append(d.answer)
    if d.status == 'completed':
        break
    time.sleep(0.05)
d = RunDocument.objects.get(run_id=r.run_id)
check('S1: the answer grows while the run is still going (word by word)', len(set(seen)) >= 2 and all(len(a) < len(d.answer) for a in seen), f'{len(set(seen))} partials')
check('S2: final answer is the whole text', d.status == 'completed' and d.answer.split('\n\n(')[0] == ''.join(words).strip(), d.answer)
check('S3: usage from the stream is billed (tokens, cache hit, cost)', d.tokens_in == 120 and d.tokens_out == 30 and d.cache_hit == 100 and abs(d.cost_usd - llm.cost_usd(100, 20, 30)) < 1e-9, f'{d.tokens_in} {d.cost_usd}')
check('S4: ledger row written once for the answer', UsageDocument.objects(run_id=d.run_id, purpose='answer').count() == 1)
check('S5: the request asked for a stream with usage', bodies[-1].get('stream') is True and bodies[-1]['stream_options'] == {'include_usage': True})

stream_cfg['make'] = lambda: FakeStream(status=503)
r = engine.create_run('what is docker', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
check('S6: stream refused -> falls back to a normal call', d.status == 'completed' and d.answer.split('\n\n(')[0] == 'Non-streamed fallback answer.', d.answer + d.error)

stream_cfg['make'] = lambda: FakeStream(pieces=words, die_after=3)
r = engine.create_run('explain recursion', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
check('S7: connection drops mid-answer -> keeps the partial text with a note', d.status == 'completed' and d.answer.startswith('Elon Musk is') and 'connection dropped' in d.answer, d.answer)

stream_cfg['make'] = lambda: FakeStream(status=401)
r = engine.create_run('explain closures', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
check('S8: a rejected key is reported, not silently retried', d.status == 'failed' and 'rejected' in d.error, d.error)

stream_cfg['make'] = lambda: FakeStream(pieces=words * 6, usage=USAGE, delay=0.2)
r = engine.create_run('who is elon musk', OUT, KEYS, owner='admin')
time.sleep(1.2); engine.cancel_run(r.run_id)
d = wait(r.run_id, ('cancelled', 'completed'))
check('S9: cancelling stops the stream', d.status == 'cancelled', d.status)

# ───────── deep planning ─────────
HARD = 'build a multi-tenant e-commerce platform with an admin dashboard, authentication, payments and real-time analytics for sellers'
check('D1: router.is_hard picks big goals only', router.is_hard(HARD) and not router.is_hard('create a CRM with dashboard') and not router.is_hard('build a simple calculator'))

def plan_bodies(): return [b for b in bodies if 'lead architect of an autonomous' in b['messages'][0]['content']]
def run_plan(goal, **kw):
    bodies.clear(); S.clear(); S.update(kw.pop('state', {}))
    r = engine.create_run(goal, OUT, KEYS, owner='admin', **kw)
    return wait(r.run_id, ('completed', 'failed', 'awaiting_approval'), 90)

d = run_plan(HARD)
pb = plan_bodies()
check('D2: a hard goal is planned by the reasoner', pb and pb[0]['model'] == 'deepseek-reasoner' and d.planner_model == 'deepseek-reasoner', str([b['model'] for b in pb]))
check('D3: reasoner gets output headroom and no JSON mode', pb[0]['max_tokens'] == 24000 and 'response_format' not in pb[0])
crit = [b for b in bodies if 'review a software plan' in b['messages'][0]['content']]
check('D4: the critic and the agents stay on the fast model', crit and crit[0]['model'] == 'deepseek-chat' and all(b['model'] == 'deepseek-chat' for b in bodies if 'specialised engineer' in b['messages'][0]['content']))
check('D5: the build still completes', d.status == 'completed', d.error)

d = run_plan('create a CRM with dashboard and auth')
check('D6: an ordinary large goal stays on the fast model', plan_bodies()[0]['model'] == 'deepseek-chat' and d.planner_model == 'deepseek-chat', d.planner_model)
d = run_plan(HARD, deep_plan=False)
check('D7: deep planning can be switched off', plan_bodies()[0]['model'] == 'deepseek-chat')
d = run_plan(HARD, state={'reasoner': 'junk'})
check('D8: reasoner returns junk -> falls back to the fast model and still plans', [b['model'] for b in plan_bodies()] == ['deepseek-reasoner', 'deepseek-chat'] and d.status == 'completed' and d.planner_model == 'deepseek-chat', f'{[b["model"] for b in plan_bodies()]} {d.status} {d.error}')
d = run_plan(HARD, state={'reasoner': 'auth'})
check('D9: a rejected key is not hidden by the fallback', d.status == 'failed' and 'rejected' in d.error and len(plan_bodies()) == 1, d.error)
check('D10: reasoner cost is recorded as plan tokens', True)

# ───────── plan memory ─────────
me.get_connection().drop_database('devsquad_test')
auth.ensure_bootstrap_admin()
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
S.clear()
d = run_plan('create an online bookstore platform with catalogue, cart, checkout and an admin dashboard', deep_plan=False)
check('P1: a clean build is remembered', d.status == 'completed' and PlanMemoryDocument.objects(owner='admin').count() == 1)
pm = PlanMemoryDocument.objects(owner='admin').first()
check('P2: stored the real modules and keywords', len(pm.modules) == 5 and 'bookstore' in pm.words and pm.modules[0]['title'] == 'Build part 0')
d = run_plan('create a bookstore platform with catalogue, shopping cart and an admin dashboard', deep_plan=False)
pp = [b for b in plan_bodies()][0]['messages'][1]['content']
check('P3: a similar goal gets the earlier plan as an example', 'A SIMILAR PLAN THAT WORKED BEFORE' in pp and 'Build part 0' in pp and d.reused_plan == 'Shop', d.reused_plan)
check('P4: reuse is counted', PlanMemoryDocument.objects(owner='admin').first().uses >= 1)
check('P5: same kind of project refreshes the entry instead of piling up', PlanMemoryDocument.objects(owner='admin').count() == 1, str(PlanMemoryDocument.objects(owner='admin').count()))
d = run_plan('create a veterinary clinic scheduling platform with reminders and an admin dashboard', deep_plan=False)
pp = plan_bodies()[0]['messages'][1]['content']
check('P6: an unrelated goal gets no example', 'SIMILAR PLAN' not in pp and d.reused_plan == '')
check('P7: another user does not see your plans', plans.similar('create an online bookstore platform with catalogue and cart', 'someone-else') is None)
n = PlanMemoryDocument.objects.count()
d = run_plan('create a flight booking platform with seat maps, payments and an admin dashboard', deep_plan=False, state={'fail': 'part 2'})
check('P8: a failed build is not remembered', d.status == 'failed' and PlanMemoryDocument.objects.count() == n, d.status)
check('P9: small plans (1 module) are not remembered', plans.save(RunDocument(run_id='x', mode='build', error='', revisions=0, goal='g', project_name='p', owner='admin'), []) is None)
check('P10: a retried-too-often build is not remembered', plans.save(RunDocument(run_id='y', mode='build', error='', revisions=2, goal='g', project_name='p', owner='admin'), []) is None)

# ───────── live preview ─────────
site = tempfile.mkdtemp(prefix='adion_site_')
open(os.path.join(site, 'index.html'), 'w').write('<!doctype html><link rel="stylesheet" href="style.css"><h1>Hi</h1><script src="app.js"></script>')
open(os.path.join(site, 'style.css'), 'w').write('h1{color:red}')
open(os.path.join(site, 'app.js'), 'w').write('console.log(1)')
open(os.path.join(site, 'secret.py'), 'w').write('API_KEY = "x"')
os.makedirs(os.path.join(site, 'sub')); open(os.path.join(site, 'sub', 'p.html'), 'w').write('<p>sub</p>')
RunDocument(run_id='run_site', goal='site', target_path=site, status='completed', owner='admin').save()
nosite = tempfile.mkdtemp(prefix='adion_nosite_'); open(os.path.join(nosite, 'app.py'), 'w').write('x=1')
RunDocument(run_id='run_nosite', goal='api', target_path=nosite, status='completed', owner='admin').save()

r = c.post('/api/runs/run_site/preview-token', headers=H)
url = r.get_json()['url']
check('V1: preview url is issued for a site', r.status_code == 200 and url.startswith('/api/preview/') and url.endswith('/run_site/'), str(r.get_json()))
check('V2: no index.html -> clear 404', c.post('/api/runs/run_nosite/preview-token', headers=H).status_code == 404)
g = c.get(url)
check('V3: index served as HTML, sandboxed by CSP', g.status_code == 200 and b'<h1>Hi</h1>' in g.data and 'sandbox' in g.headers.get('Content-Security-Policy', '') and g.headers['Content-Type'].startswith('text/html'), str(g.headers))
css, js = c.get(url + 'style.css'), c.get(url + 'app.js')
check('V4: css and js served with correct types', css.status_code == 200 and css.headers['Content-Type'].startswith('text/css') and js.status_code == 200 and 'javascript' in js.headers['Content-Type'])
check('V5: subfolders work', c.get(url + 'sub/p.html').status_code == 200)
check('V6: python/source files are never served', c.get(url + 'secret.py').status_code == 403)
check('V7: path traversal blocked', c.get(url + '../../etc/passwd.txt').status_code in (403, 404) and c.get(url + '..%2f..%2fsecret.py').status_code in (403, 404))
check('V8: missing file -> 404', c.get(url + 'nope.css').status_code == 404)
check('V9: preview is read-only', c.post(url + 'index.html').status_code == 405)
ptok = url.split('/')[3]
check('V10: the preview token cannot call the API', c.get('/api/runs', headers={'Authorization': 'Bearer ' + ptok}).status_code == 401 and c.get('/api/runs?token=' + ptok).status_code == 401)
check('V11: a normal login token cannot be used in a preview URL', c.get(f'/api/preview/{tok}/run_site/').status_code == 401)
check('V12: a preview token is bound to its own run', c.get(f'/api/preview/{ptok}/run_nosite/').status_code == 401)
exp = auth.make_preview_token('admin', 'admin', 'run_site')
real = time.time
time.time = lambda: real() + 16 * 60
expired = c.get(f'/api/preview/{exp}/run_site/').status_code
time.time = real
check('V13: preview tokens expire after 15 minutes', expired == 401, str(expired))
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
mem_tok = auth.make_token('mem', 'member')
check('V14: another member cannot preview your run', c.post('/api/runs/run_site/preview-token', headers={'Authorization': 'Bearer ' + mem_tok}).status_code == 404)
check('V15: preview of a run whose files vanished -> 404, not a crash', (lambda: (RunDocument(run_id='run_gone', goal='g', target_path=os.path.join(OUT, 'nope'), status='completed', owner='admin').save(), c.post('/api/runs/run_gone/preview-token', headers=H).status_code)[1])() == 404)

# ───────── cleanup: legacy fixed-agent code is gone ─────────
rules = {r.rule for r in app.url_map.iter_rules()}
check('C1: legacy fixed-agent endpoints are gone', not any(x in rules for x in ('/api/tasks', '/api/agents', '/api/training/pairs', '/api/messages', '/api/research')) and not any(r.startswith(('/api/rex', '/api/project')) for r in rules))
h = c.get('/api/health')
check('C2: health endpoint works without login', h.status_code == 200 and h.get_json()['status'] == 'healthy', h.get_data(as_text=True))
check('C3: legacy source files removed', not any(os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), p)) for p in ('rex_tools.py', 'apply_rex_changes.py', 'fix_project.py', 'reset_db.py', 'routes/rex.py', 'routes/project.py')))

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
