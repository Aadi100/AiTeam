"""
DevSquad MongoEngine Data Models
High-performance document schemas for autonomous agent nodes, multi-task threads,
custom model weights/configs, continuous training pairs, and telemetry.
"""

import mongoengine as me
from datetime import datetime


class AgentDocument(me.Document):
    agent_id = me.StringField(unique=True, required=True)
    name = me.StringField(required=True)
    role = me.StringField(required=True)
    department = me.StringField(default='Custom')
    avatar = me.StringField(default='🤖')
    color = me.StringField(default='from-cyan-600 to-indigo-700')
    status = me.StringField(default='idle')
    status_text = me.StringField(default='Ready for directives')
    current_task_id = me.StringField()
    model = me.StringField(default='gemini-2.0-flash')
    system_prompt = me.StringField(default='You are an autonomous specialized AI execution worker node.')
    skills = me.ListField(me.StringField(), default=list)
    stats = me.DictField(default=lambda: {'tasksDone': 0, 'filesCreated': 0, 'reviewsDone': 0})
    logs = me.ListField(me.DictField(), default=list)
    desk = me.DictField(default=lambda: {'room': 'Compute Pod', 'col': 1, 'row': 1})
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'agents',
        'indexes': ['agent_id', 'status', 'department']
    }

    def to_dict(self):
        return {
            'id': self.agent_id,
            'name': self.name,
            'role': self.role,
            'department': self.department,
            'avatar': self.avatar,
            'color': self.color,
            'status': self.status,
            'statusText': self.status_text,
            'currentTaskId': self.current_task_id,
            'model': self.model,
            'systemPrompt': self.system_prompt,
            'skills': self.skills,
            'stats': self.stats,
            'logs': self.logs,
            'desk': self.desk
        }


class TaskDocument(me.Document):
    task_id = me.StringField(unique=True, required=True)
    title = me.StringField(required=True)
    description = me.StringField(default='')
    assignee_id = me.StringField(required=True)
    priority = me.StringField(default='medium')  # 'low' | 'medium' | 'high' | 'critical'
    status = me.StringField(default='in_progress')  # 'backlog' | 'in_progress' | 'review' | 'done'
    progress = me.IntField(default=0)
    deliverables = me.ListField(me.StringField(), default=list)
    created_at = me.StringField(default='Just now')
    completed_at = me.StringField()
    timestamp = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'tasks',
        'indexes': ['task_id', 'assignee_id', 'status']
    }

    def to_dict(self):
        return {
            'id': self.task_id,
            'title': self.title,
            'description': self.description,
            'assigneeId': self.assignee_id,
            'priority': self.priority,
            'status': self.status,
            'progress': self.progress,
            'deliverables': self.deliverables,
            'createdAt': self.created_at,
            'completedAt': self.completed_at
        }


class TrainingPairDocument(me.Document):
    pair_id = me.StringField(unique=True, required=True)
    agent_id = me.StringField(default='cluster')
    agent_name = me.StringField(default='Cluster Core')
    prompt = me.StringField(required=True)
    response = me.StringField(required=True)
    corrected_response = me.StringField(default='')
    rating = me.StringField(default='golden')  # 'positive' | 'negative' | 'golden'
    tags = me.ListField(me.StringField(), default=list)
    created_at = me.StringField(default='Just now')
    used_in_training = me.BooleanField(default=False)
    timestamp = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'training_pairs',
        'indexes': ['pair_id', 'agent_id', 'rating', 'used_in_training']
    }

    def to_dict(self):
        return {
            'id': self.pair_id,
            'agentId': self.agent_id,
            'agentName': self.agent_name,
            'prompt': self.prompt,
            'response': self.response,
            'correctedResponse': self.corrected_response,
            'rating': self.rating,
            'tags': self.tags,
            'createdAt': self.created_at,
            'usedInTraining': self.used_in_training
        }


class CustomModelDocument(me.Document):
    model_id = me.StringField(unique=True, required=True)
    name = me.StringField(required=True)
    base_model = me.StringField(required=True)
    specialization = me.StringField(default='General')
    target_agent_id = me.StringField(default='')
    epochs = me.IntField(default=3)
    learning_rate = me.FloatField(default=0.0002)
    training_pairs_count = me.IntField(default=0)
    status = me.StringField(default='ready')  # 'draft' | 'training' | 'ready'
    accuracy = me.FloatField(default=98.4)
    loss = me.FloatField(default=0.28)
    created_at = me.StringField(default='Just now')
    modelfile_content = me.StringField(default='')
    timestamp = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'custom_models',
        'indexes': ['model_id', 'name', 'status']
    }

    def to_dict(self):
        return {
            'id': self.model_id,
            'name': self.name,
            'baseModel': self.base_model,
            'specialization': self.specialization,
            'targetAgentId': self.target_agent_id,
            'epochs': self.epochs,
            'learningRate': self.learning_rate,
            'trainingPairsCount': self.training_pairs_count,
            'status': self.status,
            'accuracy': self.accuracy,
            'loss': self.loss,
            'createdAt': self.created_at,
            'modelfileContent': self.modelfile_content
        }


class MessageDocument(me.Document):
    msg_id = me.StringField(unique=True, required=True)
    sender_id = me.StringField(required=True)
    sender_name = me.StringField(required=True)
    sender_role = me.StringField(required=True)
    sender_avatar = me.StringField(default='⚡')
    channel_id = me.StringField(default='general')
    text = me.StringField(required=True)
    timestamp = me.StringField(default='Just now')
    code_snippet = me.DictField()
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'messages',
        'indexes': ['msg_id', 'channel_id', 'created_at']
    }

    def to_dict(self):
        d = {
            'id': self.msg_id,
            'senderId': self.sender_id,
            'senderName': self.sender_name,
            'senderRole': self.sender_role,
            'senderAvatar': self.sender_avatar,
            'channelId': self.channel_id,
            'text': self.text,
            'timestamp': self.timestamp
        }
        if self.code_snippet:
            d['codeSnippet'] = self.code_snippet
        return d


class ProjectStateDocument(me.Document):
    singleton_id = me.StringField(unique=True, default='current_project')
    project_name = me.StringField(default='Idle Workspace')
    project_goal = me.StringField(default='Standing by for multi-task directive...')
    status = me.StringField(default='idle')
    progress = me.IntField(default=0)
    started_at = me.StringField(default='')
    updated_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'project_state'
    }

    def to_dict(self):
        return {
            'projectName': self.project_name,
            'projectGoal': self.project_goal,
            'status': self.status,
            'progress': self.progress,
            'startedAt': self.started_at
        }


class ResearchBriefDocument(me.Document):
    brief_id = me.StringField(unique=True, required=True)
    topic = me.StringField(required=True)
    summary = me.StringField(required=True)
    benchmarks = me.ListField(me.DictField(), default=list)
    key_findings = me.ListField(me.StringField(), default=list)
    recommendation = me.StringField(default='')
    poc_code = me.DictField()
    timestamp = me.StringField(default='Just now')

    meta = {
        'collection': 'research_briefs',
        'indexes': ['brief_id', 'topic']
    }

    def to_dict(self):
        return {
            'id': self.brief_id,
            'topic': self.topic,
            'summary': self.summary,
            'benchmarks': self.benchmarks,
            'keyFindings': self.key_findings,
            'recommendation': self.recommendation,
            'pocCode': self.poc_code,
            'timestamp': self.timestamp
        }


class ProjectHistoryDocument(me.Document):
    history_id = me.StringField(unique=True, required=True)
    prompt = me.StringField(required=True)
    target_path = me.StringField(required=True)
    timestamp = me.StringField(default='Just now')
    total_files = me.IntField(default=0)
    files = me.ListField(me.DictField(), default=list)
    streams = me.DictField(default=dict)
    models_used = me.DictField(default=dict)
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'project_history',
        'ordering': ['-created_at'],
        'indexes': ['history_id', 'created_at']
    }

    def to_dict(self):
        return {
            'id': self.history_id,
            'prompt': self.prompt,
            'targetPath': self.target_path,
            'timestamp': self.timestamp,
            'totalFiles': self.total_files,
            'files': self.files,
            'streams': self.streams,
            'modelsUsed': self.models_used,
            'createdAt': self.created_at.isoformat() if self.created_at else ''
        }


# ───────────────────────── Orchestrator (agent map) ─────────────────────────

class RunDocument(me.Document):
    """One user goal. The root node of the agent map."""
    run_id = me.StringField(unique=True, required=True)
    goal = me.StringField(required=True)
    project_name = me.StringField(default='')
    summary = me.StringField(default='')
    contract = me.StringField(default='')          # shared interface notes given to every worker
    target_path = me.StringField(required=True)
    status = me.StringField(default='planning')    # planning|running|completed|failed|cancelled
    planner_model = me.StringField(default='')
    worker_model = me.StringField(default='')
    max_tokens = me.IntField(default=0)            # 0 = unlimited budget
    tokens_in = me.IntField(default=0)
    tokens_out = me.IntField(default=0)
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
            'summary': self.summary, 'targetPath': self.target_path, 'status': self.status,
            'plannerModel': self.planner_model, 'workerModel': self.worker_model,
            'maxTokens': self.max_tokens, 'tokensIn': self.tokens_in, 'tokensOut': self.tokens_out,
            'tokens': self.tokens_in + self.tokens_out, 'error': self.error, 'source': self.source,
            'owner': self.owner, 'verify': self.verify, 'suggested': self.suggested,
            'createdAt': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'startedAt': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'endedAt': self.ended_at.isoformat() + 'Z' if self.ended_at else None,
        }


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
            'fileCount': len(self.files), 'order': self.order,
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
    """Recurring goal. Runs unattended, so it uses env/Ollama models only (keys are never stored)."""
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
    created_at = me.DateTimeField(default=datetime.utcnow)

    meta = {'collection': 'users'}

    def to_dict(self):
        return {'username': self.username, 'role': self.role, 'createdAt': self.created_at.isoformat() + 'Z'}
