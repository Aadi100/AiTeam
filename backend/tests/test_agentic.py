"""Offline test of the agentic features: clarify -> plan review -> build, agent questions, planner revision after
failures, follow-up edits, and the REAL headless-browser check. The LLM is faked (no tokens); the browser is real."""
import os, sys, json, time, tempfile, re
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, worker
from models import RunDocument, AgentTaskDocument, UsageDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))

S = {}            # scenario state the fake model reads
prompts = []      # (role, system, prompt) log
def reset(**kw):
    S.clear(); S.update(kw); prompts.clear()

def resp(text, pin=300, pout=100):
    return {'choices': [{'message': {'content': text}}],
            'usage': {'prompt_tokens': pin, 'completion_tokens': pout, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': pin}}

def build_plan(n, extra=''):
    mods = [{"key": f"m{i}", "title": f"Build module {i}{extra}", "description": f"do part {i}", "folder": f"f{i}",
             "depends_on": [], "expects": [f"page{i}.html"]} for i in range(n)]
    if S.get('dep'):   # m1 depends on m0
        mods[1]['depends_on'] = ['m0']
    return {"type": "build", "project_name": "Demo", "summary": "a demo", "assumptions": ["Plain HTML", "No auth"],
            "contract": {"stack": "html"}, "modules": mods}

def fake_post(url, **kw):
    msgs = kw['json']['messages']; system, prompt = msgs[0]['content'], msgs[1]['content']
    if 'failed twice' in system:
        prompts.append(('revise', system, prompt))
        return resp(json.dumps(S['revise']))
    if 'review a software plan' in system:
        return resp(json.dumps({"ok": True}))
    if 'lead architect of an autonomous' in system:
        prompts.append(('plan', system, prompt))
        if 'EXISTING PROJECT' in prompt:
            folder = 'f0'
            return resp(json.dumps({"type": "build", "project_name": "Demo", "summary": "edit", "assumptions": [],
                                    "contract": {"stack": "html"}, "modules": [{"key": "tweak", "title": "Change the header",
                                    "description": "make the heading say changed", "folder": folder, "depends_on": [],
                                    "expects": ["page0.html"]}]}))
        if S.get('vague') and 'CLARIFICATIONS' not in prompt:
            return resp(json.dumps({"type": "clarify", "questions": [
                {"q": "Which stack?", "options": ["Flask", "Plain HTML"]}, "What is it called?"]}))
        n = S.get('n', 5) + (1 if 'USER FEEDBACK' in prompt else 0)
        return resp(json.dumps(build_plan(n, ' (revised)' if 'USER FEEDBACK' in prompt else '')))
    if 'integration reviewer' in system:
        return resp(json.dumps({"summary": "ok", "files": [{"path": "README.md", "content": "# t"}]}))
    if 'integration engineer' in system:
        prompts.append(('fix', system, prompt))
        S['fixes'] = S.get('fixes', 0) + 1
        return resp(json.dumps({"summary": "fixed", "files": [{"path": "index.html", "content": S.get('fixed_html', S['good_html'])}]}))
    if 'specialised engineer' in system:
        prompts.append(('agent', system, prompt))
        title = prompt.split('=== YOUR MODULE ===')[1].split('\n')[1]
        S.setdefault('seen', {}); S['seen'][title] = S['seen'].get(title, 0) + 1
        if S.get('ask') and S['ask'] in title and 'THEY ANSWERED' not in prompt:
            if 'MAY ask' in prompt:
                return resp(json.dumps({"ask": {"question": "Dark or light theme?", "options": ["Dark", "Light"]}}))
        if S.get('fail') and S['fail'] in title:
            if S.get('fail_mode') == 'always' or 'simple version' not in prompt:
                return resp('this is not json at all')
        m = re.search(r'REQUIRED FILES.*?\n(\S+)', prompt, re.S)
        name = m.group(1) if m else 'index.html'
        content = '<p>changed</p>' if 'CHANGE TO AN EXISTING PROJECT' in prompt else (
            S.get('bad_html') if S.get('bad_html') and name == 'index.html' else '<p>ok</p>')
        return resp(json.dumps({"summary": "built", "files": [{"path": name, "content": content}]}))
    if 'sharp personal assistant' in system:
        return resp('An answer.')
    raise AssertionError('unexpected prompt: ' + system[:80])
llm._post = fake_post

app = create_app()
auth.ensure_bootstrap_admin()
tok = auth.make_token('admin', 'admin')
H = {'Authorization': 'Bearer ' + tok}
c = app.test_client()
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
OUT = tempfile.mkdtemp(prefix='adion_t5_')
KEYS = {'deepseek': 'sk-testtesttesttesttest'}

def wait(run_id, states, timeout=90):
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = RunDocument.objects.get(run_id=run_id)
        if d.status in states:
            time.sleep(0.5)
            return RunDocument.objects.get(run_id=run_id)
        time.sleep(0.3)
    d = RunDocument.objects.get(run_id=run_id)
    raise TimeoutError(f'{run_id} stuck in {d.status}: {d.error}')

def tasks(rid, **f): return list(AgentTaskDocument.objects(run_id=rid, **f))

# ───────── A. vague goal -> questions -> answers -> plan review -> edits -> build ─────────
reset(vague=True, n=5)
r = engine.create_run('I want an app', OUT, KEYS, owner='admin', review_plan=True)
d = wait(r.run_id, ('awaiting_input',))
check('A1: vague goal pauses with questions, no agents', d.status == 'awaiting_input' and len(d.questions) == 2 and not tasks(d.run_id))
check('A2: questions are structured (options kept, ids set)', d.questions[0]['options'] == ['Flask', 'Plain HTML'] and d.questions[0]['id'] == 'q1' and d.questions[1]['q'] == 'What is it called?')
check('A3: run released (not active) while waiting', d.run_id not in engine._active)
rr = c.post(f'/api/runs/{d.run_id}/answers', headers=H, json={'answers': {'q1': 'Plain HTML'}})
check('A4: answering only some questions is rejected', rr.status_code == 400, rr.get_data(as_text=True))
rr = c.post(f'/api/runs/{d.run_id}/answers', headers=H, json={'answers': {'q1': 'Plain HTML', 'q2': 'Brew Co'}})
check('A5: answers accepted over HTTP', rr.status_code == 200, rr.get_data(as_text=True))
d = wait(d.run_id, ('awaiting_approval',))
plan_prompt = [p for p in prompts if p[0] == 'plan'][-1][2]
check('A6: planner got the answers and was told not to ask again', 'CLARIFICATIONS' in plan_prompt and 'A: Plain HTML' in plan_prompt and 'A: Brew Co' in plan_prompt)
check('A7: 5-module plan waits for approval, nothing built, nothing on disk', d.status == 'awaiting_approval' and len(d.plan['modules']) == 5 and not tasks(d.run_id) and not os.path.isdir(d.target_path))
check('A8: assumptions surfaced', d.assumptions == ['Plain HTML', 'No auth'], str(d.assumptions))
check('A9: planning cost recorded before approval', d.tokens_in > 0 and d.cost_usd > 0)
rid = d.run_id
rr = c.post(f'/api/runs/{rid}/approve', headers=H, json={'edits': {'modules': [
    {'key': 'm4', 'removed': True}, {'key': 'm1', 'description': 'USER EDITED DESCRIPTION'}, {'key': 'm2', 'title': 'Renamed by user'}]}})
check('A10: approve over HTTP', rr.status_code == 200, rr.get_data(as_text=True))
d = wait(rid, ('completed', 'failed'))
ts = tasks(rid, kind='module')
check('A11: built with the edits (4 modules, one removed)', d.status == 'completed' and len(ts) == 4 and not any(t.key == 'm4' for t in ts), d.error)
check('A12: edited description + title reached the agents', any(t.description == 'USER EDITED DESCRIPTION' for t in ts) and any(t.title == 'Renamed by user' for t in ts))
check('A13: files exist in the per-project folder', os.path.isfile(os.path.join(d.target_path, 'f0', 'page0.html')) and os.path.basename(d.target_path).endswith(rid[-4:]), d.target_path)
check('A14: approving twice is rejected', c.post(f'/api/runs/{rid}/approve', headers=H, json={}).status_code == 409)
PARENT = d

# ───────── B. ask for changes, then reject ─────────
reset(n=5)
r = engine.create_run('build a big crm dashboard with auth', OUT, KEYS, owner='admin', review_plan=True)
d = wait(r.run_id, ('awaiting_approval',))
rr = c.post(f'/api/runs/{d.run_id}/replan', headers=H, json={'feedback': 'add a reports module'})
check('B1: replan over HTTP', rr.status_code == 200, rr.get_data(as_text=True))
d = wait(d.run_id, ('awaiting_approval',))
rp = [p for p in prompts if p[0] == 'plan'][-1][2]
check('B2: planner saw the previous plan and the feedback', 'PREVIOUS PLAN' in rp and 'USER FEEDBACK' in rp and 'add a reports module' in rp)
check('B3: revised plan replaced the old one (6 modules)', len(d.plan['modules']) == 6 and 'revised' in d.plan['modules'][0]['title'])
check('B4: empty feedback rejected', c.post(f'/api/runs/{d.run_id}/replan', headers=H, json={'feedback': ' '}).status_code == 400)
rr = c.post(f'/api/runs/{d.run_id}/reject', headers=H)
d = RunDocument.objects.get(run_id=d.run_id)
check('B5: reject cancels, clears plan, builds nothing', rr.status_code == 200 and d.status == 'cancelled' and not d.plan and not tasks(d.run_id))

# small plans skip review; cancel while waiting
reset(n=3)
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin', review_plan=True)
d = wait(r.run_id, ('completed', 'failed', 'awaiting_approval'))
check('B6: 3-module plan does not need approval', d.status == 'completed', d.status)
reset(n=5)
r = engine.create_run('build a big crm dashboard with auth', OUT, KEYS, owner='admin', review_plan=True)
d = wait(r.run_id, ('awaiting_approval',))
engine.cancel_run(d.run_id)
check('B7: cancel while waiting closes the run', RunDocument.objects.get(run_id=d.run_id).status == 'cancelled')

# ───────── C. an agent asks the user mid-build ─────────
reset(n=3, ask='module 1', dep=True)
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('awaiting_input',))
qs = d.questions
waiting = tasks(d.run_id, status='waiting')
check('C1: run pauses for the agent question', d.status == 'awaiting_input' and len(qs) == 1 and qs[0]['taskId'] and qs[0]['options'] == ['Dark', 'Light'])
check('C2: the agent that did not need to ask finished meanwhile', any(t.status == 'done' and 'module 0' in t.title for t in tasks(d.run_id, kind='module')))
check('C3: exactly one agent is waiting; downstream stays queued (not skipped)', len(waiting) == 1 and not tasks(d.run_id, status='skipped'), str([(t.title, t.status) for t in tasks(d.run_id)]))
rr = c.post(f'/api/runs/{d.run_id}/answers', headers=H, json={'answers': {qs[0]['id']: 'Dark'}})
d = wait(d.run_id, ('completed', 'failed'))
ap = [p for p in prompts if p[0] == 'agent' and 'module 1' in p[2].split('=== YOUR MODULE ===')[1].split('\n')[1]][-1][2]
check('C4: agent got the answer and finished the build', d.status == 'completed' and 'THEY ANSWERED' in ap and 'A: Dark' in ap, d.error)
check('C5: the agent was not allowed to ask twice', 'MAY ask' not in ap)
reset(n=3, ask='module 1', dep=True)
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin', source='schedule')
d = wait(r.run_id, ('completed', 'failed', 'awaiting_input'), timeout=60)
check('C7: schedule run is never allowed to ask, builds on its own', d.status == 'completed' and not any('MAY ask' in p[2] for p in prompts if p[0] == 'agent'), d.status)

# ───────── D. planner revises after an agent fails twice ─────────
reset(n=3, fail='module 1', revise={"action": "retry", "description": "simple version: just one small page", "contract_add": "keep it tiny"})
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
t1 = [t for t in tasks(d.run_id, kind='module') if 'module 1' in t.title][0]
check('D1: retry action rewrote the brief and the module then succeeded', d.status == 'completed' and t1.status == 'done' and t1.replans == 1 and 'simple version' in t1.description, d.error)
check('D2: revision counted, contract extended, planner call charged', d.revisions == 1 and 'keep it tiny' in d.contract and any(u.purpose == 'replan' for u in UsageDocument.objects(run_id=d.run_id)))
check('D3: planner saw the error and the failed module', any(p[0] == 'revise' and 'FAILED MODULE' in p[2] and 'ERROR:' in p[2] for p in prompts))

reset(n=3, dep=True, fail='module 0', fail_mode='always', revise={"action": "split", "modules": [
    {"key": "a", "title": "Left half of the first page", "description": "first half", "expects": ["a.html"]},
    {"key": "b", "title": "Right half of the first page", "description": "second half", "expects": ["b.html"]}], "contract_add": ""})
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
allt = tasks(d.run_id, kind='module')
old = [t for t in allt if t.title == 'Build module 0'][0]
parts = [t for t in allt if t.title.endswith('of the first page')]
m1 = [t for t in allt if t.title == 'Build module 1'][0]
check('D4: split replaced the failed module with 2 smaller agents', old.replaced and old.status == 'skipped' and len(parts) == 2 and all(p.status == 'done' for p in parts), str([(t.title, t.status) for t in allt]))
check('D5: parts live inside the old folder', all(p.folder.startswith('f0/') for p in parts), str([p.folder for p in parts]))
check('D6: dependents were rewired and still ran', m1.status == 'done' and set(p.task_id for p in parts) <= set(m1.depends_on) and old.task_id not in m1.depends_on, str(m1.depends_on))
check('D7: run completed even though one module was replaced', d.status == 'completed' and d.revisions == 1, d.error)

reset(n=3, fail='module 0', fail_mode='always', revise={"action": "drop", "reason": "cannot fix"})
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
check('D8: drop action ends honestly as failed (no template, no fake result)', d.status == 'failed' and 'did not finish' in d.error, d.error)
reset(n=3, fail='module 0', fail_mode='always', revise={"action": "retry", "description": "still hopeless", "contract_add": ""})
r = engine.create_run('build a crm dashboard with auth', OUT, KEYS, owner='admin')
d = wait(r.run_id, ('completed', 'failed'))
check('D9: revision is limited: one re-plan per agent, then it fails', d.status == 'failed' and d.revisions == 1 and len([p for p in prompts if p[0] == 'revise']) == 1, f'{d.status} {d.revisions}')

# ───────── E. follow-up edit of an existing project ─────────
reset(n=2)
r = engine.create_run('change the heading to say changed in the crm project', OUT, KEYS, owner='admin', continue_from=PARENT.run_id)
d = wait(r.run_id, ('completed', 'failed'))
pp = [p for p in prompts if p[0] == 'plan'][-1][2]
ap = [p for p in prompts if p[0] == 'agent'][-1][2]
check('E1: edit run reuses the project folder and links to the parent', d.mode == 'edit' and d.target_path == PARENT.target_path and d.parent_run_id == PARENT.run_id)
check('E2: planner saw the existing project (summary, contract, files)', 'EXISTING PROJECT' in pp and 'f0/page0.html' in pp and 'CHANGE REQUEST' in [p for p in prompts if p[0] == 'plan'][-1][1])
check('E3: agent was given the current file contents to modify', 'CHANGE TO AN EXISTING PROJECT' in ap and '--- f0/page0.html' in ap and '<p>ok</p>' in ap)
check('E4: the file on disk was changed in place', open(os.path.join(d.target_path, 'f0', 'page0.html')).read() == '<p>changed</p>' and d.status == 'completed', d.error)
check('E5: other files untouched', open(os.path.join(d.target_path, 'f1', 'page1.html')).read() == '<p>ok</p>')
check('E6: unknown parent is rejected', c.post('/api/runs', headers=H, json={'goal': 'change x', 'targetPath': OUT, 'continueRunId': 'run_nope'}).status_code == 404)
rr = c.post('/api/runs', headers=H, json={'goal': 'change the heading', 'targetPath': OUT, 'continueRunId': PARENT.run_id, 'reviewPlan': True})
check('E7: continue over HTTP', rr.status_code == 201 and rr.get_json()['mode'] == 'edit', rr.get_data(as_text=True))
wait(rr.get_json()['id'], ('completed', 'failed'))

# ───────── F. real browser check + fix loop ─────────
GOOD = '<!doctype html><html><head><title>Cafe</title></head><body><h1>Cafe</h1><p>Fresh coffee every morning.</p><button onclick="document.title=1">Order</button></body></html>'
BAD = '<!doctype html><html><head><title>Cafe</title><script src="app.js"></script></head><body><h1>Cafe</h1><p>Fresh coffee every morning.</p><button onclick="boom()">Order</button></body></html>'
reset(good_html=GOOD, bad_html=BAD)
r = engine.create_run('make a simple landing page for a cafe', OUT, KEYS, owner='admin', verify_run=True)
d = wait(r.run_id, ('completed', 'failed'), timeout=120)
vt = tasks(d.run_id, kind='verify')[0]
check('F1: browser check found real bugs, the fixer repaired them, the check then passed',
      d.status == 'completed' and vt.status == 'done' and S.get('fixes') == 1 and d.check.get('ok') is True and d.check.get('round') == 2, f'{d.status} fixes={S.get("fixes")} check={d.check}')
fixp = [p for p in prompts if p[0] == 'fix'][0][2]
check('F2: the fixer was shown the browser errors (404 for app.js, click error)', 'BROWSER CHECK' in fixp and 'app.js' in fixp and 'boom' in fixp, fixp[:400])
check('F3: screenshot saved and served', os.path.isfile(os.path.join(worker.SHOT_DIR, f'{d.run_id}.png')) and c.get(f'/api/runs/{d.run_id}/screenshot', headers=H).status_code == 200)
check('F4: check data exposed on the run API', c.get(f'/api/runs/{d.run_id}', headers=H).get_json()['run']['check']['ok'] is True)
check('F5: the fixed file is on disk', open(os.path.join(d.target_path, 'index.html')).read() == GOOD)

reset(good_html=BAD, bad_html=BAD, fixed_html=BAD)     # fixer cannot fix it
r = engine.create_run('make a simple landing page for a cafe', OUT, KEYS, owner='admin', verify_run=True)
d = wait(r.run_id, ('completed', 'failed'), timeout=150)
vt = tasks(d.run_id, kind='verify')[0]
check('F6: unfixable site: verify fails after 2 rounds, run completes with an honest warning', vt.status == 'failed' and d.status == 'completed' and 'browser check still found problems' in d.error and d.check.get('ok') is False, f'{d.status} {d.error[:120]}')
check('F7: exactly 2 fix attempts (bounded cost)', S.get('fixes') == 2, str(S.get('fixes')))

# ───────── G. permissions & recovery ─────────
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
mt = auth.make_token('mem', 'member'); MH = {'Authorization': 'Bearer ' + mt}
reset(n=5)
r = engine.create_run('build a big crm dashboard with auth', OUT, KEYS, owner='admin', review_plan=True)
d = wait(r.run_id, ('awaiting_approval',))
check('G1: another member cannot approve someone else\'s plan', c.post(f'/api/runs/{d.run_id}/approve', headers=MH, json={}).status_code in (403, 404))
check('G2: another member cannot continue someone else\'s project', c.post('/api/runs', headers=MH, json={'goal': 'change x', 'targetPath': OUT, 'continueRunId': PARENT.run_id}).status_code in (403, 404))
engine.recover_interrupted()
check('G3: restart recovery leaves runs waiting for the user alone', RunDocument.objects.get(run_id=d.run_id).status == 'awaiting_approval')
rr = c.post(f'/api/runs/{d.run_id}/approve', headers=H, json={})
wait(d.run_id, ('completed', 'failed'))
check('G4: a waiting plan can still be approved after a restart', RunDocument.objects.get(run_id=d.run_id).status == 'completed')

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
