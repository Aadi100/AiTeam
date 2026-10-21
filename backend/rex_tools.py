"""
Rex — Advanced Cross-Platform Control Agent
Works on Windows, macOS, Linux, and any Unix-like system.
Three risk tiers: low (auto-execute), medium (permission preferred), high (always ask).
"""

import os
import re
import sys
import glob
import shutil
import socket
import platform
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

# ── Platform detection ────────────────────────────────────────────────────────
IS_WINDOWS = sys.platform == 'win32'
IS_MAC     = sys.platform == 'darwin'
IS_LINUX   = sys.platform.startswith('linux')
OS_NAME    = platform.system()   # 'Windows', 'Darwin', 'Linux'


def _expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path)))


def _now() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _desktop() -> str:
    if IS_WINDOWS:
        return os.path.join(os.path.expanduser('~'), 'Desktop')
    if IS_MAC:
        return os.path.join(os.path.expanduser('~'), 'Desktop')
    # Linux: XDG
    xdg = os.environ.get('XDG_DESKTOP_DIR', '')
    return xdg if xdg else os.path.join(os.path.expanduser('~'), 'Desktop')


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


def get_desktop_path() -> dict:
    """Return the platform-appropriate Desktop path."""
    p = _desktop()
    return {'success': True, 'desktop': p, 'platform': OS_NAME, 'exists': os.path.exists(p)}


# ── APPLICATION CONTROL ───────────────────────────────────────────────────────

def open_application(app_name: str) -> dict:
    """Launch an application by name. Works on Windows, macOS, Linux."""
    try:
        if IS_WINDOWS:
            subprocess.Popen(['start', '', app_name], shell=True)
        elif IS_MAC:
            subprocess.Popen(['open', '-a', app_name])
        else:
            subprocess.Popen([app_name])
        return {'success': True, 'launched': app_name, 'platform': OS_NAME}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_file_default(path: str) -> dict:
    """Open a file with its default associated application (cross-platform)."""
    full = _expand(path)
    try:
        if IS_WINDOWS:
            os.startfile(full)
        elif IS_MAC:
            subprocess.Popen(['open', full])
        else:
            subprocess.Popen(['xdg-open', full])
        return {'success': True, 'opened': full, 'platform': OS_NAME}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_browser(url: str) -> dict:
    """Open a URL in the default web browser (cross-platform)."""
    try:
        webbrowser.open(url)
        return {'success': True, 'url': url}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_explorer(path: str) -> dict:
    """Open a folder in the system file manager (Explorer/Finder/Nautilus)."""
    full = _expand(path)
    try:
        if IS_WINDOWS:
            subprocess.Popen(['explorer', full])
        elif IS_MAC:
            subprocess.Popen(['open', full])
        else:
            subprocess.Popen(['xdg-open', full])
        return {'success': True, 'path': full, 'platform': OS_NAME}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_in_vscode(path: str) -> dict:
    """Open a file or folder in VS Code."""
    try:
        subprocess.Popen(['code', _expand(path)], shell=IS_WINDOWS)
        return {'success': True, 'path': _expand(path)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def open_terminal(path: str = None) -> dict:
    """Open a terminal window, optionally at a specific path (cross-platform)."""
    cwd = _expand(path) if path else os.path.expanduser('~')
    try:
        if IS_WINDOWS:
            subprocess.Popen(['cmd', '/K', f'cd /d "{cwd}"'], shell=True)
        elif IS_MAC:
            script = f'tell application "Terminal" to do script "cd {cwd}"'
            subprocess.Popen(['osascript', '-e', script])
        else:
            for term in ['gnome-terminal', 'xterm', 'konsole', 'xfce4-terminal']:
                try:
                    subprocess.Popen([term, '--working-directory', cwd])
                    return {'success': True, 'terminal': term, 'path': cwd}
                except FileNotFoundError:
                    continue
        return {'success': True, 'path': cwd, 'platform': OS_NAME}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── PROCESS MANAGEMENT ────────────────────────────────────────────────────────

def list_processes(top_n: int = 20) -> dict:
    """List running processes sorted by memory usage (cross-platform)."""
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=10, encoding='utf-8', errors='ignore'
            )
            procs = []
            for line in result.stdout.strip().splitlines()[:top_n]:
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 5:
                    procs.append({'name': parts[0], 'pid': parts[1], 'memory': parts[4]})
        else:
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%mem'] if IS_LINUX else ['ps', 'aux'],
                capture_output=True, text=True, timeout=10
            )
            procs = []
            for line in result.stdout.strip().splitlines()[1:top_n + 1]:
                parts = line.split()
                if len(parts) >= 11:
                    procs.append({'user': parts[0], 'pid': parts[1], 'cpu%': parts[2], 'mem%': parts[3], 'name': ' '.join(parts[10:])[:60]})
        return {'success': True, 'count': len(procs), 'processes': procs, 'platform': OS_NAME}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def kill_process(name_or_pid: str) -> dict:
    """Kill a process by name or PID (cross-platform)."""
    try:
        if IS_WINDOWS:
            if str(name_or_pid).isdigit():
                r = subprocess.run(['taskkill', '/PID', str(name_or_pid), '/F'], capture_output=True, text=True)
            else:
                r = subprocess.run(['taskkill', '/IM', name_or_pid, '/F'], capture_output=True, text=True)
            success = r.returncode == 0
            return {'success': success, 'target': name_or_pid, 'output': r.stdout.strip()}
        else:
            if str(name_or_pid).isdigit():
                r = subprocess.run(['kill', '-9', str(name_or_pid)], capture_output=True, text=True)
            else:
                r = subprocess.run(['pkill', '-9', '-f', name_or_pid], capture_output=True, text=True)
            return {'success': r.returncode == 0, 'target': name_or_pid, 'output': r.stdout.strip()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def start_process(command: str) -> dict:
    """Start a new process/application by command (cross-platform)."""
    try:
        proc = subprocess.Popen(command, shell=True)
        return {'success': True, 'command': command, 'pid': proc.pid}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── SYSTEM INFORMATION ────────────────────────────────────────────────────────

def get_system_info() -> dict:
    """Get CPU, RAM, disk, OS, and system info (cross-platform)."""
    try:
        # Disk info — cross-platform
        drives = []
        if IS_WINDOWS:
            for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
                drive = f'{letter}:\\'
                if os.path.exists(drive):
                    try:
                        total, used, free = shutil.disk_usage(drive)
                        drives.append({'drive': drive, 'total_gb': round(total / 1e9, 1), 'used_gb': round(used / 1e9, 1), 'free_gb': round(free / 1e9, 1), 'percent_used': round(used / total * 100, 1)})
                    except Exception:
                        continue
        else:
            for mp in ['/', '/home', '/Users', '/tmp']:
                if os.path.exists(mp):
                    try:
                        total, used, free = shutil.disk_usage(mp)
                        drives.append({'mount': mp, 'total_gb': round(total / 1e9, 1), 'used_gb': round(used / 1e9, 1), 'free_gb': round(free / 1e9, 1), 'percent_used': round(used / total * 100, 1)})
                    except Exception:
                        continue

        return {
            'success': True,
            'platform': OS_NAME,
            'platform_version': platform.version(),
            'architecture': platform.architecture()[0],
            'machine': platform.machine(),
            'hostname': socket.gethostname(),
            'cpu_count': os.cpu_count(),
            'python_version': sys.version.split()[0],
            'username': os.environ.get('USERNAME') or os.environ.get('USER', 'unknown'),
            'home': os.path.expanduser('~'),
            'desktop': _desktop(),
            'disk': drives
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_network_info() -> dict:
    """Get network info (cross-platform)."""
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if IS_WINDOWS:
            cmd = ['ipconfig']
        elif IS_MAC:
            cmd = ['ifconfig']
        else:
            cmd = ['ip', 'addr']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10)
        return {'success': True, 'hostname': hostname, 'local_ip': local_ip, 'platform': OS_NAME, 'adapters': result.stdout[:2000]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def ping_host(host: str) -> dict:
    """Ping a host to check connectivity (cross-platform)."""
    try:
        count_flag = '-n' if IS_WINDOWS else '-c'
        r = subprocess.run(['ping', count_flag, '3', host], capture_output=True, text=True,
                           encoding='utf-8', errors='ignore', timeout=15)
        return {'success': r.returncode == 0, 'host': host, 'output': r.stdout.strip()[-500:]}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_environment_vars() -> dict:
    """List all environment variables (filtered for safety)."""
    env = dict(os.environ)
    safe = {k: v for k, v in env.items() if not any(s in k.lower() for s in ['key', 'secret', 'token', 'password', 'pass', 'credential'])}
    return {'success': True, 'count': len(safe), 'variables': safe}


def get_env_var(name: str) -> dict:
    """Get a specific environment variable."""
    value = os.environ.get(name)
    return {'success': True, 'name': name, 'value': value, 'exists': value is not None}


def get_battery_info() -> dict:
    """Get battery/power status (cross-platform). Best on laptops/tablets."""
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ['powershell', '-command', '(Get-WmiObject Win32_Battery | Select-Object EstimatedChargeRemaining,BatteryStatus,FullChargeCapacity | ConvertTo-Json)'],
                capture_output=True, text=True, timeout=10
            )
            return {'success': True, 'platform': 'Windows', 'raw': r.stdout.strip()[:500]}
        elif IS_MAC:
            r = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True, timeout=5)
            return {'success': True, 'platform': 'macOS', 'raw': r.stdout.strip()}
        else:
            bat = Path('/sys/class/power_supply/BAT0')
            if bat.exists():
                cap = (bat / 'capacity').read_text().strip()
                status = (bat / 'status').read_text().strip()
                return {'success': True, 'platform': 'Linux', 'capacity_pct': cap, 'status': status}
            return {'success': False, 'error': 'No battery detected'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── SHELL / COMMAND ───────────────────────────────────────────────────────────

def run_command(command: str, working_dir: str = None, timeout: int = 30) -> dict:
    """Run a shell command and return stdout/stderr (cross-platform)."""
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
            'command': command,
            'platform': OS_NAME
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': f'Command timed out after {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_python_script(script_path: str, args: str = '') -> dict:
    """Run a Python script (cross-platform)."""
    py = 'python' if IS_WINDOWS else 'python3'
    return run_command(f'{py} "{_expand(script_path)}" {args}', timeout=60)


def run_powershell(script: str) -> dict:
    """Run a PowerShell script block (Windows) or fallback to bash on Mac/Linux."""
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ['powershell', '-NonInteractive', '-Command', script],
                capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore'
            )
        else:
            # pwsh (PowerShell Core) available cross-platform
            r = subprocess.run(
                ['pwsh', '-NonInteractive', '-Command', script],
                capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore'
            )
        return {'success': r.returncode == 0, 'stdout': r.stdout[:3000], 'stderr': r.stderr[:500]}
    except FileNotFoundError:
        return {'success': False, 'error': 'PowerShell not found. Use run_bash() on this platform.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def run_bash(script: str, timeout: int = 30) -> dict:
    """Run a bash/sh script (macOS and Linux; uses sh on Windows)."""
    shell = 'bash' if not IS_WINDOWS else 'sh'
    try:
        r = subprocess.run([shell, '-c', script], capture_output=True, text=True,
                           timeout=timeout, encoding='utf-8', errors='ignore')
        return {'success': r.returncode == 0, 'stdout': r.stdout[:3000], 'stderr': r.stderr[:500], 'shell': shell}
    except FileNotFoundError:
        return run_command(script, timeout=timeout)
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── CLIPBOARD ─────────────────────────────────────────────────────────────────

def get_clipboard() -> dict:
    """Read current clipboard contents (cross-platform)."""
    try:
        if IS_WINDOWS:
            r = subprocess.run(['powershell', '-command', 'Get-Clipboard'],
                               capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore')
            return {'success': True, 'content': r.stdout.strip()}
        elif IS_MAC:
            r = subprocess.run(['pbpaste'], capture_output=True, text=True, timeout=5)
            return {'success': True, 'content': r.stdout}
        else:
            for cmd in [['xclip', '-selection', 'clipboard', '-o'], ['xsel', '--clipboard', '--output']]:
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    return {'success': True, 'content': r.stdout}
                except FileNotFoundError:
                    continue
            return {'success': False, 'error': 'Install xclip or xsel for clipboard support on Linux'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def set_clipboard(text: str) -> dict:
    """Write text to clipboard (cross-platform)."""
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ['powershell', '-command', f'Set-Clipboard -Value @\'\n{text}\n\'@'],
                capture_output=True, text=True, timeout=5
            )
            return {'success': r.returncode == 0, 'set_length': len(text)}
        elif IS_MAC:
            r = subprocess.run(['pbcopy'], input=text.encode(), timeout=5)
            return {'success': r.returncode == 0, 'set_length': len(text)}
        else:
            for cmd in [['xclip', '-selection', 'clipboard'], ['xsel', '--clipboard', '--input']]:
                try:
                    r = subprocess.run(cmd, input=text.encode(), timeout=5)
                    return {'success': r.returncode == 0, 'set_length': len(text)}
                except FileNotFoundError:
                    continue
            return {'success': False, 'error': 'Install xclip or xsel for clipboard support on Linux'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── SCREENSHOT ────────────────────────────────────────────────────────────────

def take_screenshot(save_path: str = None) -> dict:
    """Take a screenshot of the primary screen (cross-platform)."""
    ts = int(datetime.now().timestamp())
    if not save_path:
        save_path = os.path.join(_desktop(), f'rex_screenshot_{ts}.png')
    full = _expand(save_path)
    try:
        if IS_WINDOWS:
            script = f'''
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $s.Width,$s.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($s.Location,[System.Drawing.Point]::Empty,$s.Size)
$bmp.Save('{full}')
$g.Dispose(); $bmp.Dispose()
'''
            subprocess.run(['powershell', '-command', script], capture_output=True, timeout=15)
        elif IS_MAC:
            subprocess.run(['screencapture', '-x', full], timeout=10)
        else:
            for tool in [['scrot', full], ['import', '-window', 'root', full], ['gnome-screenshot', '-f', full]]:
                try:
                    subprocess.run(tool, timeout=10)
                    break
                except FileNotFoundError:
                    continue

        if os.path.exists(full):
            return {'success': True, 'saved_to': full, 'platform': OS_NAME}
        return {'success': False, 'error': 'Screenshot file not created. Install scrot (Linux) or use Windows/Mac.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── NOTIFICATION ──────────────────────────────────────────────────────────────

def show_notification(title: str, message: str, duration_ms: int = 4000) -> dict:
    """Show a system notification (cross-platform: Windows/macOS/Linux)."""
    try:
        if IS_WINDOWS:
            script = f'''
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip({duration_ms}, "{title}", "{message}", [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Milliseconds {duration_ms + 500}
$n.Dispose()
'''
            subprocess.Popen(['powershell', '-command', script])
        elif IS_MAC:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.Popen(['osascript', '-e', script])
        else:
            subprocess.Popen(['notify-send', title, message, '-t', str(duration_ms)])
        return {'success': True, 'title': title, 'message': message, 'platform': OS_NAME}
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


def git_clone(url: str, dest: str = None) -> dict:
    """Clone a git repository."""
    cmd = f'git clone {url}' + (f' "{_expand(dest)}"' if dest else '')
    return run_command(cmd, timeout=120)


def git_pull(repo_path: str = '.') -> dict:
    """Pull latest changes in a repository."""
    return run_command('git pull', working_dir=repo_path, timeout=60)


# ── TOOL REGISTRY ─────────────────────────────────────────────────────────────

TOOLS = {
    # READ-ONLY / LOW RISK
    'search_files':        {'fn': search_files,        'risk': 'low',    'desc': 'Search files by name or content'},
    'list_directory':      {'fn': list_directory,      'risk': 'low',    'desc': 'List directory contents'},
    'read_file':           {'fn': read_file,           'risk': 'low',    'desc': 'Read a file contents'},
    'get_file_info':       {'fn': get_file_info,       'risk': 'low',    'desc': 'Get file metadata'},
    'find_large_files':    {'fn': find_large_files,    'risk': 'low',    'desc': 'Find files larger than N MB'},
    'get_desktop_path':    {'fn': get_desktop_path,    'risk': 'low',    'desc': 'Get Desktop folder path'},
    'get_system_info':     {'fn': get_system_info,     'risk': 'low',    'desc': 'Get CPU, RAM, disk, OS info'},
    'get_network_info':    {'fn': get_network_info,    'risk': 'low',    'desc': 'Get network and IP info'},
    'get_battery_info':    {'fn': get_battery_info,    'risk': 'low',    'desc': 'Get battery/power status'},
    'ping_host':           {'fn': ping_host,           'risk': 'low',    'desc': 'Ping a host to check connectivity'},
    'list_processes':      {'fn': list_processes,      'risk': 'low',    'desc': 'List running processes'},
    'get_clipboard':       {'fn': get_clipboard,       'risk': 'low',    'desc': 'Read clipboard contents'},
    'get_env_var':         {'fn': get_env_var,         'risk': 'low',    'desc': 'Read an environment variable'},
    'get_environment_vars':{'fn': get_environment_vars,'risk': 'low',    'desc': 'List all environment variables'},
    'git_status':          {'fn': git_status,          'risk': 'low',    'desc': 'Git status of a repo'},
    'git_log':             {'fn': git_log,             'risk': 'low',    'desc': 'Recent git commits'},
    'git_diff':            {'fn': git_diff,            'risk': 'low',    'desc': 'Git diff of uncommitted changes'},
    'take_screenshot':     {'fn': take_screenshot,     'risk': 'low',    'desc': 'Take a screenshot'},

    # WRITE / MEDIUM RISK
    'write_file':          {'fn': write_file,          'risk': 'medium', 'desc': 'Write or create a file'},
    'create_folder':       {'fn': create_folder,       'risk': 'medium', 'desc': 'Create a directory'},
    'copy_item':           {'fn': copy_item,           'risk': 'medium', 'desc': 'Copy a file or folder'},
    'zip_item':            {'fn': zip_item,            'risk': 'medium', 'desc': 'Compress to zip archive'},
    'unzip_item':          {'fn': unzip_item,          'risk': 'medium', 'desc': 'Extract a zip archive'},
    'set_clipboard':       {'fn': set_clipboard,       'risk': 'medium', 'desc': 'Set clipboard text'},
    'open_in_browser':     {'fn': open_in_browser,     'risk': 'medium', 'desc': 'Open URL in browser'},
    'open_file_default':   {'fn': open_file_default,   'risk': 'medium', 'desc': 'Open file with default app'},
    'open_in_explorer':    {'fn': open_in_explorer,    'risk': 'medium', 'desc': 'Open folder in file manager'},
    'open_in_vscode':      {'fn': open_in_vscode,      'risk': 'medium', 'desc': 'Open in VS Code'},
    'open_application':    {'fn': open_application,    'risk': 'medium', 'desc': 'Launch an application'},
    'open_terminal':       {'fn': open_terminal,       'risk': 'medium', 'desc': 'Open a terminal window'},
    'show_notification':   {'fn': show_notification,   'risk': 'low',    'desc': 'Show system notification'},
    'start_process':       {'fn': start_process,       'risk': 'medium', 'desc': 'Start a new process'},
    'git_pull':            {'fn': git_pull,            'risk': 'medium', 'desc': 'Git pull latest changes'},
    'git_clone':           {'fn': git_clone,           'risk': 'medium', 'desc': 'Clone a git repository'},

    # DESTRUCTIVE / HIGH RISK
    'rename_item':         {'fn': rename_item,         'risk': 'high',   'desc': 'Rename a file or folder'},
    'move_item':           {'fn': move_item,           'risk': 'high',   'desc': 'Move a file or folder'},
    'delete_item':         {'fn': delete_item,         'risk': 'high',   'desc': 'DELETE a file or folder permanently'},
    'kill_process':        {'fn': kill_process,        'risk': 'high',   'desc': 'Kill a running process by name/PID'},
    'run_command':         {'fn': run_command,         'risk': 'high',   'desc': 'Run a shell command'},
    'run_powershell':      {'fn': run_powershell,      'risk': 'high',   'desc': 'Run a PowerShell/pwsh script'},
    'run_bash':            {'fn': run_bash,            'risk': 'high',   'desc': 'Run a bash/sh script (Mac/Linux)'},
    'run_python_script':   {'fn': run_python_script,   'risk': 'high',   'desc': 'Run a Python script file'},
}

TOOL_DESCRIPTIONS = '\n'.join(
    f"  [{t['risk'].upper()}] {name}: {t['desc']}"
    for name, t in TOOLS.items()
)
