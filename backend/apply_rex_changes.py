"""Apply dynamic orchestrator + Rex routing to project.py."""
import re, ast

with open('routes/project.py', 'rb') as f:
    raw = f.read()
if raw.startswith(b'\xef\xbb\xbf'):
    raw = raw[3:]
src = raw.decode('utf-8')

# ── 1. Replace ORCHESTRATOR_SYSTEM (between the const and MICHAEL_SYSTEM) ────
old_sys = src[src.find('ORCHESTRATOR_SYSTEM'):src.find('MICHAEL_SYSTEM')]
new_sys = '''ORCHESTRATOR_SYSTEM_TEMPLATE = """You are the Orchestrator — the Master Technical Lead.
Your team:
{agent_roster}

Decide which agents are needed and their tasks.
Return ONLY valid JSON:
{{
  "reasoning": "Why these agents were chosen",
  "complexity": "simple|medium|complex",
  "parallel": true,
  "assignments": {{"agent_id": "Specific task description"}}
}}

RULES:
- full-stack app -> michael + dave
- frontend only  -> michael only
- backend/API only -> dave only
- PC tasks (files, apps, commands, system) -> rex only
- mixed (code + PC tasks) -> relevant combo
Output pure JSON, no markdown.
"""

'''
src = src.replace(old_sys, new_sys)

# ── 2. Replace call_orchestrator with dynamic version ─────────────────────────
# Find exact function boundaries using \r\n\r\n\r\n as separator
fn_start = src.find('def call_orchestrator(')
fn_end   = src.find('\r\n\r\n\r\n', fn_start)
if fn_end == -1:
    fn_end = src.find('\n\n\n', fn_start)
fn_end += 3  # include the blank lines

old_fn = src[fn_start:fn_end]
new_fn = '''def build_agent_roster(agents):
    lines = []
    for a in agents:
        skills = ', '.join((a.skills or [])[:4])
        lines.append(f"  - {a.agent_id} ({a.name}): {a.role}. Skills: {skills}")
    return '\\n'.join(lines) if lines else '  - michael, dave'


def call_dynamic_orchestrator(user_prompt, agents, provider, api_key, model):
    roster = build_agent_roster(agents)
    system = ORCHESTRATOR_SYSTEM_TEMPLATE.format(agent_roster=roster)
    print(f"[Orchestrator] Dynamic routing via {provider}/{model} ({len(agents)} agents)...")
    raw = call_ai_model(provider, api_key, model, user_prompt, system)
    result = parse_json_response(raw)
    if isinstance(result, dict) and result.get('assignments'):
        print(f"[Orchestrator] Assigned: {list(result['assignments'].keys())}")
        return result
    print("[Orchestrator] Routing failed, defaulting to michael+dave.")
    return None


'''
src = src[:fn_start] + new_fn + src[fn_end:]

# ── 3. Replace the build route body ──────────────────────────────────────────
# Replace the section from "Get assigned agent models" to "# Physically write"
marker_a = '        # Get assigned agent models from MongoDB'
marker_b = '        # Physically write all files to the user\'s PC hard drive!'
idx_a = src.find(marker_a)
idx_b = src.find(marker_b)

new_section = '''        # -- Dynamic orchestrator assigns tasks --------------------------------
        all_agents  = list(AgentDocument.objects())
        default_mdl = 'gemini-3.8-flash'
        orch_model  = (all_agents[0].model if all_agents else default_mdl)

        effective_keys = get_effective_keys(api_keys)
        orch_prov, orch_key = resolve_provider(effective_keys, orch_model)

        routing     = call_dynamic_orchestrator(prompt, all_agents, orch_prov, orch_key, orch_model)
        assignments = (routing['assignments'] if routing else {})
        run_par     = (routing.get('parallel', True) if routing else True)
        if not assignments:
            assignments = {'michael': prompt, 'dave': prompt}

        print(f"[Build] Active agents: {list(assignments.keys())}")

        agent_map = {a.agent_id: a for a in all_agents}
        def get_mdl(aid): return (agent_map[aid].model if aid in agent_map else default_mdl)

        code_agents = {k: v for k, v in assignments.items() if k in ('michael', 'dave')}
        rex_task    = assignments.get('rex')

        for aid, task in code_agents.items():
            AgentDocument.objects(agent_id=aid).update(
                set__status='coding',
                set__status_text=f'{aid.title()}: Generating via {get_mdl(aid)}...'
            )

        frontend_files, backend_files = [], []
        streams_data = {}

        if run_par and len(code_agents) > 1:
            from concurrent.futures import ThreadPoolExecutor as _TPE
            with _TPE(max_workers=len(code_agents)) as ex:
                futs = {}
                if 'michael' in code_agents:
                    futs['michael'] = ex.submit(generate_frontend_code, code_agents['michael'], api_keys, get_mdl('michael'))
                if 'dave' in code_agents:
                    futs['dave'] = ex.submit(generate_backend_code, code_agents['dave'], api_keys, get_mdl('dave'))
                if 'michael' in futs: frontend_files = futs['michael'].result(timeout=300)
                if 'dave'    in futs: backend_files  = futs['dave'].result(timeout=300)
        else:
            if 'michael' in code_agents:
                frontend_files = generate_frontend_code(code_agents['michael'], api_keys, get_mdl('michael'))
            if 'dave' in code_agents:
                backend_files  = generate_backend_code(code_agents['dave'],    api_keys, get_mdl('dave'))

        all_files = frontend_files + backend_files

        # Physically write all files to the user\'s PC hard drive!
'''
src = src[:idx_a] + new_section + src[idx_b + len(marker_b):]

# ── 4. Replace hardcoded agent status updates after file writing ──────────────
old_upd = (
    "        # Update Agent status back to idle + increment files\r\n"
    "        AgentDocument.objects(agent_id='michael').update(\r\n"
    "            set__status='idle',\r\n"
    "            set__status_text='Orbital Station Alpha idle. Frontend deliverables saved to disk.',\r\n"
    "            inc__stats__tasksDone=1,\r\n"
    "            inc__stats__filesCreated=len(frontend_files)\r\n"
    "        )\r\n"
    "        AgentDocument.objects(agent_id='dave').update(\r\n"
    "            set__status='idle',\r\n"
    "            set__status_text='Orbital Station Beta idle. Backend endpoints saved to disk.',\r\n"
    "            inc__stats__tasksDone=1,\r\n"
    "            inc__stats__filesCreated=len(backend_files)\r\n"
    "        )"
)
new_upd = """        for aid, task in code_agents.items():
            cnt = len(frontend_files) if aid == 'michael' else len(backend_files)
            AgentDocument.objects(agent_id=aid).update(
                set__status='idle',
                set__status_text=f'{aid.title()}: Done -- {cnt} file(s) saved.',
                inc__stats__tasksDone=1,
                inc__stats__filesCreated=cnt
            )
            streams_data[aid] = (
                f"[Orchestrator -> {aid.title()} via {get_mdl(aid)}]"
                f"\\nTask: {task}\\n\\nGenerated {cnt} file(s) and saved to disk."
            )
        if rex_task:
            streams_data['rex'] = f"[Rex queued]\\n{rex_task}\\n\\nSend to /api/rex/plan to execute." """
src = src.replace(old_upd, new_upd)

# ── 5. Fix hardcoded streams_data assignment ──────────────────────────────────
# Remove old streams_data dict literal that comes after agent status block
old_streams_section = (
    "        # Save to Project History in MongoDB\r\n"
    "        streams_data = {\r\n"
)
# Find it and remove the dict, keeping the "# Save to Project History" comment
streams_idx = src.find(old_streams_section)
if streams_idx != -1:
    dict_end = src.find("        }", streams_idx + len(old_streams_section))
    dict_end += len("        }")
    # what follows after the closing brace?
    src = src[:streams_idx] + "        # Save to Project History in MongoDB\r\n" + src[dict_end:]

# ── 6. Fix models_used ────────────────────────────────────────────────────────
src = src.replace(
    "models_used={'michael': michael_model, 'dave': dave_model}",
    "models_used={aid: get_mdl(aid) for aid in assignments}"
)

# ── 7. Fix the success message ────────────────────────────────────────────────
src = re.sub(
    r'text=f"[^"]*PARALLEL DISK SYNC COMPLETE[^"]*"',
    'text=f"BUILD COMPLETE: {len(written_files)} files to {target_path}"',
    src
)

# ── Verify ────────────────────────────────────────────────────────────────────
try:
    ast.parse(src)
    print('Syntax OK -- writing project.py')
    with open('routes/project.py', 'w', encoding='utf-8') as f:
        f.write(src)
except SyntaxError as e:
    lines = src.splitlines()
    print(f'SyntaxError line {e.lineno}: {e.msg}')
    if e.lineno and e.lineno <= len(lines):
        print(repr(lines[e.lineno - 1]))
    with open('routes/project_debug.py', 'w', encoding='utf-8') as f:
        f.write(src)
    print('Debug written to project_debug.py')
