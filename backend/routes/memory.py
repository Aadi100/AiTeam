"""Long-term memory injected into the planner prompt. Semantic (embedding) recall when an embedding
model is configured (none by default); keyword overlap otherwise."""

import os
import re
import math
import time
import uuid
import requests
from flask import Blueprint, request, jsonify
from auth import current_user
from models import MemoryDocument, UserDocument

memory_bp = Blueprint('memory', __name__)
_STOP = set('the a an and or of to in for with on is are be it this that i we you my our build make create app project'.split())


def _words(text):
    return {w for w in re.findall(r'[a-z0-9]{3,}', (text or '').lower()) if w not in _STOP}


def embed(text):
    """DeepSeek has no embeddings API and Adion uses no local models, so recall is keyword-based.
    Returning None makes every caller fall back to word overlap."""
    return None


def _cos(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def _is_admin(owner):
    return bool(UserDocument.objects(username=owner, role='admin').first())


def visible(owner):
    """Whose notes this person may use: their own, plus (for the owner/admin) the older notes made before memories were private.
    owner=None means "no filter" and is only for internal code that has no user."""
    if owner is None:
        return MemoryDocument.objects
    if _is_admin(owner):
        return MemoryDocument.objects(owner__in=[owner, ''])
    return MemoryDocument.objects(owner=owner)


def recall(goal, limit=8, owner=None):
    """Preferences always apply. Other notes are ranked by embedding similarity when an embedding model
    is available (notes without a vector fall back to word overlap), else purely by word overlap. Pass owner so people only get their own notes."""
    gw, qv = _words(goal), embed(goal)
    notes = list(visible(owner).limit(300))
    prefs = [n for n in notes if n.kind == 'preference'][:limit]
    scored = []
    for n in notes:
        if n.kind == 'preference':
            continue
        if qv and n.vector:
            sc = _cos(qv, n.vector)
            if sc >= 0.35:
                scored.append((sc, n))
        else:
            overlap = len(gw & _words(n.text))
            if overlap:
                scored.append((min(1.0, overlap / 6), n))
    scored.sort(key=lambda x: -x[0])
    # what Adion learned ABOUT the person (name, job, tools...) is useful in any conversation, not only when the words overlap
    profile = [n for n in notes if n.source == 'learned' and n.kind == 'note'][:6]
    picked = prefs + profile + [n for _, n in scored if n not in profile][:max(0, limit - len(prefs))]
    return chr(10).join(f'- [{n.kind}] {n.text}' for n in picked)


def remember(text, kind='note', owner='', source='user'):
    vec = embed(text) or []
    MemoryDocument(mem_id='mem_' + uuid.uuid4().hex[:8], text=text[:1500], kind=kind, vector=vec, owner=owner, source=source).save()


@memory_bp.route('/memory', methods=['GET'])
def list_mem():
    return jsonify([m.to_dict() for m in visible(current_user()['u']).limit(200)])


@memory_bp.route('/memory', methods=['POST'])
def add_mem():
    b = request.get_json(silent=True) or {}
    text = (b.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400
    remember(text, b.get('kind') if b.get('kind') in ('note', 'preference') else 'note', owner=current_user()['u'])
    return jsonify({'ok': True}), 201


@memory_bp.route('/memory/<mem_id>', methods=['DELETE'])
def del_mem(mem_id):
    visible(current_user()['u']).filter(mem_id=mem_id).delete()
    return jsonify({'ok': True})


@memory_bp.route('/memory/learning', methods=['GET', 'PUT'])
def learning():
    """Each person decides whether Adion may learn from their chats. Learned notes are private to them and can be deleted above."""
    me_ = current_user()['u']
    if request.method == 'PUT':
        on = bool((request.get_json(silent=True) or {}).get('on'))
        UserDocument.objects(username=me_).update_one(set__learning=on)
    row = UserDocument.objects(username=me_).first()
    return jsonify({'on': bool(row.learning) if row else True})
