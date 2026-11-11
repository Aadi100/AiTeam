"""Long-term memory injected into the planner prompt. Semantic (embedding) recall when an embedding
model is reachable (Ollama `nomic-embed-text` by default, or OpenAI); keyword overlap otherwise."""

import os
import re
import math
import time
import uuid
import requests
from flask import Blueprint, request, jsonify
from models import MemoryDocument

memory_bp = Blueprint('memory', __name__)
_STOP = set('the a an and or of to in for with on is are be it this that i we you my our build make create app project'.split())


def _words(text):
    return {w for w in re.findall(r'[a-z0-9]{3,}', (text or '').lower()) if w not in _STOP}


_embed_state = {'ok': None, 'checked': 0.0}


def embed(text):
    """Embedding vector from Ollama (EMBED_MODEL, default nomic-embed-text) or OpenAI; None if unavailable."""
    text = (text or '')[:4000]
    if _embed_state['ok'] is False and time.time() - _embed_state['checked'] < 120:
        return None
    try:
        url = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
        r = requests.post(f'{url}/api/embeddings', json={'model': os.getenv('EMBED_MODEL', 'nomic-embed-text'), 'prompt': text}, timeout=20)
        if r.status_code == 200 and r.json().get('embedding'):
            _embed_state['ok'] = True
            return r.json()['embedding']
    except requests.exceptions.RequestException:
        pass
    key = os.getenv('OPENAI_API_KEY', '')
    if key:
        try:
            r = requests.post('https://api.openai.com/v1/embeddings', headers={'Authorization': f'Bearer {key}'},
                              json={'model': 'text-embedding-3-small', 'input': text}, timeout=20)
            if r.status_code == 200:
                _embed_state['ok'] = True
                return r.json()['data'][0]['embedding']
        except requests.exceptions.RequestException:
            pass
    _embed_state.update(ok=False, checked=time.time())
    return None


def _cos(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def recall(goal, limit=8):
    """Preferences always apply. Other notes are ranked by embedding similarity when an embedding model
    is available (notes without a vector fall back to word overlap), else purely by word overlap."""
    gw, qv = _words(goal), embed(goal)
    notes = list(MemoryDocument.objects.limit(300))
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
    picked = prefs + [n for _, n in scored][:max(0, limit - len(prefs))]
    return chr(10).join(f'- [{n.kind}] {n.text}' for n in picked)


def remember(text, kind='note'):
    vec = embed(text) or []
    MemoryDocument(mem_id='mem_' + uuid.uuid4().hex[:8], text=text[:1500], kind=kind, vector=vec).save()


@memory_bp.route('/memory', methods=['GET'])
def list_mem():
    return jsonify([m.to_dict() for m in MemoryDocument.objects.limit(200)])


@memory_bp.route('/memory', methods=['POST'])
def add_mem():
    b = request.get_json(silent=True) or {}
    text = (b.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400
    remember(text, b.get('kind') if b.get('kind') in ('note', 'preference') else 'note')
    return jsonify({'ok': True}), 201


@memory_bp.route('/memory/<mem_id>', methods=['DELETE'])
def del_mem(mem_id):
    MemoryDocument.objects(mem_id=mem_id).delete()
    return jsonify({'ok': True})
