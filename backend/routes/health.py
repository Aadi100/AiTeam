"""
Health & Diagnostics Route
Checks Flask server status and verifies MongoEngine connectivity to MongoDB.
"""

from flask import Blueprint, jsonify
from models import AgentDocument, TaskDocument, TrainingPairDocument, CustomModelDocument
import mongoengine as me

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    try:
        # Check MongoEngine connection by performing a fast query
        agent_count = AgentDocument.objects.count()
        task_count = TaskDocument.objects.count()
        pair_count = TrainingPairDocument.objects.count()
        model_count = CustomModelDocument.objects.count()

        return jsonify({
            'status': 'healthy',
            'server': 'DevSquad Python Flask Engine',
            'database': {
                'engine': 'MongoEngine',
                'status': 'connected',
                'stats': {
                    'workerNodes': agent_count,
                    'tasks': task_count,
                    'trainingPairs': pair_count,
                    'customModels': model_count
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'server': 'DevSquad Python Flask Engine',
            'database': {
                'engine': 'MongoEngine',
                'status': 'disconnected',
                'error': str(e)
            }
        }), 503
