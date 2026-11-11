"""
Run engine: plan -> build the agent map -> schedule tasks on a worker pool respecting
dependencies -> retry -> (optional) run-and-fix verification -> integration review -> final status.
API keys live only in memory for the lifetime of a run; they are never stored in MongoDB.
"""

import os
import uuid
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from models import RunDocument, AgentTaskDocument
from . import llm, planner, sandbox, worker, verify

MAX_WORKERS = int(os.getenv('MAX_WORKERS', '6'))
MAX_ATTEMPTS = 2
_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='agent')
_run_keys = {}
_active = set()          # run_ids that currently have a scheduler thread
_lock = threading.Lock()

DEFAULT_PLANNER = os.getenv('PLANNER_MODEL', 'claude-sonnet-5-5')
DEFAULT_WORKER = os.getenv('WORKER_MODEL', 'gemini-2.5-flash')
TERMINAL_TASK = ('done', 'failed', 'skipped', 'cancelled')


def _now():
    return datetime.utcnow()


def create_run(goal, target_path, keys, planner_model='', worker_model='', max_tokens=0, source='manual',
               memory='', owner='', verify_run=False):
    target = sandbox.expand_root(target_path)
    os.makedirs(target, exist_ok=True)
    run = RunDocument(run_id='run_' + uuid.uuid4().hex[:10], goal=goal, target_path=target,
                      planner_model=planner_model or DEFAULT_PLANNER, worker_model=worker_model or DEFAULT_WORKER,
                      max_tokens=int(max_tokens or 0), source=source, owner=owner, verify=bool(verify_run),
                      started_at=_now())
    run.save()
    with _lock:
        _run_keys[run.run_id] = {'keys': keys or {}, 'memory': memory}
        _active.add(run.run_id)
    threading.Thread(target=_coordinate, args=(run.run_id,), daemon=True, name=run.run_id).start()
    return run


def cancel_run(run_id):
    RunDocument.objects(run_id=run_id).update_one(set__cancel_requested=True)


def retry_task(run_id, task_id, keys, max_tokens=None):
    """Re-run one failed/skipped/cancelled agent (plus everything downstream that was skipped)."""
    run = RunDocument.objects(run_id=run_id).first()
    task = AgentTaskDocument.objects(run_id=run_id, task_id=task_id).first()
    if not run or not task:
        raise LookupError('run or task not found')
    with _lock:
        if run_id in _active:
            raise RuntimeError('this run is still active; wait for it to finish or cancel it first')
    if task.status not in ('failed', 'skipped', 'cancelled'):
        raise RuntimeError(f'only failed, skipped or cancelled agents can be retried (this one is {task.status})')
    reset = {'set__status': 'queued', 'set__error': '', 'unset__ended_at': True, 'set__attempts': 0}
    task.update(**reset)
    # downstream tasks that were skipped/cancelled because of it, plus the verify/review steps
    for t in AgentTaskDocument.objects(run_id=run_id, status__in=['skipped', 'cancelled']):
        t.update(**reset)
    AgentTaskDocument.objects(run_id=run_id, kind__in=['verify', 'review']).update(**reset)
    upd = {'set__status': 'running', 'set__cancel_requested': False, 'set__error': '', 'unset__ended_at': True}
    if max_tokens:
        upd['set__max_tokens'] = int(max_tokens)
    elif run.max_tokens and run.tokens_in + run.tokens_out >= run.max_tokens:
        upd['set__max_tokens'] = (run.tokens_in + run.tokens_out) + run.max_tokens  # grant one more budget slice
    run.update(**upd)
    with _lock:
        _run_keys[run_id] = {'keys': keys or {}, 'memory': ''}
        _active.add(run_id)
    threading.Thread(target=_schedule_then_finish, args=(run_id,), daemon=True, name=run_id).start()


def _finish(run_id, status, error=''):
    upd = {'set__status': status, 'set__ended_at': _now()}
    if error or status == 'completed':
        upd['set__error'] = error
    RunDocument.objects(run_id=run_id).update_one(**upd)
    try:  # tell the user how to run the result
        run = RunDocument.objects.get(run_id=run_id)
        if status != 'cancelled' and os.path.isdir(run.target_path):
            run.update(set__suggested=verify.detect_commands(run.target_path))
    except Exception:  # noqa: BLE001 - suggestions are best-effort
        pass
    with _lock:
        _run_keys.pop(run_id, None)
        _active.discard(run_id)


def _execute(run_id, task_id):
    """Runs on a pool thread."""
    run = RunDocument.objects.get(run_id=run_id)
    task = AgentTaskDocument.objects.get(task_id=task_id)
    with _lock:
        ctx = _run_keys.get(run_id, {'keys': {}})
    spec = llm.resolve(run.worker_model, ctx['keys'])
    AgentTaskDocument.objects(task_id=task_id).update_one(
        set__status='running', set__started_at=task.started_at or _now(), set__model=spec['label'],
        inc__attempts=1, set__error='')
    task.reload()
    runner = {'review': worker.run_review, 'verify': worker.run_integration}.get(task.kind, worker.run_module)
    try:
        runner(run, task, spec)
        AgentTaskDocument.objects(task_id=task_id).update_one(set__status='done', set__ended_at=_now())
    except worker.Stopped:
        worker.log(task, 'Stopped (run cancelled or budget reached)', 'warn')
        AgentTaskDocument.objects(task_id=task_id).update_one(set__status='cancelled', set__ended_at=_now())
    except Exception as e:  # noqa: BLE001 - surface any worker failure on the task
        task.reload()
        msg = f'{type(e).__name__}: {e}'
        worker.log(task, msg, 'error')
        # the integration step already used its own fix rounds; don't repeat them
        if (task.kind != 'verify' and task.attempts < MAX_ATTEMPTS
                and not RunDocument.objects.get(run_id=run_id).cancel_requested):
            worker.log(task, 'Retrying', 'warn')
            AgentTaskDocument.objects(task_id=task_id).update_one(set__status='queued', set__error=msg)
        else:
            AgentTaskDocument.objects(task_id=task_id).update_one(
                set__status='failed', set__error=msg, set__ended_at=_now())


def _coordinate(run_id):
    try:
        run = RunDocument.objects.get(run_id=run_id)
        with _lock:
            ctx = _run_keys.get(run_id, {'keys': {}, 'memory': ''})
        # ── 1. plan ──
        pspec = llm.resolve(run.planner_model, ctx['keys'])
        run.update(set__planner_model=pspec['label'])
        try:
            plan, ti, to = planner.make_plan(pspec, run.goal, ctx.get('memory', ''), sandbox.tree(run.target_path))
        except llm.LLMError as e:
            return _finish(run_id, 'failed', f'Planning failed: {e}')
        RunDocument.objects(run_id=run_id).update_one(
            inc__tokens_in=ti, inc__tokens_out=to, set__project_name=plan['project_name'],
            set__summary=plan['summary'], set__contract=plan['contract'], set__status='running')

        # ── 2. build the agent map ──
        ids = {m['key']: 'task_' + uuid.uuid4().hex[:10] for m in plan['modules']}
        for i, m in enumerate(plan['modules']):
            AgentTaskDocument(task_id=ids[m['key']], run_id=run_id, key=m['key'], title=m['title'],
                              description=m['description'], folder=m['folder'], order=i * 100,
                              depends_on=[ids[d] for d in m['depends_on']]).save()
        review_deps = list(ids.values())
        if run.verify:
            verify_id = 'task_' + uuid.uuid4().hex[:10]
            AgentTaskDocument(task_id=verify_id, run_id=run_id, key='verify', kind='verify',
                              title='Run the project and fix integration errors', folder='', order=999_000,
                              description='Start the generated app, request /, and repair what breaks',
                              depends_on=list(ids.values())).save()
            review_deps.append(verify_id)
        AgentTaskDocument(task_id='task_' + uuid.uuid4().hex[:10], run_id=run_id, key='review', kind='review',
                          title='Integration review and README', folder='', order=999_999,
                          description='Final glue files and syntax audit', depends_on=review_deps).save()
    except Exception as e:  # noqa: BLE001
        return _finish(run_id, 'failed', f'Engine error: {type(e).__name__}: {e}')
    _schedule_then_finish(run_id)


def _schedule_then_finish(run_id):
    try:
        _schedule(run_id)
        run = RunDocument.objects.get(run_id=run_id)
        mods = list(AgentTaskDocument.objects(run_id=run_id, kind='module'))
        verify_task = AgentTaskDocument.objects(run_id=run_id, kind='verify').first()
        if run.cancel_requested:
            _finish(run_id, 'cancelled', run.error or 'Cancelled')
        elif all(t.status == 'done' for t in mods):
            warn = ''
            if verify_task and verify_task.status == 'failed':
                warn = 'Built, but the integration check failed: ' + verify_task.error[:300]
            _finish(run_id, 'completed', warn)
            try:
                from routes.memory import remember
                remember(f'Built "{run.project_name}" in {run.target_path}: {run.summary}', 'build')
            except Exception:  # noqa: BLE001 - memory is best-effort
                pass
        else:
            bad = [t.title for t in mods if t.status != 'done']
            _finish(run_id, 'failed', f'{len(bad)} module(s) did not finish: ' + '; '.join(bad[:4]))
    except Exception as e:  # noqa: BLE001
        _finish(run_id, 'failed', f'Engine error: {type(e).__name__}: {e}')


def _schedule(run_id):
    submitted = set()
    while True:
        run = RunDocument.objects.get(run_id=run_id)
        tasks = list(AgentTaskDocument.objects(run_id=run_id))
        by_id = {t.task_id: t for t in tasks}
        if run.cancel_requested:
            AgentTaskDocument.objects(run_id=run_id, status='queued').update(
                set__status='cancelled', set__ended_at=_now())
        else:
            for t in tasks:
                if t.status != 'queued' or t.task_id in submitted:
                    continue
                dep_states = [by_id[d].status for d in t.depends_on if d in by_id]
                if t.kind == 'review':
                    ready = all(s in TERMINAL_TASK for s in dep_states)   # review reports on whatever exists
                elif any(s in ('failed', 'skipped', 'cancelled') for s in dep_states):
                    AgentTaskDocument.objects(task_id=t.task_id).update_one(
                        set__status='skipped', set__ended_at=_now(),
                        set__error='A dependency failed or was cancelled')
                    continue
                else:
                    ready = all(s == 'done' for s in dep_states)
                if ready:
                    submitted.add(t.task_id)
                    _pool.submit(_run_and_release, run_id, t.task_id, submitted)
        if not any(t.status in ('queued', 'running') for t in AgentTaskDocument.objects(run_id=run_id)):
            return
        time.sleep(0.4)


def _run_and_release(run_id, task_id, submitted):
    try:
        _execute(run_id, task_id)
    finally:
        # allow a retried (re-queued) task to be submitted again
        if AgentTaskDocument.objects.get(task_id=task_id).status == 'queued':
            submitted.discard(task_id)


def recover_interrupted():
    """On boot, runs that were mid-flight died with the old process: mark them failed, not 'running' forever."""
    now = _now()
    AgentTaskDocument.objects(status__in=['running', 'queued']).update(
        set__status='failed', set__error='Server restarted while this agent was working', set__ended_at=now)
    n = RunDocument.objects(status__in=['planning', 'running']).update(
        set__status='failed', set__error='Server restarted during the run. Retry the failed agents.', set__ended_at=now)
    if n:
        print(f'[RECOVER] marked {n} interrupted run(s) as failed')
