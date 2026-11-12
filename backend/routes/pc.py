"""
PC control API (admin only).

GET/PUT /api/pc/settings          folders, pause switch, trust mode
POST/DELETE /api/pc/folders       always-allow / remove a folder
POST /api/pc/tasks                {request}  start a task
GET  /api/pc/tasks/<id>           poll it
POST /api/pc/tasks/<id>/approve   {folders: {path: once|always|deny}}
POST /api/pc/tasks/<id>/deny      /undo
GET  /api/pc/activity             the log
"""

import os
from flask import Blueprint, request, jsonify

from models import PcTaskDocument, PcActionDocument
from orchestrator.pc import engine as pc, policy
from auth import current_user, is_admin, with_stored_key

pc_bp = Blueprint('pc', __name__)


@pc_bp.before_request
def _admin_only():
    if not is_admin():
        return jsonify({'error': 'PC control is for admins only'}), 403


def _me():
    return current_user()['u']


def _settings_dict():
    s = policy.get_settings(_me())
    return {'paused': s.paused, 'trust': s.trust, 'desktop': policy.known_folder('desktop'),
            'folders': list(s.folders), 'known': {n: policy.known_folder(n) for n in policy.KNOWN}}


@pc_bp.route('/pc/settings', methods=['GET'])
def get_settings():
    return jsonify(_settings_dict())


@pc_bp.route('/pc/settings', methods=['PUT'])
def put_settings():
    b = request.get_json(silent=True) or {}
    s = policy.get_settings(_me())
    if 'paused' in b:
        s.update(set__paused=bool(b['paused']))
    if 'trust' in b:
        s.update(set__trust=bool(b['trust']))
    return jsonify(_settings_dict())


@pc_bp.route('/pc/folders', methods=['POST'])
def add_folder():
    path = str((request.get_json(silent=True) or {}).get('path') or '').strip()
    if not path:
        return jsonify({'error': 'path is required'}), 400
    real = policy.resolve(path)
    chk = policy.check_path(_me(), real, False)
    if chk['status'] == 'deny':
        return jsonify({'error': chk['reason']}), 400
    if not os.path.isdir(real):
        return jsonify({'error': f'{real} is not a folder'}), 400
    policy.get_settings(_me()).update(add_to_set__folders=real)
    return jsonify(_settings_dict())


@pc_bp.route('/pc/folders', methods=['DELETE'])
def remove_folder():
    path = str((request.get_json(silent=True) or {}).get('path') or '')
    policy.get_settings(_me()).update(pull__folders=path)
    return jsonify(_settings_dict())


@pc_bp.route('/pc/tasks', methods=['POST'])
def start_task():
    req = str((request.get_json(silent=True) or {}).get('request') or '').strip()
    if not req:
        return jsonify({'error': 'request is required'}), 400
    tid = pc.start_task(req, _me(), with_stored_key(None, _me()))
    return jsonify(PcTaskDocument.objects.get(task_id=tid).to_dict()), 201


def _task(tid):
    t = PcTaskDocument.objects(task_id=tid).first()
    return t if t and t.owner == _me() else None


@pc_bp.route('/pc/tasks/<tid>', methods=['GET'])
def get_task(tid):
    t = _task(tid)
    return (jsonify(t.to_dict()), 200) if t else (jsonify({'error': 'not found'}), 404)


def _act(fn, tid, *args):
    try:
        res = fn(tid, _me(), *args)
    except LookupError:
        return jsonify({'error': 'not found'}), 404
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    out = PcTaskDocument.objects.get(task_id=tid).to_dict()
    if isinstance(res, dict):
        out['undoReport'] = res
    return jsonify(out)


@pc_bp.route('/pc/tasks/<tid>/approve', methods=['POST'])
def approve(tid):
    b = request.get_json(silent=True) or {}
    return _act(pc.approve, tid, b.get('folders') or {}, with_stored_key(None, _me()))


@pc_bp.route('/pc/tasks/<tid>/deny', methods=['POST'])
def deny(tid):
    return _act(pc.deny, tid)


@pc_bp.route('/pc/tasks/<tid>/undo', methods=['POST'])
def undo(tid):
    return _act(pc.undo, tid)


@pc_bp.route('/pc/activity', methods=['GET'])
def activity():
    limit = max(1, min(200, request.args.get('limit', 60, type=int)))
    rows = PcActionDocument.objects(owner=_me()).limit(limit)
    tasks = PcTaskDocument.objects(owner=_me()).limit(15)
    return jsonify({'actions': [a.to_dict() for a in rows], 'tasks': [t.to_dict() for t in tasks]})
