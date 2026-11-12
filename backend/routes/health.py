"""Health check: is the server up and is MongoDB reachable? (open endpoint, no login needed)"""

from flask import Blueprint, jsonify
import mongoengine as me

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    try:
        me.get_connection().admin.command('ping')
        return jsonify({'status': 'healthy', 'server': 'Adion', 'database': 'connected'}), 200
    except Exception as e:  # noqa: BLE001
        return jsonify({'status': 'degraded', 'server': 'Adion', 'database': 'disconnected', 'error': str(e)}), 503
