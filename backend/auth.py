"""
Accounts, roles and a filesystem allow-list.

Roles
  admin  : everything, including users, shell background jobs and viewing all runs
  member : start/cancel/retry own runs, memory, schedules, voice
  viewer : read-only (GET) access to all runs

Bootstrap: the first login creates user "admin" with APP_PASSWORD (backend/.env). If that is unset a random
password is generated once into backend/.auth.json (git-ignored) and printed to the console.
Tokens are HMAC-signed (12h). EventSource cannot send headers, so GET streams also accept ?token=.
ALLOWED_ROOTS (os.pathsep separated, default: your home folder) limits where agents and jobs may write.
"""

import os
import re
import json
import time
import hmac
import base64
import hashlib
import secrets
from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

from models import UserDocument

auth_bp = Blueprint('auth', __name__)
_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.auth.json')
TOKEN_TTL = 12 * 3600
OPEN_PATHS = ('/api/health', '/api/auth/login')
ROLES = ('admin', 'member', 'viewer')


def _load():
    if os.path.exists(_FILE):
        with open(_FILE, encoding='utf-8') as f:
            return json.load(f)
    data = {'secret': secrets.token_hex(32), 'password': secrets.token_urlsafe(9)}
    with open(_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    print(f"\n[AUTH] No APP_PASSWORD set. Generated admin password: {data['password']}  (stored in backend/.auth.json)\n")
    return data


_cfg = _load()
BOOTSTRAP_PASSWORD = os.getenv('APP_PASSWORD') or _cfg['password']
SECRET = _cfg['secret'].encode()


def _sign(payload):
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(username, role):
    p = base64.urlsafe_b64encode(json.dumps({'u': username, 'r': role, 'exp': int(time.time()) + TOKEN_TTL}).encode()).decode()
    return f'{p}.{_sign(p)}'


def read_token(tok):
    """Return {'u','r'} for a valid token, else None."""
    try:
        p, sig = tok.split('.', 1)
        if not hmac.compare_digest(sig, _sign(p)):
            return None
        d = json.loads(base64.urlsafe_b64decode(p.encode()))
        return d if d['exp'] > time.time() else None
    except Exception:  # noqa: BLE001
        return None


def ensure_bootstrap_admin():
    if UserDocument.objects.count() == 0:
        UserDocument(username='admin', password_hash=generate_password_hash(BOOTSTRAP_PASSWORD), role='admin').save()


def current_user():
    return getattr(g, 'user', {'u': '', 'r': 'viewer'})


def is_admin():
    return current_user()['r'] == 'admin'


def require_auth():
    """Flask before_request hook: authenticate and enforce role rules."""
    if request.method == 'OPTIONS' or not request.path.startswith('/api') or request.path in OPEN_PATHS:
        return None
    tok = request.headers.get('Authorization', '').removeprefix('Bearer ').strip() or request.args.get('token', '')
    user = read_token(tok)
    if not user:
        return jsonify({'error': 'unauthorized'}), 401
    # the account may have been deleted or demoted since the token was issued
    row = UserDocument.objects(username=user['u']).first()
    if not row:
        return jsonify({'error': 'unauthorized'}), 401
    g.user = {'u': row.username, 'r': row.role}
    role, write = row.role, request.method != 'GET'
    if request.path.startswith('/api/users') and role != 'admin':
        return jsonify({'error': 'admin only'}), 403
    if request.path.startswith('/api/jobs') and role != 'admin':
        return jsonify({'error': 'background shell jobs are admin only'}), 403
    if write and role == 'viewer' and request.path != '/api/auth/password':
        return jsonify({'error': 'viewers are read-only'}), 403
    return None


_attempts = {}


@auth_bp.route('/auth/login', methods=['POST'])
def login():
    ensure_bootstrap_admin()
    ip = request.remote_addr or '?'
    n, t0 = _attempts.get(ip, (0, time.time()))
    if time.time() - t0 > 300:
        n, t0 = 0, time.time()
    if n >= 8:
        return jsonify({'error': 'too many attempts, wait 5 minutes'}), 429
    b = request.get_json(silent=True) or {}
    row = UserDocument.objects(username=(b.get('username') or 'admin').strip().lower()).first()
    ok = bool(row) and check_password_hash(row.password_hash, str(b.get('password', '')))
    if not ok:
        _attempts[ip] = (n + 1, t0)
        return jsonify({'error': 'wrong username or password'}), 401
    _attempts.pop(ip, None)
    return jsonify({'token': make_token(row.username, row.role), 'expiresIn': TOKEN_TTL,
                    'user': row.to_dict()})


@auth_bp.route('/auth/check', methods=['GET'])
def check():
    return jsonify({'ok': True, 'user': {'username': current_user()['u'], 'role': current_user()['r']}})


@auth_bp.route('/auth/password', methods=['POST'])
def change_password():
    b = request.get_json(silent=True) or {}
    row = UserDocument.objects(username=current_user()['u']).first()
    if not row or not check_password_hash(row.password_hash, str(b.get('current', ''))):
        return jsonify({'error': 'current password is wrong'}), 400
    if len(str(b.get('new', ''))) < 8:
        return jsonify({'error': 'new password must be at least 8 characters'}), 400
    row.update(set__password_hash=generate_password_hash(b['new']))
    return jsonify({'ok': True})


@auth_bp.route('/users', methods=['GET'])
def list_users():
    return jsonify([u.to_dict() for u in UserDocument.objects])


@auth_bp.route('/users', methods=['POST'])
def create_user():
    b = request.get_json(silent=True) or {}
    name = (b.get('username') or '').strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{2,32}', name):
        return jsonify({'error': 'username: 2-32 chars, letters/digits/._-'}), 400
    if len(str(b.get('password', ''))) < 8:
        return jsonify({'error': 'password must be at least 8 characters'}), 400
    if b.get('role') not in ROLES:
        return jsonify({'error': f'role must be one of {ROLES}'}), 400
    if UserDocument.objects(username=name).first():
        return jsonify({'error': 'user already exists'}), 409
    UserDocument(username=name, password_hash=generate_password_hash(b['password']), role=b['role']).save()
    return jsonify({'ok': True}), 201


@auth_bp.route('/users/<name>', methods=['DELETE'])
def delete_user(name):
    if name == current_user()['u']:
        return jsonify({'error': 'you cannot delete your own account'}), 400
    target = UserDocument.objects(username=name).first()
    if target and target.role == 'admin' and UserDocument.objects(role='admin').count() <= 1:
        return jsonify({'error': 'cannot delete the last admin'}), 400
    UserDocument.objects(username=name).delete()
    return jsonify({'ok': True})


@auth_bp.route('/users/<name>/role', methods=['PUT'])
def set_role(name):
    role = (request.get_json(silent=True) or {}).get('role')
    if role not in ROLES:
        return jsonify({'error': f'role must be one of {ROLES}'}), 400
    target = UserDocument.objects(username=name).first()
    if not target:
        return jsonify({'error': 'not found'}), 404
    if target.role == 'admin' and role != 'admin' and UserDocument.objects(role='admin').count() <= 1:
        return jsonify({'error': 'cannot demote the last admin'}), 400
    target.update(set__role=role)
    return jsonify({'ok': True})


def allowed_roots():
    raw = os.getenv('ALLOWED_ROOTS')
    roots = raw.split(os.pathsep) if raw else [os.path.expanduser('~')]
    return [os.path.realpath(os.path.expanduser(r)) for r in roots if r.strip()]


def path_allowed(path):
    real = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
    for r in allowed_roots():
        try:
            if os.path.commonpath([r, real]) == r:
                return True
        except ValueError:
            continue
    return False


# ── encrypted secret storage (used for schedules that opt in to keeping API keys) ──
def _fernet():
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b'keys:' + SECRET).digest()))


def encrypt_json(obj):
    return _fernet().encrypt(json.dumps(obj).encode()).decode()


def decrypt_json(token):
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except Exception:  # noqa: BLE001 - corrupted or secret rotated
        return {}
