"""Runs API: start a goal, watch the agent map live, cancel, retry one agent, inspect a task."""

import json
import time
from flask import Blueprint, request, jsonify, Response, stream_with_context

from models import RunDocument, AgentTaskDocument
from orchestrator import engine
from auth import path_allowed, current_user, is_admin
from routes.memory import recall

runs_bp = Blueprint('runs', __name__)

TERMINAL = ('completed', 'failed', 'cancelled')


def _can_view(run):
    u = current_user()
    return is_admin() or u['r'] == 'viewer' or run.owner in ('', u['u'])


def _can_modify(run):
    return is_admin() or run.owner in ('', current_user()['u'])


def _get(run_id, modify=False):
    run = RunDocument.objects(run_id=run_id).first()
    if not run or not _can_view(run):
        return None, (jsonify({'error': 'not found'}), 404)
    if modify and not _can_modify(run):
        return None, (jsonify({'error': 'this run belongs to another user'}), 403)
    return run, None


def snapshot(run_id):
    run = RunDocument.objects(run_id=run_id).first()
    if not run:
        return None
    tasks = AgentTaskDocument.objects(run_id=run_id).order_by('order')
    return {'run': run.to_dict(), 'tasks': [t.to_dict() for t in tasks]}


@runs_bp.route('/runs', methods=['POST'])
def start_run():
    b = request.get_json(silent=True) or {}
    goal = (b.get('goal') or '').strip()
    target = (b.get('targetPath') or '').strip()
    if not goal:
        return jsonify({'error': 'goal is required'}), 400
    if not target:
        return jsonify({'error': 'targetPath is required'}), 400
    if not path_allowed(target):
        return jsonify({'error': 'targetPath is outside the allowed folders (set ALLOWED_ROOTS on the server)'}), 403
    run = engine.create_run(
        goal, target, b.get('apiKeys') or {}, b.get('plannerModel', ''), b.get('workerModel', ''),
        b.get('maxTokens') or 0, source=b.get('source', 'manual'), memory=recall(goal),
        owner=current_user()['u'], verify_run=bool(b.get('verify')))
    return jsonify(run.to_dict()), 201


@runs_bp.route('/runs', methods=['GET'])
def list_runs():
    qs = RunDocument.objects
    if not (is_admin() or current_user()['r'] == 'viewer'):
        qs = qs.filter(owner__in=['', current_user()['u']])
    return jsonify([r.to_dict() for r in qs.limit(50)])


@runs_bp.route('/runs/<run_id>', methods=['GET'])
def get_run(run_id):
    run, err = _get(run_id)
    return err if err else (jsonify(snapshot(run_id)), 200)


@runs_bp.route('/runs/<run_id>/stream', methods=['GET'])
def stream_run(run_id):
    """Server-Sent Events: pushes a full snapshot whenever anything changes."""
    run, err = _get(run_id)
    if err:
        return err

    def gen():
        last, idle = None, 0
        while True:
            snap = snapshot(run_id)
            if snap is None:
                yield 'event: error\ndata: {"error":"not found"}\n\n'
                return
            payload = json.dumps(snap, separators=(',', ':'))
            if payload != last:
                yield f'data: {payload}\n\n'
                last, idle = payload, 0
            else:
                idle += 1
                if idle % 25 == 0:
                    yield ': keepalive\n\n'
            if snap['run']['status'] in TERMINAL and not any(
                    t['status'] in ('queued', 'running') for t in snap['tasks']):
                yield 'event: done\ndata: {}\n\n'
                return
            time.sleep(0.6)
    return Response(stream_with_context(gen()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})


@runs_bp.route('/runs/<run_id>/cancel', methods=['POST'])
def cancel(run_id):
    run, err = _get(run_id, modify=True)
    if err:
        return err
    engine.cancel_run(run_id)
    return jsonify({'ok': True})


@runs_bp.route('/runs/<run_id>/tasks/<task_id>/retry', methods=['POST'])
def retry(run_id, task_id):
    """Re-run a single failed/skipped/cancelled agent without starting a new run."""
    run, err = _get(run_id, modify=True)
    if err:
        return err
    b = request.get_json(silent=True) or {}
    try:
        engine.retry_task(run_id, task_id, b.get('apiKeys') or {}, b.get('maxTokens'))
    except LookupError:
        return jsonify({'error': 'not found'}), 404
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    return jsonify({'ok': True})


@runs_bp.route('/runs/<run_id>/tasks/<task_id>', methods=['GET'])
def get_task(run_id, task_id):
    run, err = _get(run_id)
    if err:
        return err
    t = AgentTaskDocument.objects(run_id=run_id, task_id=task_id).first()
    return (jsonify(t.to_dict(detail=True)), 200) if t else (jsonify({'error': 'not found'}), 404)


@runs_bp.route('/runs/<run_id>/tasks/<task_id>/file', methods=['GET'])
def get_task_file(run_id, task_id):
    """Return the content of one file a task wrote (read from disk, sandbox-checked)."""
    from orchestrator import sandbox
    run, err = _get(run_id)
    if err:
        return err
    t = AgentTaskDocument.objects(run_id=run_id, task_id=task_id).first()
    path = request.args.get('path', '')
    if not t or path not in [f['path'] for f in t.files]:
        return jsonify({'error': 'not found'}), 404
    try:
        with open(sandbox.safe_join(run.target_path, path), encoding='utf-8') as fp:
            return jsonify({'path': path, 'content': fp.read()})
    except (OSError, sandbox.SandboxError) as e:
        return jsonify({'error': str(e)}), 404
