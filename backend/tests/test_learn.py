"""Offline tests: Adion learns from chats (privately, safely) and keeps long conversations in view (bigger window + rolling summary).
Scripted model; no network, no credits."""
import os, sys, json, time, tempfile
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
os.environ['ADION_LEARN'] = '1'
os.environ['ADION_LEARN_SYNC'] = '1'         # learn inside the call so the test can look right after
os.environ['ADION_STREAM'] = '0'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from datetime import datetime, timedelta
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, learn
from models import RunDocument, MemoryDocument, ThreadSummaryDocument, UserDocument
from routes.memory import recall, remember
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

# ───────── scripted model ─────────
LEARN_REPLIES, learn_prompts, sum_prompts, agent_systems, agent_msgs = [], [], [], [], []
def resp(text): return {'choices': [{'message': {'role': 'assistant', 'content': text}}], 'usage': {'prompt_tokens': 200, 'completion_tokens': 40, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 200}}
def facts(*items): return json.dumps({'facts': [{'text': t, 'kind': k, 'replaces': r} for t, k, r in items]})
def fake_post(url, **kw):
    msgs = kw['json']['messages']; system, last = msgs[0]['content'], msgs[-1]['content']
    if 'private notebook' in system:
        learn_prompts.append(last)
        r = LEARN_REPLIES.pop(0) if LEARN_REPLIES else facts()
        if isinstance(r, Exception): raise r
        return resp(r)
    if 'compress the older part' in system:
        sum_prompts.append(last); return resp(f'SUMMARY v{len(sum_prompts)}')
    if 'You are Adion, the user' in system:
        agent_systems.append(system); agent_msgs.append(msgs); return resp('Sure.')
    raise AssertionError('unexpected prompt: ' + system[:80])
llm._post = fake_post

app = create_app(); auth.ensure_bootstrap_admin()
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
c = app.test_client()
H = lambda u, r: {'Authorization': 'Bearer ' + auth.make_token(u, r)}
OWNER, MEM = H('admin', 'admin'), H('mem', 'member')
KEYS = {'deepseek': 'sk-testtesttesttesttest'}
OUT = tempfile.mkdtemp(prefix='adion_learn_')
def ask(goal, owner='admin', thread=''):
    r = engine.create_run(goal, OUT, KEYS, owner=owner, thread_id=thread)
    t0 = time.time()
    while time.time() - t0 < 30:
        d = RunDocument.objects.get(run_id=r.run_id)
        if d.status in ('completed', 'failed'):
            time.sleep(0.5); return RunDocument.objects.get(run_id=r.run_id)
        time.sleep(0.1)
    raise TimeoutError(goal)
def mine(owner, source='learned'): return [m.text for m in MemoryDocument.objects(owner=owner, source=source)]

# ───────── what is worth a learning call ─────────
check('A1: personal statements and corrections are candidates', all(learn.worth_learning(t) for t in ("I'm a nurse in Lisbon and I prefer short answers", 'from now on reply in Spanish', "don't use emojis please", 'no, I meant the other one')))
check('A2: plain questions, greetings and one-liners are not (no model call is spent)', not any(learn.worth_learning(t) for t in ('what is the capital of france', 'hi', 'ok thanks', 'how tall is mount everest', '')))
check('A3: anything that looks like a secret is never kept', not any(learn._clean_fact(t) for t in ('The user password is hunter22', 'The user key is sk-abcdefghijklmnop1234', 'Card number 4111111111111111', 'The user has an api key for X')) and learn._clean_fact('The user is a nurse in Lisbon.'))

# ───────── learning from a chat ─────────
LEARN_REPLIES[:] = [facts(('The user is a nurse in Lisbon.', 'fact', None), ('The user wants short answers.', 'correction', None))]
d = ask("I'm a nurse in Lisbon and please keep answers short", thread='t1')
check('B1: the chat is answered first and completed', d.status == 'completed' and d.answer == 'Sure.')
check('B2: both notes were learned into the person\'s own memory', sorted(mine('admin')) == ['The user is a nurse in Lisbon.', 'The user wants short answers.'], mine('admin'))
kinds = {m.text: m.kind for m in MemoryDocument.objects(owner='admin')}
check('B3: a style correction becomes a standing preference, a fact becomes a note', kinds['The user wants short answers.'] == 'preference' and kinds['The user is a nurse in Lisbon.'] == 'note')
check('B4: the learning call saw the user\'s words and the existing notes, and was told the reply is context only', "keep answers short" in learn_prompts[0] and 'EXISTING NOTES' in learn_prompts[0] and 'never a source' in learn_prompts[0])
d = ask('help me plan my week', thread='t1')
check('B5: the next chat starts already knowing them', 'nurse in Lisbon' in agent_systems[-1] and 'short answers' in agent_systems[-1])
n_before = len(learn_prompts)
d = ask('what is the capital of france', thread='t1')
check('B6: an ordinary question costs no learning call', len(learn_prompts) == n_before)

# ───────── privacy ─────────
check('C1: another member never sees these notes', recall('nurse Lisbon short answers', owner='mem') == '' and 'nurse' not in str(c.get('/api/memory', headers=MEM).get_json()))
LEARN_REPLIES[:] = [facts(('The user is a chef.', 'fact', None))]
ask("I'm a chef and I cook at home", owner='mem', thread='t2')
check('C2: a member\'s notes are their own', mine('mem') == ['The user is a chef.'] and 'chef' not in recall('chef cook', owner='admin') and 'chef' in recall('chef cook', owner='mem'))
MemoryDocument(mem_id='mem_legacy', text='Old note about gardens', kind='note', owner='').save()
check('C3: notes from before memories were private belong to the owner/admin only', 'gardens' in recall('gardens', owner='admin') and 'gardens' not in recall('gardens', owner='mem'))
r = c.get('/api/memory', headers=MEM).get_json()
check('C4: the Memory list shows a member only their notes, marked as learned', [m['text'] for m in r] == ['The user is a chef.'] and r[0]['source'] == 'learned', r)
mid = r[0]['id']
check('C5: nobody can delete someone else\'s note', c.delete(f'/api/memory/{[m.mem_id for m in MemoryDocument.objects(owner="admin")][0]}', headers=MEM).status_code == 200 and len(mine('admin')) == 2)
c.delete(f'/api/memory/{mid}', headers=MEM)
check('C6: a person can delete what Adion learned about them', mine('mem') == [])

# ───────── switches ─────────
check('D1: learning is on by default and each person can turn theirs off', c.get('/api/memory/learning', headers=MEM).get_json() == {'on': True} and c.put('/api/memory/learning', headers=MEM, json={'on': False}).get_json() == {'on': False})
n_before = len(learn_prompts); LEARN_REPLIES[:] = [facts(('The user likes tea.', 'fact', None))]
ask("I like tea and I drink it daily", owner='mem', thread='t2')
check('D2: with it off, nothing is learned and no call is made', len(learn_prompts) == n_before and mine('mem') == [])
c.put('/api/memory/learning', headers=MEM, json={'on': True}); LEARN_REPLIES[:] = []
os.environ['ADION_LEARN'] = '0'
n_before = len(learn_prompts)
ask("I like coffee and I drink it daily", thread='t1')
check('D3: ADION_LEARN=0 switches it off for everyone', len(learn_prompts) == n_before)
os.environ['ADION_LEARN'] = '1'

# ───────── quality rules ─────────
LEARN_REPLIES[:] = [facts(('The user is a nurse in Lisbon.', 'fact', None))]
ask("I'm a nurse in Lisbon (again)", thread='t1')
check('E1: a fact already known is not saved twice', mine('admin').count('The user is a nurse in Lisbon.') == 1)
old = MemoryDocument.objects(owner='admin', text='The user is a nurse in Lisbon.').first()
LEARN_REPLIES[:] = [facts(('The user is a nurse in Porto.', 'fact', 1))]
notes = list(learn.visible(owner='admin').limit(40)) if hasattr(learn, 'visible') else None
from routes.memory import visible
ln = list(visible('admin').limit(40)); idx = [n.text for n in ln].index('The user is a nurse in Lisbon.') + 1
LEARN_REPLIES[:] = [facts(('The user is a nurse in Porto.', 'fact', idx))]
ask("I moved, I'm a nurse in Porto now", thread='t1')
check('E2: a changed fact replaces the outdated learned note', 'The user is a nurse in Porto.' in mine('admin') and 'The user is a nurse in Lisbon.' not in mine('admin'), mine('admin'))
remember('I always want tabs not spaces', 'preference', owner='admin')
ln = list(visible('admin').limit(40)); idx = [n.text for n in ln].index('I always want tabs not spaces') + 1
LEARN_REPLIES[:] = [facts(('The user wants spaces not tabs.', 'preference', idx))]
ask("I never want tabs, use spaces", thread='t1')
check('E3: a note the person typed themselves is never overwritten by a learned one', 'I always want tabs not spaces' in mine('admin', 'user'))
LEARN_REPLIES[:] = [facts(('The user has an api key sk-abcdefghijklmnop1234 for X.', 'fact', None), ('The user is learning Rust.', 'fact', None))]
ask("My api key is sk-abcdefghijklmnop1234 and I am learning Rust", thread='t1')
check('E4: a secret in the reply is dropped, the harmless note is kept', not any('sk-' in t for t in mine('admin')) and 'The user is learning Rust.' in mine('admin'))
learn.MAX_LEARNED = 3
LEARN_REPLIES[:] = [facts(('The user plays chess.', 'fact', None), ('The user owns a cat.', 'fact', None), ('The user uses Linux.', 'fact', None))]
ask("I play chess, I own a cat and I use Linux", thread='t1')
check('E5: a person\'s learned notes are capped (oldest go first); typed notes are untouched', len(mine('admin')) == 3 and len(mine('admin', 'user')) >= 1, mine('admin'))
learn.MAX_LEARNED = 150
LEARN_REPLIES[:] = [llm.LLMError('model down')]
d = ask("I live in Madrid and I work nights", thread='t1')
check('E6: if learning fails the chat is still answered', d.status == 'completed' and d.answer == 'Sure.')
LEARN_REPLIES[:] = ['not json at all']
d = ask("I live in Madrid and I work nights, really", thread='t1')
check('E7: junk from the model is ignored', d.status == 'completed')

# ───────── long conversations ─────────
check('F1: Claude gets a much bigger window than DeepSeek, and the env var overrides both', learn.history_budget({'provider': 'anthropic'}) > 4 * learn.history_budget({'provider': 'deepseek'}) and (os.environ.__setitem__('ADION_HISTORY_TOKENS', '123') or learn.history_budget({}) == 123))
os.environ.pop('ADION_HISTORY_TOKENS')
turns = [(f'question {i} ' + 'x' * 400, f'answer {i} ' + 'y' * 400) for i in range(60)]
older, recent = learn.split_turns(turns, 100_000)
check('F2: with room, up to 40 recent turns are sent in full (it used to be 16)', len(recent) == 40 and recent[-1][0].startswith('question 59') and len(older) == 20)
older, recent = learn.split_turns(turns, 1000)
check('F3: with a small budget fewer turns are sent, always the newest, and the rest is "older"', 0 < len(recent) < 10 and recent[-1][0].startswith('question 59') and len(older) + len(recent) == 60, (len(older), len(recent)))
older, recent = learn.split_turns([('q' * 9000, 'a' * 9000)], 100_000)
check('F4: a huge single turn is cut to a sane size', len(recent[0][0]) == learn.MAX_TURN_Q and len(recent[0][1]) == learn.MAX_TURN_A)

spec = {'provider': 'deepseek', 'model': 'deepseek-chat', 'key': 'k'}
os.environ['ADION_HISTORY_TOKENS'] = '1500'
T = [(f'question {i} ' + 'x' * 400, f'answer {i} ' + 'y' * 400) for i in range(30)]
older, _ = learn.split_turns(T, 1500)
sum_prompts.clear()
learn.refresh_summary(spec, 'admin', 'long1', T)
d1 = ThreadSummaryDocument.objects(owner='admin', thread_id='long1').first()
check('G1: older turns are folded into a stored summary', d1 and d1.summary == 'SUMMARY v1' and d1.covers == len(older) and 'question 0' in sum_prompts[0] and 'nothing yet' in sum_prompts[0], d1 and (d1.summary, d1.covers))
learn.refresh_summary(spec, 'admin', 'long1', T)
check('G2: nothing new has piled up, so no model call is spent', len(sum_prompts) == 1)
T2 = T + [(f'question {i} ' + 'x' * 400, f'answer {i} ' + 'y' * 400) for i in range(30, 45)]
learn.refresh_summary(spec, 'admin', 'long1', T2)
d2 = ThreadSummaryDocument.objects(owner='admin', thread_id='long1').first()
check('G3: later it is updated, not rewritten from scratch: the old summary and only the new turns go in', len(sum_prompts) == 2 and 'SUMMARY v1' in sum_prompts[1] and 'question 0 ' not in sum_prompts[1] and d2.covers > d1.covers and d2.summary == 'SUMMARY v2', sum_prompts[-1][:200])
check('G4: another person with the same thread id has a separate summary', learn.get_summary('mem', 'long1') == '' and learn.get_summary('admin', 'long1') == 'SUMMARY v2')

# the engine uses all of it
base = datetime.now() - timedelta(hours=2)
for i in range(30):
    RunDocument(run_id=f'run_h{i}', goal=f'earlier question {i} ' + 'z' * 300, answer=f'earlier answer {i} ' + 'w' * 300, status='completed', kind='chat', owner='admin', thread_id='long2', target_path=OUT,
                created_at=base + timedelta(minutes=i)).save()
os.environ['ADION_HISTORY_TOKENS'] = '100000'
agent_msgs.clear()
ask('what did we decide about the plan', thread='long2')
m = agent_msgs[-1]
check('H1: a thread with 30 earlier turns sends all 30 (before: only 16), oldest first', sum(1 for x in m if x['role'] == 'user' and x['content'].startswith('earlier question')) == 30 and m[1]['content'].startswith('earlier question 0'))
check('H2: when everything fits there is no summary block', 'EARLIER IN THIS CONVERSATION' not in m[0]['content'])
os.environ['ADION_HISTORY_TOKENS'] = '1500'
ThreadSummaryDocument(owner='admin', thread_id='long2', summary='The user is planning a kitchen rebuild; budget 20k.', covers=10).save()
agent_msgs.clear()
ask('and the budget?', thread='long2')
m = agent_msgs[-1]
sent = sum(1 for x in m if x['role'] == 'user' and x['content'].startswith('earlier question'))
check('H3: when older turns do not fit, they arrive as a summary in the system prompt, and the newest turns still arrive in full', 0 < sent < 30 and 'EARLIER IN THIS CONVERSATION' in m[0]['content'] and 'kitchen rebuild' in m[0]['content'], sent)
check('H4: the newest earlier turn is the last one sent', [x['content'] for x in m if x['role'] == 'user' and x['content'].startswith('earlier question')][-1].startswith('earlier question 29'))
check('H5: the summary refresh ran after the answer (this thread is long enough)', ThreadSummaryDocument.objects(owner='admin', thread_id='long2').first().covers >= 10 and len(sum_prompts) >= 3)

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
