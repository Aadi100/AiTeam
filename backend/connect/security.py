"""Keys, tickets, client login tokens, secret redaction and SSRF protection for Adion Connect."""

import os
import re
import json
import time
import hmac
import base64
import hashlib
import secrets
import socket
import ipaddress
from urllib.parse import urlparse

import auth   # SECRET and the encryption helpers live here


# ───────── keys ─────────
def new_public_key():
    return 'pk_' + secrets.token_urlsafe(18)


def new_secret_key():
    return 'sk_' + secrets.token_urlsafe(30)


def hash_secret(sk):
    return hashlib.sha256(sk.encode()).hexdigest()


def secret_matches(sk, stored_hash):
    return bool(stored_hash) and hmac.compare_digest(hash_secret(sk or ''), stored_hash)


# ───────── signed tokens (client login, end-user tickets) ─────────
def _sign(kind, payload):
    p = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode()
    sig = hmac.new(auth.SECRET, f'{kind}.{p}'.encode(), hashlib.sha256).hexdigest()
    return f'{p}.{sig}'


def _read(kind, token):
    try:
        p, sig = (token or '').split('.', 1)
        good = hmac.new(auth.SECRET, f'{kind}.{p}'.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        d = json.loads(base64.urlsafe_b64decode(p.encode()))
        return d if d.get('exp', 0) > time.time() else None
    except Exception:  # noqa: BLE001
        return None


def make_client_token(client_id, ttl=12 * 3600):
    return _sign('client', {'c': client_id, 'exp': int(time.time()) + ttl})


def read_client_token(token):
    d = _read('client', token)
    return d['c'] if d else None


def make_ticket(app_id, user_id, name='', ttl=2 * 3600):
    """Created by the CLIENT'S server (using the secret key) to say who the signed-in user is."""
    return _sign('ticket', {'a': app_id, 'u': str(user_id)[:120], 'n': str(name)[:80], 'exp': int(time.time()) + ttl})


def read_ticket(token):
    return _read('ticket', token)


def encrypt_json(obj):
    return auth.encrypt_json(obj)


def decrypt_json(tok):
    return auth.decrypt_json(tok) if tok else {}


# ───────── redaction: these never reach the AI ─────────
SENSITIVE = re.compile(r'(pass(word|wd)?|secret|token|api[_-]?key|cvv|cvc|pin|private[_-]?key|seed|mnemonic|otp|ssn|card[_-]?number|authorization)', re.I)


def redact(obj, hide=(), depth=0):
    """Remove fields the client hid plus anything that looks like a secret, at any depth."""
    hide = {h.lower() for h in hide}
    if depth > 8:
        return obj
    if isinstance(obj, dict):
        return {k: redact(v, hide, depth + 1) for k, v in obj.items() if k.lower() not in hide and not SENSITIVE.search(str(k))}
    if isinstance(obj, list):
        return [redact(v, hide, depth + 1) for v in obj[:200]]
    return obj


# ───────── SSRF: the platform must not be usable to call internal addresses ─────────
class UnsafeUrl(Exception):
    pass


def check_url(url):
    """Allow only public http(s) hosts. CONNECT_ALLOW_PRIVATE=1 permits localhost/LAN (development only)."""
    p = urlparse(url or '')
    if p.scheme not in ('http', 'https') or not p.hostname:
        raise UnsafeUrl('The API address must start with http:// or https://')
    allow_private = os.getenv('CONNECT_ALLOW_PRIVATE') == '1'
    if p.scheme == 'http' and not allow_private:
        raise UnsafeUrl('The API address must use https://')
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == 'https' else 80), proto=socket.IPPROTO_TCP)
    except OSError:
        raise UnsafeUrl(f'Could not find the server {p.hostname}')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not allow_private and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise UnsafeUrl('That address points inside a private network, which Adion will not call.')
    return url


def origin_allowed(origin, allowed):
    """Exact match, or *.example.com, or http://localhost:* style patterns."""
    if not origin:
        return False
    o = origin.rstrip('/').lower()
    for pat in allowed or []:
        pat = pat.strip().rstrip('/').lower()
        if not pat:
            continue
        if pat == '*':
            return True
        rx = '^' + re.escape(pat).replace(r'\*', '[^/]*') + '$'
        if re.match(rx, o):
            return True
    return False
