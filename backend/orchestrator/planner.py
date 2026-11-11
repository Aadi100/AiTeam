"""
Planner: turns one goal into independent modules with dependencies and a shared contract.
"""

from .llm import chat, parse_json, LLMError
from .sandbox import slug

MAX_MODULES = 14

SYSTEM = """You are the lead architect of an autonomous software team. You do not write code.
You split a goal into MODULES that separate AI agents will build IN PARALLEL, each in its own folder.

Return ONLY JSON:
{
 "project_name": "short name",
 "summary": "2-3 sentence description of what will be built",
 "contract": "Shared rules every agent must follow: tech stack, exact file/route/API names, data shapes, design tokens (colors, fonts, CSS class names), how modules link to each other. Be concrete: this is the only thing the agents share.",
 "modules": [
   {"key": "snake_case_id", "title": "Build the X module", "description": "what exactly to build, files expected, acceptance criteria",
    "folder": "unique/relative/folder", "depends_on": ["other_key"]}
 ]
}

Rules:
- 3 to %d modules. Prefer MANY independent modules over a few large ones.
- Folders must be unique and must not be nested inside each other, so no two agents ever touch the same file.
- Put shared foundations (design system, app shell, API base) in ONE module the others depend on; all other modules should depend on it only if they truly need it.
- Use depends_on only for real ordering needs. Independent modules run at the same time.
- Do not create a module for README or final integration; a review agent does that automatically.
""" % MAX_MODULES


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


def make_plan(spec, goal, memory_notes='', existing_files=None):
    """Returns (plan_dict, tokens_in, tokens_out). Raises LLMError if no usable plan."""
    prompt = f'GOAL:\n{goal}\n'
    if memory_notes:
        prompt += f'\nPROJECT MEMORY (facts and preferences from earlier work, follow them):\n{memory_notes}\n'
    if existing_files:
        prompt += '\nFILES ALREADY IN THE TARGET FOLDER (extend, do not duplicate):\n' + '\n'.join(existing_files[:80]) + '\n'
    text, ti, to = chat(spec, SYSTEM, prompt, json_mode=True, max_output=6000)
    data = parse_json(text)
    if not isinstance(data, dict):
        raise LLMError('planner did not return valid JSON')
    modules = _clean(data.get('modules'))
    if not modules:
        raise LLMError('planner returned no modules')
    return {
        'project_name': (data.get('project_name') or goal[:60]).strip(),
        'summary': data.get('summary') or '',
        'contract': data.get('contract') if isinstance(data.get('contract'), str) else str(data.get('contract') or ''),
        'modules': modules,
    }, ti, to
