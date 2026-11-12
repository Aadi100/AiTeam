"""
Run engine: route -> (ask / plan / review) -> build the agent map -> schedule tasks on a worker pool respecting
dependencies -> retry -> planner revises failed modules -> (optional) browser check & fix -> review -> final status.

A run can PAUSE for the user and resume later:
  awaiting_input     the planner or an agent asked a question; resumes in answer_questions()
  awaiting_approval  a large plan is waiting for "Start building"; resumes in approve_plan() / revise_plan()
API keys live only in memory while a run is active; they are never stored in MongoDB (resume calls pass them again).
"""

import os
import uuid
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from models import RunDocument, AgentTaskDocument
from . import llm, planner, sandbox, worker, verify, router, search, plans

MAX_WORKERS = int(os.getenv('MAX_WORKERS', '6'))
MAX_ATTEMPTS = 2
MAX_REVISIONS = 2            # how many times the planner may re-plan one run after agent failures
REVIEW_MIN_MODULES = 4       # plans at least this big wait for the user's approval (when review is on)
_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix='agent')
_run_keys = {}
_active = set()          # run_ids that currently have a coordinator/scheduler thread
_lock = threading.Lock()

DEFAULT_PLANNER = os.getenv('PLANNER_MODEL', 'deepseek-chat')
DEFAULT_WORKER = os.getenv('WORKER_MODEL', 'deepseek-chat')
TERMINAL_TASK = ('done', 'failed', 'skipped', 'cancelled')
AWAITING = ('awaiting_input', 'awaiting_approval')


def _now():
    return datetime.utcnow()


def _spawn(target, run_id, *args):
    threading.Thread(target=target, args=(run_id, *args), daemon=True, name=run_id).start()


def _activate(run_id, keys, memory=''):
    with _lock:
        _run_keys[run_id] = {'keys': keys or {}, 'memory': memory}
        _active.add(run_id)


def _release(run_id):
    with _lock:
        _run_keys.pop(run_id, None)
        _active.discard(run_id)


def create_run(goal, target_path, keys, planner_model='', worker_model='', max_tokens=0, source='manual',
               memory='', owner='', verify_run=False, web_search=False, review_plan=False, continue_from='', deep_plan=True):
    run_id = 'run_' + uuid.uuid4().hex[:10]
    mode, parent_id, project = 'build', '', ''
    if continue_from:   # a follow-up change to an existing project: same folder, planner sees what exists
        parent = RunDocument.objects(run_id=continue_from).first()
        if not parent:
            raise LookupError('the project to continue was not found')
        target, mode, parent_id, project = parent.target_path, 'edit', parent.run_id, parent.project_name
    else:
        # every build gets its own project folder so two projects never overwrite each other's files
        root = sandbox.expand_root(target_path)
        target = os.path.join(root, f"{sandbox.slug(goal[:30], 'project').replace('/', '-')}-{run_id[-4:]}")
    run = RunDocument(run_id=run_id, goal=goal, target_path=target, mode=mode, parent_run_id=parent_id,
                      project_name=project, planner_model=planner_model or DEFAULT_PLANNER,
                      worker_model=worker_model or DEFAULT_WORKER, max_tokens=int(max_tokens or 0), source=source,
                      owner=owner, verify=bool(verify_run), web_search=bool(web_search), review_plan=bool(review_plan), deep_plan=bool(deep_plan),
                      started_at=_now())
    run.save()
    _activate(run_id, keys, memory)
    _spawn(_coordinate, run_id)
    return run


def cancel_run(run_id):
    run = RunDocument.objects(run_id=run_id).first()
    if run and run.status in AWAITING:   # nothing is running: close it directly
        AgentTaskDocument.objects(run_id=run_id, status__in=['queued', 'waiting']).update(
            set__status='cancelled', set__ended_at=_now())
        run.update(set__status='cancelled', set__error='Cancelled', set__plan={}, set__ended_at=_now())
        return
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
    if run.status in AWAITING:
        raise RuntimeError('this run is waiting for your input')
    if task.status not in ('failed', 'skipped', 'cancelled') or task.replaced:
        raise RuntimeError(f'only failed, skipped or cancelled agents can be retried (this one is {task.status})')
    reset = {'set__status': 'queued', 'set__error': '', 'unset__ended_at': True, 'set__attempts': 0}
    task.update(**reset)
    # downstream tasks that were skipped/cancelled because of it, plus the verify/review steps
    for t in AgentTaskDocument.objects(run_id=run_id, status__in=['skipped', 'cancelled'], replaced=False):
        t.update(**reset)
    AgentTaskDocument.objects(run_id=run_id, kind__in=['verify', 'review']).update(**reset)
    upd = {'set__status': 'running', 'set__cancel_requested': False, 'set__error': '', 'unset__ended_at': True}
    if max_tokens:
        upd['set__max_tokens'] = int(max_tokens)
    elif run.max_tokens and run.tokens_in + run.tokens_out >= run.max_tokens:
        upd['set__max_tokens'] = (run.tokens_in + run.tokens_out) + run.max_tokens  # grant one more budget slice
    run.update(**upd)
    _activate(run_id, keys)
    _spawn(_schedule_then_finish, run_id)


# ───────────────────────── pause / resume ─────────────────────────

def _pause(run_id, status, **fields):
    RunDocument.objects(run_id=run_id).update_one(set__status=status, **fields)
    _release(run_id)


def _need(run_id, *statuses):
    run = RunDocument.objects(run_id=run_id).first()
    if not run:
        raise LookupError('run not found')
    if run.status not in statuses:
        raise RuntimeError(f'this run is {run.status}, not waiting for that')
    with _lock:
        if run_id in _active:
            raise RuntimeError('this run is busy')
    return run


def answer_questions(run_id, answers, keys):
    """The user answered the planner's or an agent's questions. Resume where the run stopped."""
    run = _need(run_id, 'awaiting_input')
    qs = list(run.questions)
    for q in qs:
        a = str((answers or {}).get(q['id'], '')).strip()
        if a and not q.get('answer'):
            q['answer'] = a[:500]
    if any(not q.get('answer') for q in qs):
        raise ValueError('please answer every question')
    run.update(set__questions=qs)
    has_tasks = AgentTaskDocument.objects(run_id=run_id).count() > 0
    if not has_tasks:   # the planner was waiting: plan again with the answers
        run.update(set__status='planning')
        _activate(run_id, keys)
        return _spawn(_coordinate, run_id)
    for q in qs:        # agents were waiting: hand each its answer and let it continue
        if q.get('taskId'):
            t = AgentTaskDocument.objects(task_id=q['taskId'], status='waiting').first()
            if t:
                t.update(set__status='queued', set__attempts=0, set__error='',
                         set__notes=(t.notes + f"\nQ: {q['q']}\nA: {q['answer']}").strip())
    run.update(set__status='running')
    _activate(run_id, keys)
    _spawn(_schedule_then_finish, run_id)


def approve_plan(run_id, edits, keys):
    """'Start building': apply the user's edits to the waiting plan, then build it."""
    run = _need(run_id, 'awaiting_approval')
    plan = dict(run.plan or {})
    mods = [dict(m) for m in plan.get('modules', [])]
    removed, by = set(), {m['key']: m for m in mods}
    for e in (edits or {}).get('modules') or []:
        m = by.get(e.get('key'))
        if not m:
            continue
        if e.get('removed'):
            removed.add(m['key'])
            continue
        if str(e.get('title') or '').strip():
            m['title'] = str(e['title']).strip()[:120]
        if str(e.get('description') or '').strip():
            m['description'] = str(e['description']).strip()[:3000]
    mods = [m for m in mods if m['key'] not in removed]
    for m in mods:
        m['depends_on'] = [d for d in m.get('depends_on', []) if d not in removed]
    if not mods:
        raise ValueError('at least one module must remain')
    plan['modules'] = planner._clean(mods)
    for field in ('contract', 'summary'):
        if isinstance((edits or {}).get(field), str) and edits[field].strip():
            plan[field] = edits[field].strip()[:6000]
    run.update(set__plan={}, set__status='running')
    _activate(run_id, keys)
    _spawn(_build_from_plan, run_id, plan)


def revise_plan(run_id, feedback, keys):
    """'Ask for changes': the planner revises the waiting plan using the user's feedback."""
    run = _need(run_id, 'awaiting_approval')
    if not str(feedback or '').strip():
        raise ValueError('say what to change')
    run.update(set__status='planning')
    _activate(run_id, keys)
    _spawn(_coordinate, run_id, str(feedback).strip()[:1500])


def reject_plan(run_id):
    run = _need(run_id, 'awaiting_approval')
    run.update(set__status='cancelled', set__error='Plan rejected', set__plan={}, set__ended_at=_now())


# ───────────────────────── finishing ─────────────────────────

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
    _release(run_id)


def _end_run(run_id, **fields):
    RunDocument.objects(run_id=run_id).update_one(set__ended_at=_now(), **fields)
    _release(run_id)


# ───────────────────────── one agent ─────────────────────────

def _revise_failed(run_id, task, spec):
    """An agent failed twice. The planner decides: retry with a clearer brief, split it into parts, or give up."""
    run = RunDocument.objects.get(run_id=run_id)
    if run.cancel_requested or run.revisions >= MAX_REVISIONS or task.replans:
        return False
    worker.log(task, 'Failed twice. Asking the planner to revise the plan', 'warn')
    siblings = list(AgentTaskDocument.objects(run_id=run_id, kind='module'))
    try:
        dec, ti, to = planner.revise_after_failure(
            spec, run, task, siblings, ctx={'owner': run.owner, 'run_id': run_id, 'task_id': task.task_id})
    except llm.LLMError as e:
        worker.log(task, f'Planner could not revise: {e}', 'warn')
        return False
    worker.charge(run_id, task, ti, to)
    RunDocument.objects(run_id=run_id).update_one(inc__revisions=1)
    if dec['contract_add']:
        RunDocument.objects(run_id=run_id).update_one(set__contract=(run.contract + '\n' + dec['contract_add']).strip())
    if dec['action'] == 'retry':
        AgentTaskDocument.objects(task_id=task.task_id).update_one(
            set__description=dec['description'], set__status='queued', set__attempts=0, set__error='', inc__replans=1)
        worker.log(task, 'Planner rewrote the assignment; trying again', 'ok')
        return True
    if dec['action'] == 'split':
        new_ids, used = [], {t.key for t in siblings}
        for i, m in enumerate(dec['modules']):
            key = m['key'] if m['key'] not in used else f"{m['key']}_{i + 1}"
            used.add(key)
            sub_folder = f"{task.folder}/{key}" if task.folder else key
            tid = 'task_' + uuid.uuid4().hex[:10]
            AgentTaskDocument(task_id=tid, run_id=run_id, key=key, parent_id=task.parent_id, title=m['title'],
                              description=m['description'], folder=sub_folder, order=task.order + i + 1,
                              depends_on=list(task.depends_on), expects=m.get('expects', []), replans=1).save()
            new_ids.append(tid)
        # point everything that waited on the failed module at its replacements BEFORE retiring it,
        # so the scheduler never sees a dependent with a dead dependency
        for t in AgentTaskDocument.objects(run_id=run_id, depends_on=task.task_id):
            t.update(pull__depends_on=task.task_id)
            t.update(add_to_set__depends_on=new_ids)
        AgentTaskDocument.objects(task_id=task.task_id).update_one(
            set__replaced=True, set__status='skipped', set__error='Replaced by the planner with smaller parts',
            set__ended_at=_now())
        worker.log(task, f'Planner split this module into {len(new_ids)} smaller agents', 'ok')
        return True
    worker.log(task, f'Planner: nothing more to try. {dec.get("reason", "")}', 'warn')
    return False


def _try_revise(run_id, task, spec):
    """Re-planning is a bonus: if it breaks for any reason the agent simply fails as before."""
    try:
        return _revise_failed(run_id, task, spec)
    except Exception as e:  # noqa: BLE001
        worker.log(task, f'Re-planning crashed ({type(e).__name__}); marking the agent failed', 'warn')
        return False


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
    except worker.NeedInput as e:
        qid = 'a' + uuid.uuid4().hex[:5]
        RunDocument.objects(run_id=run_id).update_one(push__questions={
            'id': qid, 'q': e.question, 'options': e.options, 'answer': '', 'taskId': task_id, 'agent': task.title})
        AgentTaskDocument.objects(task_id=task_id).update_one(set__status='waiting', inc__asks=1)
        worker.log(task, f'Asked you: {e.question}', 'warn')
    except Exception as e:  # noqa: BLE001 - surface any worker failure on the task
        task.reload()
        msg = f'{type(e).__name__}: {e}'
        worker.log(task, msg, 'error')
        cancelled = RunDocument.objects.get(run_id=run_id).cancel_requested
        if task.kind != 'verify' and task.attempts < MAX_ATTEMPTS and not cancelled:
            worker.log(task, 'Retrying', 'warn')
            AgentTaskDocument.objects(task_id=task_id).update_one(set__status='queued', set__error=msg)
        elif task.kind == 'module' and not cancelled and _try_revise(run_id, task, llm.resolve(run.planner_model, ctx['keys'])):
            AgentTaskDocument.objects(task_id=task_id).update_one(set__error=msg)
        else:
            AgentTaskDocument.objects(task_id=task_id).update_one(
                set__status='failed', set__error=msg, set__ended_at=_now())


# ───────────────────────── coordinator ─────────────────────────

ANSWER_SYSTEM_WEB = ("You are Adion, a sharp personal assistant. Answer the question using the numbered WEB SOURCES. "
                     "Cite them inline like [1] or [2]. If the sources do not cover something, say so instead of guessing. "
                     "Be direct and compact: a short paragraph or a compact list.")

ANSWER_SYSTEM = ("You are Adion, a sharp personal assistant. Answer the question directly and accurately, in a few short "
                 "paragraphs or a compact list. You have no internet access and your knowledge has a cutoff date, so for anything "
                 "recent, local or uncertain say so briefly instead of guessing. Do not offer to build anything.")

SMALL_CONTRACT = ("stack: plain HTML/CSS/JS in a few files (index.html, style.css, app.js) unless the goal clearly needs a backend, "
                  "then Python Flask (app.py, requirements.txt) serving the page at /.\n"
                  "rules: keep it simple, complete and runnable; no placeholders; no external build step.")

UNATTENDED = "This is an unattended run: nobody can answer questions. Decide everything yourself and list your assumptions."


def _answer_direct(run, spec, lctx, keys):
    """A plain question: one short call, no planner, no agents. Searches the web first when the question is
    about something recent (or the user asked for it) and a Tavily key is available."""
    system, prompt, sources, note = ANSWER_SYSTEM, run.goal, [], ''
    tkey = (keys or {}).get('tavily', '')
    if tkey and (run.web_search or search.needs_search(run.goal)):
        try:
            found = search.search(run.goal, tkey, ctx=dict(lctx, purpose='search'))['results']
            if found:
                system = ANSWER_SYSTEM_WEB
                prompt = f'WEB SOURCES:\n{search.format_sources(found)}\n\nQUESTION: {run.goal}'
                sources = [{'title': r['title'], 'url': r['url']} for r in found]
        except search.SearchError as e:
            note = f'\n\n(Web search was unavailable: {e} This answer is from my built-in knowledge and may be out of date.)'
    elif run.web_search and not tkey:
        note = '\n\n(Web search is switched on but no Tavily key is saved. Add one in Models & keys.)'
    text, ti, to = _stream_answer(run.run_id, spec, system, prompt, lctx)
    if text is None:   # cancelled while streaming
        return _finish(run.run_id, 'cancelled', 'Cancelled')
    if not text.strip():
        raise llm.LLMError('the model returned an empty answer')
    _end_run(run.run_id, inc__tokens_in=ti, inc__tokens_out=to, set__answer=text.strip() + note, set__sources=sources,
             set__project_name=run.goal[:60], set__status='completed')


def _stream_answer(run_id, spec, system, prompt, lctx):
    """Write the answer into the run as it is generated, so the UI shows it word by word.
    Falls back to one normal call if streaming fails. Returns (text, tokens_in, tokens_out); text is None if cancelled."""
    buf, ti, to, last = [], 0, 0, 0.0
    try:
        for kind, val in llm.chat_stream(spec, system, prompt, max_output=1200, ctx=dict(lctx, purpose='answer')):
            if kind == 'usage':
                ti, to = val
                continue
            buf.append(val)
            if time.time() - last > 0.25:
                last = time.time()
                RunDocument.objects(run_id=run_id).update_one(set__answer=''.join(buf))
                if RunDocument.objects.get(run_id=run_id).cancel_requested:
                    return None, 0, 0
        return ''.join(buf), ti, to
    except llm.LLMError as e:
        if not buf and 'rejected' not in str(e) and 'balance' not in str(e):
            return llm.chat(spec, system, prompt, json_mode=False, max_output=1200, ctx=dict(lctx, purpose='answer'))
        if buf:   # got part of an answer, then the connection dropped: keep what we have
            return ''.join(buf) + '\n\n(The connection dropped before the answer finished.)', ti, to
        raise


def _coordinate(run_id, feedback=''):
    try:
        run = RunDocument.objects.get(run_id=run_id)
        with _lock:
            ctx = _run_keys.get(run_id, {'keys': {}, 'memory': ''})
        # ── 0. route with plain code (zero tokens), forecast the cost ──
        lctx = {'owner': run.owner, 'run_id': run_id}
        kind = run.kind
        if not kind:
            kind = router.classify(run.goal)
            if run.mode == 'edit' and kind != 'chat':
                kind = 'edit'
            fc = router.forecast(run.goal, kind, verify=run.verify, web_search=run.web_search)
            run.update(set__kind=kind, set__estimate_tokens=fc['tokens'], set__estimate_cost=fc['cost'])
        # ── 1. plan ──
        pspec = llm.resolve(run.planner_model, ctx['keys'])
        run.update(set__planner_model=pspec['label'])
        clar = '\n'.join(f"Q: {q['q']}\nA: {q['answer']}" for q in run.questions if q.get('answer') and not q.get('taskId'))
        if run.source == 'schedule':
            clar = (clar + '\n' + UNATTENDED).strip()
        try:
            if kind == 'chat':
                return _answer_direct(run, pspec, lctx, ctx['keys'])
            if kind == 'pc':   # something to do on the user's PC: hand over to the PC engine (it asks before changing anything)
                from .pc import engine as pc_engine
                tid = pc_engine.start_task(run.goal, run.owner, ctx['keys'], run_id=run_id)
                return _end_run(run_id, set__pc_task_id=tid, set__answer='On it. Watch the card below: I will ask before I change anything.',
                                set__project_name=run.goal[:60], set__status='completed')
            if kind == 'small':   # one agent builds it at the project root; no planner, critic or review
                plan, ti, to = {'project_name': run.goal[:60], 'summary': run.goal[:240], 'contract': SMALL_CONTRACT,
                                'assumptions': [], 'modules': [{'key': 'app', 'title': 'Build ' + run.goal[:70],
                                                                'description': run.goal, 'folder': '', 'depends_on': [],
                                                                'expects': []}]}, 0, 0
            else:
                edit = None
                if run.mode == 'edit':
                    parent = RunDocument.objects(run_id=run.parent_run_id).first()
                    edit = {'summary': (parent.summary if parent else '') or run.project_name,
                            'contract': parent.contract if parent else '', 'tree': sandbox.tree(run.target_path)}
                existing = sandbox.tree(run.target_path) if os.path.isdir(run.target_path) else []
                example = ''
                if not edit and not feedback:   # an earlier plan that worked for a similar goal
                    prior = plans.similar(run.goal, run.owner)
                    if prior:
                        example = plans.brief(prior)
                        run.update(set__reused_plan=prior.project_name)
                deep = (run.deep_plan and kind in ('large', 'auto') and not edit and pspec['model'] == 'deepseek-chat'
                        and router.is_hard(run.goal))
                args = dict(ctx=lctx, clarifications=clar, feedback=feedback, previous_plan=run.plan if feedback else None,
                            edit=edit, example=example, critic_spec=pspec)
                plan = None
                if deep:   # big, multi-part goal: the reasoner plans it (slower, better architecture)
                    try:
                        dspec = llm.resolve('deepseek-reasoner', ctx['keys'])
                        run.update(set__planner_model=dspec['label'])
                        plan, ti, to = planner.make_plan(dspec, run.goal, ctx.get('memory', ''), existing, **args)
                    except llm.LLMError as e:
                        if 'rejected' in str(e) or 'balance' in str(e):
                            raise
                        plan = None   # the reasoner failed or returned junk: fall back to the fast model
                if plan is None:
                    run.update(set__planner_model=pspec['label'])
                    plan, ti, to = planner.make_plan(pspec, run.goal, ctx.get('memory', ''), existing, **args)
        except llm.LLMError as e:
            return _finish(run_id, 'failed', ('Answer failed: ' if kind == 'chat' else 'Planning failed: ') + str(e))
        RunDocument.objects(run_id=run_id).update_one(inc__tokens_in=ti, inc__tokens_out=to)
        if plan.get('answer'):  # a question, not a build: reply directly, spawn no agents
            return _end_run(run_id, set__answer=plan['answer'], set__project_name=run.goal[:60], set__status='completed')
        if plan.get('questions'):  # too vague: ask, then resume when the user answers
            return _pause(run_id, 'awaiting_input', set__questions=plan['questions'])
        fc = router.forecast(run.goal, 'small' if kind == 'small' else 'large',
                             module_descs=[m['description'] for m in plan['modules']],
                             contract_text=plan['contract'], verify=run.verify)
        RunDocument.objects(run_id=run_id).update_one(
            set__estimate_tokens=fc['tokens'], set__estimate_cost=fc['cost'],
            set__assumptions=plan.get('assumptions', []))
        if run.review_plan and len(plan['modules']) >= REVIEW_MIN_MODULES:   # wait for "Start building"
            return _pause(run_id, 'awaiting_approval', set__plan=plan, set__project_name=plan['project_name'],
                          set__summary=plan['summary'], set__contract=plan['contract'])
        _build_from_plan(run_id, plan)
    except Exception as e:  # noqa: BLE001
        _finish(run_id, 'failed', f'Engine error: {type(e).__name__}: {e}')


def _build_from_plan(run_id, plan):
    """Turn an (approved) plan into the agent map and run it."""
    try:
        run = RunDocument.objects.get(run_id=run_id)
        RunDocument.objects(run_id=run_id).update_one(
            set__project_name=plan['project_name'], set__summary=plan['summary'], set__contract=plan['contract'],
            set__assumptions=plan.get('assumptions', []), set__status='running', set__plan={})
        ids = {m['key']: 'task_' + uuid.uuid4().hex[:10] for m in plan['modules']}
        for i, m in enumerate(plan['modules']):
            AgentTaskDocument(task_id=ids[m['key']], run_id=run_id, key=m['key'], title=m['title'],
                              description=m['description'], folder=m['folder'], order=i * 100, expects=m.get('expects', []),
                              depends_on=[ids[d] for d in m['depends_on']]).save()
        review_deps = list(ids.values())
        if run.verify:
            verify_id = 'task_' + uuid.uuid4().hex[:10]
            AgentTaskDocument(task_id=verify_id, run_id=run_id, key='verify', kind='verify',
                              title='Open it in a browser and fix what breaks', folder='', order=999_000,
                              description='Start the project, open it in a real browser, and repair errors, 404s and broken links',
                              depends_on=list(ids.values())).save()
            review_deps.append(verify_id)
        if len(plan['modules']) > 1:   # a single agent has nothing to integrate
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
        tasks = list(AgentTaskDocument.objects(run_id=run_id))
        if run.cancel_requested:
            return _finish(run_id, 'cancelled', run.error or 'Cancelled')
        if any(t.status == 'waiting' for t in tasks):   # an agent asked a question: stop here until answered
            return _pause(run_id, 'awaiting_input')
        mods = [t for t in tasks if t.kind == 'module' and not t.replaced]
        verify_task = next((t for t in tasks if t.kind == 'verify'), None)
        if all(t.status == 'done' for t in mods):
            warn = ''
            if verify_task and verify_task.status == 'failed':
                warn = 'Built, but the browser check still found problems: ' + verify_task.error[:300]
            _finish(run_id, 'completed', warn)
            try:
                plans.save(run, tasks)
            except Exception:  # noqa: BLE001 - plan memory is best-effort
                pass
            try:
                from routes.memory import remember
                remember(f'{"Changed" if run.mode == "edit" else "Built"} "{run.project_name}" in {run.target_path}: {run.summary}', 'build')
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
            AgentTaskDocument.objects(run_id=run_id, status__in=['queued', 'waiting']).update(
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
        tasks = list(AgentTaskDocument.objects(run_id=run_id))
        inflight = any(t.status == 'running' or (t.status == 'queued' and t.task_id in submitted) for t in tasks)
        if not inflight:
            if any(t.status == 'waiting' for t in tasks):   # only the user can move this run forward now
                return
            if not any(t.status == 'queued' for t in tasks):
                return
        time.sleep(0.4)


def _run_and_release(run_id, task_id, submitted):
    try:
        _execute(run_id, task_id)
    except Exception as e:  # noqa: BLE001 - never leave an agent 'running' if the engine itself hiccups
        AgentTaskDocument.objects(task_id=task_id, status='running').update(
            set__status='failed', set__error=f'Engine error: {type(e).__name__}: {e}', set__ended_at=_now())
    finally:
        # allow a retried (re-queued) task to be submitted again
        if AgentTaskDocument.objects.get(task_id=task_id).status == 'queued':
            submitted.discard(task_id)


def recover_interrupted():
    """On boot, runs that were mid-flight died with the old process: mark them failed, not 'running' forever.
    Runs waiting for the user (awaiting_*) are left alone: their state is in the database and they resume on answer."""
    now = _now()
    live = RunDocument.objects(status__in=['planning', 'running']).scalar('run_id')
    AgentTaskDocument.objects(run_id__in=list(live), status__in=['running', 'queued']).update(
        set__status='failed', set__error='Server restarted while this agent was working', set__ended_at=now)
    n = RunDocument.objects(status__in=['planning', 'running']).update(
        set__status='failed', set__error='Server restarted during the run. Retry the failed agents.', set__ended_at=now)
    if n:
        print(f'[RECOVER] marked {n} interrupted run(s) as failed')
