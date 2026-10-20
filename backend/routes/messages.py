"""
Cluster Messages & Telemetry Stream Route
Stores and retrieves real-time messages, directives, and channel discussions in MongoDB.
"""

from flask import Blueprint, request, jsonify
from models import MessageDocument
import time

messages_bp = Blueprint('messages', __name__)


@messages_bp.route('/messages', methods=['GET'])
def get_messages():
    """Retrieve messages from MongoDB, optionally filtered by channel."""
    try:
        channel_id = request.args.get('channel')
        query = MessageDocument.objects
        if channel_id:
            query = query.filter(channel_id=channel_id)

        messages = query.order_by('created_at')
        return jsonify({
            'success': True,
            'count': len(messages),
            'messages': [m.to_dict() for m in messages]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@messages_bp.route('/messages', methods=['POST'])
def post_message():
    """Post a message into MongoDB."""
    try:
        data = request.get_json() or {}
        text = data.get('text')
        sender_id = data.get('senderId', 'boss')

        if not text:
            return jsonify({'success': False, 'error': 'Message text is required.'}), 400

        msg_id = data.get('id') or f"msg-{int(time.time() * 1000)}"

        msg = MessageDocument(
            msg_id=msg_id,
            sender_id=sender_id,
            sender_name=data.get('senderName', 'Controller (You)'),
            sender_role=data.get('senderRole', 'Tool Master'),
            sender_avatar=data.get('senderAvatar', '⚡'),
            channel_id=data.get('channelId', 'general'),
            text=text,
            timestamp=data.get('timestamp') or time.strftime("%I:%M %p"),
            code_snippet=data.get('codeSnippet')
        ).save()

        return jsonify({'success': True, 'message': msg.to_dict()}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
