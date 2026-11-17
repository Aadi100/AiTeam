"""
One adapter per service. Every adapter offers the same five operations so the assistant's tools do not care which service an account is:

  mail_search(token, query, limit) · mail_read(token, id) · mail_send(token, to, subject, body, cc)
  calendar_list(token, days) · calendar_create(token, title, start, end, attendees, description, location)

All results are small, plain dicts. Text written by other people (mail bodies, event notes) is cut to a safe length.
"""

import re
import base64
import html as _html
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import requests

from .providers import PROVIDERS

TIMEOUT = 20
MAX_BODY = 6000


class AdapterError(Exception):
    pass


def _call(method, url, token, extra_headers=None, raw=False, **kw):
    try:
        r = requests.request(method, url, headers={'Accept': 'application/json', **(extra_headers or {}), 'Authorization': f'Bearer {token}'}, timeout=TIMEOUT, **kw)
    except requests.exceptions.RequestException as e:
        raise AdapterError(f'could not reach the service: {type(e).__name__}')
    if r.status_code == 401:
        raise AdapterError('The service rejected the sign-in. Reconnect this account.')
    if r.status_code == 403:
        raise AdapterError('The service refused: this account did not give the needed permission. Reconnect it and allow everything.')
    if r.status_code >= 400:
        try:
            msg = (r.json().get('error') or {})
            msg = msg.get('message') if isinstance(msg, dict) else str(msg)
        except ValueError:
            msg = r.text
        raise AdapterError(f'service error {r.status_code}: {str(msg)[:200]}')
    if raw:
        return r.text
    if not r.content:
        return {}
    try:
        return r.json()
    except ValueError:
        return {}


def _local_iso(s):
    """'2026-03-05T14:00' -> with this computer's UTC offset, so the calendar gets an unambiguous time."""
    try:
        d = datetime.fromisoformat(str(s).strip().replace('Z', '+00:00'))
    except ValueError:
        raise AdapterError(f'"{s}" is not a date and time like 2026-03-05T14:00')
    if d.tzinfo is None:
        d = d.astimezone()          # naive = local time of this computer
    return d.isoformat(timespec='seconds')


def _strip_html(t):
    t = re.sub(r'(?is)<(script|style).*?</\1>', ' ', t or '')
    t = re.sub(r'(?i)<br\s*/?>|</p>|</div>', '\n', t)
    t = _html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n', t)).strip()


# ───────────────────────── Google ─────────────────────────
def _g_header(msg, name):
    for h in (msg.get('payload') or {}).get('headers') or []:
        if h.get('name', '').lower() == name.lower():
            return h.get('value', '')
    return ''


def _g_text(payload):
    """The readable text of a Gmail message: prefer text/plain, else strip the HTML."""
    plain, htm = [], []

    def walk(p):
        mt, data = p.get('mimeType', ''), (p.get('body') or {}).get('data')
        if data and mt in ('text/plain', 'text/html'):
            txt = base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', 'replace')
            (plain if mt == 'text/plain' else htm).append(txt)
        for c in p.get('parts') or []:
            walk(c)
    walk(payload or {})
    return '\n'.join(plain) if plain else _strip_html('\n'.join(htm))


class Google:
    gm = PROVIDERS['google']['api']['gmail']
    cal = PROVIDERS['google']['api']['calendar']

    @classmethod
    def mail_search(cls, token, query, limit):
        d = _call('GET', f'{cls.gm}/messages', token, params={'q': query, 'maxResults': limit})
        out = []
        for m in (d.get('messages') or [])[:limit]:
            x = _call('GET', f'{cls.gm}/messages/{m["id"]}', token, params={'format': 'metadata', 'metadataHeaders': ['From', 'Subject', 'Date']})
            out.append({'id': m['id'], 'from': _g_header(x, 'From'), 'subject': _g_header(x, 'Subject'), 'date': _g_header(x, 'Date'), 'snippet': _html.unescape(x.get('snippet', ''))})
        return out

    @classmethod
    def mail_read(cls, token, mid):
        x = _call('GET', f'{cls.gm}/messages/{mid}', token, params={'format': 'full'})
        return {'id': mid, 'from': _g_header(x, 'From'), 'to': _g_header(x, 'To'), 'subject': _g_header(x, 'Subject'), 'date': _g_header(x, 'Date'),
                'body': _g_text(x.get('payload'))[:MAX_BODY]}

    @classmethod
    def mail_send(cls, token, to, subject, body, cc):
        m = EmailMessage()
        m['To'], m['Subject'] = ', '.join(to), subject
        if cc:
            m['Cc'] = ', '.join(cc)
        m.set_content(body)
        raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
        d = _call('POST', f'{cls.gm}/messages/send', token, json={'raw': raw})
        return {'sent': True, 'id': d.get('id', '')}

    @classmethod
    def calendar_list(cls, token, days):
        now = datetime.now(timezone.utc)
        d = _call('GET', f'{cls.cal}/calendars/primary/events', token, params={
            'timeMin': now.isoformat(timespec='seconds'), 'timeMax': (now + timedelta(days=days)).isoformat(timespec='seconds'),
            'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': 40})
        return [{'id': e.get('id'), 'title': e.get('summary', '(no title)'), 'start': (e.get('start') or {}).get('dateTime') or (e.get('start') or {}).get('date'),
                 'end': (e.get('end') or {}).get('dateTime') or (e.get('end') or {}).get('date'), 'location': e.get('location', ''),
                 'attendees': [a.get('email') for a in e.get('attendees') or []][:10]} for e in d.get('items') or []]

    @classmethod
    def calendar_create(cls, token, title, start, end, attendees, description, location):
        body = {'summary': title, 'start': {'dateTime': _local_iso(start)}, 'end': {'dateTime': _local_iso(end)}}
        if attendees:
            body['attendees'] = [{'email': a} for a in attendees]
        if description:
            body['description'] = description
        if location:
            body['location'] = location
        d = _call('POST', f'{cls.cal}/calendars/primary/events', token, json=body, params={'sendUpdates': 'all' if attendees else 'none'})
        return {'created': True, 'id': d.get('id', ''), 'link': d.get('htmlLink', '')}


# ───────────────────────── Microsoft ─────────────────────────
class Microsoft:
    g = PROVIDERS['microsoft']['api']['graph']

    @classmethod
    def mail_search(cls, token, query, limit):
        params = {'$top': limit, '$select': 'id,subject,from,receivedDateTime,bodyPreview'}
        if query:
            params['$search'] = '"' + query.replace('"', ' ') + '"'
        d = _call('GET', f'{cls.g}/me/messages', token, params=params)
        return [{'id': m['id'], 'from': ((m.get('from') or {}).get('emailAddress') or {}).get('address', ''), 'subject': m.get('subject', ''),
                 'date': m.get('receivedDateTime', ''), 'snippet': m.get('bodyPreview', '')[:200]} for m in d.get('value') or []]

    @classmethod
    def mail_read(cls, token, mid):
        m = _call('GET', f'{cls.g}/me/messages/{mid}', token)
        b = m.get('body') or {}
        text = _strip_html(b.get('content', '')) if b.get('contentType') == 'html' else b.get('content', '')
        return {'id': mid, 'from': ((m.get('from') or {}).get('emailAddress') or {}).get('address', ''),
                'to': ', '.join(((r.get('emailAddress') or {}).get('address', '')) for r in m.get('toRecipients') or []), 'subject': m.get('subject', ''),
                'date': m.get('receivedDateTime', ''), 'body': text[:MAX_BODY]}

    @classmethod
    def mail_send(cls, token, to, subject, body, cc):
        rec = lambda xs: [{'emailAddress': {'address': a}} for a in xs]  # noqa: E731
        _call('POST', f'{cls.g}/me/sendMail', token, json={'message': {'subject': subject, 'body': {'contentType': 'Text', 'content': body},
                                                                       'toRecipients': rec(to), 'ccRecipients': rec(cc)}})
        return {'sent': True}

    @classmethod
    def calendar_list(cls, token, days):
        now = datetime.now(timezone.utc)
        d = _call('GET', f'{cls.g}/me/calendarView', token, params={'startDateTime': now.isoformat(timespec='seconds'),
                                                                    'endDateTime': (now + timedelta(days=days)).isoformat(timespec='seconds'),
                                                                    '$orderby': 'start/dateTime', '$top': 40}, )
        return [{'id': e.get('id'), 'title': e.get('subject', '(no title)'), 'start': (e.get('start') or {}).get('dateTime'), 'end': (e.get('end') or {}).get('dateTime'),
                 'location': (e.get('location') or {}).get('displayName', ''),
                 'attendees': [((a.get('emailAddress') or {}).get('address', '')) for a in e.get('attendees') or []][:10]} for e in d.get('value') or []]

    @classmethod
    def calendar_create(cls, token, title, start, end, attendees, description, location):
        def when(s):
            d = datetime.fromisoformat(_local_iso(s)).astimezone(timezone.utc)
            return {'dateTime': d.strftime('%Y-%m-%dT%H:%M:%S'), 'timeZone': 'UTC'}
        body = {'subject': title, 'start': when(start), 'end': when(end)}
        if attendees:
            body['attendees'] = [{'emailAddress': {'address': a}, 'type': 'required'} for a in attendees]
        if description:
            body['body'] = {'contentType': 'Text', 'content': description}
        if location:
            body['location'] = {'displayName': location}
        d = _call('POST', f'{cls.g}/me/events', token, json=body)
        return {'created': True, 'id': d.get('id', ''), 'link': d.get('webLink', '')}


ADAPTERS = {'google': Google, 'microsoft': Microsoft}
