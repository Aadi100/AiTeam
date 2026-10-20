"""
Tasks & Multi-Task Concurrency Engine Route
Handles task persistence in MongoDB, status updates, and concurrent multi-task batch execution.
"""

from flask import Blueprint, request, jsonify
from models import TaskDocument, AgentDocument, ProjectStateDocument, MessageDocument
import time

tasks_bp = Blueprint('tasks', __name__)


@tasks_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """Retrieve all tasks from MongoDB sorted by creation time."""
    try:
        tasks = TaskDocument.objects.order_by('-timestamp')
        return jsonify({
            'success': True,
            'count': len(tasks),
            'tasks': [t.to_dict() for t in tasks]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_bp.route('/tasks', methods=['POST'])
def create_task():
    """Create a single task in MongoDB."""
    try:
        data = request.get_json() or {}
        title = data.get('title')
        assignee_id = data.get('assigneeId') or 'architect'

        if not title:
            return jsonify({'success': False, 'error': 'Task title is required.'}), 400

        task_id = data.get('id') or f"task-{int(time.time() * 1000)}"

        task = TaskDocument(
            task_id=task_id,
            title=title,
            description=data.get('description', f"Task: {title}"),
            assignee_id=assignee_id,
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'in_progress'),
            progress=data.get('progress', 10),
            created_at='Just now'
        ).save()

        # Update assigned worker status in MongoDB
        AgentDocument.objects(agent_id=assignee_id).update_one(
            set__status='coding',
            set__status_text=f"Processing task: {title[:30]}..."
        )

        return jsonify({'success': True, 'task': task.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_bp.route('/tasks/parallel', methods=['POST'])
def dispatch_parallel_tasks():
    """
    Concurrent Multi-Task Batch Dispatcher:
    Receives an array of tasks and executes them simultaneously across worker nodes,
    persisting everything to MongoDB.
    """
    try:
        data = request.get_json() or {}
        task_batch = data.get('tasks') or []

        if not task_batch:
            return jsonify({'success': False, 'error': 'Task batch array cannot be empty.'}), 400

        created_tasks = []
        now_str = time.strftime("%I:%M %p")

        # 1. Update Project State in MongoDB
        project_state = ProjectStateDocument.objects(singleton_id='current_project').first()
        if not project_state:
            project_state = ProjectStateDocument(singleton_id='current_project')
        project_state.project_name = f"Multi-Task Batch ({len(task_batch)} Threads)"
        project_state.project_goal = f"Concurrent execution of {len(task_batch)} tasks across worker swarm"
        project_state.status = 'building'
        project_state.progress = 25
        project_state.started_at = now_str
        project_state.save()

        # 2. Record launch message in MongoDB
        task_titles = "\n".join([f"{i+1}. **{t.get('title')}**" for i, t in enumerate(task_batch)])
        MessageDocument(
            msg_id=f"msg-{int(time.time()*1000)}",
            sender_id='boss',
            sender_name='Controller (You)',
            sender_role='Tool Master',
            sender_avatar='⚡',
            channel_id='general',
            text=f"⚡ **CONCURRENT MULTI-TASK DISPATCHED TO MONGODB**: Launching **{len(task_batch)} parallel threads**:\n{task_titles}",
            timestamp=now_str
        ).save()

        # 3. Create all Task documents and update agents in MongoDB
        default_assignees = ['architect', 'frontend', 'backend', 'qa', 'devops']
        for idx, item in enumerate(task_batch):
            assignee = item.get('assigneeId') or default_assignees[idx % len(default_assignees)]
            task_id = f"parallel-{int(time.time()*1000)}-{idx}"

            task = TaskDocument(
                task_id=task_id,
                title=item.get('title', 'Concurrent Task'),
                description=item.get('description', f"Concurrent execution thread #{idx + 1}"),
                assignee_id=assignee,
                priority='high',
                status='in_progress',
                progress=20,
                created_at='Just now'
            ).save()
            created_tasks.append(task.to_dict())

            # Transition worker to active coding in MongoDB
            AgentDocument.objects(agent_id=assignee).update_one(
                set__status='coding',
                set__status_text=f"[Parallel Thread] {item.get('title', '')[:30]}..."
            )

        return jsonify({
            'success': True,
            'message': f"Dispatched {len(created_tasks)} tasks concurrently to MongoDB",
            'tasks': created_tasks,
            'project': project_state.to_dict()
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_bp.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    """Update task status or progress in MongoDB."""
    try:
        data = request.get_json() or {}
        task = TaskDocument.objects(task_id=task_id).first()
        if not task:
            return jsonify({'success': False, 'error': 'Task not found.'}), 404

        if 'status' in data:
            task.status = data['status']
            if data['status'] == 'done':
                task.progress = 100
                task.completed_at = 'Just now'
        if 'progress' in data:
            task.progress = int(data['progress'])
        if 'title' in data:
            task.title = data['title']

        task.save()
        return jsonify({'success': True, 'task': task.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@tasks_bp.route('/tasks', methods=['DELETE'])
def clear_tasks():
    """Clear/reset all tasks in MongoDB."""
    try:
        TaskDocument.objects.delete()
        # Reset agents to idle
        AgentDocument.objects.update(set__status='idle', set__status_text='Ready for directives')
        return jsonify({'success': True, 'message': 'All tasks cleared.'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
