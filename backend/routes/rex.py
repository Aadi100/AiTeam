"""
Rex — Advanced PC Control Agent
Planning: keyword fast-path first, then Gemini Function Calling if no match.
Execution: separate /rex/execute endpoint after optional user confirmation.
"""

import os
import re
import sys
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests as _req
from flask import Blueprint, request, jsonify
from rex_tools import TOOLS
from models import AgentDocument, MessageDocument

rex_bp = Blueprint('rex', __name__)

# ── Gemini function declarations for all 42 tools ────────────────────────────

REX_FUNCTION_DECLARATIONS = [
    # File system — low risk
    {"name": "search_files",      "description": "Search files by name pattern or content inside a folder",
     "parameters": {"type": "object", "properties": {
       "path":           {"type": "string", "description": "Root folder to search in, use ~ for home"},
       "pattern":        {"type": "string", "description": "Glob pattern e.g. *.txt, report*"},
       "content_search": {"type": "string", "description": "Optional: search inside file contents for this text"},
       "max_depth":      {"type": "integer","description": "Max folder depth to search (default 5)"}
     }, "required": ["path"]}},

    {"name": "list_directory",    "description": "List all files and folders inside a directory",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Directory path to list, use ~ for home"}
     }, "required": ["path"]}},

    {"name": "read_file",         "description": "Read and return the contents of a text file",
     "parameters": {"type": "object", "properties": {
       "path":      {"type": "string",  "description": "Full file path"},
       "max_chars": {"type": "integer", "description": "Max characters to return (default 5000)"}
     }, "required": ["path"]}},

    {"name": "get_file_info",     "description": "Get metadata about a file: size, dates, type",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Full file path"}
     }, "required": ["path"]}},

    {"name": "find_large_files",  "description": "Find files larger than a given size in MB",
     "parameters": {"type": "object", "properties": {
       "path":        {"type": "string", "description": "Folder to search"},
       "min_size_mb": {"type": "number", "description": "Minimum size in megabytes (default 100)"}
     }, "required": ["path"]}},

    {"name": "get_desktop_path",  "description": "Get the Desktop folder path for the current user",
     "parameters": {"type": "object", "properties": {}}},

    # System info — low risk
    {"name": "get_system_info",   "description": "Get CPU, RAM, disk usage, OS details and uptime",
     "parameters": {"type": "object", "properties": {}}},

    {"name": "get_network_info",  "description": "Get network interfaces, IP addresses, MAC addresses",
     "parameters": {"type": "object", "properties": {}}},

    {"name": "get_battery_info",  "description": "Get battery level, charging status and time remaining",
     "parameters": {"type": "object", "properties": {}}},

    {"name": "ping_host",         "description": "Ping a hostname or IP to check if it is reachable",
     "parameters": {"type": "object", "properties": {
       "host": {"type": "string", "description": "Hostname or IP address e.g. google.com"}
     }, "required": ["host"]}},

    {"name": "list_processes",    "description": "List currently running processes with CPU and memory usage",
     "parameters": {"type": "object", "properties": {
       "top_n": {"type": "integer", "description": "Number of processes to return (default 30)"}
     }}},

    {"name": "get_clipboard",     "description": "Read the current text content of the clipboard",
     "parameters": {"type": "object", "properties": {}}},

    {"name": "get_env_var",       "description": "Read the value of a specific environment variable",
     "parameters": {"type": "object", "properties": {
       "name": {"type": "string", "description": "Environment variable name e.g. PATH, HOME"}
     }, "required": ["name"]}},

    {"name": "get_environment_vars","description": "List all environment variables and their values",
     "parameters": {"type": "object", "properties": {}}},

    # Git — low risk reads
    {"name": "git_status",        "description": "Show git status of a repository (staged, unstaged, untracked files)",
     "parameters": {"type": "object", "properties": {
       "repo_path": {"type": "string", "description": "Path to the git repository"}
     }, "required": ["repo_path"]}},

    {"name": "git_log",           "description": "Show recent git commits for a repository",
     "parameters": {"type": "object", "properties": {
       "repo_path": {"type": "string", "description": "Path to the git repository"},
       "n":         {"type": "integer", "description": "Number of commits to show (default 10)"}
     }, "required": ["repo_path"]}},

    {"name": "git_diff",          "description": "Show uncommitted changes (git diff) in a repository",
     "parameters": {"type": "object", "properties": {
       "repo_path": {"type": "string", "description": "Path to the git repository"}
     }, "required": ["repo_path"]}},

    {"name": "take_screenshot",   "description": "Take a screenshot of the entire screen and save it",
     "parameters": {"type": "object", "properties": {
       "save_path": {"type": "string", "description": "Optional: file path to save the screenshot (default: Desktop)"}
     }}},

    # Write / create — medium risk
    {"name": "write_file",        "description": "Create or overwrite a file with given text content",
     "parameters": {"type": "object", "properties": {
       "path":    {"type": "string",  "description": "Full file path to write"},
       "content": {"type": "string",  "description": "Text content to write"},
       "append":  {"type": "boolean", "description": "If true, append instead of overwrite (default false)"}
     }, "required": ["path", "content"]}},

    {"name": "create_folder",     "description": "Create a new directory (including nested folders)",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Full path of directory to create"}
     }, "required": ["path"]}},

    {"name": "copy_item",         "description": "Copy a file or folder to a destination",
     "parameters": {"type": "object", "properties": {
       "src": {"type": "string", "description": "Source file or folder path"},
       "dst": {"type": "string", "description": "Destination path"}
     }, "required": ["src", "dst"]}},

    {"name": "zip_item",          "description": "Compress a file or folder into a zip archive",
     "parameters": {"type": "object", "properties": {
       "src":     {"type": "string", "description": "File or folder to compress"},
       "dst_zip": {"type": "string", "description": "Output .zip file path"}
     }, "required": ["src", "dst_zip"]}},

    {"name": "unzip_item",        "description": "Extract a zip archive to a destination folder",
     "parameters": {"type": "object", "properties": {
       "zip_path": {"type": "string", "description": "Path to the .zip file"},
       "dst":      {"type": "string", "description": "Folder to extract into"}
     }, "required": ["zip_path", "dst"]}},

    {"name": "set_clipboard",     "description": "Copy text to the clipboard",
     "parameters": {"type": "object", "properties": {
       "text": {"type": "string", "description": "Text to copy to clipboard"}
     }, "required": ["text"]}},

    {"name": "open_in_browser",   "description": "Open a URL in the default web browser",
     "parameters": {"type": "object", "properties": {
       "url": {"type": "string", "description": "Full URL to open e.g. https://google.com"}
     }, "required": ["url"]}},

    {"name": "open_file_default", "description": "Open a file with its default application",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "File path to open"}
     }, "required": ["path"]}},

    {"name": "open_in_explorer",  "description": "Open a folder in the file manager (Explorer / Finder / Nautilus)",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Folder path to open"}
     }, "required": ["path"]}},

    {"name": "open_in_vscode",    "description": "Open a file or folder in VS Code",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "File or folder path to open in VS Code"}
     }, "required": ["path"]}},

    {"name": "open_application",  "description": "Launch an application by name (chrome, notepad, vscode, spotify, etc.)",
     "parameters": {"type": "object", "properties": {
       "app_name": {"type": "string", "description": "Application name or executable e.g. chrome, notepad, vlc"}
     }, "required": ["app_name"]}},

    {"name": "open_terminal",     "description": "Open a new terminal window, optionally at a specific folder",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Optional: folder path to open terminal in"}
     }}},

    {"name": "show_notification", "description": "Show a desktop notification with a title and message",
     "parameters": {"type": "object", "properties": {
       "title":       {"type": "string",  "description": "Notification title"},
       "message":     {"type": "string",  "description": "Notification body text"},
       "duration_ms": {"type": "integer", "description": "Duration in milliseconds (default 3000)"}
     }, "required": ["title", "message"]}},

    {"name": "start_process",     "description": "Start a process/application from a command string",
     "parameters": {"type": "object", "properties": {
       "command": {"type": "string", "description": "Command to run e.g. notepad.exe, python app.py"}
     }, "required": ["command"]}},

    # Git writes — medium risk
    {"name": "git_pull",          "description": "Pull latest changes from remote for a git repository",
     "parameters": {"type": "object", "properties": {
       "repo_path": {"type": "string", "description": "Path to the git repository"}
     }, "required": ["repo_path"]}},

    {"name": "git_clone",         "description": "Clone a git repository from a URL",
     "parameters": {"type": "object", "properties": {
       "url":  {"type": "string", "description": "Git repository URL"},
       "dest": {"type": "string", "description": "Local destination folder path"}
     }, "required": ["url", "dest"]}},

    # High risk
    {"name": "rename_item",       "description": "Rename a file or folder",
     "parameters": {"type": "object", "properties": {
       "path":     {"type": "string", "description": "Current file or folder path"},
       "new_name": {"type": "string", "description": "New name (not full path, just the name)"}
     }, "required": ["path", "new_name"]}},

    {"name": "move_item",         "description": "Move a file or folder to a new location",
     "parameters": {"type": "object", "properties": {
       "src": {"type": "string", "description": "Source path"},
       "dst": {"type": "string", "description": "Destination path"}
     }, "required": ["src", "dst"]}},

    {"name": "delete_item",       "description": "Permanently delete a file or folder",
     "parameters": {"type": "object", "properties": {
       "path": {"type": "string", "description": "Full path of file or folder to delete"}
     }, "required": ["path"]}},

    {"name": "kill_process",      "description": "Kill/terminate a running process by name or PID",
     "parameters": {"type": "object", "properties": {
       "name_or_pid": {"type": "string", "description": "Process name (e.g. chrome.exe) or numeric PID"}
     }, "required": ["name_or_pid"]}},

    {"name": "run_command",       "description": "Run a shell command and return stdout/stderr",
     "parameters": {"type": "object", "properties": {
       "command":     {"type": "string",  "description": "Shell command to run"},
       "working_dir": {"type": "string",  "description": "Optional: working directory"},
       "timeout":     {"type": "integer", "description": "Timeout in seconds (default 30)"}
     }, "required": ["command"]}},

    {"name": "run_powershell",    "description": "Run a PowerShell script (Windows) or pwsh script (Mac/Linux)",
     "parameters": {"type": "object", "properties": {
       "script": {"type": "string", "description": "PowerShell script content"}
     }, "required": ["script"]}},

    {"name": "run_bash",          "description": "Run a bash/sh shell script (Mac/Linux only)",
     "parameters": {"type": "object", "properties": {
       "script":  {"type": "string",  "description": "Bash script content"},
       "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"}
     }, "required": ["script"]}},

    {"name": "run_python_script", "description": "Run a Python script file with optional arguments",
     "parameters": {"type": "object", "properties": {
       "script_path": {"type": "string", "description": "Path to the .py file"},
       "args":        {"type": "string", "description": "Optional command-line arguments string"}
     }, "required": ["script_path"]}},
]

# ── Keyword fast-path ─────────────────────────────────────────────────────────
# Each entry: (compiled_regex, tool_name, args_fn)
# args_fn receives the re.Match object and returns a dict of args (or {})

def _mk_keyword_map():
    return [
        # Screenshot
        (re.compile(r'\b(take\s+a?\s*)?screenshot\b', re.I),
         'take_screenshot', lambda m: {}),

        # Clipboard read
        (re.compile(r'\b(read|get|show|what.?s\s+in)\s+(my\s+)?clipboard\b', re.I),
         'get_clipboard', lambda m: {}),

        # System info
        (re.compile(r'\b(system\s+info|cpu\s+usage|ram\s+usage|disk\s+space|how\s+much\s+(ram|memory|storage)|pc\s+specs?)\b', re.I),
         'get_system_info', lambda m: {}),

        # Battery
        (re.compile(r'\bbattery\b', re.I),
         'get_battery_info', lambda m: {}),

        # Network / IP
        (re.compile(r'\b(network\s+info|my\s+ip|ip\s+address|wifi\s+info|network\s+status)\b', re.I),
         'get_network_info', lambda m: {}),

        # Processes
        (re.compile(r'\b(list|show|running)\s+(processes|apps|applications|programs)\b', re.I),
         'list_processes', lambda m: {}),

        # Desktop path
        (re.compile(r'\b(desktop\s+path|where\s+is\s+(my\s+)?desktop|desktop\s+folder)\b', re.I),
         'get_desktop_path', lambda m: {}),

        # Open browser with URL
        (re.compile(r'\bopen\s+(https?://\S+)\b', re.I),
         'open_in_browser', lambda m: {'url': m.group(1)}),

        # Open browser app (no URL)
        (re.compile(r'\bopen\s+(chrome|firefox|browser|edge|safari|brave|opera)\b', re.I),
         'open_application', lambda m: {'app_name': m.group(1).lower()}),

        # Open VS Code
        (re.compile(r'\bopen\s+(vscode?|visual\s+studio\s+code)\b', re.I),
         'open_application', lambda m: {'app_name': 'code'}),

        # Open notepad / text editor
        (re.compile(r'\bopen\s+(notepad|textedit|gedit|nano|vim)\b', re.I),
         'open_application', lambda m: {'app_name': m.group(1).lower()}),

        # Open Spotify / VLC / any named app
        (re.compile(r'\bopen\s+(spotify|vlc|discord|slack|zoom|teams|word|excel|powerpoint|calculator|paint)\b', re.I),
         'open_application', lambda m: {'app_name': m.group(1).lower()}),

        # Open terminal
        (re.compile(r'\bopen\s+(a\s+)?(terminal|cmd|command\s+prompt|powershell|bash)\b', re.I),
         'open_terminal', lambda m: {}),

        # Open Explorer / Finder on Desktop
        (re.compile(r'\bopen\s+(file\s+)?explorer\b', re.I),
         'open_in_explorer', lambda m: {'path': '~'}),

        # Ping
        (re.compile(r'\bping\s+([\w.\-]+)\b', re.I),
         'ping_host', lambda m: {'host': m.group(1)}),

        # Notification
        (re.compile(r'\b(show|send|display)\s+notification[:\s]+(.+)', re.I),
         'show_notification', lambda m: {'title': 'Rex', 'message': m.group(2).strip()}),
    ]

KEYWORD_MAP = _mk_keyword_map()


def _try_keyword(task: str):
    """
    Try to match task against keyword patterns.
    Returns (tool_name, args) or None.
    """
    for pattern, tool_name, args_fn in KEYWORD_MAP:
        m = pattern.search(task)
        if m:
            return tool_name, args_fn(m)
    return None


# ── Gemini Function Calling ───────────────────────────────────────────────────

_GEMINI_FC_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

_REX_CONTEXT = (
    "You are Rex, an AI PC Control Agent. "
    "The user wants you to perform a task on their computer. "
    "Call one or more tools to accomplish it. "
    "Use ~ for the home directory. Be precise with file paths. "
    "For multi-step tasks call all needed tools."
)


def _call_gemini_function_calling(task: str, api_key: str, model: str = 'gemini-2.0-flash'):
    """
    Use Gemini's native function calling to get structured tool calls.
    Returns a list of {"name": tool_name, "args": {...}} dicts, or None on failure.
    """
    url = _GEMINI_FC_URL.format(model=model, key=api_key)
    payload = {
        "system_instruction": {"parts": [{"text": _REX_CONTEXT}]},
        "contents": [{"role": "user", "parts": [{"text": task}]}],
        "tools": [{"function_declarations": REX_FUNCTION_DECLARATIONS}],
        "tool_config": {"function_calling_config": {"mode": "AUTO"}},
        "generationConfig": {"temperature": 0.1},
    }

    for attempt in range(2):
        try:
            r = _req.post(url, json=payload, timeout=25)
            if r.status_code == 200:
                data = r.json()
                parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                calls = []
                for part in parts:
                    if 'functionCall' in part:
                        fc = part['functionCall']
                        calls.append({'name': fc['name'], 'args': fc.get('args', {})})
                return calls if calls else None
            elif r.status_code == 503 and attempt == 0:
                time.sleep(3)
            else:
                print(f'[Rex FC] Gemini {r.status_code}: {r.text[:200]}')
                break
        except Exception as e:
            print(f'[Rex FC] attempt {attempt}: {e}')
            if attempt == 0:
                time.sleep(2)
    return None


def _build_action(tool_name: str, args: dict, source: str = 'ai') -> dict:
    """Build a standardised action object from a tool name + args."""
    tool = TOOLS.get(tool_name)
    if not tool:
        return None
    risk = tool['risk']
    needs_perm = risk in ('medium', 'high')
    reason_map = {
        'medium': 'This action creates or opens something on your PC.',
        'high':   'This action is destructive or runs code — confirmation required.',
    }
    return {
        'tool': tool_name,
        'args': args,
        'risk': risk,
        'source': source,
        'requires_permission': needs_perm,
        'permission_reason': reason_map.get(risk, ''),
        'description': tool['desc'],
    }


def _execute_tool(tool_name: str, args: dict) -> dict:
    if tool_name not in TOOLS:
        return {'success': False, 'error': f'Unknown tool: {tool_name}'}
    try:
        return TOOLS[tool_name]['fn'](**args)
    except TypeError as e:
        return {'success': False, 'error': f'Wrong args for {tool_name}: {e}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── Routes ────────────────────────────────────────────────────────────────────

@rex_bp.route('/rex/plan', methods=['POST'])
def rex_plan():
    """
    Plan Rex actions for a task.
    1. Try keyword fast-path (instant, no API).
    2. Fall back to Gemini Function Calling (structured, no JSON parsing).
    Returns a plan with actions split into safe (auto-execute) and pending (need confirmation).
    """
    data    = request.get_json() or {}
    task    = (data.get('task') or data.get('prompt') or '').strip()
    api_key = data.get('apiKey') or data.get('apiKeys', {}).get('gemini') or os.getenv('GEMINI_API_KEY', '')
    model   = data.get('model', 'gemini-2.0-flash')

    if not task:
        return jsonify({'success': False, 'error': 'No task provided'}), 400

    try:
        AgentDocument.objects(agent_id='rex').update(
            set__status='thinking',
            set__status_text=f'Rex: Planning — {task[:60]}...'
        )
    except Exception:
        pass

    actions = []
    source  = 'keyword'

    # ── Step 1: keyword fast-path ──────────────────────────────────────────
    kw = _try_keyword(task)
    if kw:
        tool_name, args = kw
        action = _build_action(tool_name, args, source='keyword')
        if action:
            actions.append(action)
            print(f'[Rex] keyword match → {tool_name}({args})')

    # ── Step 2: Gemini Function Calling fallback ───────────────────────────
    if not actions:
        if not api_key:
            return jsonify({'success': False,
                            'error': 'No API key — Rex needs Gemini for this command. '
                                     'Add your key in AI Settings.'}), 400

        source = 'ai'
        print(f'[Rex] No keyword match for "{task[:60]}" — calling Gemini Function Calling...')
        calls = _call_gemini_function_calling(task, api_key, model)

        if not calls:
            try:
                AgentDocument.objects(agent_id='rex').update(
                    set__status='idle',
                    set__status_text='Rex: Could not plan that task'
                )
            except Exception:
                pass
            return jsonify({'success': False,
                            'error': 'Rex could not understand that command. Try rephrasing.'}), 500

        for call in calls:
            action = _build_action(call['name'], call['args'], source='ai')
            if action:
                actions.append(action)
                print(f'[Rex] FC → {call["name"]}({call["args"]})')

    if not actions:
        return jsonify({'success': False, 'error': 'Rex found no valid actions for this task'}), 500

    # ── Auto-execute low-risk (keyword) actions immediately ───────────────
    safe    = [a for a in actions if not a['requires_permission']]
    pending = [a for a in actions if a['requires_permission']]

    executed = []
    if source == 'keyword' and safe:
        for action in safe:
            result = _execute_tool(action['tool'], action['args'])
            executed.append({**action, 'result': result})
            print(f'[Rex] auto-exec {action["tool"]} → {"OK" if result.get("success") else "FAIL"}')

    try:
        AgentDocument.objects(agent_id='rex').update(
            set__status='waiting' if pending else 'idle',
            set__status_text=(f'Rex: {len(pending)} action(s) need approval'
                              if pending else 'Rex: Done')
        )
    except Exception:
        pass

    return jsonify({
        'success':              True,
        'source':               source,
        'task':                 task,
        'actions':              actions,
        'safe_actions':         safe,
        'pending_permissions':  pending,
        'requires_confirmation':len(pending) > 0,
        'executed':             executed,
        'explanation':          _summarise(actions, executed),
    })


def _summarise(actions: list, executed: list) -> str:
    if executed:
        parts = []
        for e in executed:
            ok = e.get('result', {}).get('success', False)
            parts.append(f'{"✓" if ok else "✗"} {e["description"]}')
        return '\n'.join(parts)
    elif actions:
        return 'Ready to execute: ' + ', '.join(a['description'] for a in actions)
    return 'No actions planned.'


@rex_bp.route('/rex/execute', methods=['POST'])
def rex_execute():
    """Execute a list of confirmed actions (after user approves permissions)."""
    data    = request.get_json() or {}
    actions = data.get('actions', [])
    task    = data.get('task', '')

    if not actions:
        return jsonify({'success': False, 'error': 'No actions to execute'}), 400

    try:
        AgentDocument.objects(agent_id='rex').update(
            set__status='executing',
            set__status_text=f'Rex: Executing {len(actions)} action(s)...'
        )
    except Exception:
        pass

    results = []
    for action in actions:
        tool_name = action.get('tool', '')
        args      = action.get('args', {})
        desc      = action.get('description', tool_name)
        print(f'[Rex] exec: {tool_name}({args})')
        result = _execute_tool(tool_name, args)
        results.append({
            'tool': tool_name, 'description': desc,
            'args': args, 'result': result,
            'success': result.get('success', False)
        })

    all_ok = all(r['success'] for r in results)
    ok_count = sum(r['success'] for r in results)

    try:
        AgentDocument.objects(agent_id='rex').update(
            set__status='idle',
            set__status_text=f'Rex: Done — {ok_count}/{len(results)} succeeded',
            inc__stats__tasksDone=1
        )
        summary = '\n'.join(f'{"✓" if r["success"] else "✗"} {r["description"]}' for r in results)
        MessageDocument(
            msg_id=f'rex-{int(time.time()*1000)}',
            sender_id='rex', sender_name='Rex',
            sender_role='PC Control Agent', sender_avatar='🖥️',
            channel_id='general',
            text=f'**Rex completed:** {task}\n\n{summary}',
            timestamp=time.strftime('%I:%M %p')
        ).save()
    except Exception:
        pass

    return jsonify({
        'success': all_ok, 'task': task,
        'total': len(results), 'succeeded': ok_count,
        'results': results
    })


@rex_bp.route('/rex/quick', methods=['POST'])
def rex_quick():
    """Execute a single low/medium risk tool directly (no AI needed)."""
    data      = request.get_json() or {}
    tool_name = data.get('tool', '')
    args      = data.get('args', {})

    if tool_name not in TOOLS:
        return jsonify({'success': False, 'error': f'Unknown tool: {tool_name}'}), 400
    if TOOLS[tool_name]['risk'] == 'high':
        return jsonify({'success': False, 'error': 'High-risk tools require the /rex/plan flow'}), 403

    result = _execute_tool(tool_name, args)
    return jsonify({'success': result.get('success', False), 'tool': tool_name, 'result': result})


@rex_bp.route('/rex/tools', methods=['GET'])
def rex_list_tools():
    """List all Rex tools with descriptions and risk levels."""
    return jsonify({
        'success': True,
        'count': len(TOOLS),
        'tools': [{'name': n, 'description': t['desc'], 'risk': t['risk']} for n, t in TOOLS.items()]
    })
