"""
Connected accounts API (Gmail, Calendar, GitHub, Slack, Notion...). Every user manages only their own accounts.

GET    /api/integrations                       services (is each set up?) + my connected accounts
PUT    /api/integrations/config/<provider>     owner only: the service's OAuth client id + secret (DELETE removes them)
POST   /api/integrations/connect/<provider>    -> {url}: send the browser there to allow access
GET    /api/integrations/callback/<provider>   the service sends the browser back here (no login header: the signed state identifies the user)
DELETE /api/integrations/links/<id>            disconnect
POST   /api/integrations/tasks {request}       ask Adion to do something in my accounts;  GET .../tasks/<id>;  POST .../approve | .../deny
GET    /api/integrations/activity              what Adion did in my accounts
GET/POST /api/integrations/mcp {name,url,token?}   my tool servers (MCP, e.g. a Zapier link); POST .../<id>/refresh; DELETE .../<id>
"""

import os
from urllib.parse import urlencode
from flask import Blueprint, request, jsonify, redirect

from auth import current_user, is_admin, with_stored_key
from integrations import oauth, engine, mcp, mode
from integrations.models import LinkedAccount, AppTask, AppLog, McpServer
from integrations.providers import PROVIDERS

integrations_bp = Blueprint('integrations', __name__)


def _me():
    return current_user()['u']


def _base():
    """The public address of THIS backend (the service redirects the browser here, so it must be reachable from the browser)."""
    return os.getenv('PUBLIC_URL', '').rstrip('/') or request.url_root.rstrip('/')


def _front():
    return os.getenv('FRONTEND_URL', 'http://localhost:3001').rstrip('/')


@integrations_bp.route('/integrations', methods=['GET'])
def overview():
    out = []
    for pid, p in PROVIDERS.items():
        cid, secret = oauth.get_config(pid)
        d = {'id': pid, 'name': p['name'], 'group': p['group'], 'configured': bool(cid and secret), 'review': p['review'], 'caps': p['caps']}
        if is_admin():
            d.update(clientIdHint=(cid[:6] + '…' + cid[-3:]) if cid else '', redirectUri=oauth.redirect_uri(pid, _base()), setup=p['setup'], console=p['console'])
        out.append(d)
    return jsonify({'mode': mode.get(), 'providers': out, 'links': [l.to_dict() for l in LinkedAccount.objects(owner=_me()).order_by('created_at')]})


@integrations_bp.route('/integrations/mode', methods=['GET', 'PUT'])
def connect_mode():
    """How everyone connects their apps: 'direct' (Connect buttons) or 'zapier' (tool-server links). Only the owner changes it."""
    if request.method == 'PUT':
        if not is_admin():
            return jsonify({'error': 'only the owner chooses how apps are connected'}), 403
        try:
            mode.set_mode(str((request.get_json(silent=True) or {}).get('mode', '')).strip().lower())
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
    return jsonify({'mode': mode.get()})


@integrations_bp.route('/integrations/config/<provider>', methods=['PUT', 'DELETE'])
def config(provider):
    if not is_admin():
        return jsonify({'error': 'only the owner sets up services'}), 403
    if provider not in PROVIDERS:
        return jsonify({'error': 'unknown service'}), 404
    if request.method == 'DELETE':
        oauth.clear_config(provider)
        return jsonify({'ok': True})
    b = request.get_json(silent=True) or {}
    try:
        oauth.set_config(provider, b.get('clientId'), b.get('clientSecret'))
    except oauth.OAuthError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'ok': True})


@integrations_bp.route('/integrations/connect/<provider>', methods=['POST'])
def connect(provider):
    if mode.get() != 'direct':
        return jsonify({'error': 'The owner chose Zapier (tool servers) for connecting apps. Add your Zapier link in the Apps tab instead.'}), 400
    try:
        return jsonify({'url': oauth.begin(_me(), provider, _base())})
    except oauth.OAuthError as e:
        return jsonify({'error': str(e)}), 400


@integrations_bp.route('/integrations/callback/<provider>', methods=['GET'])
def callback(provider):
    back = _front() + '/'
    if request.args.get('error') or not request.args.get('code'):
        return redirect(back + '?' + urlencode({'connect_error': f'{provider}: ' + (request.args.get('error_description') or request.args.get('error') or 'cancelled')[:160]}))
    try:
        link = oauth.finish(request.args['code'], request.args.get('state', ''), _base())
    except oauth.OAuthError as e:
        return redirect(back + '?' + urlencode({'connect_error': str(e)[:200]}))
    return redirect(back + '?' + urlencode({'connected': link.provider, 'as': link.email}))


@integrations_bp.route('/integrations/links/<lid>', methods=['DELETE'])
def disconnect(lid):
    n = LinkedAccount.objects(link_id=lid, owner=_me()).delete()
    return (jsonify({'ok': True}), 200) if n else (jsonify({'error': 'not found'}), 404)


@integrations_bp.route('/integrations/mcp', methods=['GET'])
def mcp_list():
    return jsonify([s.to_dict() for s in mcp.servers_for(_me())])


@integrations_bp.route('/integrations/mcp', methods=['POST'])
def mcp_add():
    if mode.get() != 'zapier':
        return jsonify({'error': 'The owner chose direct Connect buttons for connecting apps, so tool servers are switched off.'}), 400
    b = request.get_json(silent=True) or {}
    try:
        s = mcp.add(_me(), b.get('name'), b.get('url'), b.get('token'))
    except mcp.McpError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(s.to_dict()), 201


@integrations_bp.route('/integrations/mcp/<sid>/refresh', methods=['POST'])
def mcp_refresh(sid):
    s = McpServer.objects(server_id=sid, owner=_me()).first()
    if not s:
        return jsonify({'error': 'not found'}), 404
    try:
        mcp.refresh(s)
    except mcp.McpError as e:
        return jsonify({'error': str(e), **s.reload().to_dict()}), 400
    return jsonify(s.to_dict())


@integrations_bp.route('/integrations/mcp/<sid>', methods=['DELETE'])
def mcp_remove(sid):
    n = McpServer.objects(server_id=sid, owner=_me()).delete()
    return (jsonify({'ok': True}), 200) if n else (jsonify({'error': 'not found'}), 404)


@integrations_bp.route('/integrations/tasks', methods=['POST'])
def start():
    req = str((request.get_json(silent=True) or {}).get('request') or '').strip()
    if not req:
        return jsonify({'error': 'request is required'}), 400
    tid = engine.start_task(req, _me(), with_stored_key(None, _me()))
    return jsonify(AppTask.objects.get(task_id=tid).to_dict()), 201


@integrations_bp.route('/integrations/tasks/<tid>', methods=['GET'])
def get_task(tid):
    t = AppTask.objects(task_id=tid, owner=_me()).first()
    return (jsonify(t.to_dict()), 200) if t else (jsonify({'error': 'not found'}), 404)


def _act(fn, tid, *args):
    try:
        fn(tid, _me(), *args)
    except LookupError:
        return jsonify({'error': 'not found'}), 404
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    return jsonify(AppTask.objects.get(task_id=tid).to_dict())


@integrations_bp.route('/integrations/tasks/<tid>/approve', methods=['POST'])
def approve(tid):
    return _act(engine.approve, tid, with_stored_key(None, _me()))


@integrations_bp.route('/integrations/tasks/<tid>/deny', methods=['POST'])
def deny(tid):
    return _act(engine.deny, tid)


@integrations_bp.route('/integrations/activity', methods=['GET'])
def activity():
    return jsonify([a.to_dict() for a in AppLog.objects(owner=_me()).limit(max(1, min(100, request.args.get('limit', 40, type=int))))])
