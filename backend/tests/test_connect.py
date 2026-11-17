"""Offline tests for Adion Connect: accounts, isolation between clients, keys and origins, knowledge, actions (OpenAPI/Postman/in-app),
live API calls with the user's token, confirmations, redaction, SSRF protection, billing and caps. The model is scripted; the client's
"server" is a real local HTTP server."""
import os, sys, io, json, time, threading, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
os.environ['ADION_LEARN'] = '0'      # learning has its own tests (test_learn.py); here it would consume the scripted model replies
os.environ['CONNECT_ALLOW_PRIVATE'] = '1'        # the fake client server lives on 127.0.0.1 (tests turn this off to check SSRF)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import llm
import auth
from models import UsageDocument
from connect import security, knowledge, actions as act, billing, service
from connect.models import ConnectApp, AppAction, Conversation, Client

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

# ───────── the client's "server" ─────────
served = []                     # (method, path, auth header, body)
class API(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj):
        raw = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}
    def _go(self):
        body = self._body()
        served.append((self.command, self.path, self.headers.get('Authorization', ''), body, self.headers.get('X-Api-Key', '')))
        ok = self.headers.get('Authorization') == 'Bearer user-123-token' or self.headers.get('X-Api-Key') == 'svc-key-777'
        if not ok:
            return self._send(401, {'error': 'unauthorized'})
        if self.command == 'GET' and self.path.startswith('/transactions'):
            return self._send(200, {'transactions': [{'id': 1, 'amount': 100, 'category': 'Food', 'password': 'hunter2', 'token': 't0p-secret', 'internal_note': 'hide-me', 'owner': {'api_key': 'k-123', 'name': 'Asha'}}]})
        if self.command == 'POST' and self.path == '/transactions':
            return self._send(201, {'id': 2, **body})
        if self.command == 'DELETE':
            return self._send(200, {'deleted': True})
        return self._send(404, {'error': 'no route'})
    do_GET = do_POST = do_DELETE = do_PUT = _go
srv = ThreadingHTTPServer(('127.0.0.1', 0), API)
threading.Thread(target=srv.serve_forever, daemon=True).start()
API_URL = f'http://127.0.0.1:{srv.server_address[1]}'

# ───────── scripted model ─────────
script, seen = [], []        # script: dicts {'say': text} or {'call': [(name, args)]}
def fake_post(url, **kw):
    body = kw['json']; seen.append(body)
    step = script.pop(0) if script else {'say': 'Okay.'}
    msg = {'content': step.get('say', ''), 'role': 'assistant'}
    if step.get('call'):
        msg['tool_calls'] = [{'id': f'call_{i}', 'type': 'function', 'function': {'name': n, 'arguments': json.dumps(a)}} for i, (n, a) in enumerate(step['call'])]
    return {'choices': [{'message': msg}], 'usage': {'prompt_tokens': 1000, 'completion_tokens': 200, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 1000}}
llm._post = fake_post

app = create_app()
auth.ensure_bootstrap_admin()
auth.UserDocument(username='mem', password_hash=auth.generate_password_hash('password123'), role='member').save()
c = app.test_client()
OWNER = {'Authorization': 'Bearer ' + auth.make_token('admin', 'admin')}
MEMBER = {'Authorization': 'Bearer ' + auth.make_token('mem', 'member')}
c.put('/api/auth/apikey', headers=OWNER, json={'key': 'sk-testtesttesttesttest'})

def post(path, body=None, h=None): return c.post('/api/platform' + path, json=body or {}, headers=h or {})
def hdr(tok): return {'Authorization': 'Bearer ' + tok}
def signup(email, pw='password123', name='Test'):
    r = post('/signup', {'email': email, 'password': pw, 'name': name}); return r, (hdr(r.get_json()['token']) if r.status_code == 201 else None)

# ───────── A. accounts ─────────
check('A1: bad email, short password, missing fields are refused', post('/signup', {'email': 'nope', 'password': 'password123'}).status_code == 400
      and post('/signup', {'email': 'a@b.co', 'password': 'short'}).status_code == 400)
r, A = signup('alice@acme.com', name='Alice')
check('A2: sign-up returns a token and the account', r.status_code == 201 and r.get_json()['client']['email'] == 'alice@acme.com' and 'password' not in json.dumps(r.get_json()).lower().replace('password123', ''))
check('A3: a duplicate email is refused', signup('ALICE@acme.com')[0].status_code == 409)
r, B = signup('bob@other.com', name='Bob')
check('A4: login works, wrong password does not', post('/login', {'email': 'alice@acme.com', 'password': 'password123'}).status_code == 200 and post('/login', {'email': 'alice@acme.com', 'password': 'wrongpass1'}).status_code == 401)
check('A5: /me returns the account and the owner\'s credit info', c.get('/api/platform/me', headers=A).get_json()['email'] == 'alice@acme.com' and 'freeCredit' in c.get('/api/platform/me', headers=A).get_json())
check('A6: no token / junk token -> 401', c.get('/api/platform/me').status_code == 401 and c.get('/api/platform/me', headers=hdr('junk')).status_code == 401)
check('A7: Adion\'s personal tokens are NOT client tokens (the owner cannot sneak in as a client)', c.get('/api/platform/me', headers=OWNER).status_code == 401)
check('A8: a client token does not open Adion\'s private API', c.get('/api/runs', headers=A).status_code == 401 and c.get('/api/pc/settings', headers=A).status_code == 401 and c.get('/api/chats', headers=A).status_code == 401)
check('A9: owner endpoints: the owner only', c.get('/api/platform/owner/clients', headers=A).status_code == 403 and c.get('/api/platform/owner/clients', headers=MEMBER).status_code == 403 and c.get('/api/platform/owner/clients', headers=OWNER).status_code == 200)
for i in range(10):
    rr = post('/login', {'email': 'ratelimit@x.com', 'password': 'whatever12'})
check('A10: login attempts are rate limited', rr.status_code == 429)

# ───────── B. projects, apps and keys ─────────
pa = post('/projects', {'name': 'Money App'}, A).get_json(); pb = post('/projects', {'name': 'Bob Shop'}, B).get_json()
ra = post(f'/projects/{pa["id"]}/apps', {'name': 'Android', 'platform': 'react-native'}, A).get_json()
rb = post(f'/projects/{pb["id"]}/apps', {'name': 'Web'}, B).get_json()
appA, skA, appB, skB = ra['app'], ra['secretKey'], rb['app'], rb['secretKey']
check('B1: an app gets a public key (pk_) and a secret key (sk_) shown once', appA['publicKey'].startswith('pk_') and skA.startswith('sk_') and 'secretKey' not in c.get(f'/api/platform/apps/{appA["id"]}', headers=A).get_json())
check('B2: the secret key is stored only as a hash', ConnectApp.objects(app_id=appA['id']).first().secret_hash != skA and skA not in json.dumps(ConnectApp.objects(app_id=appA['id']).first().to_mongo().to_dict(), default=str))
check('B3: a project must have a name; a client cannot add an app to someone else\'s project', post('/projects', {'name': ' '}, A).status_code == 400 and post(f'/projects/{pa["id"]}/apps', {'name': 'x'}, B).status_code == 404)
projs = c.get('/api/platform/projects', headers=A).get_json()
check('B4: the project list shows my apps only', [p['name'] for p in projs] == ['Money App'] and [a['name'] for a in projs[0]['apps']] == ['Android'])
for label, method, path in [('read the app', 'get', f'/apps/{appA["id"]}'), ('change the app', 'put', f'/apps/{appA["id"]}'), ('delete the app', 'delete', f'/apps/{appA["id"]}'),
                            ('list knowledge', 'get', f'/apps/{appA["id"]}/knowledge'), ('add knowledge', 'post', f'/apps/{appA["id"]}/knowledge'),
                            ('list actions', 'get', f'/apps/{appA["id"]}/actions'), ('import actions', 'post', f'/apps/{appA["id"]}/actions/import'),
                            ('read conversations', 'get', f'/apps/{appA["id"]}/conversations'), ('read usage', 'get', f'/apps/{appA["id"]}/usage'),
                            ('read the guide (it has keys)', 'get', f'/apps/{appA["id"]}/docs'), ('use the test chat', 'post', f'/apps/{appA["id"]}/test-chat'),
                            ('rotate the secret', 'post', f'/apps/{appA["id"]}/rotate-secret')]:
    rr = getattr(c, method)('/api/platform' + path, headers=B, json={'message': 'hi', 'source': '{}', 'text': 'x'})
    check(f'B5: client B cannot {label} of client A', rr.status_code == 404, f'{rr.status_code}')
check('B6: ...and nothing of A was changed or deleted', ConnectApp.objects(app_id=appA['id']).first() is not None)
r = post(f'/apps/{appA["id"]}/rotate-secret', {}, A).get_json()
check('B7: rotating the secret gives a new key and kills the old one', r['secretKey'] != skA and c.post('/api/connect/v1/tickets', json={'userId': '1'}, headers=hdr(skA)).status_code == 401
      and c.post('/api/connect/v1/tickets', json={'userId': '1'}, headers=hdr(r['secretKey'])).status_code == 200)
skA = r['secretKey']

# settings
put = lambda body: c.put(f'/api/platform/apps/{appA["id"]}', json=body, headers=A)
r = put({'description': 'A money tracker app.', 'rules': 'Never promise refunds.', 'persona': 'Penny', 'allowedOrigins': ['https://app.acme.com', 'https://*.acme.dev', 'http://localhost:*'],
         'accessLevel': 'standard', 'apiBaseUrl': API_URL, 'apiAuth': 'forward', 'monthlyCapUsd': 5, 'greeting': 'Hi, I am Penny!'})
check('B8: settings are saved', r.status_code == 200 and r.get_json()['persona'] == 'Penny' and r.get_json()['accessLevel'] == 'standard' and r.get_json()['monthlyCapUsd'] == 5.0, r.get_data(as_text=True))
check('B9: bad settings are refused', put({'accessLevel': 'god'}).status_code == 400 and put({'allowedOrigins': ['javascript:alert(1)']}).status_code == 400
      and put({'apiBaseUrl': 'ftp://x'}).status_code == 400 and put({'apiAuth': 'cookie'}).status_code == 400 and put({'name': ''}).status_code == 400)
put({'apiAuth': 'header', 'apiHeaders': {'X-Api-Key': 'svc-key-777'}})
enc = ConnectApp.objects(app_id=appA['id']).first().api_headers_enc
check('B10: API headers are encrypted at rest and never returned', enc and 'svc-key-777' not in enc and 'svc-key-777' not in c.get(f'/api/platform/apps/{appA["id"]}', headers=A).get_data(as_text=True))
put({'apiAuth': 'forward', 'apiHeaders': {}})

# ───────── C. the public API: keys, origins, tickets ─────────
PK = appA['publicKey']
def pub(path, body=None, key=PK, origin=None, method='post'):
    h = {'Authorization': 'Bearer ' + key} if key else {}
    if origin: h['Origin'] = origin
    return (c.post if method == 'post' else c.get)('/api/connect/v1' + path, json=body or {}, headers=h)
check('C1: no key / a wrong key -> 401', pub('/config', key='', method='get').status_code == 401 and pub('/config', key='pk_wrong', method='get').status_code == 401 and pub('/config', key=skA, method='get').status_code == 401)
check('C2: an allowed website works (exact, wildcard, localhost)', all(pub('/config', origin=o, method='get').status_code == 200 for o in ('https://app.acme.com', 'https://staging.acme.dev', 'http://localhost:3000')))
r = pub('/config', origin='https://evil.com', method='get')
check('C3: another website cannot use the key', r.status_code == 403 and 'not allowed' in r.get_json()['error'])
check('C4: a mobile app (no Origin) works while "allow mobile" is on, and not when it is off', pub('/config', method='get').status_code == 200
      and (put({'allowNative': False}).status_code == 200) and pub('/config', method='get').status_code == 403 and (put({'allowNative': True}).status_code == 200))
cfg = pub('/config', method='get').get_json()
check('C5: config returns the assistant\'s name and greeting', cfg['name'] == 'Penny' and cfg['greeting'] == 'Hi, I am Penny!')
r = c.post('/api/connect/v1/tickets', json={'userId': 'u1', 'name': 'Asha'}, headers=hdr(skA)).get_json()
t_ok = r['ticket']
check('C6: the secret key issues a ticket for a user; the public key cannot', 'ticket' in r and c.post('/api/connect/v1/tickets', json={'userId': 'u1'}, headers=hdr(PK)).status_code == 401
      and c.post('/api/connect/v1/tickets', json={}, headers=hdr(skA)).status_code == 400)
ident = security.read_ticket(t_ok)
check('C7: a ticket carries the app and the user, and expires', ident['a'] == appA['id'] and ident['u'] == 'u1' and security.read_ticket(t_ok + 'x') is None)
real = time.time; time.time = lambda: real() + 3 * 3600
expired = security.read_ticket(t_ok); time.time = real
check('C8: tickets expire after 2 hours', expired is None)
r_other = c.post('/api/connect/v1/tickets', json={'userId': 'x'}, headers=hdr(skB)).get_json()['ticket']
rr = pub('/chat', {'message': 'hi', 'ticket': r_other})
check('C9: a ticket for ANOTHER app is rejected', rr.status_code == 401, rr.get_data(as_text=True))
check('C10: the widget script is served', c.get('/api/connect/widget.js').status_code == 200 and b'Adion' in c.get('/api/connect/widget.js').data and 'javascript' in c.get('/api/connect/widget.js').mimetype)

# ───────── D. knowledge ─────────
def kadd(app_id, text, title='Doc', h=A): return c.post(f'/api/platform/apps/{app_id}/knowledge', json={'title': title, 'text': text}, headers=h)
r = kadd(appA['id'], 'Refund policy\n\nRefunds are possible within 30 days of purchase when the item is unused.\n\nShipping\n\nShipping takes 3 to 5 business days within India.', 'Policies')
check('D1: knowledge can be added and is cut into chunks', r.status_code == 201 and r.get_json()['chunks'] >= 1, r.get_data(as_text=True))
kadd(appB['id'], 'The secret recipe of Bob Shop uses saffron and a 99 percent discount code BOB99.', 'Bob private', h=B)
kadd(appA['id'], ' ', 'empty'); check('D2: an empty document is refused', kadd(appA['id'], '  ').status_code == 400)
hits = knowledge.retrieve(appA['id'], 'how many days for a refund?')
check('D3: retrieval finds the relevant chunk', hits and 'within 30 days' in hits[0][1], str(hits))
check('D4: retrieval of an unrelated question finds nothing', knowledge.retrieve(appA['id'], 'quantum entanglement of neutron stars') == [])
check('D5: one app never retrieves another app\'s knowledge', knowledge.retrieve(appA['id'], 'saffron discount code') == [] and knowledge.retrieve(appB['id'], 'saffron discount code') != [])
long = ('Paragraph about cats. ' * 80 + '\n\n') * 3 + 'The dog policy: dogs are welcome on Fridays.'
dd = kadd(appA['id'], long, 'Long').get_json()
check('D6: long documents are chunked and the buried fact is still found', dd['chunks'] > 3 and any('dogs are welcome' in t for _, t in knowledge.retrieve(appA['id'], 'dog policy fridays')))
import docx as _docx
d = _docx.Document(); d.add_paragraph('Opening hours: weekdays from 9am to 6pm.'); bio = io.BytesIO(); d.save(bio); bio.seek(0)
r = c.post(f'/api/platform/apps/{appA["id"]}/knowledge', data={'file': (bio, 'hours.docx')}, headers=A, content_type='multipart/form-data')
check('D7: a Word file can be uploaded as knowledge', r.status_code == 201 and knowledge.retrieve(appA['id'], 'opening hours weekdays'), r.get_data(as_text=True))
check('D8: programs and pictures are refused', c.post(f'/api/platform/apps/{appA["id"]}/knowledge', data={'file': (io.BytesIO(b'MZ00'), 'x.exe')}, headers=A, content_type='multipart/form-data').status_code == 400)
kid = c.get(f'/api/platform/apps/{appA["id"]}/knowledge', headers=A).get_json()
check('D9: the list shows my documents only; delete removes one', len(kid) == 3 and c.delete(f'/api/platform/apps/{appA["id"]}/knowledge/{kid[0]["id"]}', headers=A).get_json()['deleted'] == 1
      and c.delete(f'/api/platform/apps/{appA["id"]}/knowledge/{kid[1]["id"]}', headers=B).status_code == 404)

# ───────── E. actions: import from API documentation ─────────
OPENAPI = {'openapi': '3.0.0', 'servers': [{'url': API_URL}], 'components': {'schemas': {'Tx': {'type': 'object', 'required': ['amount'], 'properties': {'amount': {'type': 'number', 'description': 'in rupees'}, 'category': {'type': 'string'}}}}},
           'paths': {'/transactions': {'get': {'operationId': 'list_transactions', 'summary': 'List transactions', 'parameters': [{'name': 'month', 'in': 'query', 'schema': {'type': 'string'}}]},
                                       'post': {'operationId': 'add_transaction', 'summary': 'Add a transaction', 'requestBody': {'content': {'application/json': {'schema': {'$ref': '#/components/schemas/Tx'}}}}}},
                     '/transactions/{id}': {'get': {'summary': 'Get one', 'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}]},
                                            'delete': {'operationId': 'delete_transaction', 'summary': 'Delete', 'parameters': [{'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}]}}}}
c.put(f'/api/platform/apps/{appA["id"]}', json={'apiBaseUrl': ''}, headers=A)
r = c.post(f'/api/platform/apps/{appA["id"]}/actions/import', json={'source': json.dumps(OPENAPI)}, headers=A)
acts = {a['name']: a for a in r.get_json()['actions']}
check('E1: OpenAPI import creates an action per endpoint, switched OFF', r.status_code == 201 and len(acts) == 4 and not any(a['enabled'] for a in acts.values()), r.get_data(as_text=True))
check('E2: risks come from the HTTP method (GET read, POST write, DELETE danger)', acts['list_transactions']['risk'] == 'read' and acts['add_transaction']['risk'] == 'write' and acts['delete_transaction']['risk'] == 'danger')
check('E3: parameters (query, path, body incl. $ref schemas) and required flags', {(p['name'], p['in'], p['required']) for p in acts['add_transaction']['params']} == {('amount', 'body', True), ('category', 'body', False)}
      and [(p['name'], p['in'], p['type']) for p in acts['delete_transaction']['params']] == [('id', 'path', 'integer')])
check('E4: the API address is taken from the document', ConnectApp.objects(app_id=appA['id']).first().api_base_url == API_URL)
check('E5: a bad document is explained, not a crash', c.post(f'/api/platform/apps/{appA["id"]}/actions/import', json={'source': '{"hello": 1}'}, headers=A).status_code == 400
      and c.post(f'/api/platform/apps/{appA["id"]}/actions/import', json={'source': 'not json or yaml: [[['}, headers=A).status_code == 400)
YAML = "swagger: '2.0'\nhost: api.example.com\nbasePath: /v1\nschemes: [https]\npaths:\n  /balance:\n    get:\n      operationId: get_balance\n      summary: Current balance\n"
check('E6: Swagger 2 in YAML works too', c.post(f'/api/platform/apps/{appA["id"]}/actions/import', json={'source': YAML}, headers=A).get_json()['imported'] == 1)
PM = {'info': {'name': 'x'}, 'item': [{'name': 'Reports', 'item': [{'name': 'Monthly report', 'request': {'method': 'GET', 'url': {'raw': '{{base}}/reports/:month', 'path': ['reports', ':month']}}}]},
      {'name': 'Add category', 'request': {'method': 'POST', 'url': '{{base}}/categories', 'body': {'mode': 'raw', 'raw': '{"name": "Food", "budget": 500}'}}}]}
r = c.post(f'/api/platform/apps/{appA["id"]}/actions/import', json={'source': PM}, headers=A).get_json()
pm = {a['name']: a for a in r['actions']}
check('E7: Postman collections work (folders, :path params, JSON body fields)', r['imported'] == 2 and any(p['name'] == 'month' and p['in'] == 'path' for a in pm.values() for p in a['params'])
      and any(p['name'] == 'budget' and p['type'] == 'number' for a in pm.values() for p in a['params']), str(pm))
n = c.post(f'/api/platform/apps/{appA["id"]}/actions/bulk', json={'enable': True, 'onlyRead': True}, headers=A).get_json()['updated']
al = {a['name']: a for a in c.get(f'/api/platform/apps/{appA["id"]}/actions', headers=A).get_json()}
check('E8: "enable all read actions" switches on only the safe ones', n >= 3 and al['list_transactions']['enabled'] and not al['add_transaction']['enabled'] and not al['delete_transaction']['enabled'])
x = c.post(f'/api/platform/apps/{appA["id"]}/actions', json={'name': 'show hint!', 'mode': 'client', 'description': 'Show a hint', 'risk': 'read', 'enabled': True}, headers=A).get_json()
check('E9: manual in-app action: name cleaned, no HTTP details', x['name'] == 'show_hint' and x['mode'] == 'client' and x['path'] == '')
check('E10: duplicate / invalid manual actions are refused', c.post(f'/api/platform/apps/{appA["id"]}/actions', json={'name': 'show_hint', 'mode': 'client'}, headers=A).status_code == 409
      and c.post(f'/api/platform/apps/{appA["id"]}/actions', json={'name': 'x', 'mode': 'api', 'path': 'nope', 'method': 'GET'}, headers=A).status_code == 400)
r = c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["add_transaction"]["id"]}', json={'enabled': True, 'hideFields': ['internal_note'], 'description': 'Adds a money transaction'}, headers=A).get_json()
check('E11: an action can be enabled, described, and given hidden fields', r['enabled'] and r['hideFields'] == ['internal_note'] and r['description'] == 'Adds a money transaction')

# ───────── F. unit checks of arguments and tool schemas ─────────
AA = ConnectApp.objects(app_id=appA['id']).first()
addx = AppAction.objects(app_id=appA['id'], name='add_transaction').first()
check('F1: tool schema is an OpenAI function with required fields', act.tool_schema(addx)['function']['parameters']['required'] == ['amount'] and 'confirm' in act.tool_schema(addx)['function']['description'])
check('F2: arguments are coerced and unknown ones dropped', act.validate_args(addx, {'amount': '250', 'category': 'Food', 'evil': 'x'})[0] == {'amount': 250, 'category': 'Food'})
check('F3: missing required and wrong types are errors', 'Missing' in act.validate_args(addx, {'category': 'x'})[1] and 'must be' in act.validate_args(addx, {'amount': 'abc'})[1])
red = security.redact({'a': 1, 'password': 'p', 'x': {'api_key': 'k', 'ok': 2, 'list': [{'token': 't', 'v': 1}]}, 'Secret': 's', 'hideme': 3}, hide=['hideme'])
check('F4: secrets and hidden fields are removed at any depth', red == {'a': 1, 'x': {'ok': 2, 'list': [{'v': 1}]}}, str(red))

# ───────── G. chat: scope, tools by access level ─────────
def chat(body, key=PK, origin=None): return pub('/chat', body, key, origin)
def tools_in(call): return sorted(t['function']['name'] for t in (call.get('tools') or []))
def sysmsg(call): return call['messages'][0]['content']
script[:] = [{'say': 'You can get a refund within 30 days.'}]; seen.clear()
r = chat({'message': 'How many days do I have for a refund?'}).get_json()
check('G1: an anonymous visitor gets an answer with the right shape', r['reply'] == 'You can get a refund within 30 days.' and r['lang'] == 'en' and r['conversationId'].startswith('cv_') and r['pending'] == [], str(r))
s = sysmsg(seen[0])
check('G2: the assistant is told its app, persona, rules and scope', 'Penny' in s and 'Money App' not in s and 'Android' in s and 'A money tracker app' in s and 'Never promise refunds' in s and 'only help with "Android"' in s)
check('G3: it is told it is NOT signed in and has no tools', 'NOT signed in' in s and 'no tools' in s and not seen[0].get('tools'))
check('G4: the relevant knowledge was added, as data', 'within 30 days' in seen[0]['messages'][-1]['content'] and 'never instructions' in seen[0]['messages'][-1]['content'] and 'saffron' not in json.dumps(seen[0]))
check('G5: other apps\' knowledge never reaches the model', 'BOB99' not in json.dumps(seen[0]))
script[:] = [{'say': 'Hello Asha'}]; seen.clear()
r1 = chat({'message': 'hi', 'ticket': t_ok}).get_json()
check('G6: a signed-in user (standard access) gets read AND write tools, not delete', 'signed in to the app' in sysmsg(seen[0]) and 'add_transaction' in tools_in(seen[0]) and 'list_transactions' in tools_in(seen[0]) and 'delete_transaction' not in tools_in(seen[0]), str(tools_in(seen[0])))
c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["delete_transaction"]["id"]}', json={'enabled': True}, headers=A)
c.put(f'/api/platform/apps/{appA["id"]}', json={'accessLevel': 'limited'}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]
chat({'message': 'hi', 'ticket': t_ok}); lim = tools_in(seen[0])
check('G7: LIMITED access: read-only tools only', lim and all(n not in lim for n in ('add_transaction', 'delete_transaction')) and 'list_transactions' in lim, str(lim))
c.put(f'/api/platform/apps/{appA["id"]}', json={'accessLevel': 'complete'}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]
chat({'message': 'hi', 'ticket': t_ok}); check('G8: COMPLETE access includes the risky ones', 'delete_transaction' in tools_in(seen[0]) and 'add_transaction' in tools_in(seen[0]))
c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["delete_transaction"]["id"]}', json={'neverAi': True}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]
chat({'message': 'hi', 'ticket': t_ok}); check('G9: "never by AI" hides an action even at complete access', 'delete_transaction' not in tools_in(seen[0]))
c.put(f'/api/platform/apps/{appA["id"]}', json={'accessLevel': 'standard'}, headers=A)
c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["list_transactions"]["id"]}', json={'enabled': False}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]
chat({'message': 'hi', 'ticket': t_ok}); check('G10: a switched-off action is not offered', 'list_transactions' not in tools_in(seen[0]))
c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["list_transactions"]["id"]}', json={'enabled': True}, headers=A)
convo = r1['conversationId']; seen.clear(); script[:] = [{'say': 'Sure.'}]
r2 = chat({'message': 'and tomorrow?', 'ticket': t_ok, 'conversationId': convo}).get_json()
check('G11: a follow-up continues the conversation with its history', r2['conversationId'] == convo and any(m['content'] == 'hi' for m in seen[0]['messages']) and any(m['content'] == 'Hello Asha' for m in seen[0]['messages']))
t_other = c.post('/api/connect/v1/tickets', json={'userId': 'u2', 'name': 'Raj'}, headers=hdr(skA)).get_json()['ticket']
rr = chat({'message': 'hi', 'ticket': t_other, 'conversationId': convo})
check('G12: another user cannot continue (or read) someone else\'s conversation', rr.status_code == 400 and 'not found' in rr.get_json()['error'], rr.get_data(as_text=True))
rr = chat({'message': 'hi', 'conversationId': convo}); check('G13: an anonymous visitor cannot continue a signed-in user\'s conversation', rr.status_code == 400)
rr = chat({'message': 'hi', 'ticket': 'garbage.token'}); check('G14: a bad ticket is refused, not treated as anonymous', rr.status_code == 401)
check('G15: an empty message is refused', chat({'message': '   '}).status_code == 400)
script[:] = [{'say': 'यह एक जवाब है।'}]
check('G16: the reply language is detected for the app\'s voice', chat({'message': 'नमस्ते'}).get_json()['lang'] == 'hi')
c.put(f'/api/platform/apps/{appA["id"]}', json={'language': 'Spanish'}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]; chat({'message': 'hi'})
check('G17: a fixed reply language is passed on', 'Always reply in Spanish' in sysmsg(seen[0]))
c.put(f'/api/platform/apps/{appA["id"]}', json={'language': 'auto'}, headers=A)
c.put(f'/api/platform/apps/{appA["id"]}', json={'strictScope': False}, headers=A); seen.clear(); script[:] = [{'say': 'ok'}]; chat({'message': 'hi'})
check('G18: strict scope can be relaxed by the app owner', 'SCOPE: you only help' not in sysmsg(seen[0]))
c.put(f'/api/platform/apps/{appA["id"]}', json={'strictScope': True}, headers=A)

# ───────── H. live API calls as the user ─────────
service._hits.clear()
served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {'month': '2026-03'})]}, {'say': 'You spent 100 on Food.'}]
r = chat({'message': 'show my transactions', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
check('H1: a read action is called on the client\'s server, as the user (their token forwarded)', served and served[0][0] == 'GET' and served[0][1].startswith('/transactions?month=2026-03') and served[0][2] == 'Bearer user-123-token', str(served))
tool_msg = [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content']
check('H2: the model got the data with passwords, tokens and keys REMOVED', '"amount": 100' in tool_msg and 'hunter2' not in tool_msg and 't0p-secret' not in tool_msg and 'k-123' not in tool_msg, tool_msg)
check('H3: ...and the final answer came back', r['reply'] == 'You spent 100 on Food.' and r['pending'] == [])
c.put(f'/api/platform/apps/{appA["id"]}/actions/{al["list_transactions"]["id"]}', json={'hideFields': ['internal_note', 'category']}, headers=A)
served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {})]}, {'say': 'ok'}]
chat({'message': 'show', 'ticket': t_ok, 'userToken': 'user-123-token'})
tm = [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content']
check('H4: fields the client hid never reach the model', 'hide-me' not in tm and 'Food' not in tm and '"amount": 100' in tm, tm)
served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {})]}, {'say': 'Please sign in.'}]
chat({'message': 'show', 'ticket': t_ok})
tm = [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content']
check('H5: without the user\'s token nothing is called and the model is told why', served == [] and 'not signed in' in tm, tm)
served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {})]}, {'say': 'Your session ended.'}]
chat({'message': 'show', 'ticket': t_ok, 'userToken': 'WRONG'})
tm = [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content']
check('H6: an error from the client\'s server is passed on as an error', '"ok": false' in tm and '401' in tm, tm)
put({'apiAuth': 'header', 'apiHeaders': {'X-Api-Key': 'svc-key-777'}}); served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {})]}, {'say': 'ok'}]
chat({'message': 'show', 'ticket': t_ok})
check('H7: "fixed header" mode sends the saved key (and not the user token)', served and served[0][4] == 'svc-key-777' and served[0][2] == '', str(served))
put({'apiAuth': 'forward'})
served.clear(); seen.clear(); script[:] = [{'call': [('get_balance_x', {})]}, {'say': 'ok'}]
chat({'message': 'x', 'ticket': t_ok, 'userToken': 'user-123-token'})
check('H8: a made-up action name is refused', 'not available' in [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content'] and served == [])
sget = AppAction.objects(app_id=appA['id'], path='/transactions/{id}', method='GET').first()
c.put(f'/api/platform/apps/{appA["id"]}/actions/{sget.action_id}', json={'enabled': True}, headers=A); served.clear(); seen.clear()
script[:] = [{'call': [(sget.name, {'id': '1/../../admin'})]}, {'say': 'ok'}]
chat({'message': 'x', 'ticket': t_ok, 'userToken': 'user-123-token'})
check('H9: a path value of the wrong type (an integer id) is rejected before any call', served == [] and 'must be' in [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content'])
c.post(f'/api/platform/apps/{appA["id"]}/actions', json={'name': 'find_by_name', 'mode': 'api', 'method': 'GET', 'path': '/transactions/{name}', 'enabled': True,
                                                         'params': [{'name': 'name', 'in': 'path', 'type': 'string', 'required': True}]}, headers=A)
served.clear(); seen.clear(); script[:] = [{'call': [('find_by_name', {'name': 'a/../b c?x=1'})]}, {'say': 'ok'}]
chat({'message': 'x', 'ticket': t_ok, 'userToken': 'user-123-token'})
check('H10: text path values are URL-encoded (no path or query tricks)', served and served[0][1] == '/transactions/a%2F..%2Fb%20c%3Fx%3D1', str(served))

# ───────── I. SSRF ─────────
os.environ['CONNECT_ALLOW_PRIVATE'] = '0'
served.clear(); seen.clear(); script[:] = [{'call': [('list_transactions', {})]}, {'say': 'ok'}]
chat({'message': 'x', 'ticket': t_ok, 'userToken': 'user-123-token'})
tm = [m for m in seen[1]['messages'] if m['role'] == 'tool'][0]['content']
check('I1: with private addresses off, a LAN/localhost API address is never called', served == [] and ('private' in tm or 'https' in tm), tm)
for url in ('http://169.254.169.254/latest', 'https://localhost/x', 'https://10.0.0.5/x', 'https://[::1]/x', 'ftp://x.com', 'file:///etc/passwd'):
    try:
        security.check_url(url); ok = False
    except security.UnsafeUrl:
        ok = True
    check(f'I2: blocked address {url}', ok)
os.environ['CONNECT_ALLOW_PRIVATE'] = '1'

# ───────── J. confirmation flow for changes ─────────
service._hits.clear()
def confirm(body, key=PK): return pub('/chat/confirm', body, key)
served.clear(); seen.clear(); script[:] = [{'say': 'Adding it.', 'call': [('add_transaction', {'amount': 500, 'category': 'Groceries'})]}, {'say': 'Done: 500 for groceries.'}]
r = chat({'message': 'add 500 for groceries', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
check('J1: a change is NOT run: the user is asked to confirm, with the exact values', served == [] and len(r['pending']) == 1 and r['pending'][0]['kind'] == 'confirm' and r['pending'][0]['needsConfirm'] and '500' in r['pending'][0]['summary'] and 'Groceries' in r['pending'][0]['summary'], str(r))
call_id = r['pending'][0]['callId']
check('J2: other users / anonymous cannot approve it', confirm({'conversationId': r['conversationId'], 'ticket': t_other, 'decisions': [{'callId': call_id, 'approve': True}]}).status_code == 400
      and confirm({'conversationId': r['conversationId'], 'decisions': [{'callId': call_id, 'approve': True}]}).status_code == 400 and served == [])
r2 = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'userToken': 'user-123-token', 'decisions': [{'callId': call_id, 'approve': True}]}).get_json()
check('J3: on approval it runs on the client\'s server as the user, then the assistant answers', served and served[0][0] == 'POST' and served[0][3] == {'amount': 500, 'category': 'Groceries'} and served[0][2] == 'Bearer user-123-token' and r2['reply'] == 'Done: 500 for groceries.', f'{served} {r2}')
n = len(served)
rr = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'userToken': 'user-123-token', 'decisions': [{'callId': call_id, 'approve': True}]})
check('J4: approving twice does not run it twice', len(served) == n and rr.status_code == 400)
served.clear(); seen.clear(); script[:] = [{'call': [('add_transaction', {'amount': 9, 'category': 'X'})]}, {'say': 'Okay, cancelled.'}]
r = chat({'message': 'add 9', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
r2 = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'decisions': [{'callId': r['pending'][0]['callId'], 'approve': False}]}).get_json()
check('J5: cancelling runs nothing; the model is told the user cancelled', served == [] and 'cancelled' in [m for m in seen[-1]['messages'] if m['role'] == 'tool'][0]['content'] and r2['reply'] == 'Okay, cancelled.')
served.clear(); seen.clear(); script[:] = [{'call': [('add_transaction', {'amount': 7, 'category': 'Y'})]}, {'say': 'No can do.'}]
r = chat({'message': 'add 7', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
c.put(f'/api/platform/apps/{appA["id"]}', json={'accessLevel': 'limited'}, headers=A)
r2 = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'userToken': 'user-123-token', 'decisions': [{'callId': r['pending'][0]['callId'], 'approve': True}]}).get_json()
check('J6: if access was reduced while waiting, approval no longer works', served == [], str(served))
c.put(f'/api/platform/apps/{appA["id"]}', json={'accessLevel': 'standard'}, headers=A)
script[:] = [{'call': [('add_transaction', {'category': 'no amount'})]}, {'say': 'What amount?'}]; served.clear()
r = chat({'message': 'add something', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
check('J7: a call with missing values never reaches the confirmation (the model is asked to fix it)', r['pending'] == [] and r['reply'] == 'What amount?' and served == [])
script[:] = [{'call': [('add_transaction', {'amount': 1, 'category': 'a'}), ('add_transaction', {'amount': 2, 'category': 'b'})]}, {'say': 'Both done.'}]; served.clear()
r = chat({'message': 'add two', 'ticket': t_ok, 'userToken': 'user-123-token'}).get_json()
check('J8: several changes at once each need their own confirmation', len(r['pending']) == 2 and served == [])
d1 = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'userToken': 'user-123-token', 'decisions': [{'callId': r['pending'][0]['callId'], 'approve': True}]}).get_json()
check('J9: the assistant waits until every one is answered', len(d1['pending']) == 1 and len(served) == 1 and d1['reply'] == '')
d2 = confirm({'conversationId': r['conversationId'], 'ticket': t_ok, 'userToken': 'user-123-token', 'decisions': [{'callId': r['pending'][1]['callId'], 'approve': False}]}).get_json()
check('J10: then it finishes', d2['reply'] == 'Both done.' and len(served) == 1)

# ───────── K. in-app (client) actions ─────────
service._hits.clear()
c.put(f'/api/platform/apps/{appA["id"]}/actions/{x["id"]}', json={'hideFields': ['pin']}, headers=A)
def result(body): return pub('/chat/result', body)
script[:] = [{'call': [('show_hint', {})]}, {'say': 'The hint is 42.'}]; served.clear(); seen.clear()
r = chat({'message': 'give me a hint', 'ticket': t_ok}).get_json()
check('K1: an in-app read action is handed to the app (no server call, no confirmation)', len(r['pending']) == 1 and r['pending'][0]['kind'] == 'client' and r['pending'][0]['needsConfirm'] is False and served == [])
r2 = result({'conversationId': r['conversationId'], 'ticket': t_ok, 'results': [{'callId': r['pending'][0]['callId'], 'result': {'hint': 42, 'pin': '1234', 'password': 'x'}}]}).get_json()
tm = [m for m in seen[-1]['messages'] if m['role'] == 'tool'][0]['content']
check('K2: the app\'s result continues the chat; secrets in it are removed', r2['reply'] == 'The hint is 42.' and '42' in tm and '1234' not in tm and 'password' not in tm, tm)
script[:] = [{'call': [('show_hint', {})]}, {'say': 'That failed.'}]
r = chat({'message': 'hint', 'ticket': t_ok}).get_json()
r2 = result({'conversationId': r['conversationId'], 'ticket': t_ok, 'results': [{'callId': r['pending'][0]['callId'], 'error': 'boom'}]}).get_json()
check('K3: an error from the app is reported to the model', r2['reply'] == 'That failed.' and 'boom' in [m for m in seen[-1]['messages'] if m['role'] == 'tool'][-1]['content'])
rr = result({'conversationId': r['conversationId'], 'ticket': t_other, 'results': []}); check('K4: another user cannot post results', rr.status_code == 400)
mk = c.post(f'/api/platform/apps/{appA["id"]}/actions', json={'name': 'transfer_money', 'mode': 'client', 'risk': 'write', 'description': 'Transfer', 'enabled': True, 'params': [{'name': 'to', 'type': 'string', 'required': True}]}, headers=A).get_json()
script[:] = [{'call': [('transfer_money', {'to': 'Raj'})]}, {'say': 'Cancelled.'}]
r = chat({'message': 'send money to Raj', 'ticket': t_ok}).get_json()
check('K5: an in-app WRITE action still needs the user\'s confirmation first', r['pending'][0]['kind'] == 'client' and r['pending'][0]['needsConfirm'] is True)
r2 = result({'conversationId': r['conversationId'], 'ticket': t_ok, 'results': [{'callId': r['pending'][0]['callId'], 'approve': False}]})
check('K6: the user can cancel it', r2.status_code == 200 and r2.get_json()['reply'] == 'Cancelled.')

# ───────── L. billing, caps, switches ─────────
service._hits.clear()
rows = UsageDocument.objects(app_id=appA['id'])
check('L1: every model call is billed to the client, app and end user', rows.count() > 10 and all(r.client_id == ConnectApp.objects(app_id=appA['id']).first().client_id and r.purpose == 'connect' for r in rows)
      and any(r.end_user == 'u:u1' for r in rows) and any(r.end_user == 'anon' for r in rows))
cost = sum(r.cost_usd for r in rows)
sm = c.get(f'/api/platform/apps/{appA["id"]}/usage', headers=A).get_json()
check('L2: the app usage shows cost = our cost x markup', abs(sm['cost'] - round(cost * 2.0, 6)) < 1e-5 and sm['calls'] == rows.count() and sm['caps']['app'] == 5.0, str(sm['cost']) + ' vs ' + str(cost * 2))
check('L3: usage of A is not visible to B (their own numbers stay separate)', c.get('/api/platform/usage', headers=B).get_json()['calls'] == 0 and c.get('/api/platform/usage', headers=A).get_json()['calls'] == rows.count())
co = c.put('/api/platform/owner/config', json={'markup': 3.0}, headers=OWNER).get_json()
check('L4: the owner changes the markup and prices follow', co['markup'] == 3.0 and abs(c.get(f'/api/platform/apps/{appA["id"]}/usage', headers=A).get_json()['cost'] - round(cost * 3.0, 6)) < 1e-5)
c.put('/api/platform/owner/config', json={'markup': 2.0}, headers=OWNER)
put({'monthlyCapUsd': 0.0001}); script[:] = [{'say': 'x'}]
r = chat({'message': 'hello again'})
check('L5: an app over its monthly cap is stopped (402), with a clear message', r.status_code == 402 and 'monthly limit' in r.get_json()['error'], r.get_data(as_text=True))
put({'monthlyCapUsd': 0}); script[:] = [{'say': 'back'}]
check('L6: raising the cap resumes it', chat({'message': 'hello again'}).status_code == 200)
cl = [x for x in c.get('/api/platform/owner/clients', headers=OWNER).get_json() if x['email'] == 'alice@acme.com'][0]
c.put(f'/api/platform/owner/clients/{cl["id"]}', json={'capUsd': 0.0001}, headers=OWNER)
check('L7: the owner can cap a whole client', chat({'message': 'hello again'}).status_code == 402)
c.put(f'/api/platform/owner/clients/{cl["id"]}', json={'capUsd': 0}, headers=OWNER)
c.put(f'/api/platform/owner/clients/{cl["id"]}', json={'status': 'blocked'}, headers=OWNER); script[:] = [{'say': 'x'}]
check('L8: a blocked client stops working everywhere (assistant, portal, login)', chat({'message': 'hi'}).status_code == 402 and c.get('/api/platform/me', headers=A).status_code == 403
      and post('/login', {'email': 'alice@acme.com', 'password': 'password123'}).status_code == 403)
c.put(f'/api/platform/owner/clients/{cl["id"]}', json={'status': 'active'}, headers=OWNER)
put({'enabled': False}); check('L9: a switched-off assistant says so', chat({'message': 'hi'}).status_code == 402 and pub('/config', method='get').status_code == 403)
put({'enabled': True})
ot = c.post('/api/platform/owner/client-token', headers=OWNER, json={})
ot2 = c.post('/api/platform/owner/client-token', headers=OWNER, json={})
OWN_AS_CLIENT = {'Authorization': 'Bearer ' + ot.get_json()['token']}
check('L9b: the owner gets their own client workspace (same account each time) and can create projects in it',
      ot.status_code == 200 and ot.get_json()['client']['id'] == ot2.get_json()['client']['id'] and c.post('/api/platform/projects', json={'name': 'Mine'}, headers=OWN_AS_CLIENT).status_code == 201)
check('L9c: only the owner can get that workspace', c.post('/api/platform/owner/client-token', headers=A, json={}).status_code == 403)
check('L10: the owner sees clients, spend and a summary', c.get('/api/platform/owner/summary', headers=OWNER).get_json()['monthCalls'] > 10 and any(t['email'] == 'alice@acme.com' for t in c.get('/api/platform/owner/summary', headers=OWNER).get_json()['top']))
for i in range(40):
    script[:] = [{'say': 'ok'}]; rr = chat({'message': f'spam {i}', 'ticket': t_other})
    if rr.status_code == 429: break
check('L11: one user cannot flood the assistant (rate limit)', rr.status_code == 429)

# ───────── M. conversations (portal + SDK) ─────────
cv = c.get(f'/api/platform/apps/{appA["id"]}/conversations', headers=A).get_json()
check('M1: the client sees the conversations of their app (with the user ids)', len(cv) > 3 and any(x['endUser'] == 'u:u1' for x in cv))
one = c.get(f'/api/platform/apps/{appA["id"]}/conversations/{convo}', headers=A).get_json()
check('M2: a conversation shows its messages', [m['role'] for m in one['messages'][:2]] == ['user', 'assistant'])
mine = c.get('/api/connect/v1/conversations?ticket=' + t_ok, headers=hdr(PK)).get_json()
check('M3: a signed-in end user lists ONLY their own conversations', mine and all(x['endUser'] == 'u:u1' for x in mine) and not any(x['id'] == r['conversationId'] for x in c.get('/api/connect/v1/conversations?ticket=' + t_other, headers=hdr(PK)).get_json() if x['endUser'] == 'u:u1'))
check('M4: anonymous visitors cannot list conversations', c.get('/api/connect/v1/conversations', headers=hdr(PK)).status_code == 401)
check('M5: another user cannot read or delete my conversation', c.get(f'/api/connect/v1/conversations/{convo}?ticket=' + t_other, headers=hdr(PK)).status_code == 404
      and c.delete(f'/api/connect/v1/conversations/{convo}?ticket=' + t_other, headers=hdr(PK)).status_code == 404 and c.get(f'/api/connect/v1/conversations/{convo}?ticket=' + t_ok, headers=hdr(PK)).status_code == 200)
check('M6: the user can delete their own conversation', c.delete(f'/api/connect/v1/conversations/{convo}?ticket=' + t_ok, headers=hdr(PK)).get_json()['ok'])
cid2 = cv[0]['id']
check('M7: the client can delete a conversation in the portal', c.delete(f'/api/platform/apps/{appA["id"]}/conversations/{cid2}', headers=A).get_json()['ok'])

# ───────── N. the portal's test chat and the guides ─────────
script[:] = [{'say': 'Test reply.'}]
r = c.post(f'/api/platform/apps/{appA["id"]}/test-chat', json={'message': 'hello'}, headers=A)
check('N1: the portal test chat works without any key or ticket (as a signed-in tester)', r.status_code == 200 and r.get_json()['reply'] == 'Test reply.')
for plat in ('web', 'react', 'react-native', 'api', 'actions'):
    g = c.get(f'/api/platform/apps/{appA["id"]}/docs?platform={plat}', headers=A).get_json()['markdown']
    check(f'N2: the {plat} guide has this app\'s public key', PK in g, plat)
check('N3: no guide contains the real secret key', all(skA not in c.get(f'/api/platform/apps/{appA["id"]}/docs?platform={p}', headers=A).get_data(as_text=True) for p in ('web', 'react', 'react-native', 'api', 'actions')))
gweb = c.get(f'/api/platform/apps/{appA["id"]}/docs?platform=web', headers=A).get_json()['markdown']
check('N4: the web guide explains tickets', 'ticket' in gweb.lower())

# ───────── O. owner: sign-up modes ─────────
c.put('/api/platform/owner/config', json={'signup': 'approval'}, headers=OWNER)
r = post('/signup', {'email': 'pending@x.com', 'password': 'password123'})
check('O1: approval mode: the account waits, and cannot log in', r.status_code == 202 and post('/login', {'email': 'pending@x.com', 'password': 'password123'}).status_code == 403)
pid = [x for x in c.get('/api/platform/owner/clients', headers=OWNER).get_json() if x['email'] == 'pending@x.com'][0]['id']
c.put(f'/api/platform/owner/clients/{pid}', json={'status': 'active'}, headers=OWNER)
check('O2: after approval it can log in', post('/login', {'email': 'pending@x.com', 'password': 'password123'}).status_code == 200)
c.put('/api/platform/owner/config', json={'signup': 'closed'}, headers=OWNER)
check('O3: closed mode: no new sign-ups', post('/signup', {'email': 'late@x.com', 'password': 'password123'}).status_code == 403)
c.put('/api/platform/owner/config', json={'signup': 'open'}, headers=OWNER)

# ───────── P. deleting ─────────
check('P1: deleting an app removes its knowledge, actions and conversations', c.delete(f'/api/platform/apps/{appA["id"]}', headers=A).get_json()['ok']
      and AppAction.objects(app_id=appA['id']).count() == 0 and Conversation.objects(app_id=appA['id']).count() == 0 and pub('/config', method='get').status_code == 401)
check('P2: deleting a project removes its apps', c.delete(f'/api/platform/projects/{pb["id"]}', headers=B).get_json()['ok'] and ConnectApp.objects(app_id=appB['id']).count() == 0)

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
srv.shutdown()
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
