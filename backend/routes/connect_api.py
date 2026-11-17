"""
Adion Connect public API: what a connected app's website, mobile app or server calls.

  GET  /api/connect/widget.js            the embeddable chat
  GET  /api/connect/v1/config            (public key)
  POST /api/connect/v1/tickets           (secret key, from the client's SERVER)
  POST /api/connect/v1/chat              (public key [+ ticket])
  POST /api/connect/v1/chat/confirm      the user confirmed or cancelled a change
  POST /api/connect/v1/chat/result       the app ran an in-app action
  GET  /api/connect/v1/conversations     the signed-in user's own conversations
"""

import os
from flask import Blueprint, request, jsonify, Response

from connect import security, service, runtime
from connect.models import ConnectApp, Conversation

connect_bp = Blueprint('connect_api', __name__)
_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'connect', 'static')


def _bearer():
    return request.headers.get('Authorization', '').removeprefix('Bearer ').strip()


def _err(msg, code):
    return jsonify({'error': msg}), code


def _app_by_public_key():
    """-> (app, error_response). Checks the key and that a browser comes from an allowed website."""
    key = _bearer()
    app = ConnectApp.objects(public_key=key).first() if key.startswith('pk_') else None
    if not app:
        return None, _err('Unknown or missing public key.', 401)
    origin = request.headers.get('Origin', '')
    if origin:
        if not security.origin_allowed(origin, app.allowed_origins):
            return None, _err(f'This website ({origin}) is not allowed for this key. Add it under Access & rules.', 403)
    elif not app.allow_native:
        return None, _err('Mobile and server access is switched off for this app.', 403)
    return app, None


def _identity(app, body):
    t = body.get('ticket') or request.args.get('ticket') or ''
    if t:
        d = security.read_ticket(t)
        if not d or d.get('a') != app.app_id:
            return None
        return service.identity_for(d['u'], d.get('n', ''))
    return service.identity_for()


def _call(fn):
    app, bad = _app_by_public_key()
    if bad:
        return bad
    body = request.get_json(silent=True) or {}
    ident = _identity(app, body)
    if ident is None:
        return _err('The ticket is invalid or has expired. Ask your server for a new one.', 401)
    try:
        return jsonify(fn(app, ident, body))
    except service.RateLimited as e:
        return _err(str(e), 429)
    except runtime.Blocked as e:
        return _err(str(e), 402)
    except runtime.ConnectError as e:
        return _err(str(e), 400)


@connect_bp.route('/connect/widget.js', methods=['GET'])
def widget():
    with open(os.path.join(_STATIC, 'widget.js'), encoding='utf-8') as fh:
        return Response(fh.read(), mimetype='application/javascript', headers={'Cache-Control': 'public, max-age=300'})


@connect_bp.route('/connect/v1/config', methods=['GET'])
def config():
    app, bad = _app_by_public_key()
    if bad:
        return bad
    if not app.enabled:
        return _err('This assistant is switched off.', 403)
    return jsonify({'name': app.persona or app.name, 'greeting': app.greeting, 'language': app.language})


@connect_bp.route('/connect/v1/tickets', methods=['POST'])
def tickets():
    sk = _bearer()
    app = ConnectApp.objects(secret_hash=security.hash_secret(sk)).first() if sk.startswith('sk_') else None
    if not app:
        return _err('Unknown or missing secret key.', 401)
    b = request.get_json(silent=True) or {}
    uid = str(b.get('userId') or '').strip()
    if not uid:
        return _err('userId is required.', 400)
    return jsonify({'ticket': security.make_ticket(app.app_id, uid, b.get('name', '')), 'expiresIn': 7200})


@connect_bp.route('/connect/v1/chat', methods=['POST'])
def chat():
    return _call(service.do_chat)


@connect_bp.route('/connect/v1/chat/confirm', methods=['POST'])
def confirm():
    return _call(service.do_confirm)


@connect_bp.route('/connect/v1/chat/result', methods=['POST'])
def result():
    return _call(service.do_result)


def _own(app, ident):
    return Conversation.objects(app_id=app.app_id, end_user=ident['id']) if ident['identified'] else Conversation.objects(app_id=None)


@connect_bp.route('/connect/v1/conversations', methods=['GET'])
def conversations():
    app, bad = _app_by_public_key()
    if bad:
        return bad
    ident = _identity(app, {})
    if ident is None or not ident['identified']:
        return _err('Sign in (send a ticket) to see conversations.', 401)
    return jsonify([c.to_dict() for c in _own(app, ident).order_by('-updated_at').limit(30)])


@connect_bp.route('/connect/v1/conversations/<cid>', methods=['GET', 'DELETE'])
def one_conversation(cid):
    app, bad = _app_by_public_key()
    if bad:
        return bad
    ident = _identity(app, {})
    if ident is None or not ident['identified']:
        return _err('Sign in (send a ticket) first.', 401)
    c = _own(app, ident).filter(conv_id=cid).first()
    if not c:
        return _err('not found', 404)
    if request.method == 'DELETE':
        c.delete()
        return jsonify({'ok': True})
    return jsonify(c.to_dict(full=True))
