"""Linked accounts (Gmail, Calendar, ...): the owner's OAuth app settings, each user's connected accounts, and their tasks."""

from datetime import datetime
import mongoengine as me


class IntegrationConfig(me.Document):
    """The OAuth app of a provider (created once by the owner, shared by everyone: users just press Connect)."""
    provider = me.StringField(unique=True, required=True)
    client_id = me.StringField(default='')
    client_secret_enc = me.StringField(default='')
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'ig_config'}


class LinkedAccount(me.Document):
    link_id = me.StringField(unique=True, required=True)
    owner = me.StringField(required=True)            # the Adion username
    provider = me.StringField(required=True)         # google | microsoft
    email = me.StringField(default='')
    tokens_enc = me.StringField(default='')          # encrypted {access, refresh, exp}
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'ig_links', 'indexes': ['owner', ('owner', 'provider', 'email')]}

    def to_dict(self):
        return {'id': self.link_id, 'provider': self.provider, 'email': self.email, 'createdAt': self.created_at.isoformat() + 'Z'}


class AppTask(me.Document):
    """One request to Adion about the user's accounts. Same shape as a PC task so the same card shows it."""
    task_id = me.StringField(unique=True, required=True)
    owner = me.StringField(required=True)
    run_id = me.StringField(default='')
    request = me.StringField(default='')
    status = me.StringField(default='planning')      # planning|running|awaiting_approval|done|failed|denied|cancelled
    say = me.StringField(default='')
    steps = me.ListField(me.DictField(), default=list)
    state = me.DictField(default=dict)               # {messages: [...], pending: [{call_id, step_id}]}
    untrusted = me.BooleanField(default=False)       # the plan was made after reading mail/events written by others
    error = me.StringField(default='')
    created_at = me.DateTimeField(default=datetime.utcnow)
    ended_at = me.DateTimeField()

    meta = {'collection': 'ig_tasks', 'ordering': ['-created_at'], 'indexes': ['task_id', 'owner']}

    def to_dict(self):
        steps = [{k: (v[:1500] if isinstance(v, str) else v) for k, v in s.items() if k not in ('args', 'call_id')} for s in self.steps]
        return {'id': self.task_id, 'runId': self.run_id, 'request': self.request, 'status': self.status, 'say': self.say, 'steps': steps,
                'pendingFolders': [], 'pendingPhase': 'propose' if self.status == 'awaiting_approval' else '', 'untrusted': self.untrusted,
                'error': self.error, 'undoable': 0, 'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None}


class AppLog(me.Document):
    """Everything Adion did in an account (also used to limit sends per hour)."""
    owner = me.StringField(required=True)
    task_id = me.StringField(default='')
    tool = me.StringField(default='')
    account = me.StringField(default='')
    summary = me.StringField(default='')
    ok = me.BooleanField(default=True)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'ig_log', 'ordering': ['-created_at'], 'indexes': ['owner', '-created_at']}

    def to_dict(self):
        return {'id': str(self.id), 'taskId': self.task_id, 'tool': self.tool, 'account': self.account, 'summary': self.summary, 'ok': self.ok,
                'createdAt': self.created_at.isoformat() + 'Z'}


class McpServer(me.Document):
    """A tool server (MCP) a user added, for example their own Zapier link. The address and token are stored encrypted; only the host is ever shown."""
    server_id = me.StringField(unique=True, required=True)
    owner = me.StringField(required=True)
    name = me.StringField(default='')
    slug = me.StringField(default='')
    host = me.StringField(default='')
    conn_enc = me.StringField(default='')            # encrypted {url, token}
    tools = me.ListField(me.DictField(), default=list)    # [{name, alias, desc, schema, read}]
    status = me.StringField(default='ok')            # ok | error
    error = me.StringField(default='')
    created_at = me.DateTimeField(default=datetime.utcnow)
    checked_at = me.DateTimeField()

    meta = {'collection': 'ig_mcp', 'indexes': ['owner']}

    def to_dict(self):
        return {'id': self.server_id, 'name': self.name, 'host': self.host, 'status': self.status, 'error': self.error,
                'tools': [{'name': t['name'], 'read': bool(t.get('read')), 'desc': t.get('desc', '')[:160]} for t in self.tools],
                'createdAt': self.created_at.isoformat() + 'Z'}
