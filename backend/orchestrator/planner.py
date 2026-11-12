"""
Planner: turns one goal into independent modules with dependencies and a strict shared contract.
It can also answer a question directly or ask for missing detail instead of building.
"""

import json
from .llm import chat, parse_json, LLMError
from .sandbox import slug

MAX_MODULES = 14

SYSTEM = """You are the lead architect of an autonomous software team. You do not write code.

STEP 1 - decide what the user wants.
- If the goal is a question, a request for information or explanation, or small talk, answer it yourself, briefly and
  honestly (you have no internet; say so if it needs current facts) and return ONLY: {"type": "answer", "answer": "..."}
- If the goal is too vague to build well (no clear kind of app, or key choices missing), do not guess: return ONLY
  {"type": "clarify", "questions": [{"q": "short question", "options": ["optional", "quick", "answers"]}]} with at most 3 questions.
  Never ask about things you can reasonably decide yourself, and never ask twice (see CLARIFICATIONS).
- Otherwise it is a build request: go to STEP 2.

STEP 2 - split the goal into MODULES that separate AI agents build IN PARALLEL, each in its own folder.
Size the plan to the request: simple = 3-4 modules, large = more. Never pad with features the user did not ask for.

Return ONLY JSON:
{
 "type": "build",
 "project_name": "short name",
 "summary": "1-2 sentences",
 "assumptions": ["every choice YOU made where the goal was silent, one short sentence each, e.g. 'Plain HTML/CSS/JS, no framework'"],
 "contract": {"stack": "exact technologies", "files": "key file names and where they live", "api": "every route: METHOD /path -> request/response shape", "data": "data models and field names", "ui": "colors, fonts, shared CSS class names", "links": "how modules link to each other"},
 "modules": [
   {"key": "snake_case_id", "title": "Build the X module", "description": "what to build and acceptance criteria",
    "folder": "unique/relative/folder", "depends_on": ["other_key"], "expects": ["files/this/module/must/create.ext"]}
 ]
}

Rules:
- 3 to %d modules. Folders are unique and never nested, so no two agents touch the same file.
- The contract is the ONLY thing agents share, so make it exact and compact (names, routes, shapes), not prose.
- Put real shared foundations in ONE module the others depend on. Everything else should be independent so agents run at the same time.
- "expects" lists the files (relative to the module folder) the module must produce; they are checked by code.
- No module for README or final integration; a review agent does that.
""" % MAX_MODULES

EDIT_RULES = """
THIS IS A CHANGE REQUEST to an EXISTING project (see EXISTING PROJECT). Do not rebuild it. Plan only the modules that must
change or be added, as few as possible (1-3 is typical). A module's folder must be an EXISTING folder when it modifies
existing files, or a new unique folder for new parts. Keep the existing stack, names and routes; extend the contract only
where needed. The description of each module must say exactly what to change."""

REVISE_FAILED_SYSTEM = """You are the lead architect. One engineer in a parallel team failed twice. Decide how to recover.
Return ONLY JSON:
{"action": "retry", "description": "a clearer, simpler assignment for the same module", "contract_add": ""}
 or {"action": "split", "modules": [{"key": "id", "title": "Build the X part", "description": "...", "expects": ["file"]}], "contract_add": ""}
 or {"action": "drop", "reason": "why this cannot be fixed automatically"}
Prefer "split" when the module was too big (2-4 smaller parts, each independent), "retry" when the assignment was unclear or
the error shows a simple mistake, and "drop" only when nothing sensible can be done. Split parts are written inside the failed
module's folder (do not give folders). Keep descriptions concrete and short."""

CRITIC_SYSTEM = """You review a software plan made for parallel agents. Find only real defects: two modules writing the same
files, an API route used by one module but defined by none, a missing dependency, a dependency that is not needed
(it blocks parallelism), or an unrealistic scope. Return ONLY JSON:
{"ok": true}  when the plan is fine, otherwise
{"ok": false, "fixes": [{"key": "module_key", "description": "new text or omit", "depends_on": ["keys"], "expects": ["files"]}], "contract_add": "text to append to the contract or empty"}
Change as little as possible."""


def _expects(raw):
    return [str(x).strip().lstrip('/') for x in (raw or []) if isinstance(x, str) and x.strip()][:8]


def _clean(modules):
    """Validate: unique keys/folders, drop unknown deps, break cycles."""
    out, keys, folders = [], set(), set()
    for m in modules or []:
        if not isinstance(m, dict):
            continue
        key = slug(m.get('key') or m.get('title'), 'module').replace('/', '_')
        if key in keys:
            continue
        folder = slug(m.get('folder') or key)
        if folder in folders or any(folder.startswith(f + '/') or f.startswith(folder + '/') for f in folders):
            folder = f'{folder}-{len(folders) + 1}'
        keys.add(key)
        folders.add(folder)
        out.append({'key': key, 'title': (m.get('title') or key)[:120],
                    'description': m.get('description') or '', 'folder': folder,
                    'expects': _expects(m.get('expects')),
                    'depends_on': [slug(d).replace('/', '_') for d in (m.get('depends_on') or []) if isinstance(d, str)]})
    out = out[:MAX_MODULES]
    valid = {m['key'] for m in out}
    for m in out:
        m['depends_on'] = [d for d in m['depends_on'] if d in valid and d != m['key']]
    # cycle breaking: repeatedly resolve in topological order; drop deps of nodes stuck in a cycle
    resolved, remaining = set(), {m['key']: m for m in out}
    while remaining:
        ready = [k for k, m in remaining.items() if all(d in resolved for d in m['depends_on'])]
        if not ready:
            for m in remaining.values():
                m['depends_on'] = [d for d in m['depends_on'] if d in resolved]
            continue
        for k in ready:
            resolved.add(k)
            remaining.pop(k)
    return out


def _contract_text(c):
    if isinstance(c, dict):
        return '\n'.join(f'{k}: {v if isinstance(v, str) else json.dumps(v, separators=(",", ":"))}'
                         for k, v in c.items() if v)
    return c if isinstance(c, str) else str(c or '')


def _critic(spec, plan, ctx):
    brief = '\n'.join(f"- {m['key']} [{m['folder']}] deps={m['depends_on']} expects={m['expects']}: {m['description'][:160]}"
                      for m in plan['modules'])
    text, ti, to = chat(spec, CRITIC_SYSTEM, f"CONTRACT:\n{plan['contract'][:2500]}\n\nMODULES:\n{brief}",
                        json_mode=True, max_output=700, ctx=dict(ctx or {}, purpose='critic'))
    data = parse_json(text)
    if isinstance(data, dict) and data.get('ok') is False:
        by_key = {m['key']: m for m in plan['modules']}
        for fx in data.get('fixes') or []:
            m = by_key.get(slug(str(fx.get('key', ''))).replace('/', '_')) if isinstance(fx, dict) else None
            if not m:
                continue
            if isinstance(fx.get('description'), str) and fx['description'].strip():
                m['description'] = fx['description']
            if isinstance(fx.get('depends_on'), list):
                m['depends_on'] = [d for d in (slug(str(x)).replace('/', '_') for x in fx['depends_on'])
                                   if d in by_key and d != m['key']]
            if isinstance(fx.get('expects'), list):
                m['expects'] = _expects(fx['expects'])
        if isinstance(data.get('contract_add'), str) and data['contract_add'].strip():
            plan['contract'] += '\n' + data['contract_add'].strip()
        plan['modules'] = _clean(plan['modules'])
    return ti, to


def _questions(raw):
    out = []
    for i, q in enumerate(raw or [], 1):
        if isinstance(q, str) and q.strip():
            out.append({'id': f'q{i}', 'q': q.strip()[:300], 'options': [], 'answer': '', 'taskId': ''})
        elif isinstance(q, dict) and str(q.get('q') or q.get('question') or '').strip():
            opts = [str(o).strip()[:80] for o in (q.get('options') or []) if str(o).strip()][:5]
            out.append({'id': f'q{i}', 'q': str(q.get('q') or q.get('question')).strip()[:300], 'options': opts,
                        'answer': '', 'taskId': ''})
    return out[:3]


def _brief(plan):
    mods = '\n'.join(f"- {m['key']} [{m['folder']}] deps={m.get('depends_on', [])}: {m['title']} - {m['description'][:200]}"
                     for m in plan.get('modules', []))
    return f"SUMMARY: {plan.get('summary', '')}\nCONTRACT:\n{str(plan.get('contract', ''))[:2500]}\nMODULES:\n{mods}"


def make_plan(spec, goal, memory_notes='', existing_files=None, ctx=None, clarifications='', feedback='',
              previous_plan=None, edit=None, example='', critic_spec=None, attachments=''):
    """Returns (plan_dict, tokens_in, tokens_out). Raises LLMError if no usable plan.
    plan has 'answer' (a direct answer), 'questions' (goal too vague) or 'modules' (a build).
    clarifications: the user's answers to earlier questions. feedback + previous_plan: revise a plan the user reviewed.
    edit: {'summary','contract','tree'} when this is a change to an existing project."""
    system = SYSTEM + (EDIT_RULES if edit else '')
    prompt = f'GOAL:\n{goal}\n'
    if edit:
        prompt += (f"\nEXISTING PROJECT:\nsummary: {edit.get('summary', '')}\ncontract:\n{str(edit.get('contract', ''))[:2500]}\n"
                   f"files:\n" + '\n'.join((edit.get('tree') or [])[:80]) + '\n')
    if attachments:
        prompt += f'\n{attachments}\n'
    if clarifications:
        prompt += f'\nCLARIFICATIONS (the user answered your questions; do NOT ask again, build now):\n{clarifications}\n'
    if previous_plan and feedback:
        prompt += f'\nPREVIOUS PLAN:\n{_brief(previous_plan)}\n\nUSER FEEDBACK ON THAT PLAN (revise it accordingly):\n{feedback}\n'
    if example and not edit and not previous_plan:
        prompt += ('\nA SIMILAR PLAN THAT WORKED BEFORE (use it as a model for structure and stack; adapt it to THIS goal, '
                   f'do not copy blindly):\n{example}\n')
    if memory_notes:
        prompt += f'\nPROJECT MEMORY (follow it):\n{memory_notes[:1200]}\n'
    if existing_files and not edit:
        prompt += '\nFILES ALREADY IN THE TARGET FOLDER (extend, do not duplicate):\n' + '\n'.join(existing_files[:40]) + '\n'
    text, ti, to = chat(spec, system, prompt, json_mode=True, max_output=6000, ctx=dict(ctx or {}, purpose='plan'))
    data = parse_json(text)
    if not isinstance(data, dict):
        raise LLMError('planner did not return valid JSON')
    kind = str(data.get('type', '')).lower()
    if kind == 'answer' and str(data.get('answer') or '').strip():
        return {'answer': str(data['answer']).strip(), 'modules': []}, ti, to
    if kind == 'clarify' and not clarifications:
        qs = _questions(data.get('questions'))
        if qs:
            return {'questions': qs, 'modules': []}, ti, to
    modules = _clean(data.get('modules'))
    if not modules:
        raise LLMError('planner returned no modules')
    plan = {
        'project_name': (data.get('project_name') or goal[:60]).strip(),
        'summary': data.get('summary') or '',
        'assumptions': [str(a).strip()[:200] for a in (data.get('assumptions') or []) if str(a).strip()][:8],
        'contract': _contract_text(data.get('contract')),
        'modules': modules,
    }
    if len(modules) >= 5:  # a cheap second look only pays off on bigger plans
        try:
            ci, co = _critic(critic_spec or spec, plan, ctx)
            ti, to = ti + ci, to + co
        except LLMError:
            pass
    return plan, ti, to


def revise_after_failure(spec, run, task, siblings, ctx=None):
    """The planner looks at a module that failed twice and decides: retry with a clearer brief, split it, or drop it.
    Returns ({'action', ...}, tokens_in, tokens_out)."""
    prompt = (f'GOAL:\n{run.goal}\n\nCONTRACT:\n{run.contract[:2500]}\n\n'
              f'FAILED MODULE: {task.title} [{task.folder or "root"}]\nASSIGNMENT: {task.description[:700]}\n'
              f'WHAT IT BUILT: {task.summary[:300] or "nothing usable"}\nERROR: {task.error[-700:]}\n\n'
              'OTHER MODULES (already planned, do not duplicate): ' + ', '.join(s.title for s in siblings if s.task_id != task.task_id)[:600])
    text, ti, to = chat(spec, REVISE_FAILED_SYSTEM, prompt, json_mode=True, max_output=1500, ctx=dict(ctx or {}, purpose='replan'))
    data = parse_json(text)
    if not isinstance(data, dict):
        return {'action': 'drop', 'reason': 'planner gave no usable revision'}, ti, to
    action = str(data.get('action', '')).lower()
    out = {'action': action if action in ('retry', 'split', 'drop') else 'drop',
           'contract_add': str(data.get('contract_add') or '').strip()[:800],
           'description': str(data.get('description') or '').strip()[:1500], 'reason': str(data.get('reason') or '')[:300]}
    if out['action'] == 'split':
        parts = []
        for i, m in enumerate(data.get('modules') or []):
            if isinstance(m, dict) and (m.get('title') or m.get('description')):
                parts.append({'key': slug(m.get('key') or m.get('title') or f'part{i + 1}').replace('/', '_'),
                              'title': str(m.get('title') or f'Part {i + 1}')[:120],
                              'description': str(m.get('description') or ''), 'expects': _expects(m.get('expects'))})
        out['modules'] = parts[:4]
        if len(out['modules']) < 2:
            out['action'] = 'retry' if out['description'] else 'drop'
    if out['action'] == 'retry' and not out['description']:
        out['action'] = 'drop'
    return out, ti, to
