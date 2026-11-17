"""
Adion Connect data models: clients (people who sign up on the platform), their projects and apps, what Adion knows about an app,
what it may do in it, the app's end users, their conversations, and the owner's pricing settings.
Every document that holds client data carries client_id and app_id, and every query filters by them.
"""

from datetime import datetime
import mongoengine as me


class Client(me.Document):
    """Someone who signed up on the Adion platform to connect their own apps."""
    client_id = me.StringField(unique=True, required=True)
    email = me.StringField(unique=True, required=True)
    name = me.StringField(default='')
    password_hash = me.StringField(required=True)
    status = me.StringField(default='active')         # active | blocked | pending
    verified = me.BooleanField(default=True)
    cap_usd = me.FloatField(default=0.0)              # monthly spend cap for the whole client (0 = use the owner's default)
    created_at = me.DateTimeField(default=datetime.utcnow)
    last_login = me.DateTimeField()

    meta = {'collection': 'cn_clients'}

    def to_dict(self):
        return {'id': self.client_id, 'email': self.email, 'name': self.name, 'status': self.status, 'capUsd': self.cap_usd,
                'createdAt': self.created_at.isoformat() + 'Z', 'lastLogin': self.last_login.isoformat() + 'Z' if self.last_login else None}


class Project(me.Document):
    project_id = me.StringField(unique=True, required=True)
    client_id = me.StringField(required=True)
    name = me.StringField(required=True)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'cn_projects', 'indexes': ['client_id']}

    def to_dict(self):
        return {'id': self.project_id, 'name': self.name, 'createdAt': self.created_at.isoformat() + 'Z'}


class ConnectApp(me.Document):
    """One connected app / website / mobile app, with its keys, rules, access level and API connection."""
    app_id = me.StringField(unique=True, required=True)
    project_id = me.StringField(required=True)
    client_id = me.StringField(required=True)
    name = me.StringField(required=True)
    platform = me.StringField(default='web')          # web | react-native | other (only changes the docs shown)
    public_key = me.StringField(unique=True, required=True)     # pk_...  (safe to put in the app)
    secret_hash = me.StringField(default='')                    # sha256 of sk_...  (shown once)
    secret_prefix = me.StringField(default='')
    allowed_origins = me.ListField(me.StringField(), default=list)   # sites allowed to use the public key
    allow_native = me.BooleanField(default=True)                      # mobile apps send no Origin header
    description = me.StringField(default='')          # what the app is, in the client's own words
    rules = me.StringField(default='')                # "never promise refunds", "always ask for the order number"
    persona = me.StringField(default='')              # name / tone of the assistant
    greeting = me.StringField(default='')
    strict_scope = me.BooleanField(default=True)      # refuse anything unrelated to this app
    language = me.StringField(default='auto')         # auto = reply in the user's language
    access_level = me.StringField(default='limited')  # limited (read only) | standard (changes need confirmation) | complete
    web_search = me.BooleanField(default=False)
    api_base_url = me.StringField(default='')
    api_auth = me.StringField(default='forward')      # forward (the user's own token) | header (a fixed key) | none
    api_headers_enc = me.StringField(default='')      # encrypted {header: value} sent with every API call
    monthly_cap_usd = me.FloatField(default=0.0)      # 0 = no cap beyond the client's
    enabled = me.BooleanField(default=True)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'cn_apps', 'indexes': ['client_id', 'project_id']}

    def to_dict(self):
        return {'id': self.app_id, 'projectId': self.project_id, 'name': self.name, 'platform': self.platform, 'publicKey': self.public_key,
                'secretPrefix': self.secret_prefix, 'allowedOrigins': self.allowed_origins, 'allowNative': self.allow_native,
                'description': self.description, 'rules': self.rules, 'persona': self.persona, 'greeting': self.greeting,
                'strictScope': self.strict_scope, 'language': self.language, 'accessLevel': self.access_level, 'webSearch': self.web_search,
                'apiBaseUrl': self.api_base_url, 'apiAuth': self.api_auth, 'hasApiHeaders': bool(self.api_headers_enc),
                'monthlyCapUsd': self.monthly_cap_usd, 'enabled': self.enabled, 'createdAt': self.created_at.isoformat() + 'Z'}


class KnowledgeDoc(me.Document):
    doc_id = me.StringField(unique=True, required=True)
    app_id = me.StringField(required=True)
    client_id = me.StringField(required=True)
    title = me.StringField(default='')
    kind = me.StringField(default='text')
    text = me.StringField(default='')
    chunks = me.ListField(me.StringField(), default=list)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'cn_knowledge', 'indexes': ['app_id']}

    def to_dict(self):
        return {'id': self.doc_id, 'title': self.title, 'kind': self.kind, 'chars': len(self.text), 'chunks': len(self.chunks),
                'preview': self.text[:200], 'createdAt': self.created_at.isoformat() + 'Z'}


class AppAction(me.Document):
    """Something Adion may do inside an app. mode=api: Adion calls the app's server. mode=client: the app's own code runs it."""
    action_id = me.StringField(unique=True, required=True)
    app_id = me.StringField(required=True)
    client_id = me.StringField(required=True)
    name = me.StringField(required=True)              # tool name, letters/digits/_ only
    description = me.StringField(default='')
    mode = me.StringField(default='api')
    method = me.StringField(default='GET')
    path = me.StringField(default='')                 # /transactions/{id}
    params = me.ListField(me.DictField(), default=list)    # [{name, in: path|query|body, type, required, description}]
    risk = me.StringField(default='read')             # read | write | danger
    enabled = me.BooleanField(default=False)
    confirm = me.BooleanField(default=False)          # also ask before a READ (changes and risky actions are ALWAYS confirmed)
    never_ai = me.BooleanField(default=False)         # listed for the docs, but Adion may never run it
    requires_user = me.BooleanField(default=True)     # only for signed-in users
    hide_fields = me.ListField(me.StringField(), default=list)    # response fields removed before the AI sees them
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'cn_actions', 'indexes': ['app_id']}

    def to_dict(self):
        return {'id': self.action_id, 'name': self.name, 'description': self.description, 'mode': self.mode, 'method': self.method,
                'path': self.path, 'params': self.params, 'risk': self.risk, 'enabled': self.enabled, 'confirm': self.confirm,
                'neverAi': self.never_ai, 'requiresUser': self.requires_user, 'hideFields': self.hide_fields}


class Conversation(me.Document):
    conv_id = me.StringField(unique=True, required=True)
    app_id = me.StringField(required=True)
    client_id = me.StringField(required=True)
    end_user = me.StringField(default='')             # the app's own user id, or "anon:<random>" / "portal:<client>"
    title = me.StringField(default='')
    messages = me.ListField(me.DictField(), default=list)       # [{role: user|assistant, text, ts}]
    state = me.DictField(default=dict)                # paused model state while waiting for a confirmation or an in-app result
    created_at = me.DateTimeField(default=datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'cn_conversations', 'indexes': ['app_id', 'end_user', '-updated_at']}

    def to_dict(self, full=False):
        d = {'id': self.conv_id, 'endUser': self.end_user, 'title': self.title, 'count': len(self.messages),
             'updatedAt': self.updated_at.isoformat() + 'Z'}
        if full:
            d['messages'] = self.messages
        return d


class ConnectConfig(me.Document):
    """The owner's platform settings (one row)."""
    key = me.StringField(unique=True, default='main')
    markup = me.FloatField(default=2.0)               # what clients are charged = your DeepSeek cost x markup
    default_cap_usd = me.FloatField(default=20.0)     # monthly spend cap per client unless changed
    free_credit_usd = me.FloatField(default=1.0)      # shown to clients as included credit
    signup = me.StringField(default='open')           # open | approval | closed

    meta = {'collection': 'cn_config'}
