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
