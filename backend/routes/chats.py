"""
Chats: conversations as the user sees them. A conversation is every question/answer (and PC request) that shares a thread id.
Builds are NOT chats: they stay in the projects list (/api/runs).

GET    /api/chats          my conversations, newest first
GET    /api/chats/<id>     all turns of one conversation, oldest first ([] if there are none)
DELETE /api/chats/<id>     delete the conversation's turns (never projects)
"""

from flask import Blueprint, jsonify
from mongoengine import Q

from models import RunDocument
from auth import current_user

chats_bp = Blueprint('chats', __name__)


def _turns(owner, tid):
    """Chat turns of a thread. Older runs that never had a thread are their own one-turn conversation (thread = run id)."""
    return RunDocument.objects(Q(owner=owner) & (Q(thread_id=tid) | Q(run_id=tid)) & (Q(answer__ne='') | Q(pc_task_id__ne='')))


@chats_bp.route('/chats', methods=['GET'])
def list_chats():
    me = current_user()['u']
    runs = RunDocument.objects(Q(owner=me) & (Q(answer__ne='') | Q(pc_task_id__ne=''))).order_by('-created_at').limit(600)
    groups = {}
    for r in runs:                                   # newest first
        key = r.thread_id or r.run_id
        g = groups.setdefault(key, {'threadId': key, 'count': 0, 'updatedAt': r.created_at, 'preview': (r.answer or r.goal)[:110], 'title': r.goal})
        g['count'] += 1
        g['title'] = r.goal                          # ends as the OLDEST question: the conversation's title
    out = sorted(groups.values(), key=lambda g: g['updatedAt'], reverse=True)[:60]
    for g in out:
        g['title'] = g['title'].strip().split('\n')[0][:70]
        g['updatedAt'] = g['updatedAt'].isoformat() + 'Z' if g['updatedAt'] else None
    return jsonify(out)


@chats_bp.route('/chats/<tid>', methods=['GET'])
def get_chat(tid):
    turns = _turns(current_user()['u'], tid).order_by('created_at')
    return jsonify([r.to_dict() for r in turns])     # an empty list (not a 404): a brand-new chat has no turns yet


@chats_bp.route('/chats/<tid>', methods=['DELETE'])
def delete_chat(tid):
    n = _turns(current_user()['u'], tid).delete()
    return jsonify({'ok': True, 'deleted': n})
