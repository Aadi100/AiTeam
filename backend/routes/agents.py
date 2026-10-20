"""
Worker Nodes & Agent Swarm Route
Handles node provisioning, deployment, prompt tuning, and pause/resume cluster controls in MongoDB.
"""

from flask import Blueprint, request, jsonify
from models import AgentDocument, MessageDocument
import time

agents_bp = Blueprint('agents', __name__)


@agents_bp.route('/agents', methods=['GET'])
def get_agents():
    """Retrieve all autonomous worker nodes from MongoDB."""
    try:
        agents = AgentDocument.objects()
        return jsonify({
            'success': True,
            'count': len(agents),
            'agents': [a.to_dict() for a in agents]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@agents_bp.route('/agents', methods=['POST'])
def deploy_agent():
    """Provision and deploy a new autonomous worker node into MongoDB."""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        role = data.get('role')

        if not name or not role:
            return jsonify({'success': False, 'error': 'Name and role are required.'}), 400

        agent_id = data.get('id') or f"agent-{int(time.time() * 1000)}"

        # Check if already exists
        if AgentDocument.objects(agent_id=agent_id).first():
            return jsonify({'success': False, 'error': f"Agent {agent_id} already exists."}), 409

        agent = AgentDocument(
            agent_id=agent_id,
            name=name,
            role=role,
            department=data.get('department', 'Custom'),
            avatar=data.get('avatar', '🤖'),
            color=data.get('color', 'from-cyan-600 to-indigo-700'),
            status='idle',
            status_text='Worker node online & synced with cluster',
            model=data.get('model', 'gemini-2.0-flash'),
            system_prompt=data.get('systemPrompt', f"You are {name}, specialized {role}."),
            skills=data.get('skills', ['Architecture', 'Optimization']),
            stats={'tasksDone': 0, 'filesCreated': 0, 'reviewsDone': 0},
            logs=[{
                'id': f"log-{int(time.time()*1000)}",
                'timestamp': time.strftime("%I:%M %p"),
                'text': f"Provisioned into compute cluster as {role}",
                'type': 'info'
            }],
            desk=data.get('desk', {'room': 'Compute Pod', 'col': 1, 'row': 4})
        ).save()

        # Record deployment message in MongoDB
        MessageDocument(
            msg_id=f"msg-{int(time.time()*1000)}",
            sender_id='boss',
            sender_name='Controller (You)',
            sender_role='Tool Master',
            sender_avatar='⚡',
            channel_id='general',
            text=f"🤖 **WORKER NODE PROVISIONED IN MONGODB**: **{name}** ({role}) has been deployed to the compute cluster!",
            timestamp=time.strftime("%I:%M %p")
        ).save()

        return jsonify({'success': True, 'agent': agent.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@agents_bp.route('/agents/<agent_id>', methods=['PUT'])
def update_agent(agent_id):
    """Update worker node prompt, model, or status in MongoDB."""
    try:
        data = request.get_json() or {}
        agent = AgentDocument.objects(agent_id=agent_id).first()
        if not agent:
            return jsonify({'success': False, 'error': 'Agent not found.'}), 404

        if 'systemPrompt' in data:
            agent.system_prompt = data['systemPrompt']
        if 'model' in data:
            agent.model = data['model']
        if 'status' in data:
            agent.status = data['status']
        if 'statusText' in data:
            agent.status_text = data['statusText']

        agent.save()
        return jsonify({'success': True, 'agent': agent.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@agents_bp.route('/agents/<agent_id>', methods=['DELETE'])
def remove_agent(agent_id):
    """Decommission / remove worker node from MongoDB."""
    try:
        agent = AgentDocument.objects(agent_id=agent_id).first()
        if not agent:
            return jsonify({'success': False, 'error': 'Agent not found.'}), 404

        agent.delete()
        return jsonify({'success': True, 'message': f"Worker node {agent_id} decommissioned."}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@agents_bp.route('/agents/pause', methods=['POST'])
def pause_all_agents():
    """Pause all worker nodes in MongoDB."""
    try:
        AgentDocument.objects.update(
            set__status='paused',
            set__status_text='Worker node paused by controller'
        )
        return jsonify({'success': True, 'message': 'All worker nodes paused.'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@agents_bp.route('/agents/resume', methods=['POST'])
def resume_all_agents():
    """Resume all worker nodes in MongoDB."""
    try:
        AgentDocument.objects.update(
            set__status='idle',
            set__status_text='Active & ready for concurrent task dispatch'
        )
        return jsonify({'success': True, 'message': 'All worker nodes resumed.'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
