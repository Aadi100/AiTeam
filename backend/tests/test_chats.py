"""Offline tests: the chats list (one entry per conversation), reopening, deleting, and privacy. Builds are not chats."""
import os, sys, json, time, tempfile
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from datetime import datetime, timedelta
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm
from models import RunDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

prompts = []
def fake_post(url, **kw):
    msgs = kw['json']['messages']; system, prompt = msgs[0]['content'], msgs[1]['content']
    prompts.append(prompt)
    return {'choices': [{'message': {'content': 'A reply.'}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}}
llm._post = fake_post
def _no_stream(*a, **k):
    raise llm.LLMError('off')
    yield
llm.chat_stream = _no_stream

app = create_app()
auth.ensure_bootstrap_admin()
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
auth.UserDocument(username='view', password_hash=auth.generate_password_hash('password123'), role='viewer').save()
H = {'Authorization': 'Bearer ' + auth.make_token('admin', 'admin')}
MH = {'Authorization': 'Bearer ' + auth.make_token('mem', 'member')}
VH = {'Authorization': 'Bearer ' + auth.make_token('view', 'viewer')}
c = app.test_client()
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
now = datetime.utcnow()
def mk(rid, goal, answer='', thread='', owner='admin', mins=0, kind='chat', pc='', status='completed'):
    RunDocument(run_id=rid, goal=goal, answer=answer, thread_id=thread, owner=owner, kind=kind, pc_task_id=pc, status=status,
                target_path='x', created_at=now - timedelta(minutes=mins)).save()

# conversation A: 3 turns (oldest first by minutes ago); B: 1 turn; a legacy run with no thread; a PC request; a build; someone else's chat
mk('run_a1', 'who is elon musk', 'An entrepreneur.', 'th_A', mins=60)
mk('run_a2', 'how old is he', 'Born 1971.', 'th_A', mins=50)
mk('run_a3', 'where was he born', 'Pretoria.', 'th_A', mins=40)
mk('run_b1', 'what is docker', 'Containers.', 'th_B', mins=5)
mk('run_old', 'who is the pope', 'Leo.', '', mins=300)
mk('run_pc', 'open spotify', 'On it.', 'th_C', mins=20, kind='pc', pc='pc_1')
mk('run_build', 'make a landing page', '', 'th_A', mins=45, kind='small')
mk('run_fail', 'broken question', '', 'th_D', mins=30, status='failed')
mk('run_x1', 'secret question', 'secret answer', 'th_X', owner='mem', mins=2)

lst = c.get('/api/chats', headers=H).get_json()
by = {g['threadId']: g for g in lst}
check('L1: one entry per conversation, not per question', len(lst) == 4 and set(by) == {'th_A', 'th_B', 'th_C', 'run_old'}, str([g['threadId'] for g in lst]))
check('L2: title is the first question, count is the number of turns', by['th_A']['title'] == 'who is elon musk' and by['th_A']['count'] == 3 and by['th_B']['count'] == 1)
check('L3: newest conversation first', [g['threadId'] for g in lst] == ['th_B', 'th_C', 'th_A', 'run_old'], str([g['threadId'] for g in lst]))
check('L4: preview is the latest answer', by['th_A']['preview'] == 'Pretoria.')
check('L5: a build is not a chat turn (not counted, not listed)', by['th_A']['count'] == 3 and 'run_build' not in str(lst))
check('L6: a failed question with no answer is not listed', 'th_D' not in by)
check('L7: PC requests are part of the chats', by['th_C']['title'] == 'open spotify')
check('L8: older runs without a thread are their own conversation', by['run_old']['title'] == 'who is the pope' and by['run_old']['count'] == 1)
check('L9: other people\'s chats are not in my list', 'th_X' not in by and [g['threadId'] for g in c.get('/api/chats', headers=MH).get_json()] == ['th_X'])
check('L10: the list has update times (ISO)', all(g['updatedAt'].endswith('Z') for g in lst))

t = c.get('/api/chats/th_A', headers=H).get_json()
check('G1: a conversation returns its turns oldest first, with answers', [r['goal'] for r in t] == ['who is elon musk', 'how old is he', 'where was he born'] and t[1]['answer'] == 'Born 1971.', str(t))
check('G2: turns carry the run fields the UI needs', all(k in t[0] for k in ('id', 'answer', 'sources', 'threadId', 'attachments', 'pcTaskId')))
check('G3: a legacy run opens by its run id', c.get('/api/chats/run_old', headers=H).get_json()[0]['answer'] == 'Leo.')
check('G4: an unknown conversation is simply empty (no 404 noise), and others\' conversations are invisible', c.get('/api/chats/nope', headers=H).get_json() == [] and c.get('/api/chats/th_X', headers=H).get_json() == [])

# legacy conversation continues with its memory
prompts.clear()
r = engine.create_run('and how old is he', tempfile.mkdtemp(), {'deepseek': 'sk-testtesttesttesttest'}, owner='admin', thread_id='run_old')
time.sleep(1.5)
check('H1: continuing an old one-turn chat keeps its memory', any('User: who is the pope' in p for p in prompts), str(prompts)[:300])
check('H2: ...and the new turn joins that conversation', c.get('/api/chats', headers=H).get_json()[0]['count'] >= 1 and len(c.get('/api/chats/run_old', headers=H).get_json()) == 2)

# delete
check('D1: another user cannot delete my chat', c.delete('/api/chats/th_A', headers=MH).get_json()['deleted'] == 0 and len(c.get('/api/chats/th_A', headers=H).get_json()) == 3)
check('D2: viewers cannot delete', c.delete('/api/chats/th_A', headers=VH).status_code == 403)
r = c.delete('/api/chats/th_A', headers=H).get_json()
check('D3: deleting removes the conversation\'s turns', r['ok'] and r['deleted'] == 3 and c.get('/api/chats/th_A', headers=H).get_json() == [] and 'th_A' not in str(c.get('/api/chats', headers=H).get_json()))
check('D4: ...but never a project (the build in the same thread survives)', RunDocument.objects(run_id='run_build').first() is not None)
check('D5: other chats are untouched', len(c.get('/api/chats/th_B', headers=H).get_json()) == 1 and len(c.get('/api/chats/th_X', headers=MH).get_json()) == 1)

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
