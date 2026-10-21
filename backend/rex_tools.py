"""
Rex — Advanced PC Control Agent Tool Set
Full Windows system control: files, apps, processes, system, shell, clipboard, network, etc.
"""

import os
import re
import glob
import shutil
import socket
import platform
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime


def _expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path)))


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ── FILE SYSTEM ───────────────────────────────────────────────────────────────

def search_files(path: str, pattern: str = '*', content_search: str = None, max_depth: int = 5) -> dict:
    """Search files by name pattern and optionally by content."""
    results = []
    base = _expand(path)
    try:
        matches = glob.glob(os.path.join(base, '**', pattern), recursive=True)
        for match in matches[:200]:
            try:
                stat = os.stat(match)
                info = {
                    'path': match,
                    'name': os.path.basename(match),
                    'type': 'folder' if os.path.isdir(match) else 'file',
                    'size_kb': round(stat.st_size / 1024, 1),
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'extension': Path(match).suffix.lower()
                }
                if content_search and os.path.isfile(match):
                    try:
                        with open(match, 'r', encoding='utf-8', errors='ignore') as f:
                            if content_search.lower() in f.read().lower():
                                results.append(info)
                    except Exception:
                        pass
                else:
                    results.append(info)
            except Exception:
                continue
        return {'success': True, 'count': len(results), 'search_path': base, 'pattern': pattern, 'files': results[:50]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def list_directory(path: str) -> dict:
    """List all items in a directory with metadata."""
    base = _expand(path)
    try:
        items = []
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            try:
                stat = os.stat(full)
                items.append({
                    'name': name,
                    'type': 'folder' if os.path.isdir(full) else 'file',
                    'size_kb': round(stat.st_size / 1024, 1) if os.path.isfile(full) else None,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                    'extension': Path(full).suffix.lower() if os.path.isfile(full) else None
                })
            except Exception:
                continue
        return {'success': True, 'path': base, 'count': len(items), 'items': items}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def read_file(path: str, max_chars: int = 8000) -> dict:
    """Read and return file contents."""
    full = _expand(path)
    try:
        size = os.path.getsize(full)
        with open(full, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_chars)
        return {
            'success': True, 'path': full, 'size_kb': round(size / 1024, 1),
            'content': content, 'truncated': size > max_chars,
            'lines': content.count('\n') + 1
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def write_file(path: str, content: str, append: bool = False) -> dict:
    """Write or append content to a file (creates parent dirs if needed)."""
    full = _expand(path)
    try:
        os.makedirs(os.path.dirname(full) or '.', exist_ok=True)
        mode = 'a' if append else 'w'
        with open(full, mode, encoding='utf-8') as f:
            f.write(content)
        return {'success': True, 'path': full, 'bytes': len(content.encode('utf-8')), 'mode': 'append' if append else 'write'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def copy_item(src: str, dst: str) -> dict:
    """Copy a file or folder to destination."""
    try:
        s, d = _expand(src), _expand(dst)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            os.makedirs(os.path.dirname(d) or '.', exist_ok=True)
            shutil.copy2(s, d)
        return {'success': True, 'src': s, 'dst': d}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def move_item(src: str, dst: str) -> dict:
    """Move a file or folder to a new location."""
    try:
        s, d = _expand(src), _expand(dst)
        shutil.move(s, d)
        return {'success': True, 'src': s, 'dst': d}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def delete_item(path: str) -> dict:
    """Permanently delete a file or folder."""
    full = _expand(path)
    try:
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        return {'success': True, 'deleted': full}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def rename_item(path: str, new_name: str) -> dict:
    """Rename a file or folder."""
    full = _expand(path)
    try:
        new_path = os.path.join(os.path.dirname(full), new_name)
        os.rename(full, new_path)
        return {'success': True, 'old': full, 'new': new_path}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def create_folder(path: str) -> dict:
    """Create a directory (and all parents)."""
    try:
        os.makedirs(_expand(path), exist_ok=True)
        return {'success': True, 'path': _expand(path)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_file_info(path: str) -> dict:
    """Get detailed metadata for a file or folder."""
    full = _expand(path)
    try:
        stat = os.stat(full)
        return {
            'success': True,
            'path': full,
            'name': os.path.basename(full),
            'type': 'folder' if os.path.isdir(full) else 'file',
            'size_kb': round(stat.st_size / 1024, 1),
            'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M'),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'extension': Path(full).suffix.lower(),
            'exists': True
        }
    except FileNotFoundError:
        return {'success': False, 'exists': False, 'path': full, 'error': 'File not found'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def zip_item(src: str, dst_zip: str) -> dict:
    """Compress a file or folder into a zip archive."""
    try:
        s, d = _expand(src), _expand(dst_zip)
        base = d[:-4] if d.endswith('.zip') else d
        shutil.make_archive(base, 'zip', os.path.dirname(s), os.path.basename(s))
        return {'success': True, 'archive': base + '.zip', 'src': s}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def unzip_item(zip_path: str, dst: str) -> dict:
    """Extract a zip archive to a destination folder."""
    try:
        shutil.unpack_archive(_expand(zip_path), _expand(dst))
        return {'success': True, 'extracted_to': _expand(dst)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def find_large_files(path: str, min_size_mb: float = 100) -> dict:
    """Find files larger than a given size in MB."""
    base = _expand(path)
    results = []
    try:
        for root, _, files in os.walk(base):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    if size >= min_size_mb * 1024 * 1024:
                        results.append({'path': fp, 'size_mb': round(size / 1e6, 1)})
                except Exception:
                    continue
        results.sort(key=lambda x: x['size_mb'], reverse=True)
        return {'success': True, 'min_size_mb': min_size_mb, 'count': len(results), 'files': results[:30]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── APPLICATION CONTROL ───────────────────────────────────────────────────────

def open_application(app_name: str) -> dict:
    """Launch an application by name (e.g. 'notepad', 'chrome', 'code')."""
    try:
        subprocess.Popen(['start', '', app_name], shell=True)
        return {'success': True, 'launched': app_name}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_file_default(path: str) -> dict:
    """Open a file with its default associated application."""
    full = _expand(path)
    try:
        os.startfile(full)
        return {'success': True, 'opened': full}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_browser(url: str) -> dict:
    """Open a URL in the default web browser."""
    try:
        webbrowser.open(url)
        return {'success': True, 'url': url}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_explorer(path: str) -> dict:
    """Open a folder in Windows File Explorer."""
    full = _expand(path)
    try:
        subprocess.Popen(['explorer', full])
        return {'success': True, 'path': full}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_vscode(path: str) -> dict:
    """Open a file or folder in VS Code."""
    try:
        subprocess.Popen(['code', _expand(path)], shell=True)
        return {'success': True, 'path': _expand(path)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── PROCESS MANAGEMENT ────────────────────────────────────────────────────────

def list_processes(top_n: int = 20) -> dict:
    """List running processes sorted by memory usage."""
    try:
        result = subprocess.run(
            ['tasklist', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore'
        )
        procs = []
        for line in result.stdout.strip().splitlines()[:top_n]:
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 5:
                procs.append({'name': parts[0], 'pid': parts[1], 'memory': parts[4]})
        return {'success': True, 'count': len(procs), 'processes': procs}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def kill_process(name_or_pid: str) -> dict:
    """Kill a process by name (e.g. 'notepad.exe') or PID."""
    try:
        if str(name_or_pid).isdigit():
            r = subprocess.run(['taskkill', '/PID', str(name_or_pid), '/F'], capture_output=True, text=True)
        else:
            r = subprocess.run(['taskkill', '/IM', name_or_pid, '/F'], capture_output=True, text=True)
        success = r.returncode == 0
        return {'success': success, 'target': name_or_pid, 'output': r.stdout.strip()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def start_process(command: str) -> dict:
    """Start a new process/application by command."""
    try:
        proc = subprocess.Popen(command, shell=True)
        return {'success': True, 'command': command, 'pid': proc.pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── SYSTEM INFORMATION ────────────────────────────────────────────────────────

def get_system_info() -> dict:
    """Get CPU, RAM, disk, OS, and network information."""
    try:
        drives = []
        for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            drive = f'{letter}:\\'
            if os.path.exists(drive):
                try:
                    total, used, free = shutil.disk_usage(drive)
                    drives.append({
                        'drive': drive,
                        'total_gb': round(total / 1e9, 1),
                        'used_gb': round(used / 1e9, 1),
                        'free_gb': round(free / 1e9, 1),
                        'percent_used': round(used / total * 100, 1)
                    })
                except Exception:
                    continue

        info = {
            'success': True,
            'os': platform.system(),
            'os_version': platform.version(),
            'architecture': platform.architecture()[0],
            'hostname': socket.gethostname(),
            'cpu_count': os.cpu_count(),
            'username': os.getenv('USERNAME', 'unknown'),
            'home': os.path.expanduser('~'),
            'desktop': os.path.join(os.path.expanduser('~'), 'Desktop'),
            'disk_drives': drives
        }
        return info
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_network_info() -> dict:
    """Get network adapter info, IP addresses."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        result = subprocess.run(['ipconfig'], capture_output=True, text=True,
                                encoding='utf-8', errors='ignore', timeout=10)
        return {'success': True, 'hostname': hostname, 'local_ip': local_ip,
                'adapters': result.stdout[:2000]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def ping_host(host: str) -> dict:
    """Ping a host to check connectivity."""
    try:
        r = subprocess.run(['ping', '-n', '3', host], capture_output=True, text=True,
                           encoding='utf-8', errors='ignore', timeout=15)
        return {'success': r.returncode == 0, 'host': host, 'output': r.stdout.strip()[-500:]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_environment_vars() -> dict:
    """List all environment variables."""
    env = dict(os.environ)
    safe = {k: v for k, v in env.items() if not any(s in k.lower() for s in ['key', 'secret', 'token', 'password', 'pass'])}
    return {'success': True, 'count': len(safe), 'variables': safe}


def get_env_var(name: str) -> dict:
    """Get a specific environment variable."""
    value = os.environ.get(name)
    return {'success': True, 'name': name, 'value': value, 'exists': value is not None}


# ── SHELL / COMMAND ───────────────────────────────────────────────────────────

def run_command(command: str, working_dir: str = None, timeout: int = 30) -> dict:
    """Run a shell/PowerShell command and return stdout/stderr."""
    try:
        cwd = _expand(working_dir) if working_dir else None
        r = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, cwd=cwd, timeout=timeout,
            encoding='utf-8', errors='ignore'
        )
        return {
            'success': r.returncode == 0,
            'returncode': r.returncode,
            'stdout': r.stdout[:4000],
            'stderr': r.stderr[:1000],
            'command': command
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Command timed out after {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_python_script(script_path: str, args: str = '') -> dict:
    """Run a Python script."""
    return run_command(f'python "{_expand(script_path)}" {args}', timeout=60)


def run_powershell(script: str) -> dict:
    """Run a PowerShell script block."""
    try:
        r = subprocess.run(
            ['powershell', '-NonInteractive', '-Command', script],
            capture_output=True, text=True, timeout=30,
            encoding='utf-8', errors='ignore'
        )
        return {'success': r.returncode == 0, 'stdout': r.stdout[:3000], 'stderr': r.stderr[:500]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── CLIPBOARD ─────────────────────────────────────────────────────────────────

def get_clipboard() -> dict:
    """Read current clipboard contents."""
    try:
        r = subprocess.run(
            ['powershell', '-command', 'Get-Clipboard'],
            capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore'
        )
        return {'success': True, 'content': r.stdout.strip()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def set_clipboard(text: str) -> dict:
    """Write text to clipboard."""
    try:
        r = subprocess.run(
            ['powershell', '-command', f'Set-Clipboard -Value @\'\n{text}\n\'@'],
            capture_output=True, text=True, timeout=5
        )
        return {'success': r.returncode == 0, 'set_length': len(text)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── SCREENSHOT ────────────────────────────────────────────────────────────────

def take_screenshot(save_path: str = None) -> dict:
    """Take a screenshot of the primary screen."""
    if not save_path:
        save_path = os.path.join(os.path.expanduser('~'), 'Desktop',
                                 f'rex_screenshot_{int(datetime.now().timestamp())}.png')
    full = _expand(save_path)
    script = f'''
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $s.Width,$s.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size)
$bmp.Save('{full}')
$g.Dispose(); $bmp.Dispose()
'''
    try:
        r = subprocess.run(['powershell', '-command', script], capture_output=True, timeout=15)
        if os.path.exists(full):
            return {'success': True, 'saved_to': full}
        return {'success': False, 'error': 'Screenshot file not created'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── WINDOWS NOTIFICATION ──────────────────────────────────────────────────────

def show_notification(title: str, message: str, duration_ms: int = 4000) -> dict:
    """Show a Windows toast/balloon notification."""
    script = f'''
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip({duration_ms}, "{title}", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Milliseconds {duration_ms + 500}
$n.Dispose()
'''
    try:
        subprocess.Popen(['powershell', '-command', script])
        return {'success': True, 'title': title, 'message': message}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── GIT OPERATIONS ────────────────────────────────────────────────────────────

def git_status(repo_path: str = '.') -> dict:
    """Get git status of a repository."""
    return run_command('git status --porcelain', working_dir=repo_path, timeout=10)


def git_log(repo_path: str = '.', n: int = 10) -> dict:
    """Get last N git commits."""
    return run_command(f'git log --oneline -{n}', working_dir=repo_path, timeout=10)


def git_diff(repo_path: str = '.') -> dict:
    """Show git diff of unstaged changes."""
    return run_command('git diff --stat', working_dir=repo_path, timeout=10)


# ── TOOL REGISTRY ─────────────────────────────────────────────────────────────

TOOLS = {
    # READ-ONLY / LOW RISK — no permission needed
    'search_files':        {'fn': search_files,        'risk': 'low',    'desc': 'Search files by name or content'},
    'list_directory':      {'fn': list_directory,      'risk': 'low',    'desc': 'List directory contents'},
    'read_file':           {'fn': read_file,           'risk': 'low',    'desc': 'Read a file\'s contents'},
    'get_file_info':       {'fn': get_file_info,       'risk': 'low',    'desc': 'Get file metadata'},
    'find_large_files':    {'fn': find_large_files,    'risk': 'low',    'desc': 'Find files larger than N MB'},
    'get_system_info':     {'fn': get_system_info,     'risk': 'low',    'desc': 'Get CPU, RAM, disk, OS info'},
    'get_network_info':    {'fn': get_network_info,    'risk': 'low',    'desc': 'Get network and IP info'},
    'ping_host':           {'fn': ping_host,           'risk': 'low',    'desc': 'Ping a host to check connectivity'},
    'list_processes':      {'fn': list_processes,      'risk': 'low',    'desc': 'List running processes'},
    'get_clipboard':       {'fn': get_clipboard,       'risk': 'low',    'desc': 'Read clipboard contents'},
    'get_env_var':         {'fn': get_env_var,         'risk': 'low',    'desc': 'Read an environment variable'},
    'get_environment_vars':{'fn': get_environment_vars,'risk': 'low',    'desc': 'List all environment variables'},
    'git_status':          {'fn': git_status,          'risk': 'low',    'desc': 'Git status of a repo'},
    'git_log':             {'fn': git_log,             'risk': 'low',    'desc': 'Recent git commits'},
    'git_diff':            {'fn': git_diff,            'risk': 'low',    'desc': 'Git diff of uncommitted changes'},

    # WRITE / MEDIUM RISK — permission required
    'write_file':          {'fn': write_file,          'risk': 'medium', 'desc': 'Write or create a file'},
    'create_folder':       {'fn': create_folder,       'risk': 'medium', 'desc': 'Create a directory'},
    'copy_item':           {'fn': copy_item,           'risk': 'medium', 'desc': 'Copy a file or folder'},
    'zip_item':            {'fn': zip_item,            'risk': 'medium', 'desc': 'Compress to zip archive'},
    'unzip_item':          {'fn': unzip_item,          'risk': 'medium', 'desc': 'Extract a zip archive'},
    'set_clipboard':       {'fn': set_clipboard,       'risk': 'medium', 'desc': 'Set clipboard text'},
    'open_in_browser':     {'fn': open_in_browser,     'risk': 'medium', 'desc': 'Open URL in browser'},
    'open_file_default':   {'fn': open_file_default,   'risk': 'medium', 'desc': 'Open file with default app'},
    'open_in_explorer':    {'fn': open_in_explorer,    'risk': 'medium', 'desc': 'Open folder in Explorer'},
    'open_in_vscode':      {'fn': open_in_vscode,      'risk': 'medium', 'desc': 'Open in VS Code'},
    'open_application':    {'fn': open_application,    'risk': 'medium', 'desc': 'Launch an application'},
    'show_notification':   {'fn': show_notification,   'risk': 'low',    'desc': 'Show Windows notification'},
    'take_screenshot':     {'fn': take_screenshot,     'risk': 'low',    'desc': 'Take a screenshot'},
    'start_process':       {'fn': start_process,       'risk': 'medium', 'desc': 'Start a new process'},

    # DESTRUCTIVE / HIGH RISK — always require permission
    'rename_item':         {'fn': rename_item,         'risk': 'high',   'desc': 'Rename a file or folder'},
    'move_item':           {'fn': move_item,           'risk': 'high',   'desc': 'Move a file or folder'},
    'delete_item':         {'fn': delete_item,         'risk': 'high',   'desc': 'DELETE a file or folder permanently'},
    'kill_process':        {'fn': kill_process,        'risk': 'high',   'desc': 'Kill a running process by name/PID'},
    'run_command':         {'fn': run_command,         'risk': 'high',   'desc': 'Run a shell command'},
    'run_powershell':      {'fn': run_powershell,      'risk': 'high',   'desc': 'Run a PowerShell script'},
    'run_python_script':   {'fn': run_python_script,   'risk': 'high',   'desc': 'Run a Python script file'},
}

TOOL_DESCRIPTIONS = '\n'.join(
    f"  [{t['risk'].upper()}] {name}: {t['desc']}"
    for name, t in TOOLS.items()
)
