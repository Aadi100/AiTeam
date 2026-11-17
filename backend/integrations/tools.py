"""
The tools the assistant can use on a user's connected accounts, and the rules for them. Safety lives here, never in the prompt:
reads run by themselves, anything that changes something outside Adion is shown to the user first and runs only after they approve.
"""

import re
import json
from urllib.parse import quote

from . import oauth, mcp
from .adapters import ADAPTERS, AdapterError, _call
from .providers import PROVIDERS

EMAIL = re.compile(r'^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$')
MAX_RESULT = 8000


class ToolError(Exception):
    pass


def _obj(props, required=()):
    return {'type': 'object', 'properties': props, 'required': list(required)}


ACCOUNT = {'type': 'string', 'description': 'Which connected account (its email or service name). Optional when there is only one that fits.'}
LIST_OF_EMAILS = {'type': 'array', 'items': {'type': 'string'}}

SPECS = {
    'mail_search': ('Search the user\'s email. Use the service\'s normal search syntax (from:, subject:, is:unread, newer_than:7d...). Returns id, sender, subject, date, snippet.',
                    _obj({'account': ACCOUNT, 'query': {'type': 'string'}, 'limit': {'type': 'integer', 'description': 'max 15, default 8'}})),
    'mail_read': ('Read one email in full by id (from mail_search).', _obj({'account': ACCOUNT, 'id': {'type': 'string'}}, ['id'])),
    'mail_send': ('Send an email. The user must approve it first.',
                  _obj({'account': ACCOUNT, 'to': LIST_OF_EMAILS, 'subject': {'type': 'string'}, 'body': {'type': 'string'}, 'cc': LIST_OF_EMAILS}, ['to', 'subject', 'body'])),
    'calendar_list': ('List upcoming calendar events.', _obj({'account': ACCOUNT, 'days': {'type': 'integer', 'description': 'how many days ahead, default 7, max 60'}})),
    'calendar_create': ('Create a calendar event. Times are ISO 8601 like 2026-03-05T14:00 (local time when no offset is given). The user must approve it first.',
                        _obj({'account': ACCOUNT, 'title': {'type': 'string'}, 'start': {'type': 'string'}, 'end': {'type': 'string'}, 'attendees': LIST_OF_EMAILS,
                              'description': {'type': 'string'}, 'location': {'type': 'string'}}, ['title', 'start', 'end'])),
    'service_api': ('Call the REST API of ANY connected service (files, tasks, repos, messages, posts...) using that service\'s own documented API. '
                    'GET requests run at once. Anything that creates, changes or deletes needs the user\'s approval first. '
                    'Never guess ids: list or search first. path is relative to the service API base (for example /repos/OWNER/REPO/issues).',
                    _obj({'account': ACCOUNT, 'api': {'type': 'string', 'description': 'which API of the service when it has several (Google: gmail, calendar, drive, docs, sheets, tasks)'},
                          'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']}, 'path': {'type': 'string'},
                          'query': {'type': 'object'}, 'body': {'type': 'object'}}, ['account', 'method', 'path'])),
}
READ_TOOLS = ('mail_search', 'mail_read', 'calendar_list')


def specs_for(links):
    """The tool list for the accounts this user has connected."""
    accounts = [l for l in links if l.provider != 'mcp']
    caps = {c for l in accounts for c in PROVIDERS[l.provider]['caps']}
    names = [n for n, need in (('mail_search', 'mail'), ('mail_read', 'mail'), ('mail_send', 'mail'), ('calendar_list', 'calendar'), ('calendar_create', 'calendar')) if need in caps]
    if accounts:
        names.append('service_api')
    return [{'type': 'function', 'function': {'name': n, 'description': SPECS[n][0], 'parameters': SPECS[n][1]}} for n in names] + mcp.specs(links)


def pick(links, account, cap=None, service=None):
    """Choose the connected account a call is meant for."""
    links = [l for l in links if l.provider != 'mcp']
    pool = [l for l in links if not cap or cap in PROVIDERS[l.provider]['caps']]
    a = str(account or '').strip().lower()
    if a:
        hit = [l for l in pool if a in (l.email.lower(), l.link_id.lower(), l.provider) or a in l.email.lower() or a in PROVIDERS[l.provider]['name'].lower()]
        if len(hit) == 1:
            return hit[0]
        if len(hit) > 1:
            raise ToolError('Several accounts match; say which one: ' + ', '.join(f'{l.email} ({l.provider})' for l in hit))
        raise ToolError(f'No connected account matches "{account}". Connected: ' + (', '.join(f'{l.email} ({l.provider})' for l in links) or 'none'))
    if len(pool) == 1:
        return pool[0]
    if not pool:
        raise ToolError('No connected account can do that. Ask the user to connect one in the Apps tab.')
    raise ToolError('Which account? Connected: ' + ', '.join(f'{l.email} ({l.provider})' for l in pool))


def _emails(v, what):
    items = [x.strip() for x in (v.split(',') if isinstance(v, str) else v or []) if str(x).strip()]
    if len(items) > 10 or any(not EMAIL.match(x) for x in items):
        raise ToolError(f'"{what}" must be up to 10 valid email addresses.')
    return items


def _safe_path(path):
    path = str(path or '').strip()
    if not path.startswith('/') or '//' in path or '..' in path or '\\' in path or re.search(r'[\s#?]', path) or len(path) > 400:
        raise ToolError('path must start with / and be a plain path (put parameters in "query").')
    return path


def clean(tool, args, links):
    """Validate the model's arguments. -> (link, cleaned args). Raises ToolError with a message the model can act on."""
    if tool.startswith('mcp_'):
        try:
            return mcp.clean(tool, args, links)
        except mcp.McpError as e:
            raise ToolError(str(e))
    if not isinstance(args, dict):
        raise ToolError('arguments must be an object')
    cap = 'mail' if tool.startswith('mail_') else 'calendar' if tool.startswith('calendar_') else None
    link = pick(links, args.get('account'), cap)
    out = {}
    if tool == 'mail_search':
        out = {'query': str(args.get('query') or '')[:300], 'limit': max(1, min(15, int(args.get('limit') or 8)))}
    elif tool == 'mail_read':
        mid = str(args.get('id') or '')
        if not re.match(r'^[\w.=-]{1,200}$', mid):
            raise ToolError('id looks wrong; use an id from mail_search')
        out = {'id': mid}
    elif tool == 'mail_send':
        to = _emails(args.get('to'), 'to')
        if not to:
            raise ToolError('"to" needs at least one email address')
        subj, body = str(args.get('subject') or '').strip(), str(args.get('body') or '')
        if not subj or not body.strip() or len(subj) > 200 or len(body) > 8000 or re.search(r'[\r\n]', subj):
            raise ToolError('subject (one line, up to 200 chars) and body (up to 8000 chars) are required')
        out = {'to': to, 'cc': _emails(args.get('cc'), 'cc'), 'subject': subj, 'body': body}
    elif tool == 'calendar_list':
        out = {'days': max(1, min(60, int(args.get('days') or 7)))}
    elif tool == 'calendar_create':
        title = str(args.get('title') or '').strip()[:200]
        if not title or not args.get('start') or not args.get('end'):
            raise ToolError('title, start and end are required')
        out = {'title': title, 'start': str(args['start']), 'end': str(args['end']), 'attendees': _emails(args.get('attendees'), 'attendees'),
               'description': str(args.get('description') or '')[:2000], 'location': str(args.get('location') or '')[:200]}
    elif tool == 'service_api':
        p = PROVIDERS[link.provider]
        api = str(args.get('api') or '').strip().lower() or next(iter(p['api']))
        if api not in p['api']:
            raise ToolError(f'api must be one of: {", ".join(p["api"])}')
        method = str(args.get('method') or 'GET').upper()
        if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
            raise ToolError('method must be GET, POST, PUT, PATCH or DELETE')
        q, b = args.get('query') or {}, args.get('body')
        if not isinstance(q, dict) or (b is not None and not isinstance(b, (dict, list))):
            raise ToolError('query and body must be objects')
        if len(json.dumps(b or {})) > 20000:
            raise ToolError('body is too large')
        out = {'api': api, 'method': method, 'path': _safe_path(args.get('path')), 'query': {str(k)[:60]: str(v)[:300] for k, v in list(q.items())[:20]}, 'body': b}
    else:
        raise ToolError(f'unknown tool {tool}')
    return link, out


def risk(tool, args, link):
    """'read' runs at once; 'change' and 'danger' need the user's approval."""
    if link.provider == 'mcp':
        return mcp.risk(tool, link)
    if tool in READ_TOOLS:
        return 'read'
    if tool == 'service_api':
        p, m, path = PROVIDERS[link.provider], args['method'], args['path']
        if m == 'GET':
            return 'read'
        if m == 'DELETE':
            return 'danger'
        if m == 'POST' and any(path.startswith(x) for x in p['safe_post']):
            return 'read'
        if p['graphql'] and isinstance(args.get('body'), dict):
            qtext = str(args['body'].get('query', '')).lstrip()
            if qtext.startswith('{') or qtext.startswith('query'):
                return 'read'
        return 'change'
    return 'change'


def preview(tool, args, link):
    if link.provider == 'mcp':
        return mcp.preview(tool, args, link)
    who = f'{link.email} ({link.provider})'
    if tool == 'mail_search':
        return f'Search {who} mail for "{args["query"]}"'
    if tool == 'mail_read':
        return f'Read an email in {who}'
    if tool == 'mail_send':
        cc = f', cc {", ".join(args["cc"])}' if args['cc'] else ''
        return f'SEND EMAIL from {who} to {", ".join(args["to"])}{cc}\nSubject: {args["subject"]}\n\n{args["body"][:1200]}'
    if tool == 'calendar_list':
        return f'Look at the next {args["days"]} days of {who} calendar'
    if tool == 'calendar_create':
        att = f'\nInviting: {", ".join(args["attendees"])} (they get an invitation)' if args['attendees'] else ''
        return f'CREATE EVENT in {who}: {args["title"]}\n{args["start"]} to {args["end"]}{att}' + (f'\nPlace: {args["location"]}' if args['location'] else '')
    body = f'\n{json.dumps(args["body"], ensure_ascii=False)[:800]}' if args.get('body') else ''
    return f'{args["method"]} {args["api"]} {args["path"]} on {who}{body}'


def _service_api(link, token, a):
    p = PROVIDERS[link.provider]
    url = p['api'][a['api']] + quote(a['path'], safe='/:@!$&\'()*+,;=-._~%')
    kw = {'params': a['query']} if a['query'] else {}
    if a['body'] is not None:
        kw['json'] = a['body']
    txt = _call(a['method'], url, token, extra_headers=p['api_headers'], raw=True, **kw)
    try:
        return json.loads(txt) if txt else {'ok': True}
    except ValueError:
        return {'text': txt[:MAX_RESULT]}


def run(link, tool, args):
    """Execute a validated call. -> JSON-able result (cut to a safe size). Raises ToolError."""
    if link.provider == 'mcp':
        try:
            return mcp.run(link, tool, args)
        except mcp.McpError as e:
            raise ToolError(str(e))
    ad = ADAPTERS.get(link.provider)

    def go(token):
        if tool == 'mail_search':
            return ad.mail_search(token, args['query'], args['limit'])
        if tool == 'mail_read':
            return ad.mail_read(token, args['id'])
        if tool == 'mail_send':
            return ad.mail_send(token, args['to'], args['subject'], args['body'], args['cc'])
        if tool == 'calendar_list':
            return ad.calendar_list(token, args['days'])
        if tool == 'calendar_create':
            return ad.calendar_create(token, args['title'], args['start'], args['end'], args['attendees'], args['description'], args['location'])
        return _service_api(link, token, args)
    try:
        try:
            res = go(oauth.access_token(link))
        except AdapterError as e:
            if 'rejected the sign-in' not in str(e):
                raise
            res = go(oauth.access_token(link, force=True))      # the token was revoked or expired early: refresh once and retry
    except (AdapterError, oauth.OAuthError) as e:
        raise ToolError(str(e))
    text = json.dumps(res, ensure_ascii=False)
    if len(text) > MAX_RESULT:
        text = text[:MAX_RESULT] + ' ...(cut)'
    return text
