"""Offline tests: chat that remembers the conversation, and search that happens by itself for factual questions.
Fake model, fake Tavily; no tokens, no credits."""
import os, sys, json, time, tempfile, types
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import mongoengine as me
from datetime import datetime, timedelta
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import engine, llm, search
from models import RunDocument
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

S = {'rewrite': 'ok', 'answers': []}
calls = []          # ('answer'|'rewrite'|'plan', system, prompt)
def resp(text):
    return {'choices': [{'message': {'content': text}}], 'usage': {'prompt_tokens': 200, 'completion_tokens': 50, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 200}}
def fake_post(url, **kw):
    msgs = kw['json']['messages']; system, prompt = msgs[0]['content'], msgs[1]['content']
    if 'Rewrite the LAST message' in system:
        calls.append(('rewrite', system, prompt))
        if S['rewrite'] == 'error':
            raise llm.LLMError('boom')
        return resp('mia malkova biography career')
    if 'sharp personal assistant' in system:
        calls.append(('answer', system, prompt))
        return resp(S['answers'].pop(0) if S['answers'] else 'An answer.')
    if 'lead architect of an autonomous' in system:
        calls.append(('plan', system, prompt))
        return resp(json.dumps({'type': 'answer', 'answer': 'Planner answer.'}))
    raise AssertionError('unexpected: ' + system[:60])
llm._post = fake_post
def _no_stream(*a, **k):
    raise llm.LLMError('streaming off in this test')
    yield
llm.chat_stream = _no_stream

tavily = []
class Resp:
    status_code = 200
    def __init__(self, d): self._d, self.text = d, ''
    def json(self): return self._d
def fake_tavily(url, **kw):
    tavily.append(kw['json']['query'])
    return Resp({'results': [{'title': 'Wikipedia', 'url': 'https://example.com/a', 'content': 'Born in 1992. Known for modelling and online content.'},
                             {'title': 'News', 'url': 'https://example.com/b', 'content': 'Recent interview about her career.'}]})
search.requests = types.SimpleNamespace(post=fake_tavily, exceptions=requests.exceptions)

app = create_app()
auth.ensure_bootstrap_admin()
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
H = {'Authorization': 'Bearer ' + auth.make_token('admin', 'admin')}
c = app.test_client()
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
OUT = tempfile.mkdtemp(prefix='adion_chat_')
WITH = {'deepseek': 'sk-testtesttesttesttest', 'tavily': 'tvly-testtesttest'}
NO_TAVILY = {'deepseek': 'sk-testtesttesttesttest'}

def ask(goal, thread='', keys=WITH, owner='admin'):
    calls.clear(); tavily.clear()
    r = engine.create_run(goal, OUT, keys, owner=owner, thread_id=thread)
    t0 = time.time()
    while time.time() - t0 < 30:
        d = RunDocument.objects.get(run_id=r.run_id)
        if d.status in ('completed', 'failed'):
            time.sleep(0.2); return RunDocument.objects.get(run_id=r.run_id)
        time.sleep(0.1)
    raise TimeoutError(goal)
def answer_prompt(): return [x for x in calls if x[0] == 'answer'][-1]

# ───────── when to search ─────────
for text, want in [('how is mia malkova', True), ('go read its real information', True), ('who is elon musk', True), ('what is docker', True),
                   ('tell me about tesla', True), ('look up the weather in paris', True), ('bitcoin price today', True), ('hi', False), ('thanks', False),
                   ('how old is he', True), ('ok', False), ('explain recursion', False), ('write a poem about cats', False), ('translate this to french', False),
                   ('summarize this article', False), ('good morning', False), ('', False)]:
    check(f'S1: should_search({text!r}) == {want}', search.should_search(text) == want)
check('S2: the "always search" switch overrides', search.should_search('hi', always=True))

# ───────── a plain factual question now searches by itself ─────────
d = ask('how is mia malkova\ngo read its real information')
p = answer_prompt()[2]
check('A1: it searched without being told to use a keyword', len(tavily) == 1 and 'WEB SOURCES' in p and 'Known for modelling' in p, f'{tavily} {p[:200]}')
check('A2: sources are saved for the answer', [s['url'] for s in d.sources] == ['https://example.com/a', 'https://example.com/b'])
check('A3: the prompt says what was searched for', 'searched for: how is mia malkova' in p)
check('A4: it no longer claims it has no internet access', 'no internet' not in answer_prompt()[1].lower() and "can't browse" not in answer_prompt()[1].lower())
d = ask('hi')
check('A5: greetings do not spend a search', tavily == [] and d.answer == 'An answer.')
d = ask('explain recursion')
check('A6: writing/explaining tasks do not spend a search', tavily == [])
d = ask('who is the ceo of nvidia', keys=NO_TAVILY)
check('A7: no Tavily key: honest note telling the user how to fix it', tavily == [] and 'Add a free Tavily key' in d.answer and d.answer.startswith('An answer.'), d.answer)
d = ask('hi', keys=NO_TAVILY)
check('A8: ...but no nagging on a greeting', 'Tavily' not in d.answer)

# ───────── conversation memory ─────────
S['answers'] = ['She is a model and online creator.', 'Her real name and career details are in the sources [1].']
t1 = ask('who is mia malkova', thread='th_one')
check('C1: first turn has no history', 'CONVERSATION SO FAR' not in answer_prompt()[2])
t2 = ask('go read its real information', thread='th_one')
kinds = [x[0] for x in calls]
p2 = answer_prompt()[2]
check('C2: the follow-up is treated as chat (not sent to the planner)', t2.kind == 'chat' and 'plan' not in kinds and t2.status == 'completed', f'{t2.kind} {kinds}')
check('C3: the model sees the earlier question and answer', 'CONVERSATION SO FAR' in p2 and 'User: who is mia malkova' in p2 and 'Adion: She is a model' in p2)
check('C4: the vague follow-up was rewritten into a real search query using the chat', 'rewrite' in kinds and tavily == ['mia malkova biography career'], f'{kinds} {tavily}')
check('C5: the rewrite prompt contained the conversation', 'who is mia malkova' in [x for x in calls if x[0] == 'rewrite'][0][2])
check('C6: the follow-up got web sources too', 'WEB SOURCES (searched for: mia malkova biography career)' in p2 and len(t2.sources) == 2)
check('C7: the system prompt tells it to use the conversation', 'CONVERSATION SO FAR' in answer_prompt()[1] and 'resolve' in answer_prompt()[1])
S['answers'] = ['Third answer.']
t3 = ask('what year was she born', thread='th_one')
p3 = answer_prompt()[2]
check('C8: a third turn sees both earlier turns, oldest first', p3.index('who is mia malkova') < p3.index('go read its real information') and 'Her real name' in p3)
calls.clear(); ask('what is the population of lisbon portugal in 2024 according to official statistics', thread='th_one')
check('C9b: ...really, no extra rewrite call', not any(x[0] == 'rewrite' for x in calls) and tavily[0].startswith('what is the population'), str(tavily))

# ───────── isolation ─────────
ask('what year was she born', thread='th_other')
check('I1: another conversation does not see this one', 'CONVERSATION SO FAR' not in answer_prompt()[2])
ask('what year was she born', thread='th_one', owner='mem')
check('I2: another user with the same thread id does not see it', 'CONVERSATION SO FAR' not in answer_prompt()[2])
RunDocument.objects(thread_id='th_one').update(set__created_at=datetime.utcnow() - timedelta(hours=3))
ask('go read its real information', thread='th_one')
check('I3: turns older than 90 minutes are forgotten', not any('CONVERSATION SO FAR' in x[2] for x in calls) and len(calls) > 0, str(calls))
calls.clear(); ask('I want an app', thread='th_fresh')
check('I5: a vague message in an EMPTY thread is not forced into chat', any(x[0] == 'plan' for x in calls), str([x[0] for x in calls]))

# ───────── robustness ─────────
S['answers'] = ['Mia is X.']
ask('who is mia malkova', thread='th_err')
S['rewrite'] = 'error'
ask('go read its real information', thread='th_err')
check('R1: if the query rewrite fails, it falls back to previous question + message', tavily and tavily[0].startswith('who is mia malkova go read'), str(tavily))
S['rewrite'] = 'ok'
# no key + follow-up: still remembers
S['answers'] = ['First.', 'Second.']
ask('who is the pope', thread='th_nokey', keys=NO_TAVILY)
ask('how old is he', thread='th_nokey', keys=NO_TAVILY)
check('R2: memory works even without web search', 'User: who is the pope' in answer_prompt()[2] and any('Tavily' in r.answer for r in RunDocument.objects(thread_id='th_nokey')))

# ───────── API ─────────
r = c.post('/api/runs', headers=H, json={'goal': 'hi there', 'targetPath': OUT, 'threadId': 'th_api'})
check('P1: threadId is accepted and returned', r.status_code == 201 and r.get_json()['threadId'] == 'th_api', r.get_data(as_text=True))
check('P2: a huge threadId is cut to 40 chars', len(c.post('/api/runs', headers=H, json={'goal': 'hi again', 'targetPath': OUT, 'threadId': 'x' * 200}).get_json()['threadId']) == 40)
f = c.post('/api/usage/estimate', headers=H, json={'goal': 'how is mia malkova'}).get_json()
check('P3: the forecast knows a factual question will be searched', 'web' in f['parts'][0]['name'].lower(), str(f['parts']))

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
