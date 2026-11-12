"""
Adion MongoEngine data models: runs, agent tasks, the usage ledger, memory, schedules, background jobs and users.
"""

import mongoengine as me
from datetime import datetime


# ───────────────────────── Orchestrator (agent map) ─────────────────────────

class RunDocument(me.Document):
    """One user goal. The root node of the agent map."""
    run_id = me.StringField(unique=True, required=True)
    goal = me.StringField(required=True)
    project_name = me.StringField(default='')
    summary = me.StringField(default='')
    answer = me.StringField(default='')            # set when the goal was a question, not a build
    sources = me.ListField(me.DictField(), default=list)   # web sources behind an answer [{title, url}]
    web_search = me.BooleanField(default=False)    # always search the web for this question
    kind = me.StringField(default='')              # routing decision: chat|small|large|edit
    mode = me.StringField(default='build')         # build | edit (a follow-up change to an existing project)
    parent_run_id = me.StringField(default='')     # the run an edit continues
    review_plan = me.BooleanField(default=False)   # pause for the user's approval before building
    deep_plan = me.BooleanField(default=True)      # plan big projects with the slower, smarter reasoner model
    reused_plan = me.StringField(default='')       # name of an earlier good plan this one was modelled on
    pc_task_id = me.StringField(default='')        # a PC-control request started from the composer
    questions = me.ListField(me.DictField(), default=list)  # [{id, q, options, answer, taskId}] asked of the user
    plan = me.DictField(default=dict)              # plan waiting for approval
    assumptions = me.ListField(me.StringField(), default=list)
    revisions = me.IntField(default=0)             # how many times the planner re-planned after failures
    check = me.DictField(default=dict)             # last browser check {ok, url, issues[], screenshot, ...}
    contract = me.StringField(default='')          # shared interface notes given to every worker
    target_path = me.StringField(required=True)
    status = me.StringField(default='planning')    # planning|running|completed|failed|cancelled
    planner_model = me.StringField(default='')
    worker_model = me.StringField(default='')
    max_tokens = me.IntField(default=0)            # 0 = unlimited budget
    tokens_in = me.IntField(default=0)
    tokens_out = me.IntField(default=0)
    cache_hit = me.IntField(default=0)             # input tokens served from DeepSeek's cache (billed ~10x cheaper)
    cost_usd = me.FloatField(default=0.0)
    estimate_tokens = me.IntField(default=0)       # forecast made right after planning
    estimate_cost = me.FloatField(default=0.0)
    cancel_requested = me.BooleanField(default=False)
    error = me.StringField(default='')
    source = me.StringField(default='manual')      # manual|voice|schedule
    owner = me.StringField(default='')
    verify = me.BooleanField(default=False)        # run the generated project and auto-fix
    suggested = me.ListField(me.DictField(), default=list)   # [{title, command, cwd}] to run the result
    created_at = me.DateTimeField(default=datetime.utcnow)
    started_at = me.DateTimeField()
    ended_at = me.DateTimeField()

    meta = {'collection': 'runs', 'ordering': ['-created_at'], 'indexes': ['run_id', 'status', '-created_at']}

    def to_dict(self):
        return {
            'id': self.run_id, 'goal': self.goal, 'projectName': self.project_name,
            'summary': self.summary, 'answer': self.answer, 'sources': self.sources,
            'kind': self.kind, 'mode': self.mode, 'parentRunId': self.parent_run_id, 'reviewPlan': self.review_plan,
            'questions': self.questions, 'plan': self.plan, 'assumptions': self.assumptions,
            'deepPlan': self.deep_plan, 'reusedPlan': self.reused_plan, 'pcTaskId': self.pc_task_id,
            'revisions': self.revisions, 'check': self.check, 'targetPath': self.target_path, 'status': self.status,
            'plannerModel': self.planner_model, 'workerModel': self.worker_model,
            'maxTokens': self.max_tokens, 'tokensIn': self.tokens_in, 'tokensOut': self.tokens_out,
            'tokens': self.tokens_in + self.tokens_out, 'error': self.error, 'source': self.source,
            'cacheHit': self.cache_hit, 'cost': round(self.cost_usd, 5),
            'estimateTokens': self.estimate_tokens, 'estimateCost': round(self.estimate_cost, 5),
            'owner': self.owner, 'verify': self.verify, 'suggested': self.suggested,
            'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'startedAt': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'endedAt': self.ended_at.isoformat() + 'Z' if self.ended_at else None,
        }


class PlanMemoryDocument(me.Document):
    """A plan that produced a finished, error-free build. Reused as an example for similar goals."""
    owner = me.StringField(default='')
    goal = me.StringField(default='')
    project_name = me.StringField(default='')
    summary = me.StringField(default='')
    contract = me.StringField(default='')
    modules = me.ListField(me.DictField(), default=list)    # [{title, folder, depends, description, expects}]
    words = me.ListField(me.StringField(), default=list)    # keywords for matching
    uses = me.IntField(default=0)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'plan_memory', 'indexes': ['owner', '-created_at']}


class PcSettingsDocument(me.Document):
    """PC control settings per user: extra allowed folders, the pause switch and trust mode."""
    owner = me.StringField(unique=True, required=True)
    folders = me.ListField(me.StringField(), default=list)     # folders the user chose "Always allow" for (Desktop is built in)
    paused = me.BooleanField(default=False)                    # emergency stop
    trust = me.BooleanField(default=False)                     # run plain file changes in allowed folders without asking

    meta = {'collection': 'pc_settings'}


class PcTaskDocument(me.Document):
    """One request to control the PC, with its steps and what is waiting for the user."""
    task_id = me.StringField(unique=True, required=True)
    owner = me.StringField(required=True)
    run_id = me.StringField(default='')
    request = me.StringField(default='')
    status = me.StringField(default='planning')    # planning|awaiting_approval|running|done|failed|denied|cancelled
    say = me.StringField(default='')
    steps = me.ListField(me.DictField(), default=list)
    transcript = me.ListField(me.StringField(), default=list)
    pending_folders = me.ListField(me.StringField(), default=list)
    pending_phase = me.StringField(default='')     # run | propose
    granted = me.ListField(me.StringField(), default=list)     # folders allowed "once" for this task
    untrusted = me.BooleanField(default=False)     # the plan was made after reading file contents
    rounds = me.IntField(default=0)
    error = me.StringField(default='')
    created_at = me.DateTimeField(default=datetime.utcnow)
    ended_at = me.DateTimeField()

    meta = {'collection': 'pc_tasks', 'ordering': ['-created_at'], 'indexes': ['task_id', 'owner', '-created_at']}

    def to_dict(self):
        steps = [{k: (v[:1500] if isinstance(v, str) else v) for k, v in s.items() if k != 'reported'} for s in self.steps]
        undoable = PcActionDocument.objects(task_id=self.task_id, undone=False, ok=True, undo__ne={}).count()
        return {'id': self.task_id, 'runId': self.run_id, 'request': self.request, 'status': self.status, 'say': self.say,
                'steps': steps, 'pendingFolders': self.pending_folders, 'pendingPhase': self.pending_phase,
                'untrusted': self.untrusted, 'error': self.error, 'undoable': undoable,
                'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None}


class PcActionDocument(me.Document):
    """Activity log: one row per tool run, with how to undo it."""
    task_id = me.StringField(default='')
    owner = me.StringField(default='')
    tool = me.StringField(default='')
    summary = me.StringField(default='')
    risk = me.StringField(default='')
    ok = me.BooleanField(default=True)
    result = me.StringField(default='')
    undo = me.DictField(default=dict)
    undone = me.BooleanField(default=False)
    auto = me.BooleanField(default=False)          # ran without a click (trust mode)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'pc_actions', 'ordering': ['-created_at'], 'indexes': ['task_id', 'owner', '-created_at']}

    def to_dict(self):
        return {'id': str(self.id), 'taskId': self.task_id, 'tool': self.tool, 'summary': self.summary, 'risk': self.risk,
                'ok': self.ok, 'result': self.result, 'undone': self.undone, 'canUndo': bool(self.undo) and not self.undone and self.ok,
                'auto': self.auto, 'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None}


class UsageDocument(me.Document):
    """Ledger: one row per model call. Powers the token calculator."""
    owner = me.StringField(default='')
    run_id = me.StringField(default='')
    task_id = me.StringField(default='')
    purpose = me.StringField(default='other')      # answer|plan|critic|agent|fix|review|assistant
    model = me.StringField(default='')
    tokens_in = me.IntField(default=0)
    cache_hit = me.IntField(default=0)
    tokens_out = me.IntField(default=0)
    cost_usd = me.FloatField(default=0.0)
    saved_usd = me.FloatField(default=0.0)         # what the cache saved versus full price
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'usage', 'indexes': ['run_id', 'owner', '-created_at']}


class AgentTaskDocument(me.Document):
    """One sub-agent in the map. Agents are created per plan, never fixed."""
    task_id = me.StringField(unique=True, required=True)
    run_id = me.StringField(required=True)
    key = me.StringField(required=True)            # planner-assigned short key
    parent_id = me.StringField(default='')         # '' = child of the run root
    kind = me.StringField(default='module')        # module|review
    title = me.StringField(required=True)
    description = me.StringField(default='')
    folder = me.StringField(default='')            # the only directory this agent may write in
    depends_on = me.ListField(me.StringField(), default=list)   # task_ids
    status = me.StringField(default='queued')      # queued|running|done|failed|skipped|cancelled
    model = me.StringField(default='')
    attempts = me.IntField(default=0)
    tokens_in = me.IntField(default=0)
    tokens_out = me.IntField(default=0)
    summary = me.StringField(default='')
    error = me.StringField(default='')
    files = me.ListField(me.DictField(), default=list)
    expects = me.ListField(me.StringField(), default=list)   # files this agent must produce (acceptance check)
    notes = me.StringField(default='')             # the user's answers to this agent's questions
    asks = me.IntField(default=0)                  # questions this agent has asked
    replans = me.IntField(default=0)               # times the planner revised this agent's assignment
    replaced = me.BooleanField(default=False)     # superseded by a revised plan
    log = me.ListField(me.DictField(), default=list)
    order = me.IntField(default=0)
    started_at = me.DateTimeField()
    ended_at = me.DateTimeField()

    meta = {'collection': 'agent_tasks', 'indexes': ['task_id', 'run_id', 'status']}

    def to_dict(self, detail=False):
        d = {
            'id': self.task_id, 'runId': self.run_id, 'key': self.key, 'parentId': self.parent_id,
            'kind': self.kind, 'title': self.title, 'description': self.description,
            'folder': self.folder, 'dependsOn': self.depends_on, 'status': self.status,
            'model': self.model, 'attempts': self.attempts,
            'tokensIn': self.tokens_in, 'tokensOut': self.tokens_out,
            'tokens': self.tokens_in + self.tokens_out, 'summary': self.summary, 'error': self.error,
            'fileCount': len(self.files), 'order': self.order, 'replaced': self.replaced, 'replans': self.replans,
            'startedAt': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'endedAt': self.ended_at.isoformat() + 'Z' if self.ended_at else None,
            'lastLog': self.log[-1]['msg'] if self.log else '',
        }
        if detail:
            d['files'] = self.files
            d['log'] = self.log
        return d


class BackgroundJobDocument(me.Document):
    """A shell job (dev server, tests, n8n...) started from the Background tasks panel."""
    job_id = me.StringField(unique=True, required=True)
    title = me.StringField(required=True)
    command = me.StringField(required=True)
    cwd = me.StringField(required=True)
    status = me.StringField(default='running')      # running|exited|failed|stopped|lost
    pid = me.IntField(default=0)
    exit_code = me.IntField()
    log_tail = me.StringField(default='')
    created_at = me.DateTimeField(default=datetime.utcnow)
    ended_at = me.DateTimeField()

    meta = {'collection': 'background_jobs', 'ordering': ['-created_at']}

    def to_dict(self):
        return {'id': self.job_id, 'title': self.title, 'command': self.command, 'cwd': self.cwd,
                'status': self.status, 'pid': self.pid, 'exitCode': self.exit_code,
                'createdAt': self.created_at.isoformat() + 'Z',
                'endedAt': self.ended_at.isoformat() + 'Z' if self.ended_at else None}


class MemoryDocument(me.Document):
    """Long-term notes (preferences, past builds) injected into the planner prompt."""
    mem_id = me.StringField(unique=True, required=True)
    text = me.StringField(required=True)
    kind = me.StringField(default='note')           # note|preference|build
    vector = me.ListField(me.FloatField(), default=list)   # embedding, when an embedding model is available
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'memories', 'ordering': ['-created_at']}

    def to_dict(self):
        return {'id': self.mem_id, 'text': self.text, 'kind': self.kind,
                'createdAt': self.created_at.isoformat() + 'Z'}


class ScheduleDocument(me.Document):
    """Recurring goal. Runs unattended, so it uses the server's DeepSeek key unless keys are stored (keys are never stored)."""
    sched_id = me.StringField(unique=True, required=True)
    name = me.StringField(required=True)
    goal = me.StringField(required=True)
    target_path = me.StringField(required=True)
    every_minutes = me.IntField(default=0)          # interval mode when > 0
    daily_at = me.StringField(default='')           # 'HH:MM' local time when every_minutes == 0
    planner_model = me.StringField(default='')
    worker_model = me.StringField(default='')
    max_tokens = me.IntField(default=0)
    enabled = me.BooleanField(default=True)
    keys_enc = me.StringField(default='')          # Fernet-encrypted API keys (opt-in)
    owner = me.StringField(default='')
    last_run_at = me.DateTimeField()
    last_run_id = me.StringField(default='')
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'schedules', 'ordering': ['-created_at']}

    def to_dict(self):
        return {'id': self.sched_id, 'name': self.name, 'goal': self.goal, 'targetPath': self.target_path,
                'everyMinutes': self.every_minutes, 'dailyAt': self.daily_at,
                'plannerModel': self.planner_model, 'workerModel': self.worker_model,
                'maxTokens': self.max_tokens, 'enabled': self.enabled, 'lastRunId': self.last_run_id,
                'hasKeys': bool(self.keys_enc), 'owner': self.owner,
                'lastRunAt': self.last_run_at.isoformat() + 'Z' if self.last_run_at else None}


class UserDocument(me.Document):
    username = me.StringField(unique=True, required=True)
    password_hash = me.StringField(required=True)
    role = me.StringField(default='member')        # admin | member | viewer
    deepseek_enc = me.StringField(default='')      # Fernet-encrypted DeepSeek API key
    tavily_enc = me.StringField(default='')        # Fernet-encrypted Tavily (web search) API key
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'users'}

    def to_dict(self):
        return {'username': self.username, 'role': self.role, 'createdAt': self.created_at.isoformat() + 'Z'}
