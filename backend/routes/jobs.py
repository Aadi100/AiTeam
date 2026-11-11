"""Background tasks panel: start / watch / stop / restart shell jobs (dev servers, tests, workers)."""

import os
import sys
import uuid
import subprocess
import threading
from collections import deque
from datetime import datetime
from flask import Blueprint, request, jsonify

from models import BackgroundJobDocument
from auth import path_allowed

jobs_bp = Blueprint('jobs', __name__)
_procs, _logs = {}, {}
_lock = threading.Lock()


def _pump(job_id, proc):
    buf = _logs[job_id]
    for line in iter(proc.stdout.readline, ''):
        buf.append(line.rstrip('\n')[:1000])
    code = proc.wait()
    doc = BackgroundJobDocument.objects(job_id=job_id).first()
    if doc:
        status = doc.status if doc.status == 'stopped' else ('exited' if code == 0 else 'failed')
        doc.update(set__status=status, set__exit_code=code, set__ended_at=datetime.utcnow(),
                   set__log_tail='\n'.join(list(buf)[-300:]))


def start_job(title, command, cwd, job_id=None):
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    proc = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', creationflags=flags)
    job_id = job_id or 'job_' + uuid.uuid4().hex[:8]
    with _lock:
        _procs[job_id], _logs[job_id] = proc, deque(maxlen=1000)
    BackgroundJobDocument.objects(job_id=job_id).update_one(
        upsert=True, set__title=title, set__command=command, set__cwd=cwd, set__status='running',
        set__pid=proc.pid, unset__exit_code=True, unset__ended_at=True, set__log_tail='')
    threading.Thread(target=_pump, args=(job_id, proc), daemon=True).start()
    return job_id


def _kill(proc):
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True)
    else:
        proc.terminate()


def mark_lost_on_boot():
    BackgroundJobDocument.objects(status='running').update(set__status='lost')


@jobs_bp.route('/jobs', methods=['GET'])
def list_jobs():
    return jsonify([j.to_dict() for j in BackgroundJobDocument.objects.limit(50)])


@jobs_bp.route('/jobs', methods=['POST'])
def create_job():
    b = request.get_json(silent=True) or {}
    cmd, cwd = (b.get('command') or '').strip(), (b.get('cwd') or '').strip()
    if not cmd or not cwd:
        return jsonify({'error': 'command and cwd are required'}), 400
    if not path_allowed(cwd) or not os.path.isdir(os.path.expanduser(cwd)):
        return jsonify({'error': 'cwd must be an existing folder inside ALLOWED_ROOTS'}), 400
    jid = start_job((b.get('title') or cmd)[:80], cmd, os.path.abspath(os.path.expanduser(cwd)))
    return jsonify(BackgroundJobDocument.objects.get(job_id=jid).to_dict()), 201


@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def job_detail(job_id):
    doc = BackgroundJobDocument.objects(job_id=job_id).first()
    if not doc:
        return jsonify({'error': 'not found'}), 404
    live = _logs.get(job_id)
    log = '\n'.join(live) if live is not None else doc.log_tail
    return jsonify({**doc.to_dict(), 'log': log[-20000:]})


@jobs_bp.route('/jobs/<job_id>/stop', methods=['POST'])
def stop_job(job_id):
    proc = _procs.get(job_id)
    doc = BackgroundJobDocument.objects(job_id=job_id).first()
    if not doc:
        return jsonify({'error': 'not found'}), 404
    if proc and proc.poll() is None:
        doc.update(set__status='stopped')
        _kill(proc)
    return jsonify({'ok': True})


@jobs_bp.route('/jobs/<job_id>/restart', methods=['POST'])
def restart_job(job_id):
    doc = BackgroundJobDocument.objects(job_id=job_id).first()
    if not doc:
        return jsonify({'error': 'not found'}), 404
    proc = _procs.get(job_id)
    if proc and proc.poll() is None:
        doc.update(set__status='stopped')
        _kill(proc)
        proc.wait(timeout=10)
    start_job(doc.title, doc.command, doc.cwd, job_id=job_id)
    return jsonify(BackgroundJobDocument.objects.get(job_id=job_id).to_dict())
