"""
MCP tool servers (Model Context Protocol): a ready-made kit of tools Adion can use, for example a Zapier MCP link (thousands of apps),
or any other server that speaks MCP over HTTPS.

Every person adds their OWN link, so what Adion does through it happens in that person's accounts and nobody else's.
This is a small client for MCP's "streamable HTTP" transport (JSON-RPC 2.0 over POST; the reply is JSON or a server-sent event).

Safety, same rules as the other account tools:
  - the address and token are stored encrypted and are never sent back to the browser or to the AI;
  - only public https addresses are called (no localhost / private networks), redirects are not followed, replies are size-capped;
  - tools whose name or hints say they only look things up run at once; EVERYTHING else is shown to the user and waits for Approve;
  - tool descriptions and tool results come from someone else: they are treated as data, never as instructions.
"""

import re
import json
import uuid
import hashlib
from datetime import datetime
from urllib.parse import urlparse

import requests

from connect import security
from .models import McpServer

PROTOCOL = '2025-03-26'
MAX_BODY = 1_000_000
MAX_SERVERS = 5
MAX_TOOLS = 100
MAX_RESULT = 8000
MAX_ARGS = 20000


class McpError(Exception):
    pass


# ───────────────────────── the wire ─────────────────────────

class Session:
    """One conversation with one server: initialize, then any number of requests."""

    def __init__(self, url, token=''):
        self.url, self.token, self.sid, self.n = url, token.strip(), '', 0

    def _headers(self):
        h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL, 'User-Agent': 'Adion'}
        if self.token:
            h['Authorization'] = self.token if re.match(r'(?i)(bearer|basic) ', self.token) else 'Bearer ' + self.token
        if self.sid:
            h['Mcp-Session-Id'] = self.sid
        return h

    def _post(self, payload, want_id=None):
        try:
            security.check_url(self.url)
        except security.UnsafeUrl as e:
            raise McpError(str(e))
        try:
            r = requests.post(self.url, json=payload, headers=self._headers(), timeout=(10, 60), stream=True, allow_redirects=False)
        except requests.exceptions.RequestException as e:
            raise McpError(f'Could not reach the tool server: {type(e).__name__}')
        try:
            if 300 <= r.status_code < 400:
                raise McpError('The tool server tried to redirect Adion somewhere else, which is not allowed.')
            if r.status_code in (401, 403):
                raise McpError('The tool server refused the sign-in (401/403). Check the link or token.')
            if r.status_code >= 400:
                raise McpError(f'The tool server answered with an error ({r.status_code}).')
            sid = r.headers.get('Mcp-Session-Id')
            if sid:
                self.sid = sid
            if want_id is None:
                return None
            body, size = [], 0
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > MAX_BODY:
                    raise McpError('The tool server sent a reply that is too large.')
                body.append(chunk)
            raw = b''.join(body).decode('utf-8', 'replace')
            ctype = r.headers.get('Content-Type', '')
        finally:
            r.close()
        msgs = []
        try:
            if 'text/event-stream' in ctype:
                for ev in re.split(r'\r?\n\r?\n', raw):
                    data = '\n'.join(l[5:].strip() for l in ev.splitlines() if l.startswith('data:'))
                    if data:
                        msgs.append(json.loads(data))
            else:
                j = json.loads(raw)
                msgs = j if isinstance(j, list) else [j]
        except ValueError:
            raise McpError('The tool server sent a reply Adion could not read.')
        for m in msgs:
            if isinstance(m, dict) and m.get('id') == want_id:
                if m.get('error'):
                    raise McpError(str((m['error'] or {}).get('message') or 'the tool server reported an error')[:300])
                return m.get('result') or {}
        raise McpError('The tool server did not answer the request.')

    def request(self, method, params=None):
        self.n += 1
        return self._post({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}}, self.n)

    def open(self):
        self.request('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'Adion', 'version': '1.0'}})
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return self

    def close(self):
        if self.sid:
            try:
                requests.delete(self.url, headers=self._headers(), timeout=5, allow_redirects=False)
            except requests.exceptions.RequestException:
                pass

    def __enter__(self):
        return self.open()

    def __exit__(self, *a):
        self.close()
        return False


# ───────────────────────── tools: what is a read, what changes things ─────────────────────────

READ_WORDS = {'get', 'list', 'search', 'find', 'read', 'fetch', 'lookup', 'look', 'check', 'view', 'show', 'query', 'retrieve', 'count', 'describe', 'browse'}
WRITE_WORDS = {'send', 'create', 'update', 'delete', 'remove', 'add', 'post', 'write', 'reply', 'forward', 'archive', 'move', 'upload', 'share', 'invite', 'publish', 'set',
               'edit', 'append', 'cancel', 'book', 'pay', 'buy', 'trigger', 'run', 'execute', 'submit', 'approve', 'merge', 'close', 'assign', 'schedule', 'make', 'save',
               'insert', 'clear', 'drop', 'reset', 'revoke', 'grant', 'transfer', 'rename', 'copy', 'import', 'sync', 'start', 'stop', 'enable', 'disable', 'lock', 'unlock',
               'block', 'tag', 'label', 'mark', 'star', 'like', 'follow', 'comment', 'respond', 'dispatch', 'call', 'order', 'subscribe', 'unsubscribe', 'tweet', 'message'}


def is_read(name, annotations):
    """True only when it is clearly a lookup. When in doubt it is a change, so the user is asked."""
    ann = annotations if isinstance(annotations, dict) else {}
    if ann.get('destructiveHint') is True:
        return False
    if ann.get('readOnlyHint') is True:
        return True
    words = set(w for w in re.split(r'[^a-z0-9]+', re.sub(r'([a-z])([A-Z])', r'\1_\2', str(name)).lower()) if w)
    return bool(words & READ_WORDS) and not (words & WRITE_WORDS)


def slugify(name):
    s = re.sub(r'[^a-z0-9]+', '_', str(name).lower()).strip('_')[:14]
    return s or 'tools'


def alias(slug, tool):
    """The name the AI sees: unique per server and within the 64-character limit models allow."""
    a = re.sub(r'[^A-Za-z0-9_-]', '_', f'mcp_{slug}_{tool}')
    if len(a) > 64:
        a = a[:55] + '_' + hashlib.md5(a.encode()).hexdigest()[:8]
    return a


def _schema(s):
    s = s if isinstance(s, dict) else {}
    s = {k: v for k, v in s.items() if k != '$schema'}
    if s.get('type') != 'object':
        s = {'type': 'object', 'properties': {}}
    s.setdefault('properties', {})
    return s


def _clean_text(t, n):
    return re.sub(r'\s+', ' ', str(t or '')).strip()[:n]


def fetch_tools(url, token, slug):
    """Ask a server what it can do. -> list of {name, alias, desc, schema, read}. Raises McpError."""
    out, cursor = [], None
    with Session(url, token) as s:
        for _ in range(5):
            res = s.request('tools/list', {'cursor': cursor} if cursor else {})
            for t in res.get('tools') or []:
                if not isinstance(t, dict) or not t.get('name'):
                    continue
                out.append({'name': str(t['name'])[:120], 'alias': alias(slug, str(t['name'])[:120]), 'desc': _clean_text(t.get('description') or t.get('title'), 400),
                            'schema': _schema(t.get('inputSchema')), 'read': is_read(t['name'], t.get('annotations'))})
            cursor = res.get('nextCursor')
            if not cursor or len(out) >= MAX_TOOLS:
                break
    return out[:MAX_TOOLS]


# ───────────────────────── a user's servers ─────────────────────────

class McpLink:
    """A tool server shaped like a connected account, so the account engine can show it, approve it and log it the same way."""
    provider = 'mcp'

    def __init__(self, server):
        self.server = server
        self.link_id = server.server_id
        self.email = server.name


def servers_for(owner):
    return list(McpServer.objects(owner=owner).order_by('created_at'))


def links_for(owner):
    return [McpLink(s) for s in servers_for(owner) if s.status == 'ok' and s.tools]


def _conn(server):
    c = security.decrypt_json(server.conn_enc)
    return c.get('url', ''), c.get('token', '')


def add(owner, name, url, token=''):
    """Check the server works, then save it. Raises McpError with a message for the person."""
    name = _clean_text(name, 40)
    url = str(url or '').strip()
    if not name:
        raise McpError('Give the tool server a name.')
    if not re.match(r'^https?://', url) or len(url) > 1000:
        raise McpError('The link must start with https://')
    if McpServer.objects(owner=owner).count() >= MAX_SERVERS:
        raise McpError(f'You can connect up to {MAX_SERVERS} tool servers. Remove one first.')
    slug, taken = slugify(name), {s.slug for s in McpServer.objects(owner=owner)}
    base, i = slug, 2
    while slug in taken:
        slug, i = f'{base[:11]}_{i}', i + 1
    tools = fetch_tools(url, str(token or ''), slug)
    if not tools:
        raise McpError('The tool server answered but has no tools yet. In Zapier, add some actions to the server first.')
    s = McpServer(server_id='mc_' + uuid.uuid4().hex[:10], owner=owner, name=name, slug=slug, host=urlparse(url).hostname or '',
                  conn_enc=security.encrypt_json({'url': url, 'token': str(token or '').strip()}), tools=tools, status='ok', checked_at=datetime.utcnow())
    s.save()
    return s


def refresh(server):
    url, token = _conn(server)
    try:
        tools = fetch_tools(url, token, server.slug)
        server.update(set__tools=tools, set__status='ok', set__error='', set__checked_at=datetime.utcnow())
    except McpError as e:
        server.update(set__status='error', set__error=str(e)[:300], set__checked_at=datetime.utcnow())
        raise
    server.reload()
    return server


# ───────────────────────── what the account engine calls ─────────────────────────

def specs(links):
    """Tool definitions (OpenAI style, translated for Claude when needed) for the tool servers among these links."""
    out = []
    for l in links:
        if l.provider != 'mcp':
            continue
        for t in l.server.tools:
            out.append({'type': 'function', 'function': {'name': t['alias'], 'description': f'[tool server "{l.server.name}"] {t["desc"]}'[:500], 'parameters': t['schema']}})
    return out


def find(tool, links):
    for l in links:
        if l.provider == 'mcp':
            for t in l.server.tools:
                if t['alias'] == tool:
                    return l, t
    raise McpError(f'unknown tool {tool}')


def clean(tool, args, links):
    link, t = find(tool, links)
    if not isinstance(args, dict):
        raise McpError('arguments must be an object')
    if len(json.dumps(args, ensure_ascii=False)) > MAX_ARGS:
        raise McpError('arguments are too large')
    missing = [k for k in (t['schema'].get('required') or []) if k not in args]
    if missing:
        raise McpError('missing required: ' + ', '.join(str(m) for m in missing[:8]))
    return link, args


def risk(tool, link):
    for t in link.server.tools:
        if t['alias'] == tool:
            return 'read' if t['read'] else 'change'
    return 'change'


def preview(tool, args, link):
    t = next((x for x in link.server.tools if x['alias'] == tool), {'name': tool})
    shown = json.dumps(args, ensure_ascii=False)[:900]
    return f'{"LOOK UP" if t.get("read") else "RUN"} "{t["name"]}" on tool server "{link.server.name}"\n{shown}'


def run(link, tool, args):
    """Call one tool. -> text (cut to a safe size). Raises McpError."""
    t = next((x for x in link.server.tools if x['alias'] == tool), None)
    if not t:
        raise McpError('that tool no longer exists on the server')
    url, token = _conn(link.server)
    with Session(url, token) as s:
        res = s.request('tools/call', {'name': t['name'], 'arguments': args})
    parts = []
    for c in res.get('content') or []:
        if isinstance(c, dict) and c.get('type') == 'text':
            parts.append(str(c.get('text') or ''))
        elif isinstance(c, dict):
            parts.append(f'[{c.get("type", "data")} omitted]')
    if not parts and res.get('structuredContent') is not None:
        parts.append(json.dumps(res['structuredContent'], ensure_ascii=False))
    text = '\n'.join(parts) or 'ok'
    if res.get('isError'):
        raise McpError(text[:300])
    return text[:MAX_RESULT] + (' ...(cut)' if len(text) > MAX_RESULT else '')
