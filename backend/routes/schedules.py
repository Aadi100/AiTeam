"""Scheduled runs: interval ('every N minutes') or daily at HH:MM (server local time).
Unattended runs use the server's DEEPSEEK_API_KEY, or keys you explicitly chose to store (encrypted at rest)."""

import re
import time
import uuid
import threading
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from models import ScheduleDocument
from auth import path_allowed, current_user, is_admin, encrypt_json, decrypt_json, with_stored_key

schedules_bp = Blueprint('schedules', __name__)


def _own():
    return {} if is_admin() else {'owner__in': ['', current_user()['u']]}


def _due(s, now_utc):
    if not s.enabled:
        return False
    last = s.last_run_at
    if s.every_minutes > 0:
        return last is None or now_utc - last >= timedelta(minutes=s.every_minutes)
    if re.fullmatch(r'\d{2}:\d{2}', s.daily_at or ''):
        h, m = map(int, s.daily_at.split(':'))
        slot = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
        local_last = (last + (datetime.now() - datetime.utcnow())) if last else None
        return datetime.now() >= slot and (local_last is None or local_last < slot)
    return False


def _tick():
    from orchestrator import engine
    from routes.memory import recall
    now = datetime.utcnow()
    for s in ScheduleDocument.objects(enabled=True):
        if _due(s, now):
            keys = with_stored_key(decrypt_json(s.keys_enc) if s.keys_enc else {}, s.owner)
            run = engine.create_run(s.goal, s.target_path, keys, s.planner_model, s.worker_model,
                                    s.max_tokens, source='schedule', memory=recall(s.goal), owner=s.owner)
            s.update(set__last_run_at=now, set__last_run_id=run.run_id)
            print(f'[SCHEDULE] "{s.name}" started {run.run_id}')


def start_scheduler():
    def loop():
        while True:
            try:
                _tick()
            except Exception as e:  # noqa: BLE001
                print(f'[SCHEDULE] tick error: {e}')
            time.sleep(20)
    threading.Thread(target=loop, daemon=True, name='scheduler').start()


@schedules_bp.route('/schedules', methods=['GET'])
def list_s():
    qs = ScheduleDocument.objects if is_admin() else ScheduleDocument.objects(owner__in=['', current_user()['u']])
    return jsonify([s.to_dict() for s in qs])


@schedules_bp.route('/schedules', methods=['POST'])
def create_s():
    b = request.get_json(silent=True) or {}
    goal, target = (b.get('goal') or '').strip(), (b.get('targetPath') or '').strip()
    every, daily = int(b.get('everyMinutes') or 0), (b.get('dailyAt') or '').strip()
    if not goal or not target:
        return jsonify({'error': 'goal and targetPath are required'}), 400
    if not path_allowed(target):
        return jsonify({'error': 'targetPath is outside ALLOWED_ROOTS'}), 400
    if every < 0 or (every == 0 and not re.fullmatch(r'\d{2}:\d{2}', daily)):
        return jsonify({'error': 'set everyMinutes (>0) or dailyAt as HH:MM'}), 400
    ScheduleDocument(sched_id='sch_' + uuid.uuid4().hex[:8], name=(b.get('name') or goal[:40]), goal=goal,
                     target_path=target, every_minutes=every, daily_at=daily,
                     planner_model=b.get('plannerModel', ''), worker_model=b.get('workerModel', ''),
                     max_tokens=int(b.get('maxTokens') or 0), owner=current_user()['u'],
                     keys_enc=encrypt_json(b['apiKeys']) if b.get('storeKeys') and isinstance(b.get('apiKeys'), dict) else '').save()
    return jsonify({'ok': True}), 201


@schedules_bp.route('/schedules/<sid>', methods=['PUT'])
def toggle_s(sid):
    en = bool((request.get_json(silent=True) or {}).get('enabled', True))
    ScheduleDocument.objects(sched_id=sid, **_own()).update(set__enabled=en)
    return jsonify({'ok': True})


@schedules_bp.route('/schedules/<sid>', methods=['DELETE'])
def delete_s(sid):
    ScheduleDocument.objects(sched_id=sid, **_own()).delete()
    return jsonify({'ok': True})
