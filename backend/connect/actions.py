"""
Actions: what Adion may DO inside a connected app.

  mode "api"     Adion calls the client's server. Imported from OpenAPI/Swagger or Postman, or typed in by hand.
  mode "client"  The app's own code runs it (registered with the SDK). Nothing leaves the app, no tokens are shared.

Access levels: limited = read actions only, standard = + changes (always confirmed), complete = + risky ones (always confirmed).
Every response has secrets and hidden fields removed before the AI sees it.
"""

import re
import json
import uuid
from urllib.parse import quote, urlparse

import requests

from .models import AppAction
from . import security

MAX_RESPONSE_BYTES = 200_000
MAX_ACTIONS_PER_APP = 300
TYPES = {'string', 'number', 'integer', 'boolean', 'object', 'array'}


class ActionError(Exception):
    pass


def tool_name(text, fallback='action'):
    n = re.sub(r'[^A-Za-z0-9_]+', '_', str(text or '')).strip('_')[:60]
    return n or fallback


# ───────────────────────── import ─────────────────────────
def _load(text_or_obj):
    if isinstance(text_or_obj, (dict, list)):
        return text_or_obj
    t = str(text_or_obj or '').strip()
    if not t:
        raise ActionError('Paste or upload an API description first.')
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    try:
        import yaml
        d = yaml.safe_load(t)
        if isinstance(d, dict):
            return d
    except Exception:  # noqa: BLE001
        pass
    raise ActionError('That is not valid JSON or YAML.')


def _ref(spec, node, depth=0):
    """Resolve local $ref pointers like #/components/schemas/Transaction."""
    while isinstance(node, dict) and '$ref' in node and depth < 6:
        ref = node['$ref']
        if not ref.startswith('#/'):
            return {}
        cur = spec
        for part in ref[2:].split('/'):
            cur = cur.get(part, {}) if isinstance(cur, dict) else {}
        node, depth = cur, depth + 1
    return node if isinstance(node, dict) else {}


def _ptype(schema):
    t = (schema or {}).get('type')
    return t if t in TYPES else 'string'


def _unique(app_id, name, used):
    base, i = name, 2
    while name in used:
        name = f'{base}_{i}'; i += 1
    used.add(name)
    return name


def import_openapi(app, source):
    """Create actions (switched OFF until the client enables them) from an OpenAPI 3 / Swagger 2 document."""
    spec = _load(source)
    if not isinstance(spec, dict) or not ('openapi' in spec or 'swagger' in spec or 'paths' in spec):
        raise ActionError('That does not look like an OpenAPI/Swagger document (no "paths").')
    base = ''
    if spec.get('servers'):
        base = str((spec['servers'][0] or {}).get('url', ''))
    elif spec.get('host'):
        base = f"{(spec.get('schemes') or ['https'])[0]}://{spec['host']}{spec.get('basePath', '')}"
    used = {a.name for a in AppAction.objects(app_id=app.app_id)}
    made = []
    room = MAX_ACTIONS_PER_APP - len(used)
    for path, item in (spec.get('paths') or {}).items():
        item = _ref(spec, item)
        shared = [_ref(spec, p) for p in item.get('parameters', [])]
        for method in ('get', 'post', 'put', 'patch', 'delete'):
            op = _ref(spec, item.get(method))
            if not op or len(made) >= room:
                continue
            params = []
            for p in shared + [_ref(spec, x) for x in op.get('parameters', [])]:
                if p.get('in') in ('path', 'query') and p.get('name'):
                    sch = _ref(spec, p.get('schema', p))
                    params.append({'name': p['name'], 'in': p['in'], 'type': _ptype(sch), 'required': bool(p.get('required') or p['in'] == 'path'),
                                   'description': str(p.get('description', ''))[:200]})
            body = None
            rb = _ref(spec, op.get('requestBody', {}))
            if rb:
                body = _ref(spec, ((rb.get('content') or {}).get('application/json') or {}).get('schema', {}))
            else:
                for p in [_ref(spec, x) for x in op.get('parameters', [])]:
                    if p.get('in') == 'body':
                        body = _ref(spec, p.get('schema', {}))
            if body:
                req = set(body.get('required', []))
                for k, v in (body.get('properties') or {}).items():
                    v = _ref(spec, v)
                    params.append({'name': k, 'in': 'body', 'type': _ptype(v), 'required': k in req, 'description': str(v.get('description', ''))[:200]})
            name = _unique(app.app_id, tool_name(op.get('operationId') or f'{method}_{path}'), used)
            desc = (op.get('summary') or '') + ((' - ' + op['description']) if op.get('description') else '')
            made.append(AppAction(action_id='ac_' + uuid.uuid4().hex[:10], app_id=app.app_id, client_id=app.client_id, name=name,
                                  description=desc[:400] or f'{method.upper()} {path}', mode='api', method=method.upper(), path=path, params=params,
                                  risk='read' if method == 'get' else 'danger' if method == 'delete' else 'write', enabled=False).save())
    if base and not app.api_base_url:
        app.update(set__api_base_url=base)
    if not made:
        raise ActionError('No endpoints were found to import.')
    return made


def _pm_url(u):
    raw = u.get('raw', '') if isinstance(u, dict) else str(u or '')
    p = urlparse(re.sub(r'\{\{[^}]+\}\}', 'x', raw) if raw else '')
    path = '/' + '/'.join(u.get('path', [])) if isinstance(u, dict) and u.get('path') else (p.path or '/')
    path = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', path)
    path = re.sub(r'/:([A-Za-z_]\w*)', r'/{\1}', path)
    q = [x.get('key') for x in (u.get('query') or []) if isinstance(x, dict) and x.get('key')] if isinstance(u, dict) else []
    return path, q


def import_postman(app, source):
    col = _load(source)
    if not isinstance(col, dict) or 'item' not in col:
        raise ActionError('That does not look like a Postman collection (no "item").')
    used = {a.name for a in AppAction.objects(app_id=app.app_id)}
    made = []
    room = MAX_ACTIONS_PER_APP - len(used)

    def walk(items, prefix=''):
        for it in items:
            if 'item' in it:
                walk(it['item'], (prefix + ' ' + it.get('name', '')).strip())
                continue
            req = it.get('request') or {}
            if not isinstance(req, dict) or len(made) >= room:
                continue
            method = str(req.get('method', 'GET')).upper()
            path, query = _pm_url(req.get('url', ''))
            params = [{'name': m, 'in': 'path', 'type': 'string', 'required': True, 'description': ''} for m in re.findall(r'\{(\w+)\}', path)]
            params += [{'name': k, 'in': 'query', 'type': 'string', 'required': False, 'description': ''} for k in query]
            body = (req.get('body') or {})
            if body.get('mode') == 'raw':
                try:
                    obj = json.loads(body.get('raw', ''))
                    for k, v in (obj.items() if isinstance(obj, dict) else []):
                        params.append({'name': k, 'in': 'body', 'type': 'number' if isinstance(v, (int, float)) and not isinstance(v, bool) else
                                       'boolean' if isinstance(v, bool) else 'string', 'required': False, 'description': ''})
                except (json.JSONDecodeError, TypeError):
                    pass
            name = _unique(app.app_id, tool_name(f'{prefix} {it.get("name", method)}'), used)
            desc = req.get('description') if isinstance(req.get('description'), str) else ''
            made.append(AppAction(action_id='ac_' + uuid.uuid4().hex[:10], app_id=app.app_id, client_id=app.client_id, name=name,
                                  description=(desc or it.get('name', '') or f'{method} {path}')[:400], mode='api', method=method, path=path,
                                  params=params, risk='read' if method in ('GET', 'HEAD') else 'danger' if method == 'DELETE' else 'write',
                                  enabled=False).save())
    walk(col['item'])
    if not made:
        raise ActionError('No requests were found to import.')
    return made


# ───────────────────────── using actions ─────────────────────────
def usable(app, action, identified):
    """May the AI use this action for this user right now?"""
    if not action.enabled or action.never_ai:
        return False
    if action.requires_user and not identified:
        return False
    if app.access_level == 'limited':
        return action.risk == 'read'
    if app.access_level == 'standard':
        return action.risk in ('read', 'write')
    return True


def needs_confirmation(action):
    return action.risk != 'read' or action.confirm


def tool_schema(action):
    props, req = {}, []
    for p in action.params:
        sch = {'type': p.get('type') if p.get('type') in TYPES else 'string'}
        if p.get('description'):
            sch['description'] = p['description']
        if sch['type'] == 'array':
            sch['items'] = {'type': 'string'}
        props[p['name']] = sch
        if p.get('required'):
            req.append(p['name'])
    desc = (action.description or action.name) + ('' if action.risk == 'read' else ' (changes data: the user will be asked to confirm)')
    return {'type': 'function', 'function': {'name': action.name, 'description': desc[:500],
                                              'parameters': {'type': 'object', 'properties': props, 'required': req}}}


def validate_args(action, args):
    """-> (clean_args, error). Unknown arguments are dropped, types coerced, required ones checked."""
    if not isinstance(args, dict):
        return {}, 'Arguments must be an object.'
    clean = {}
    for p in action.params:
        n, t = p['name'], p.get('type', 'string')
        if n not in args or args[n] in (None, ''):
            if p.get('required'):
                return {}, f'Missing required argument "{n}".'
            continue
        v = args[n]
        try:
            if t == 'integer':
                v = int(float(v))
            elif t == 'number':
                v = float(v)
                v = int(v) if v == int(v) and isinstance(args[n], int) else v
            elif t == 'boolean':
                v = v if isinstance(v, bool) else str(v).lower() in ('true', '1', 'yes')
            elif t == 'string':
                v = str(v)
        except (TypeError, ValueError):
            return {}, f'Argument "{n}" must be a {t}.'
        clean[n] = v
    return clean, ''


def describe_call(action, args):
    parts = ', '.join(f'{k} = {v}' for k, v in security.redact(args).items())
    return f'{action.description or action.name}' + (f' ({parts})' if parts else '')


def execute_api(app, action, args, user_token=''):
    """Call the client's server. Returns {'status', 'data'} with secrets removed. Raises ActionError."""
    if not app.api_base_url:
        raise ActionError('This app has no API address set.')
    try:
        security.check_url(app.api_base_url)
    except security.UnsafeUrl as e:
        raise ActionError(str(e))
    path, query, body = action.path or '/', {}, {}
    for p in action.params:
        n = p['name']
        if n not in args:
            continue
        if p['in'] == 'path':
            path = path.replace('{' + n + '}', quote(str(args[n]), safe=''))
        elif p['in'] == 'query':
            query[n] = args[n]
        else:
            body[n] = args[n]
    if re.search(r'\{\w+\}', path):
        raise ActionError('A required path value is missing.')
    url = app.api_base_url.rstrip('/') + '/' + path.lstrip('/')
    headers = {'Accept': 'application/json', 'User-Agent': 'Adion-Connect/1.0'}
    if app.api_auth == 'forward':
        if not user_token:
            raise ActionError('The user is not signed in to the app, so I cannot do this.')
        headers['Authorization'] = 'Bearer ' + user_token
    elif app.api_auth == 'header':
        headers.update({str(k): str(v) for k, v in security.decrypt_json(app.api_headers_enc).items()})
    try:
        r = requests.request(action.method, url, params=query or None, json=body or None if action.method != 'GET' else None, headers=headers,
                             timeout=15, allow_redirects=False, stream=True)
        raw = b''
        for chunk in r.iter_content(8192):
            raw += chunk
            if len(raw) > MAX_RESPONSE_BYTES:
                break
        r.close()
    except requests.exceptions.RequestException as e:
        raise ActionError(f'The app server did not answer: {type(e).__name__}')
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except json.JSONDecodeError:
        data = raw.decode('utf-8', errors='replace')[:2000]
    if r.status_code >= 400:
        msg = security.redact(data, action.hide_fields) if isinstance(data, (dict, list)) else data
        raise ActionError(f'The app returned HTTP {r.status_code}: {json.dumps(msg)[:300]}')
    return {'status': r.status_code, 'data': security.redact(data, action.hide_fields)}
