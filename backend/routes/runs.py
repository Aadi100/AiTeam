"""Runs API: start a goal, watch the agent map live, cancel, retry one agent, inspect a task."""

import json
import time
from flask import Blueprint, request, jsonify, Response, stream_with_context

from models import RunDocument, AgentTaskDocument
from orchestrator import engine, files
from auth import path_allowed, current_user, is_admin, with_stored_key, make_preview_token
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
    try:
        ups = files.get_many(b.get('attachments'), current_user()['u'])
    except files.FileError as e:
        return jsonify({'error': str(e)}), 400
    cont = (b.get('continueRunId') or '').strip()
    if cont:   # a follow-up change must target a project this user may modify, inside an allowed folder
        parent, err = _get(cont, modify=True)
        if err:
            return err
        if not path_allowed(parent.target_path):
            return jsonify({'error': 'that project folder is outside the allowed folders'}), 403
    run = engine.create_run(
        goal, target, with_stored_key(b.get('apiKeys'), current_user()['u']), b.get('plannerModel', ''), b.get('workerModel', ''),
        b.get('maxTokens') or 0, source=b.get('source', 'manual'), memory=recall(goal),
        owner=current_user()['u'], verify_run=bool(b.get('verify')), web_search=bool(b.get('webSearch')),
        review_plan=bool(b.get('reviewPlan')), continue_from=cont,
        deep_plan=b.get('deepPlan', True) is not False, thread_id=str(b.get('threadId') or '')[:40],
        attachments=[{'id': u.upload_id, 'name': u.name, 'kind': u.kind} for u in ups])
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
        engine.retry_task(run_id, task_id, with_stored_key(b.get('apiKeys'), current_user()['u']), b.get('maxTokens'))
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


def _resume(fn, run_id, *args):
    run, err = _get(run_id, modify=True)
    if err:
        return err
    try:
        fn(run_id, *args)
    except LookupError:
        return jsonify({'error': 'not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 409
    return jsonify(snapshot(run_id))


@runs_bp.route('/runs/<run_id>/answers', methods=['POST'])
def answers(run_id):
    """Answer the planner's or an agent's questions and resume the run."""
    b = request.get_json(silent=True) or {}
    return _resume(engine.answer_questions, run_id, b.get('answers') or {}, with_stored_key(b.get('apiKeys'), current_user()['u']))


@runs_bp.route('/runs/<run_id>/approve', methods=['POST'])
def approve(run_id):
    """'Start building': optional edits {modules:[{key,title,description,removed}], contract, summary}."""
    b = request.get_json(silent=True) or {}
    return _resume(engine.approve_plan, run_id, b.get('edits') or {}, with_stored_key(b.get('apiKeys'), current_user()['u']))


@runs_bp.route('/runs/<run_id>/replan', methods=['POST'])
def replan(run_id):
    """Ask the planner to revise the waiting plan with feedback."""
    b = request.get_json(silent=True) or {}
    return _resume(engine.revise_plan, run_id, b.get('feedback') or '', with_stored_key(b.get('apiKeys'), current_user()['u']))


@runs_bp.route('/runs/<run_id>/reject', methods=['POST'])
def reject(run_id):
    return _resume(engine.reject_plan, run_id)


@runs_bp.route('/runs/<run_id>/screenshot', methods=['GET'])
def screenshot(run_id):
    """The browser-check screenshot of the finished site."""
    import os
    from flask import send_file
    from orchestrator.worker import SHOT_DIR
    run, err = _get(run_id)
    if err:
        return err
    path = os.path.join(SHOT_DIR, f'{run_id}.png')
    if not os.path.isfile(path):
        return jsonify({'error': 'no screenshot'}), 404
    return send_file(path, mimetype='image/png', max_age=0)


PREVIEW_TYPES = {'.html': 'text/html; charset=utf-8', '.htm': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
                 '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
                 '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
                 '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp', '.ico': 'image/x-icon',
                 '.txt': 'text/plain; charset=utf-8', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
                 '.map': 'application/json', '.xml': 'application/xml', '.csv': 'text/csv'}


@runs_bp.route('/runs/<run_id>/preview-token', methods=['POST'])
def preview_token(run_id):
    """Start a live preview of the finished static site. Returns a URL path (15-minute, read-only token)."""
    from orchestrator import verify
    run, err = _get(run_id)
    if err:
        return err
    if not verify._static_dir(run.target_path):
        return jsonify({'error': 'There is no web page to preview here (no index.html). Python apps can be run from "Run the result".'}), 404
    u = current_user()
    return jsonify({'url': f'/api/preview/{make_preview_token(u["u"], u["r"], run_id)}/{run_id}/'})


@runs_bp.route('/preview/<token>/<run_id>/', defaults={'rel': ''})
@runs_bp.route('/preview/<token>/<run_id>/<path:rel>')
def preview(token, run_id, rel):
    """Serve the finished site's static files, sandboxed. Never executes server code, only whitelisted file types."""
    import os
    from flask import send_file
    from orchestrator import verify, sandbox
    run, err = _get(run_id)
    if err:
        return err
    site = verify._static_dir(run.target_path)
    if not site:
        return jsonify({'error': 'no web page'}), 404
    rel = (rel or 'index.html')
    if rel.endswith('/'):
        rel += 'index.html'
    ext = os.path.splitext(rel)[1].lower()
    if ext not in PREVIEW_TYPES:
        return jsonify({'error': 'file type not served'}), 403
    try:
        path = sandbox.safe_join(site, rel)
    except sandbox.SandboxError:
        return jsonify({'error': 'not found'}), 404
    if not os.path.isfile(path):
        return jsonify({'error': 'not found'}), 404
    resp = send_file(path, mimetype=PREVIEW_TYPES[ext], max_age=0)
    # even if someone opens the URL directly, the page runs in an opaque origin and cannot reach Adion
    resp.headers['Content-Security-Policy'] = 'sandbox allow-scripts allow-forms allow-modals allow-popups'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Cache-Control'] = 'no-store'
    return resp
