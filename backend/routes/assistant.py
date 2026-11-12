"""
Adion: the conversational brain behind the voice UI.

POST /api/assistant/chat {message, history[], runId?, apiKeys, model}
  -> {reply, action: {type, ...}, readout?}

The model decides whether the user is chatting, asking about the current build, or giving a command
(build / cancel / read a file / remember something). Replies are written to be spoken aloud.
"""

import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify

from models import RunDocument, AgentTaskDocument
from orchestrator import llm, sandbox, search
from auth import current_user, is_admin, with_stored_key
from routes.memory import recall, remember

assistant_bp = Blueprint('assistant', __name__)

SYSTEM = """You are Adion, the user's personal AI assistant and the voice of their autonomous software team.
You are talking OUT LOUD, so: 1 to 3 short sentences, plain spoken English, no markdown, no lists, no code, no emojis.
Be warm, quick and personal. Use the user's name sometimes. Use their remembered preferences. If you are unsure, say so.
You can see the CONTEXT below (current build, agents, files, memory, date/time). Answer questions from it; never invent files or results.

Return ONLY JSON: {"reply": "what you say", "action": {"type": "none|build|cancel|read_file|remember|pc", "goal": "", "path": "", "text": "", "request": ""}}

Action rules:
- build: the user wants software created or changed. goal = one complete self-contained description using everything they said. In reply, confirm briefly what you are starting.
- cancel: the user wants the current run stopped.
- read_file: the user wants something read out (README, a file, a summary). path = exact path from FILES. In reply, say you are reading it.
- remember: the user wants you to remember a preference or fact. text = the fact, phrased as a standalone sentence.
- pc: the user wants something done ON THEIR COMPUTER: open an app or website, find/read/move/copy/rename/delete files or folders, volume, lock, system status. request = the full request in plain words. In reply, say you are on it (you will ask before changing anything).
- none: normal conversation, status questions, jokes, advice, anything else."""


def _context(run_id, user, message):
    now = datetime.now().strftime('%A, %d %B %Y, %H:%M')
    parts = [f'User name: {user}', f'Now: {now}']
    mem = recall(message)
    if mem:
        parts.append('MEMORY:\n' + mem)
    run = RunDocument.objects(run_id=run_id).first() if run_id else None
    if run is None:
        run = RunDocument.objects.first()
    if run:
        tasks = AgentTaskDocument.objects(run_id=run.run_id).order_by('order')
        lines = [f'- {t.title}: {t.status}' + (f' ({t.error[:80]})' if t.error else '') for t in tasks]
        parts.append(f'CURRENT BUILD: "{run.project_name or run.goal[:60]}" status={run.status}, '
                     f'{run.tokens_in + run.tokens_out} tokens, folder {run.target_path}\n'
                     f'Summary: {run.summary}\nAgents:\n' + ('\n'.join(lines) or '(planning)'))
        if run.error:
            parts.append(f'Run note: {run.error}')
        try:
            parts.append('FILES:\n' + '\n'.join(sandbox.tree(run.target_path, limit=60)))
        except Exception:  # noqa: BLE001
            pass
    others = [f'- {r.project_name or r.goal[:50]} ({r.status})' for r in RunDocument.objects.limit(5)]
    if others:
        parts.append('RECENT BUILDS:\n' + '\n'.join(others))
    return '\n\n'.join(parts), run


@assistant_bp.route('/assistant/chat', methods=['POST'])
def chat():
    b = request.get_json(silent=True) or {}
    message = (b.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'message is required'}), 400
    ctx, run = _context(b.get('runId'), current_user()['u'] or 'friend', message)
    history = [h for h in (b.get('history') or [])[-8:] if isinstance(h, dict) and h.get('text')]
    convo = '\n'.join(f"{'User' if h.get('role') == 'user' else 'Adion'}: {h['text'][:400]}" for h in history)
    keys = with_stored_key(b.get('apiKeys'), current_user()['u'])
    web = ''
    if keys.get('tavily') and search.needs_search(message):
        try:
            found = search.search(message, keys['tavily'], ctx={'owner': current_user()['u'], 'run_id': ''})['results']
            if found:
                web = '\n\nWEB SOURCES (use them for current facts, never read URLs aloud):\n' + search.format_sources(found)
        except search.SearchError:
            pass
    prompt = f'CONTEXT:\n{ctx}{web}\n\nCONVERSATION SO FAR:\n{convo or "(new conversation)"}\n\nUser: {message}'
    spec = llm.resolve(b.get('model') or os.getenv('ASSISTANT_MODEL') or os.getenv('WORKER_MODEL', ''), keys)
    try:
        text, _, _ = llm.chat(spec, SYSTEM, prompt, json_mode=True, max_output=700,
                              ctx={'owner': current_user()['u'], 'run_id': '', 'purpose': 'assistant'})
    except llm.LLMError as e:
        return jsonify({'error': f'I could not reach my language model: {str(e)[:160]}'}), 502
    data = llm.parse_json(text)
    if not isinstance(data, dict) or not isinstance(data.get('reply'), str):
        # model ignored the format: just speak what it said
        return jsonify({'reply': (text or 'Sorry, I lost my train of thought.').strip()[:600], 'action': {'type': 'none'}})
    action = data.get('action') if isinstance(data.get('action'), dict) else {'type': 'none'}
    atype = action.get('type') if action.get('type') in ('none', 'build', 'cancel', 'read_file', 'remember', 'pc') else 'none'
    out = {'reply': data['reply'].strip()[:600], 'action': {'type': atype}}

    if atype == 'pc':
        from orchestrator.pc import engine as pc_engine
        out['action']['taskId'] = pc_engine.start_task((action.get('request') or message).strip(), current_user()['u'], keys)
    elif atype == 'build':
        goal = (action.get('goal') or message).strip()
        out['action']['goal'] = goal
    elif atype == 'remember' and (action.get('text') or '').strip():
        remember(action['text'].strip(), 'preference')
    elif atype == 'read_file':
        path = (action.get('path') or '').strip()
        if run and path:
            try:
                with open(sandbox.safe_join(run.target_path, path), encoding='utf-8') as fp:
                    out['readout'] = fp.read(2200)
            except (OSError, sandbox.SandboxError):
                out['reply'] = f"I couldn't open {os.path.basename(path)}."
                out['action'] = {'type': 'none'}
        else:
            out['reply'] = "I don't see a project to read from yet."
            out['action'] = {'type': 'none'}
    return jsonify(out)
