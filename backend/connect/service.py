"""Chat entry points shared by the public SDK API and the portal's test chat."""

import time
import uuid
from collections import defaultdict, deque

from . import runtime
from .models import Conversation

_hits = defaultdict(deque)
PER_USER_PER_MIN = 30
PER_APP_PER_MIN = 600


class RateLimited(Exception):
    pass


def rate_check(app, identity):
    now = time.time()
    for key, limit in (((app.app_id, identity['id']), PER_USER_PER_MIN), ((app.app_id, '*'), PER_APP_PER_MIN)):
        q = _hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            raise RateLimited('Too many messages. Please wait a moment.')
        q.append(now)


def identity_for(user_id='', name='', portal=''):
    if portal:
        return {'id': f'portal:{portal}', 'user': portal, 'name': 'tester', 'identified': True}
    if user_id:
        return {'id': f'u:{user_id}', 'user': user_id, 'name': name, 'identified': True}
    return {'id': 'anon', 'user': '', 'name': '', 'identified': False}


def get_conv(app, identity, conv_id, create=True):
    """The caller's own conversation, a new one, or None if the id belongs to someone else."""
    if conv_id:
        c = Conversation.objects(conv_id=str(conv_id), app_id=app.app_id).first()
        if not c:
            return None
        ok = c.end_user == identity['id'] if identity['identified'] else c.end_user.startswith('anon')
        return c if ok else None
    if not create:
        return None
    owner = identity['id'] if identity['identified'] else 'anon:' + uuid.uuid4().hex[:8]
    return Conversation(conv_id='cv_' + uuid.uuid4().hex[:16], app_id=app.app_id, client_id=app.client_id, end_user=owner).save()


def do_chat(app, identity, body):
    rate_check(app, identity)
    conv = get_conv(app, identity, body.get('conversationId'))
    if conv is None:
        raise runtime.ConnectError('That conversation was not found.')
    return runtime.chat(app, identity, conv, str(body.get('message') or ''), str(body.get('userToken') or ''))


def do_confirm(app, identity, body):
    rate_check(app, identity)
    conv = get_conv(app, identity, body.get('conversationId'), create=False)
    if conv is None:
        raise runtime.ConnectError('That conversation was not found.')
    return runtime.resolve(app, identity, conv, [{'callId': d.get('callId'), 'approve': d.get('approve')} for d in (body.get('decisions') or []) if isinstance(d, dict)],
                           str(body.get('userToken') or ''))


def do_result(app, identity, body):
    rate_check(app, identity)
    conv = get_conv(app, identity, body.get('conversationId'), create=False)
    if conv is None:
        raise runtime.ConnectError('That conversation was not found.')
    ds = []
    for r in body.get('results') or []:
        if isinstance(r, dict):
            d = {'callId': r.get('callId')}
            if 'error' in r:
                d['error'] = r['error']
            else:
                d['result'] = r.get('result')
            ds.append(d)
    return runtime.resolve(app, identity, conv, ds, str(body.get('userToken') or ''))
