"""OAuth 2.0 "Connect" flow (authorization code + PKCE) and token refresh. Tokens are stored encrypted, per user."""

import time
import uuid
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import requests

import auth
from connect import security
from .models import IntegrationConfig, LinkedAccount
from .providers import PROVIDERS

STATE_TTL = 600
TIMEOUT = 20


class OAuthError(Exception):
    pass


def get_config(provider):
    row = IntegrationConfig.objects(provider=provider).first()
    secret = auth.decrypt_json(row.client_secret_enc).get('s', '') if row and row.client_secret_enc else ''
    return (row.client_id, secret) if row and row.client_id and secret else ('', '')


def set_config(provider, client_id, client_secret):
    if provider not in PROVIDERS:
        raise OAuthError('Unknown service.')
    client_id, client_secret = str(client_id or '').strip(), str(client_secret or '').strip()
    if len(client_id) < 8 or len(client_secret) < 8 or any(c.isspace() for c in client_id + client_secret):
        raise OAuthError('That does not look like a client ID and secret.')
    IntegrationConfig.objects(provider=provider).update_one(set__client_id=client_id, set__client_secret_enc=auth.encrypt_json({'s': client_secret}), upsert=True)


def clear_config(provider):
    IntegrationConfig.objects(provider=provider).delete()


def redirect_uri(provider, base):
    return f'{base.rstrip("/")}/api/integrations/callback/{provider}'


def begin(owner, provider, base):
    """-> the address to send the user to so they can allow access."""
    p = PROVIDERS.get(provider)
    if not p:
        raise OAuthError('Unknown service.')
    cid, _ = get_config(provider)
    if not cid:
        raise OAuthError(f'{p["name"]} is not set up yet. The owner adds its client ID and secret on the Owner tab.')
    verifier = secrets.token_urlsafe(48)
    state = security._sign('oauth', {'o': owner, 'p': provider, 'v': verifier, 'n': secrets.token_hex(6), 'exp': int(time.time()) + STATE_TTL})
    q = {'client_id': cid, 'redirect_uri': redirect_uri(provider, base), 'response_type': 'code', 'state': state, **p['extra_auth']}
    if p['scopes']:
        q[p['scope_param']] = p['scope_sep'].join(p['scopes'])
    if p['pkce']:
        q.update(code_challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='), code_challenge_method='S256')
    return p['auth_url'] + '?' + urlencode(q)


def _token_request(provider, data):
    p = PROVIDERS[provider]
    cid, secret = get_config(provider)
    kw = {'timeout': TIMEOUT, 'headers': {'Accept': 'application/json'}}
    body = dict(data)
    if p['token_auth'] == 'basic':
        kw['auth'] = (cid, secret)
    else:
        body.update(client_id=cid, client_secret=secret)
    kw['json' if p['token_json'] else 'data'] = body
    try:
        r = requests.post(p['token_url'], **kw)
    except requests.exceptions.RequestException as e:
        raise OAuthError(f'Could not reach {p["name"]}: {type(e).__name__}')
    try:
        d = r.json()
    except ValueError:
        d = {}
    if p['token_path'] and isinstance(d.get(p['token_path']), dict):
        d = {**d, **d[p['token_path']]}          # Slack puts the user's token inside "authed_user"
    if r.status_code >= 400 or 'access_token' not in d:
        raise OAuthError(f'{p["name"]} refused: {str(d.get("error_description") or d.get("error") or r.status_code)[:160]}')
    return d


def _dig(d, path):
    for k in path.split('.'):
        d = d.get(k) if isinstance(d, dict) else None
    return d if isinstance(d, str) else ''


def finish(code, state, base):
    """The user came back from the service. -> LinkedAccount (created or refreshed). Raises OAuthError."""
    st = security._read('oauth', state)
    if not st or st.get('p') not in PROVIDERS:
        raise OAuthError('This connection attempt expired. Please press Connect again.')
    provider, owner = st['p'], st['o']
    d = _token_request(provider, {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri(provider, base), 'code_verifier': st['v']})
    p = PROVIDERS[provider]
    email = next((v for v in (_dig(d, k) for k in p['token_label_keys']) if v), '')
    if not email and p['userinfo_url']:
        try:
            u = requests.request(p['userinfo_method'], p['userinfo_url'], headers={'Authorization': f'Bearer {d["access_token"]}', **p['api_headers']}, timeout=TIMEOUT).json()
            email = next((v for v in (_dig(u, k) for k in p['label_keys']) if v), '').lower()
        except (requests.exceptions.RequestException, ValueError):
            pass
    email = email or f'{provider} account'
    link = LinkedAccount.objects(owner=owner, provider=provider, email=email).first()
    prev = auth.decrypt_json(link.tokens_enc) if link else {}
    tokens = {'access': d['access_token'], 'refresh': d.get('refresh_token') or prev.get('refresh', ''), 'exp': int(time.time()) + int(d['expires_in']) if d.get('expires_in') else 0}
    if link:
        link.update(set__tokens_enc=auth.encrypt_json(tokens))
        link.reload()
    else:
        link = LinkedAccount(link_id='ln_' + uuid.uuid4().hex[:10], owner=owner, provider=provider, email=email, tokens_enc=auth.encrypt_json(tokens)).save()
    return link


def access_token(link, force=False):
    """A valid access token for this account (refreshing it when it is about to expire)."""
    t = auth.decrypt_json(link.tokens_enc) if link.tokens_enc else {}
    if not force and t.get('access') and (t.get('exp', 0) == 0 or t['exp'] > time.time() + 60):   # exp 0 = this service's tokens do not expire
        return t['access']
    if not t.get('refresh'):
        raise OAuthError('This account needs to be reconnected.')
    d = _token_request(link.provider, {'grant_type': 'refresh_token', 'refresh_token': t['refresh']})
    t = {'access': d['access_token'], 'refresh': d.get('refresh_token') or t['refresh'], 'exp': int(time.time()) + int(d['expires_in']) if d.get('expires_in') else 0}
    link.update(set__tokens_enc=auth.encrypt_json(t))
    return t['access']
