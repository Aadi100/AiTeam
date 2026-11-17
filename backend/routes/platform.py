"""
Adion Connect portal API.

Clients (people who sign up) manage their own projects and apps here. The owner (your admin login) manages clients, pricing and caps.
Every query below is filtered by the signed-in client's id, so one client can never see another client's apps, knowledge or chats.

  POST /api/platform/signup | /login        GET /api/platform/me
  /api/platform/projects ...                /api/platform/apps/<id>/{knowledge,actions,conversations,usage,docs,test-chat}
  /api/platform/owner/...                   (owner only: the normal Adion admin token)
"""

import os
import re
import time
import uuid
import tempfile
from collections import defaultdict, deque
from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

import auth
from models import UserDocument, UsageDocument
from orchestrator import files as ofiles
from connect import security, knowledge, actions as act, billing, docs, service, runtime
from connect.models import Client, Project, ConnectApp, KnowledgeDoc, AppAction, Conversation, ConnectConfig

platform_bp = Blueprint('platform', __name__)
MAX_PROJECTS, MAX_APPS = 10, 20
EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_attempts = defaultdict(deque)


def _err(msg, code=400):
    return jsonify({'error': msg}), code


def _limited(key, n, per=300):
    now = time.time()
    q = _attempts[key]
    while q and now - q[0] > per:
        q.popleft()
    if len(q) >= n:
        return True
    q.append(now)
    return False


@platform_bp.before_request
def _gate():
    if request.method == 'OPTIONS' or request.path in ('/api/platform/signup', '/api/platform/login'):
        return None
    tok = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    if request.path.startswith('/api/platform/owner/'):
        u = auth.read_token(tok)
        row = UserDocument.objects(username=u['u']).first() if u and not u.get('p') else None
        if not row or row.role != 'admin':
            return _err('owner only', 403)
        g.owner = row.username
        return None
    cid = security.read_client_token(tok)
    client = Client.objects(client_id=cid).first() if cid else None
    if not client:
        return _err('Please sign in.', 401)
    if client.status != 'active':
        return _err('This account is not active.', 403)
    g.client = client
    return None


# ───────────────────────── account ─────────────────────────
@platform_bp.route('/platform/signup', methods=['POST'])
def signup():
    b = request.get_json(silent=True) or {}
    email, pw, name = str(b.get('email', '')).strip().lower(), str(b.get('password', '')), str(b.get('name', '')).strip()[:80]
    cfg = billing.config()
    if cfg.signup == 'closed':
        return _err('Sign-ups are closed right now.', 403)
    if _limited(('signup', request.remote_addr), 8, 3600):
        return _err('Too many sign-ups from this address. Try again later.', 429)
    if not EMAIL.match(email):
        return _err('Enter a valid email address.')
    if len(pw) < 8:
        return _err('The password must be at least 8 characters.')
    if Client.objects(email=email).first():
        return _err('An account with this email already exists.', 409)
    c = Client(client_id='cl_' + uuid.uuid4().hex[:10], email=email, name=name or email.split('@')[0], password_hash=generate_password_hash(pw),
               status='pending' if cfg.signup == 'approval' else 'active').save()
    if c.status == 'pending':
        return jsonify({'pending': True, 'message': 'Your account was created and is waiting for approval.'}), 202
    return jsonify({'token': security.make_client_token(c.client_id), 'client': c.to_dict()}), 201


@platform_bp.route('/platform/login', methods=['POST'])
def login():
    b = request.get_json(silent=True) or {}
    email = str(b.get('email', '')).strip().lower()
    if _limited(('login', request.remote_addr, email), 8):
        return _err('Too many attempts. Wait a few minutes.', 429)
    c = Client.objects(email=email).first()
    if not c or not check_password_hash(c.password_hash, str(b.get('password', ''))):
        return _err('Wrong email or password.', 401)
    if c.status == 'pending':
        return _err('Your account is waiting for approval.', 403)
    if c.status != 'active':
        return _err('This account is not active.', 403)
    c.update(set__last_login=billing.datetime.utcnow())
    return jsonify({'token': security.make_client_token(c.client_id), 'client': c.to_dict()})


@platform_bp.route('/platform/me', methods=['GET'])
def me():
    cfg = billing.config()
    return jsonify({**g.client.to_dict(), 'freeCredit': cfg.free_credit_usd, 'defaultCap': cfg.default_cap_usd})


# ───────────────────────── projects & apps ─────────────────────────
def _own_app(app_id):
    return ConnectApp.objects(app_id=app_id, client_id=g.client.client_id).first()


@platform_bp.route('/platform/projects', methods=['GET'])
def list_projects():
    cid = g.client.client_id
    apps = {}
    for a in ConnectApp.objects(client_id=cid):
        apps.setdefault(a.project_id, []).append(a.to_dict())
    return jsonify([{**p.to_dict(), 'apps': apps.get(p.project_id, [])} for p in Project.objects(client_id=cid).order_by('created_at')])


@platform_bp.route('/platform/projects', methods=['POST'])
def create_project():
    name = str((request.get_json(silent=True) or {}).get('name', '')).strip()[:80]
    if not name:
        return _err('Give the project a name.')
    if Project.objects(client_id=g.client.client_id).count() >= MAX_PROJECTS:
        return _err(f'At most {MAX_PROJECTS} projects.')
    p = Project(project_id='pj_' + uuid.uuid4().hex[:10], client_id=g.client.client_id, name=name).save()
    return jsonify({**p.to_dict(), 'apps': []}), 201


@platform_bp.route('/platform/projects/<pid>', methods=['DELETE'])
def delete_project(pid):
    p = Project.objects(project_id=pid, client_id=g.client.client_id).first()
    if not p:
        return _err('not found', 404)
    for a in ConnectApp.objects(project_id=pid, client_id=g.client.client_id):
        _delete_app(a)
    p.delete()
    return jsonify({'ok': True})


@platform_bp.route('/platform/projects/<pid>/apps', methods=['POST'])
def create_app(pid):
    cid = g.client.client_id
    if not Project.objects(project_id=pid, client_id=cid).first():
        return _err('Project not found.', 404)
    if ConnectApp.objects(client_id=cid).count() >= MAX_APPS:
        return _err(f'At most {MAX_APPS} apps.')
    b = request.get_json(silent=True) or {}
    name = str(b.get('name', '')).strip()[:80]
    if not name:
        return _err('Give the app a name.')
    sk = security.new_secret_key()
    a = ConnectApp(app_id='ap_' + uuid.uuid4().hex[:10], project_id=pid, client_id=cid, name=name,
                   platform=b.get('platform') if b.get('platform') in ('web', 'react-native', 'other') else 'web',
                   public_key=security.new_public_key(), secret_hash=security.hash_secret(sk), secret_prefix=sk[:7]).save()
    return jsonify({'app': a.to_dict(), 'secretKey': sk}), 201


def _delete_app(a):
    KnowledgeDoc.objects(app_id=a.app_id).delete()
    AppAction.objects(app_id=a.app_id).delete()
    Conversation.objects(app_id=a.app_id).delete()
    a.delete()


@platform_bp.route('/platform/apps/<app_id>', methods=['GET', 'PUT', 'DELETE'])
def one_app(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    if request.method == 'GET':
        return jsonify(a.to_dict())
    if request.method == 'DELETE':
        _delete_app(a)
        return jsonify({'ok': True})
    b = request.get_json(silent=True) or {}
    upd = {}
    for key, field, mx in (('name', 'name', 80), ('description', 'description', 4000), ('rules', 'rules', 3000), ('persona', 'persona', 200),
                           ('greeting', 'greeting', 300), ('language', 'language', 40)):
        if key in b:
            upd[field] = str(b[key]).strip()[:mx]
    if 'platform' in b and b['platform'] in ('web', 'react-native', 'other'):
        upd['platform'] = b['platform']
    for key, field in (('strictScope', 'strict_scope'), ('allowNative', 'allow_native'), ('enabled', 'enabled'), ('webSearch', 'web_search')):
        if key in b:
            upd[field] = bool(b[key])
    if 'accessLevel' in b:
        if b['accessLevel'] not in ('limited', 'standard', 'complete'):
            return _err('accessLevel must be limited, standard or complete.')
        upd['access_level'] = b['accessLevel']
    if 'allowedOrigins' in b:
        origins = [str(o).strip().rstrip('/') for o in (b['allowedOrigins'] or []) if str(o).strip()][:20]
        if any(not re.match(r'^(\*|https?://[\w.*:-]+)$', o) for o in origins):
            return _err('Each website must look like https://example.com (a * wildcard is allowed, e.g. https://*.example.com).')
        upd['allowed_origins'] = origins
    if 'apiBaseUrl' in b:
        url = str(b['apiBaseUrl']).strip()
        if url and not re.match(r'^https?://[^\s]+$', url):
            return _err('The API address must start with https://')
        upd['api_base_url'] = url.rstrip('/')
    if 'apiAuth' in b:
        if b['apiAuth'] not in ('forward', 'header', 'none'):
            return _err('apiAuth must be forward, header or none.')
        upd['api_auth'] = b['apiAuth']
    if 'apiHeaders' in b:
        h = b['apiHeaders'] if isinstance(b['apiHeaders'], dict) else {}
        upd['api_headers_enc'] = security.encrypt_json({str(k)[:60]: str(v)[:400] for k, v in list(h.items())[:10]}) if h else ''
    if 'monthlyCapUsd' in b:
        try:
            upd['monthly_cap_usd'] = max(0.0, float(b['monthlyCapUsd']))
        except (TypeError, ValueError):
            return _err('monthlyCapUsd must be a number.')
    if upd.get('name') == '':
        return _err('The name cannot be empty.')
    if upd:
        a.update(**{f'set__{k}': v for k, v in upd.items()})
        a.reload()
    return jsonify(a.to_dict())


@platform_bp.route('/platform/apps/<app_id>/rotate-secret', methods=['POST'])
def rotate(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    sk = security.new_secret_key()
    a.update(set__secret_hash=security.hash_secret(sk), set__secret_prefix=sk[:7])
    return jsonify({'secretKey': sk})


# ───────────────────────── knowledge ─────────────────────────
@platform_bp.route('/platform/apps/<app_id>/knowledge', methods=['GET'])
def list_knowledge(app_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    return jsonify([d.to_dict() for d in KnowledgeDoc.objects(app_id=app_id).order_by('-created_at')])


@platform_bp.route('/platform/apps/<app_id>/knowledge', methods=['POST'])
def add_knowledge(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    try:
        f = request.files.get('file')
        if f is not None:
            data = f.read(ofiles.MAX_BYTES + 1)
            if len(data) > ofiles.MAX_BYTES:
                return _err('That file is too large (10 MB limit).')
            name = ofiles.safe_name(f.filename or 'document')
            kind = ofiles.kind_of(name)
            if kind == 'image':
                return _err('Pictures cannot be used as knowledge yet. Upload text, PDF or Word files.')
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, name)
                open(path, 'wb').write(data)
                text, _, _ = ofiles.extract(path, kind)
            doc = knowledge.add_doc(a, request.form.get('title') or name, text, kind)
        else:
            b = request.get_json(silent=True) or {}
            doc = knowledge.add_doc(a, b.get('title') or 'Notes', b.get('text'), 'text')
    except (ValueError, ofiles.FileError) as e:
        return _err(str(e))
    return jsonify(doc.to_dict()), 201


@platform_bp.route('/platform/apps/<app_id>/knowledge/<doc_id>', methods=['DELETE'])
def delete_knowledge(app_id, doc_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    n = KnowledgeDoc.objects(app_id=app_id, doc_id=doc_id).delete()
    return jsonify({'ok': True, 'deleted': n})


# ───────────────────────── actions ─────────────────────────
def _clean_params(raw):
    out = []
    for p in (raw or [])[:30]:
        if isinstance(p, dict) and re.match(r'^[A-Za-z_][\w.-]{0,59}$', str(p.get('name', ''))):
            out.append({'name': str(p['name']), 'in': p.get('in') if p.get('in') in ('path', 'query', 'body') else 'body',
                        'type': p.get('type') if p.get('type') in act.TYPES else 'string', 'required': bool(p.get('required')),
                        'description': str(p.get('description', ''))[:200]})
    return out


@platform_bp.route('/platform/apps/<app_id>/actions', methods=['GET'])
def list_actions(app_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    return jsonify([x.to_dict() for x in AppAction.objects(app_id=app_id).order_by('name')])


@platform_bp.route('/platform/apps/<app_id>/actions', methods=['POST'])
def create_action(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    if AppAction.objects(app_id=app_id).count() >= act.MAX_ACTIONS_PER_APP:
        return _err(f'At most {act.MAX_ACTIONS_PER_APP} actions per app.')
    b = request.get_json(silent=True) or {}
    name = act.tool_name(b.get('name'), '')
    if not name:
        return _err('Give the action a name (letters, numbers and _).')
    if AppAction.objects(app_id=app_id, name=name).first():
        return _err('An action with that name already exists.', 409)
    mode = 'client' if b.get('mode') == 'client' else 'api'
    method = str(b.get('method', 'GET')).upper()
    if mode == 'api' and (method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE') or not str(b.get('path', '')).startswith('/')):
        return _err('An API action needs a method and a path that starts with /.')
    risk = b.get('risk') if b.get('risk') in ('read', 'write', 'danger') else ('read' if mode == 'api' and method == 'GET' else 'write')
    x = AppAction(action_id='ac_' + uuid.uuid4().hex[:10], app_id=app_id, client_id=a.client_id, name=name, description=str(b.get('description', ''))[:400],
                  mode=mode, method=method if mode == 'api' else 'CLIENT', path=str(b.get('path', ''))[:300] if mode == 'api' else '',
                  params=_clean_params(b.get('params')), risk=risk, enabled=bool(b.get('enabled', False)), hide_fields=[str(h)[:60] for h in (b.get('hideFields') or [])][:30]).save()
    return jsonify(x.to_dict()), 201


@platform_bp.route('/platform/apps/<app_id>/actions/<action_id>', methods=['PUT', 'DELETE'])
def one_action(app_id, action_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    x = AppAction.objects(app_id=app_id, action_id=action_id).first()
    if not x:
        return _err('not found', 404)
    if request.method == 'DELETE':
        x.delete()
        return jsonify({'ok': True})
    b = request.get_json(silent=True) or {}
    upd = {}
    for key, field in (('enabled', 'enabled'), ('confirm', 'confirm'), ('neverAi', 'never_ai'), ('requiresUser', 'requires_user')):
        if key in b:
            upd[field] = bool(b[key])
    if 'description' in b:
        upd['description'] = str(b['description'])[:400]
    if b.get('risk') in ('read', 'write', 'danger'):
        upd['risk'] = b['risk']
    if 'hideFields' in b:
        upd['hide_fields'] = [str(h)[:60] for h in (b['hideFields'] or [])][:30]
    if 'params' in b:
        upd['params'] = _clean_params(b['params'])
    if 'path' in b and x.mode == 'api':
        upd['path'] = str(b['path'])[:300]
    if upd:
        x.update(**{f'set__{k}': v for k, v in upd.items()})
        x.reload()
    return jsonify(x.to_dict())


@platform_bp.route('/platform/apps/<app_id>/actions/import', methods=['POST'])
def import_actions(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    b = request.get_json(silent=True) or {}
    try:
        src = act._load(b.get('source'))
        kind = b.get('kind') or ('postman' if isinstance(src, dict) and 'item' in src and 'paths' not in src else 'openapi')
        made = act.import_postman(a, src) if kind == 'postman' else act.import_openapi(a, src)
    except act.ActionError as e:
        return _err(str(e))
    a.reload()
    return jsonify({'imported': len(made), 'actions': [m.to_dict() for m in made], 'apiBaseUrl': a.api_base_url}), 201


@platform_bp.route('/platform/apps/<app_id>/actions/bulk', methods=['POST'])
def bulk_actions(app_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    b = request.get_json(silent=True) or {}
    qs = AppAction.objects(app_id=app_id)
    if b.get('onlyRead'):
        qs = qs.filter(risk='read')
    n = qs.update(set__enabled=bool(b.get('enable', True)))
    return jsonify({'updated': n})


# ───────────────────────── test chat, conversations ─────────────────────────
def _test_call(app_id, fn):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    ident = service.identity_for(portal=g.client.client_id)
    b = request.get_json(silent=True) or {}
    if b.get('anonymous'):
        ident = service.identity_for()
    try:
        return jsonify(fn(a, ident, b))
    except service.RateLimited as e:
        return _err(str(e), 429)
    except runtime.Blocked as e:
        return _err(str(e), 402)
    except runtime.ConnectError as e:
        return _err(str(e), 400)


@platform_bp.route('/platform/apps/<app_id>/test-chat', methods=['POST'])
def test_chat(app_id):
    return _test_call(app_id, service.do_chat)


@platform_bp.route('/platform/apps/<app_id>/test-chat/confirm', methods=['POST'])
def test_confirm(app_id):
    return _test_call(app_id, service.do_confirm)


@platform_bp.route('/platform/apps/<app_id>/test-chat/result', methods=['POST'])
def test_result(app_id):
    return _test_call(app_id, service.do_result)


@platform_bp.route('/platform/apps/<app_id>/conversations', methods=['GET'])
def list_convs(app_id):
    if not _own_app(app_id):
        return _err('not found', 404)
    return jsonify([c.to_dict() for c in Conversation.objects(app_id=app_id).order_by('-updated_at').limit(100)])


@platform_bp.route('/platform/apps/<app_id>/conversations/<cid>', methods=['GET', 'DELETE'])
def one_conv(app_id, cid):
    if not _own_app(app_id):
        return _err('not found', 404)
    c = Conversation.objects(app_id=app_id, conv_id=cid).first()
    if not c:
        return _err('not found', 404)
    if request.method == 'DELETE':
        c.delete()
        return jsonify({'ok': True})
    return jsonify(c.to_dict(full=True))


# ───────────────────────── usage & docs ─────────────────────────
@platform_bp.route('/platform/usage', methods=['GET'])
def usage_all():
    return jsonify(billing.summary(g.client.client_id, days=max(1, min(365, request.args.get('days', 30, type=int)))))


@platform_bp.route('/platform/apps/<app_id>/usage', methods=['GET'])
def usage_app(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    s = billing.summary(a.client_id, a.app_id, max(1, min(365, request.args.get('days', 30, type=int))))
    s['caps'] = billing.caps(a)
    return jsonify(s)


@platform_bp.route('/platform/apps/<app_id>/docs', methods=['GET'])
def app_docs(app_id):
    a = _own_app(app_id)
    if not a:
        return _err('not found', 404)
    base = os.getenv('PUBLIC_URL', '').rstrip('/') or request.url_root.rstrip('/')
    plat = request.args.get('platform') or ('react-native' if a.platform == 'react-native' else 'web')
    return jsonify({'platform': plat, 'platforms': [{'id': i, 'name': n} for i, n in docs.PLATFORMS], 'markdown': docs.guide(a, plat, base)})


# ───────────────────────── owner ─────────────────────────
@platform_bp.route('/platform/owner/summary', methods=['GET'])
def owner_summary():
    since = billing.month_start()
    col = UsageDocument._get_collection()
    rows = list(col.aggregate([{'$match': {'client_id': {'$ne': ''}, 'created_at': {'$gte': since}}},
                               {'$group': {'_id': '$client_id', 'c': {'$sum': '$cost_usd'}, 'n': {'$sum': 1}}}, {'$sort': {'c': -1}}]))
    names = {c.client_id: c.email for c in Client.objects}
    cost = sum(r['c'] for r in rows)
    return jsonify({'clients': Client.objects.count(), 'apps': ConnectApp.objects.count(), 'monthCost': round(cost, 6), 'monthRevenue': round(billing.price(cost), 6),
                    'monthCalls': sum(r['n'] for r in rows),
                    'top': [{'clientId': r['_id'], 'email': names.get(r['_id'], r['_id']), 'cost': round(r['c'], 6), 'price': round(billing.price(r['c']), 6), 'calls': r['n']} for r in rows[:10]]})


@platform_bp.route('/platform/owner/clients', methods=['GET'])
def owner_clients():
    out = []
    for c in Client.objects.order_by('-created_at'):
        out.append({**c.to_dict(), 'apps': ConnectApp.objects(client_id=c.client_id).count(), 'monthPrice': billing.month_spend(client_id=c.client_id)})
    return jsonify(out)


@platform_bp.route('/platform/owner/clients/<cid>', methods=['PUT'])
def owner_client(cid):
    c = Client.objects(client_id=cid).first()
    if not c:
        return _err('not found', 404)
    b = request.get_json(silent=True) or {}
    if b.get('status') in ('active', 'blocked', 'pending'):
        c.update(set__status=b['status'])
    if 'capUsd' in b:
        try:
            c.update(set__cap_usd=max(0.0, float(b['capUsd'])))
        except (TypeError, ValueError):
            return _err('capUsd must be a number.')
    c.reload()
    return jsonify(c.to_dict())


@platform_bp.route('/platform/owner/client-token', methods=['POST'])
def owner_client_token():
    """The owner's own workspace: a normal client account (created on first use, no spending cap) so the owner can connect their own apps."""
    email = f'owner+{g.owner}@adion.local'
    c = Client.objects(email=email).first()
    if not c:
        c = Client(client_id='cl_' + uuid.uuid4().hex[:10], email=email, name='Owner', cap_usd=100000.0,
                   password_hash=generate_password_hash(uuid.uuid4().hex + uuid.uuid4().hex)).save()
    return jsonify({'token': security.make_client_token(c.client_id), 'client': c.to_dict()})


@platform_bp.route('/platform/owner/config', methods=['GET', 'PUT'])
def owner_config():
    cfg = billing.config()
    if request.method == 'PUT':
        b = request.get_json(silent=True) or {}
        try:
            if 'markup' in b:
                cfg.update(set__markup=max(1.0, float(b['markup'])))
            if 'defaultCapUsd' in b:
                cfg.update(set__default_cap_usd=max(0.0, float(b['defaultCapUsd'])))
            if 'freeCreditUsd' in b:
                cfg.update(set__free_credit_usd=max(0.0, float(b['freeCreditUsd'])))
        except (TypeError, ValueError):
            return _err('Prices must be numbers.')
        if b.get('signup') in ('open', 'approval', 'closed'):
            cfg.update(set__signup=b['signup'])
        cfg.reload()
    return jsonify({'markup': cfg.markup, 'defaultCapUsd': cfg.default_cap_usd, 'freeCreditUsd': cfg.free_credit_usd, 'signup': cfg.signup})
