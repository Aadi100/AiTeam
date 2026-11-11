"""
Worker: one sub-agent. Generates its module's files, writes them inside its own folder,
runs fixed syntax checks, and feeds errors back to the model (up to MAX_ITER passes).
"""

from datetime import datetime
from models import RunDocument, AgentTaskDocument
from .llm import chat, parse_json, LLMError
from . import sandbox, verify
import uuid

MAX_ITER = 3

SYSTEM = """You are one specialised engineer on a team building a project in parallel.
You own ONE folder. Other engineers own other folders at the same time, so follow the shared CONTRACT exactly
(file names, routes, CSS class names, data shapes) and never write outside your folder.

Return ONLY JSON:
{"summary": "what you built, one or two sentences", "files": [{"path": "relative/to/your/folder.ext", "content": "complete file contents"}],
 "subtasks": [{"key": "short_id", "title": "Build the Y part", "description": "...", "subfolder": "y"}]}
"subtasks" is OPTIONAL: only if your module is too big, hand up to 4 self-contained pieces to helper agents. Each helper
gets its own subfolder INSIDE your folder and builds it in parallel after you finish. Leave it out for small modules.

Rules:
- Paths are RELATIVE to your folder. Do not include the folder name, '..', or absolute paths.
- Every file must be complete and runnable. No placeholders, no "..." and no TODO stubs.
- Python must be valid; JS must pass `node --check`; JSON must parse.
- Keep to the technologies named in the CONTRACT."""


class Stopped(Exception):
    pass


def log(task, msg, level='info'):
    AgentTaskDocument.objects(task_id=task.task_id).update_one(
        push__log={'t': datetime.utcnow().isoformat() + 'Z', 'level': level, 'msg': msg[:2000]})


def charge(run_id, task, ti, to):
    """Record token usage on the task and the run, then enforce the budget."""
    AgentTaskDocument.objects(task_id=task.task_id).update_one(inc__tokens_in=ti, inc__tokens_out=to)
    RunDocument.objects(run_id=run_id).update_one(inc__tokens_in=ti, inc__tokens_out=to)
    run = RunDocument.objects.get(run_id=run_id)
    if run.max_tokens and (run.tokens_in + run.tokens_out) >= run.max_tokens and not run.cancel_requested:
        run.update(set__cancel_requested=True, set__error=f'Token budget of {run.max_tokens:,} reached')


def check_stop(run_id):
    if RunDocument.objects.get(run_id=run_id).cancel_requested:
        raise Stopped()


def _dep_context(task):
    parts = []
    for dep in AgentTaskDocument.objects(task_id__in=task.depends_on):
        files = ', '.join(f['path'] for f in dep.files[:25])
        parts.append(f'- {dep.title} [{dep.folder}/]: {dep.summary}\n  files: {files}')
    return '\n'.join(parts)


def _spawn_children(run, task, subtasks):
    """A module agent may hand work to helper agents (one level deep). They appear as children on the map."""
    if not subtasks or not isinstance(subtasks, list) or task.parent_id:
        return
    made, seen = [], set()
    for i, st in enumerate(subtasks[:4]):
        if not isinstance(st, dict):
            continue
        sub = sandbox.slug(st.get('subfolder') or st.get('key') or f'part{i + 1}').replace('/', '-')
        if sub in seen:
            continue
        seen.add(sub)
        tid = 'task_' + uuid.uuid4().hex[:10]
        AgentTaskDocument(task_id=tid, run_id=run.run_id, key=sandbox.slug(st.get('key') or sub, sub).replace('/', '_'),
                          parent_id=task.task_id, title=(st.get('title') or f'Build {sub}')[:120],
                          description=st.get('description') or '', folder=f'{task.folder}/{sub}',
                          depends_on=[task.task_id], order=task.order + i + 1).save()
        made.append(tid)
    if made:
        # the verify/review steps must wait for the helpers too
        AgentTaskDocument.objects(run_id=run.run_id, kind__in=['verify', 'review']).update(add_to_set__depends_on=made)
        log(task, f'Spawned {len(made)} helper agent(s)', 'ok')


def run_module(run, task, spec):
    """Execute one module task. Raises on failure; returns nothing."""
    root = run.target_path
    base_prompt = (
        f'OVERALL GOAL:\n{run.goal}\n\nPROJECT SUMMARY:\n{run.summary}\n\n'
        f'SHARED CONTRACT:\n{run.contract}\n\n'
        f'YOUR MODULE: {task.title}\nYOUR FOLDER: {task.folder}/\n\nASSIGNMENT:\n{task.description}\n'
    )
    deps = _dep_context(task)
    if deps:
        base_prompt += f'\nMODULES YOU DEPEND ON (already built, use their real file names):\n{deps}\n'
    existing = sandbox.tree(root, task.folder)
    if existing:
        base_prompt += '\nFILES ALREADY IN YOUR FOLDER (overwrite or extend):\n' + '\n'.join(existing[:60]) + '\n'

    written, feedback = [], ''
    for it in range(1, MAX_ITER + 1):
        check_stop(run.run_id)
        prompt = base_prompt
        if feedback:
            prompt += ('\nYOUR PREVIOUS ATTEMPT FAILED THESE CHECKS. Fix them and return the corrected files '
                       f'(only files that changed are needed):\n{feedback}\n')
        log(task, f'Pass {it}/{MAX_ITER}: calling {spec["label"]}')
        text, ti, to = chat(spec, SYSTEM, prompt, json_mode=True)
        charge(run.run_id, task, ti, to)
        log(task, f'Model replied ({ti + to:,} tokens)')
        data = parse_json(text)
        if not isinstance(data, dict) or not isinstance(data.get('files'), list) or not data['files']:
            feedback = 'Your reply was not valid JSON with a non-empty "files" list.'
            log(task, 'Reply was not usable JSON, retrying', 'warn')
            continue
        try:
            records = sandbox.write_files(root, task.folder, data['files'])
        except sandbox.SandboxError as e:
            feedback = f'Rejected by sandbox: {e}'
            log(task, feedback, 'warn')
            continue
        by_path = {r['path']: r for r in written}
        by_path.update({r['path']: r for r in records})
        written = list(by_path.values())
        task.summary = data.get('summary') or task.summary
        log(task, f'Wrote {len(records)} file(s)')

        errors = []
        for r in records:
            err = sandbox.check_file(root, r['path'])
            if err:
                errors.append(f'{r["path"]}: {err}')
        AgentTaskDocument.objects(task_id=task.task_id).update_one(set__files=written, set__summary=task.summary)
        if not errors:
            log(task, 'Syntax checks passed', 'ok')
            _spawn_children(run, task, data.get('subtasks'))
            return
        feedback = '\n'.join(errors)
        log(task, f'{len(errors)} file(s) failed checks, self-correcting', 'warn')

    if written and not feedback.startswith(('Your reply', 'Rejected')):
        # Files exist but still have syntax errors after the last pass: keep them, mark failed.
        raise RuntimeError(f'Checks still failing after {MAX_ITER} passes: {feedback[:300]}')
    raise RuntimeError(f'No valid output after {MAX_ITER} passes: {feedback[:300]}')


REVIEW_SYSTEM = """You are the integration reviewer. Modules were built in parallel by separate engineers.
Write ONLY root-level glue files that tie the project together: README.md (what it is, how to run it, folder map),
and if needed a root launcher (e.g. index.html linking to the app, package.json scripts, requirements.txt, run script).
Never rewrite files that already exist inside module folders.

Return ONLY JSON: {"summary": "...", "files": [{"path": "README.md", "content": "..."}]}
Paths must be at the project root (no subfolders)."""


def run_review(run, task, spec):
    root = run.target_path
    mods = AgentTaskDocument.objects(run_id=run.run_id, kind='module')
    listing = '\n'.join(f'- {m.title} [{m.folder}/] status={m.status}: {m.summary}\n    files: ' +
                        ', '.join(f['path'] for f in m.files[:20]) for m in mods)
    problems = []
    for m in mods:
        for f in m.files:
            err = sandbox.check_file(root, f['path'])
            if err:
                problems.append(f'{f["path"]}: {err}')
    prompt = (f'GOAL:\n{run.goal}\n\nSUMMARY:\n{run.summary}\n\nCONTRACT:\n{run.contract}\n\n'
              f'MODULES:\n{listing}\n\nKNOWN SYNTAX PROBLEMS:\n' + ('\n'.join(problems) or 'none'))
    check_stop(run.run_id)
    log(task, f'Integration review via {spec["label"]}')
    text, ti, to = chat(spec, REVIEW_SYSTEM, prompt, json_mode=True, max_output=4000)
    charge(run.run_id, task, ti, to)
    data = parse_json(text)
    if not isinstance(data, dict) or not isinstance(data.get('files'), list):
        raise RuntimeError('review did not return files')
    files = [f for f in data['files'] if '/' not in (f.get('path') or '').replace('\\', '/').strip('/')]
    records = sandbox.write_files(root, '', files)
    AgentTaskDocument.objects(task_id=task.task_id).update_one(
        set__files=records, set__summary=(data.get('summary') or '') +
        (f' ({len(problems)} syntax problem(s) remain in modules)' if problems else ''))
    log(task, f'Wrote {len(records)} root file(s); {len(problems)} syntax problem(s) outstanding',
        'warn' if problems else 'ok')


FIX_SYSTEM = """You are the integration engineer. The project was built by several engineers in parallel and was just
started for real; it failed. Fix the smallest set of files so that the app starts and GET / returns a working page.

Return ONLY JSON: {"summary": "what was wrong and what you changed", "files": [{"path": "path/from/project/root.ext", "content": "complete new file contents"}]}
Paths are relative to the PROJECT ROOT (include the module folder). Return complete files. No placeholders."""

VERIFY_ROUNDS = 2


def run_integration(run, task, spec):
    """Start the generated project, request '/', and have a model fix what breaks (opt-in per run)."""
    root = run.target_path
    last = ''
    for rnd in range(1, VERIFY_ROUNDS + 2):
        check_stop(run.run_id)
        log(task, f'Smoke test {rnd}: starting the project and requesting /')
        ok, report = verify.smoke_test(root)
        log(task, report[:1500], 'ok' if ok else 'warn')
        if ok:
            AgentTaskDocument.objects(task_id=task.task_id).update_one(set__summary=f'Project starts. {report}')
            return
        last = report
        if rnd > VERIFY_ROUNDS:
            break
        sources, _ = verify.project_files_for_fix(root, report)
        nl = chr(10)
        prompt = nl.join([
            'GOAL:', run.goal, '', 'CONTRACT:', run.contract, '', 'FAILURE:', report, '',
            'FILES IN PROJECT:', nl.join(verify.verify_tree(root)[:120]), '', 'KEY SOURCES:', sources])
        text, ti, to = chat(spec, FIX_SYSTEM, prompt, json_mode=True)
        charge(run.run_id, task, ti, to)
        data = parse_json(text)
        if not isinstance(data, dict) or not isinstance(data.get('files'), list) or not data['files']:
            log(task, 'Fixer returned no files', 'warn')
            continue
        try:
            records = sandbox.write_files(root, '', data['files'])
        except sandbox.SandboxError as e:
            log(task, f'Fix rejected by sandbox: {e}', 'warn')
            continue
        AgentTaskDocument.objects(task_id=task.task_id).update_one(
            set__files=records, set__summary=data.get('summary') or '')
        log(task, f'Applied fix to {len(records)} file(s): {data.get("summary", "")[:200]}', 'ok')
    raise RuntimeError(f'Project still fails after {VERIFY_ROUNDS} fix rounds: {last[:300]}')
