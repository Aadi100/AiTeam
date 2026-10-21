"""
Rex — Advanced PC Control Agent
Handles all PC-level tasks: file ops, apps, processes, system info, shell, clipboard, etc.
Requires user permission for medium/high risk actions before executing.
"""

import os
import sys
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Blueprint, request, jsonify
from rex_tools import TOOLS, TOOL_DESCRIPTIONS
from models import AgentDocument, MessageDocument

rex_bp = Blueprint('rex', __name__)

REX_SYSTEM = f"""You are Rex, an advanced AI PC Control Agent running on a Windows machine.
You have direct access to the user's PC via specialized tools.

AVAILABLE TOOLS:
{TOOL_DESCRIPTIONS}

Given a user task, respond ONLY with valid JSON in this exact format:
{{
  "understanding": "One sentence: what the user wants",
  "plan": ["Step 1 description", "Step 2 description"],
  "actions": [
    {{
      "tool": "exact_tool_name",
      "args": {{"arg1": "value1", "arg2": "value2"}},
      "requires_permission": true,
      "permission_reason": "Explain why this needs confirmation",
      "description": "Human-readable: what this action does"
    }}
  ]
}}

PERMISSION RULES:
- LOW risk tools: requires_permission = false (read-only, safe)
- MEDIUM risk tools: requires_permission = true (creates/opens things)
- HIGH risk tools: ALWAYS requires_permission = true (delete/move/run commands)

Use ~ for home directory. Be specific with file paths.
Only include actions that are actually needed.
"""


def _call_rex_ai(task: str, api_key: str, model: str):
    """Call Gemini to plan Rex actions."""
    import requests as req
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"System: {REX_SYSTEM}\n\nUser Task: {task}"}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096, "responseMimeType": "application/json"}
    }
    for attempt in range(3):
        try:
            r = req.post(url, json=payload, timeout=60)
            if r.status_code == 200:
                text = r.json()['candidates'][0]['content']['parts'][0]['text']
                cleaned = text.replace('```json', '').replace('```', '').strip()
                try:
                    return json.loads(cleaned, strict=False)
                except Exception:
                    return None
            elif r.status_code == 503 and attempt < 2:
                time.sleep((attempt + 1) * 4)
        except Exception:
            if attempt < 2:
                time.sleep(3)
    return None


def _execute_tool(tool_name: str, args: dict) -> dict:
    """Execute a Rex tool with given args."""
    if tool_name not in TOOLS:
        return {'success': False, 'error': f'Unknown tool: {tool_name}'}
    try:
        fn = TOOLS[tool_name]['fn']
        result = fn(**args)
        return result
    except TypeError as e:
        return {'success': False, 'error': f'Wrong args for {tool_name}: {e}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@rex_bp.route('/rex/plan', methods=['POST'])
def rex_plan():
    """
    Step 1: Rex analyses the task and returns a plan with actions.
    Actions needing permission are flagged — frontend shows confirmation dialog.
    """
    data = request.get_json() or {}
    task = data.get('task', '').strip()
    api_key = data.get('apiKey', '') or os.getenv('GEMINI_API_KEY', '')
    model = data.get('model', 'gemini-3.8-flash')

    if not task:
        return jsonify({'success': False, 'error': 'No task provided'}), 400
    if not api_key:
        return jsonify({'success': False, 'error': 'No Gemini API key available'}), 400

    # Update Rex status
    AgentDocument.objects(agent_id='rex').update(
        set__status='thinking',
        set__status_text=f'Rex: Planning — {task[:60]}...'
    )

    plan = _call_rex_ai(task, api_key, model)

    if not plan:
        AgentDocument.objects(agent_id='rex').update(
            set__status='idle',
            set__status_text='Rex: Plan failed — could not parse AI response'
        )
        return jsonify({'success': False, 'error': 'Rex could not generate a plan'}), 500

    pending = [a for a in plan.get('actions', []) if a.get('requires_permission')]
    safe = [a for a in plan.get('actions', []) if not a.get('requires_permission')]

    AgentDocument.objects(agent_id='rex').update(
        set__status='waiting' if pending else 'executing',
        set__status_text=f'Rex: {len(pending)} action(s) need your approval'
                         if pending else 'Rex: Executing safe actions...'
    )

    return jsonify({
        'success': True,
        'understanding': plan.get('understanding', ''),
        'plan': plan.get('plan', []),
        'actions': plan.get('actions', []),
        'pending_permissions': pending,
        'safe_actions': safe,
        'requires_confirmation': len(pending) > 0
    })


@rex_bp.route('/rex/execute', methods=['POST'])
def rex_execute():
    """
    Step 2: Execute a list of approved actions.
    Frontend sends actions after user confirms permissions.
    """
    data = request.get_json() or {}
    actions = data.get('actions', [])
    task = data.get('task', '')

    if not actions:
        return jsonify({'success': False, 'error': 'No actions to execute'}), 400

    AgentDocument.objects(agent_id='rex').update(
        set__status='executing',
        set__status_text=f'Rex: Executing {len(actions)} action(s)...'
    )

    results = []
    for action in actions:
        tool_name = action.get('tool', '')
        args = action.get('args', {})
        desc = action.get('description', tool_name)

        print(f'[Rex] Executing: {tool_name}({args})')
        result = _execute_tool(tool_name, args)
        results.append({
            'tool': tool_name,
            'description': desc,
            'args': args,
            'result': result,
            'success': result.get('success', False)
        })
        print(f'[Rex] {tool_name} → {"OK" if result.get("success") else "FAILED"}: {str(result)[:100]}')

    all_ok = all(r['success'] for r in results)

    AgentDocument.objects(agent_id='rex').update(
        set__status='idle',
        set__status_text=f'Rex: Done — {sum(r["success"] for r in results)}/{len(results)} actions succeeded',
        inc__stats__tasksDone=1
    )

    # Log to messages
    summary = '\n'.join(
        f'{"✓" if r["success"] else "✗"} {r["description"]}'
        for r in results
    )
    try:
        MessageDocument(
            msg_id=f'rex-{int(time.time()*1000)}',
            sender_id='rex',
            sender_name='Rex',
            sender_role='PC Control Agent',
            sender_avatar='🖥️',
            channel_id='general',
            text=f'**Rex completed task:** {task}\n\n{summary}',
            timestamp=time.strftime('%I:%M %p')
        ).save()
    except Exception:
        pass

    return jsonify({
        'success': all_ok,
        'task': task,
        'total': len(results),
        'succeeded': sum(r['success'] for r in results),
        'results': results
    })


@rex_bp.route('/rex/quick', methods=['POST'])
def rex_quick():
    """Quick tool call — execute a single tool directly (low risk only, no AI needed)."""
    data = request.get_json() or {}
    tool_name = data.get('tool', '')
    args = data.get('args', {})

    if tool_name not in TOOLS:
        return jsonify({'success': False, 'error': f'Unknown tool: {tool_name}'}), 400

    risk = TOOLS[tool_name]['risk']
    if risk == 'high':
        return jsonify({'success': False, 'error': 'High risk tools require the /rex/plan flow'}), 403

    result = _execute_tool(tool_name, args)
    return jsonify({'success': result.get('success', False), 'tool': tool_name, 'result': result})


@rex_bp.route('/rex/tools', methods=['GET'])
def rex_list_tools():
    """List all available Rex tools with descriptions and risk levels."""
    tools_list = [
        {'name': name, 'description': t['desc'], 'risk': t['risk']}
        for name, t in TOOLS.items()
    ]
    return jsonify({'success': True, 'count': len(tools_list), 'tools': tools_list})
