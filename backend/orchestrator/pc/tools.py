"""
The PC tools. Each tool is one small, checked function; Adion never gets a raw shell.

risk:  read    looks only (runs without asking if the folder is allowed)
       low     harmless side effects: open an app / site / document, volume, media keys, lock (runs without asking)
       change  creates/moves/copies/renames files (needs approval unless "trust" is on)
       danger  delete, run a command, open an executable (always needs approval)

run(ctx, args) returns {'ok', 'text', 'undo'}; ctx = {'owner', 'granted', 'task_id', 'step'}.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

from . import policy

MAX_READ = 20000
MAX_WRITE = 200_000
TRASH = os.path.join(policy.home(), '.adion', 'trash')


class ToolError(Exception):
    pass


# OS hooks, replaced in tests so nothing real is opened, muted or locked
def _startfile(target):
    if os.name == 'nt':
        os.startfile(target)   # noqa: S606
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', target])
    else:
        subprocess.Popen(['xdg-open', target])


def _press_key(vk, times=1):
    import ctypes
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def _lock():
    import ctypes
    ctypes.windll.user32.LockWorkStation()


TOOLS = {}


def tool(name, desc, params, risk, paths=None, preview=None, risk_fn=None):
    def deco(fn):
        TOOLS[name] = {'name': name, 'desc': desc, 'params': params, 'risk': risk, 'run': fn,
                       'paths': paths or (lambda a: []), 'preview': preview or (lambda a: f'{name} {a}'), 'risk_fn': risk_fn}
        return fn
    return deco


def risk_of(name, args):
    t = TOOLS[name]
    return t['risk_fn'](args) if t['risk_fn'] else t['risk']


# ───────────────────────── helpers ─────────────────────────

def _real(ctx, path, write=False):
    """Resolve and re-check a path at execution time (the policy may have changed since the plan was made)."""
    chk = policy.check_path(ctx['owner'], path, write, ctx.get('granted', ()))
    if chk['status'] == 'deny':
        raise ToolError(chk['reason'])
    if chk['status'] == 'ask':
        raise ToolError(f"No permission for {chk['root']} yet.")
    return chk['real']


def _fmt_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


def _fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d')


def _unique(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f'{base} ({i}){ext}'):
        i += 1
    return f'{base} ({i}){ext}'


def _to_trash(real, task_id, step):
    """Adion's own trash (not permanent). Returns where it went so it can be restored."""
    dest_dir = os.path.join(TRASH, task_id or 'misc', str(step))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(real))
    shutil.move(real, dest)
    return dest


def purge_trash(days=30):
    cutoff = time.time() - days * 86400
    if not os.path.isdir(TRASH):
        return
    for d in os.listdir(TRASH):
        p = os.path.join(TRASH, d)
        if os.path.getmtime(p) < cutoff:
            shutil.rmtree(p, ignore_errors=True)


def _count(real):
    if os.path.isfile(real):
        return 1, os.path.getsize(real)
    n = size = 0
    for dp, dn, fn in os.walk(real):
        for f in fn:
            n += 1
            try:
                size += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
        if n > 5000:
            break
    return n, size


# ───────────────────────── read tools ─────────────────────────

@tool('list_dir', 'List the files and folders in a folder.', {'path': 'folder (default: Desktop)', 'limit': 'max entries, default 60'},
      'read', paths=lambda a: [(a.get('path') or 'desktop', False)], preview=lambda a: f'List {a.get("path") or "Desktop"}')
def list_dir(ctx, a):
    real = _real(ctx, a.get('path') or 'desktop')
    if not os.path.isdir(real):
        raise ToolError(f'{real} is not a folder.')
    limit = min(int(a.get('limit') or 60), 200)
    rows = []
    for e in sorted(os.scandir(real), key=lambda e: (not e.is_dir(), e.name.lower())):
        if policy.blocked_reason(e.path, False):
            continue
        try:
            st = e.stat()
        except OSError:
            continue
        rows.append(f'[dir]  {e.name}' if e.is_dir() else f'[file] {e.name} ({_fmt_size(st.st_size)}, {_fmt_time(st.st_mtime)})')
    shown = rows[:limit]
    return {'ok': True, 'text': f'{real}: {len(rows)} items\n' + '\n'.join(shown) + (f'\n... {len(rows) - limit} more' if len(rows) > limit else '')}


TEXT_EXT = {'.txt', '.md', '.csv', '.json', '.log', '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.xml', '.yml', '.yaml',
            '.ini', '.cfg', '.toml', '.sql', '.sh', '.bat', '.ps1', '.java', '.c', '.cpp', '.h', '.cs', '.go', '.rs', '.php', '.rb', '.tex'}


def _parse_date(s, end=False):
    s = str(s or '').strip()
    for fmt, pad in (('%Y-%m-%d', 0), ('%Y-%m', 1), ('%Y', 2)):
        try:
            d = datetime.strptime(s, fmt)
            if end and pad == 1:
                d = d.replace(year=d.year + (d.month == 12), month=d.month % 12 + 1)
            elif end and pad == 2:
                d = d.replace(year=d.year + 1)
            elif end:
                d = d.replace(hour=23, minute=59, second=59)
            return d.timestamp()
        except ValueError:
            continue
    return None


@tool('search_files', 'Find files by name, type, content or date inside a folder (searches sub-folders too).',
      {'path': 'folder to search (default: Desktop)', 'name_contains': 'words that must be in the file name', 'ext': 'extension(s), e.g. pdf or "pdf,docx"',
       'text_contains': 'text that must be inside (text files only)', 'modified_after': 'YYYY-MM-DD or YYYY-MM', 'modified_before': 'YYYY-MM-DD or YYYY-MM', 'limit': 'default 40'},
      'read', paths=lambda a: [(a.get('path') or 'desktop', False)],
      preview=lambda a: f'Search {a.get("path") or "Desktop"} for ' + ', '.join(f'{k}={v}' for k, v in a.items() if k != 'path' and v))
def search_files(ctx, a):
    real = _real(ctx, a.get('path') or 'desktop')
    if not os.path.isdir(real):
        raise ToolError(f'{real} is not a folder.')
    words = [w for w in re.split(r'\s+', str(a.get('name_contains') or '').lower()) if w]
    exts = {('.' + e.strip().lstrip('.').lower()) for e in str(a.get('ext') or '').split(',') if e.strip()}
    needle = str(a.get('text_contains') or '').lower()
    after, before = _parse_date(a.get('modified_after')), _parse_date(a.get('modified_before'), end=True)
    limit = min(int(a.get('limit') or 40), 100)
    hits, scanned, t0 = [], 0, time.time()
    for dp, dn, fn in os.walk(real):
        dn[:] = [d for d in dn if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.git')
                 and not policy.blocked_reason(os.path.join(dp, d), False)]
        if dp[len(real):].count(os.sep) >= 6:
            dn[:] = []
        for f in fn:
            scanned += 1
            p = os.path.join(dp, f)
            low = f.lower()
            ext = os.path.splitext(low)[1]
            if (words and not all(w in low for w in words)) or (exts and ext not in exts) or policy.blocked_reason(p, False):
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            if (after and st.st_mtime < after) or (before and st.st_mtime > before):
                continue
            if needle:
                if ext not in TEXT_EXT or st.st_size > 1_000_000:
                    continue
                try:
                    with open(p, encoding='utf-8', errors='ignore') as fh:
                        if needle not in fh.read().lower():
                            continue
                except OSError:
                    continue
            hits.append((st.st_mtime, p, st.st_size))
        if len(hits) >= limit * 3 or scanned > 40000 or time.time() - t0 > 8:
            break
    hits.sort(reverse=True)
    lines = [f'{p} ({_fmt_size(s)}, {_fmt_time(m)})' for m, p, s in hits[:limit]]
    return {'ok': True, 'text': f'{len(hits)} match(es) in {real}' + (f' (showing {limit})' if len(hits) > limit else '') + ':\n' + '\n'.join(lines)}


@tool('read_file', 'Read the text of a file (txt, md, csv, json, code, PDF, Word). Pictures cannot be read yet.',
      {'path': 'file', 'max_chars': 'default 6000'}, 'read', paths=lambda a: [(a.get('path'), False)], preview=lambda a: f'Read {a.get("path")}')
def read_file(ctx, a):
    real = _real(ctx, a.get('path'))
    if not os.path.isfile(real):
        raise ToolError(f'{real} is not a file.')
    cap = min(int(a.get('max_chars') or 6000), MAX_READ)
    ext = os.path.splitext(real)[1].lower()
    if ext == '.pdf':
        try:
            from pypdf import PdfReader
            text = '\n'.join((p.extract_text() or '') for p in PdfReader(real).pages[:20])
        except Exception as e:  # noqa: BLE001
            raise ToolError(f'Could not read the PDF: {e}')
    elif ext == '.docx':
        try:
            import docx
            text = '\n'.join(p.text for p in docx.Document(real).paragraphs)
        except Exception as e:  # noqa: BLE001
            raise ToolError(f'Could not read the Word file: {e}')
    elif ext in TEXT_EXT or os.path.getsize(real) < 200_000:
        with open(real, 'rb') as fh:
            raw = fh.read(cap * 4 + 1)
        if b'\x00' in raw[:2000]:
            raise ToolError('This is a binary file (picture, program or archive). I can only read text, PDF and Word files for now.')
        text = raw.decode('utf-8', errors='replace')
    else:
        raise ToolError('I can only read text, PDF and Word files for now.')
    text = text.strip()
    if not text:
        raise ToolError('The file has no readable text (a scanned PDF needs picture/OCR support, which is not built yet).')
    return {'ok': True, 'text': text[:cap] + ('\n...[cut]' if len(text) > cap else '')}


@tool('file_info', 'Size, dates and type of a file or folder.', {'path': 'file or folder'}, 'read',
      paths=lambda a: [(a.get('path'), False)], preview=lambda a: f'Info about {a.get("path")}')
def file_info(ctx, a):
    real = _real(ctx, a.get('path'))
    if not os.path.exists(real):
        raise ToolError(f'{real} does not exist.')
    st = os.stat(real)
    n, size = _count(real)
    kind = 'folder' if os.path.isdir(real) else 'file'
    return {'ok': True, 'text': f'{real}\n{kind}, {n} file(s), {_fmt_size(size)}, modified {_fmt_time(st.st_mtime)}, created {_fmt_time(st.st_ctime)}'}


@tool('system_info', 'CPU, memory, disk, battery and the busiest programs.', {}, 'read', preview=lambda a: 'Check system status')
def system_info(ctx, a):
    import psutil
    parts = [f'CPU {psutil.cpu_percent(interval=0.4):.0f}% on {psutil.cpu_count()} cores']
    vm = psutil.virtual_memory()
    parts.append(f'Memory {vm.percent:.0f}% used ({_fmt_size(vm.used)} of {_fmt_size(vm.total)})')
    try:
        du = psutil.disk_usage(os.path.splitdrive(policy.home())[0] + os.sep)
        parts.append(f'Disk {du.percent:.0f}% used, {_fmt_size(du.free)} free of {_fmt_size(du.total)}')
    except OSError:
        pass
    b = psutil.sensors_battery()
    if b:
        parts.append(f'Battery {b.percent:.0f}% ({"charging" if b.power_plugged else "on battery"})')
    procs = []
    for p in psutil.process_iter(['name', 'memory_info']):
        try:
            procs.append((p.info['memory_info'].rss, p.info['name']))
        except Exception:  # noqa: BLE001
            continue
    top = {}
    for rss, name in procs:
        top[name] = top.get(name, 0) + rss
    parts.append('Busiest programs (memory): ' + ', '.join(f'{n} {_fmt_size(r)}' for n, r in sorted(top.items(), key=lambda x: -x[1])[:6]))
    return {'ok': True, 'text': '\n'.join(parts)}


# ───────────────────────── open / media (low risk) ─────────────────────────

_ALIASES = {'notepad': 'notepad.exe', 'calculator': 'calc.exe', 'calc': 'calc.exe', 'paint': 'mspaint.exe', 'file explorer': 'explorer.exe',
            'explorer': 'explorer.exe', 'task manager': 'taskmgr.exe', 'control panel': 'control.exe', 'snipping tool': 'snippingtool.exe',
            'settings': 'ms-settings:', 'terminal': 'wt.exe', 'windows terminal': 'wt.exe', 'command prompt': 'cmd.exe', 'cmd': 'cmd.exe',
            'powershell': 'powershell.exe', 'vscode': 'Visual Studio Code', 'vs code': 'Visual Studio Code', 'code': 'Visual Studio Code',
            'chrome': 'Google Chrome', 'edge': 'Microsoft Edge', 'word': 'Word', 'excel': 'Excel', 'powerpoint': 'PowerPoint'}


def _start_menu():
    dirs = [os.path.join(os.getenv('ProgramData', ''), r'Microsoft\Windows\Start Menu\Programs'),
            os.path.join(os.getenv('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs')]
    found = {}
    for d in dirs:
        for dp, _, fn in os.walk(d):
            for f in fn:
                if f.lower().endswith('.lnk'):
                    found[f[:-4].lower()] = os.path.join(dp, f)
    return found


def find_app(name):
    n = str(name or '').strip().lower()
    n = _ALIASES.get(n, n)
    if n.lower().endswith(('.exe', ':')):
        return n
    menu = _start_menu()
    n = n.lower()
    if n in menu:
        return menu[n]
    starts = [k for k in menu if k.startswith(n)]
    if starts:
        return menu[min(starts, key=len)]
    words = n.split()
    has = [k for k in menu if all(w in k for w in words)]
    if has:
        return menu[min(has, key=len)]
    return None


@tool('open_app', 'Open an installed program by name (VS Code, Chrome, Spotify, Notepad...).', {'name': 'program name'}, 'low',
      preview=lambda a: f'Open {a.get("name")}')
def open_app(ctx, a):
    target = find_app(a.get('name'))
    if not target:
        raise ToolError(f'I could not find an app called "{a.get("name")}" in the Start Menu.')
    _startfile(target)
    return {'ok': True, 'text': f'Opened {a.get("name")}.'}


@tool('open_url', 'Open a web address in the default browser (http, https or mailto only).', {'url': 'address'}, 'low',
      preview=lambda a: f'Open {a.get("url")}')
def open_url(ctx, a):
    url = str(a.get('url') or '').strip()
    if not re.match(r'^(https?://|mailto:)', url, re.I):
        if re.match(r'^[\w.-]+\.[a-z]{2,}(/.*)?$', url, re.I):
            url = 'https://' + url
        else:
            raise ToolError('Only http, https and mailto links can be opened.')
    _startfile(url)
    return {'ok': True, 'text': f'Opened {url}.'}


def _open_path_risk(a):
    return 'danger' if os.path.splitext(str(a.get('path') or ''))[1].lower() in policy.EXEC_EXT else 'low'


@tool('open_path', 'Open a file or folder with its default program (folders open in Explorer).', {'path': 'file or folder'}, 'low',
      paths=lambda a: [(a.get('path'), False)], preview=lambda a: f'Open {a.get("path")}', risk_fn=_open_path_risk)
def open_path(ctx, a):
    real = _real(ctx, a.get('path'))
    if not os.path.exists(real):
        raise ToolError(f'{real} does not exist.')
    _startfile(real)
    return {'ok': True, 'text': f'Opened {real}.'}


@tool('set_volume', 'Set the speaker volume (0-100).', {'level': '0-100'}, 'low', preview=lambda a: f'Set volume to {a.get("level")}%')
def set_volume(ctx, a):
    level = max(0, min(100, int(a.get('level'))))
    _press_key(0xAE, 50)                 # everything down...
    _press_key(0xAF, round(level / 2))   # ...then up in 2% steps
    return {'ok': True, 'text': f'Volume set to about {level}%.'}


_MEDIA = {'play_pause': 0xB3, 'next': 0xB0, 'previous': 0xB1, 'stop': 0xB2, 'mute': 0xAD, 'volume_up': 0xAF, 'volume_down': 0xAE}


@tool('media_key', 'Press a media key: play_pause, next, previous, stop, mute, volume_up, volume_down.', {'action': 'which key'}, 'low',
      preview=lambda a: f'Media: {a.get("action")}')
def media_key(ctx, a):
    act = str(a.get('action') or '').lower()
    if act not in _MEDIA:
        raise ToolError(f'Unknown media key. Use one of: {", ".join(_MEDIA)}.')
    _press_key(_MEDIA[act])
    return {'ok': True, 'text': f'Pressed {act}.'}


@tool('lock_screen', 'Lock the computer.', {}, 'low', preview=lambda a: 'Lock the screen')
def lock_screen(ctx, a):
    _lock()
    return {'ok': True, 'text': 'Locked.'}


# ───────────────────────── change tools (approval) ─────────────────────────

@tool('make_folder', 'Create a folder.', {'path': 'new folder'}, 'change', paths=lambda a: [(a.get('path'), True)],
      preview=lambda a: f'Create folder {a.get("path")}')
def make_folder(ctx, a):
    real = _real(ctx, a.get('path'), True)
    if os.path.isdir(real):
        return {'ok': True, 'text': f'{real} already exists.'}
    os.makedirs(real)
    return {'ok': True, 'text': f'Created folder {real}.', 'undo': {'op': 'trash', 'path': real}}


@tool('create_file', 'Create a new text file (never overwrites; programs/scripts cannot be created).', {'path': 'new file', 'content': 'text'}, 'change',
      paths=lambda a: [(a.get('path'), True)], preview=lambda a: f'Create file {a.get("path")} ({len(str(a.get("content") or ""))} characters)')
def create_file(ctx, a):
    real = _real(ctx, a.get('path'), True)
    if os.path.splitext(real)[1].lower() in policy.BLOCKED_NEW_EXT:
        raise ToolError('Programs and scripts cannot be created this way.')
    content = str(a.get('content') or '')
    if len(content.encode('utf-8')) > MAX_WRITE:
        raise ToolError('That file would be too large (200 KB limit).')
    if os.path.exists(real):
        raise ToolError(f'{real} already exists; I never overwrite files.')
    os.makedirs(os.path.dirname(real), exist_ok=True)
    with open(real, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(content)
    return {'ok': True, 'text': f'Created {real}.', 'undo': {'op': 'trash', 'path': real}}


def _dest(ctx, src_real, dst):
    d = _real(ctx, dst, True)
    if os.path.isdir(d):
        d = os.path.join(d, os.path.basename(src_real))
    else:
        os.makedirs(os.path.dirname(d), exist_ok=True)
    return _unique(d)


@tool('move', 'Move a file or folder (into a folder, or to a new path). Never overwrites.', {'src': 'what to move', 'dst': 'destination folder or new path'},
      'change', paths=lambda a: [(a.get('src'), True), (a.get('dst'), True)], preview=lambda a: f'Move {a.get("src")}  ->  {a.get("dst")}')
def move(ctx, a):
    src = _real(ctx, a.get('src'), True)
    if not os.path.exists(src):
        raise ToolError(f'{src} does not exist.')
    if src in policy_roots(ctx):
        raise ToolError('That folder is one of the allowed roots and cannot be moved.')
    dst = _dest(ctx, src, a.get('dst'))
    shutil.move(src, dst)
    return {'ok': True, 'text': f'Moved to {dst}.', 'undo': {'op': 'move', 'from': dst, 'to': src}}


@tool('copy', 'Copy a file or folder. Never overwrites.', {'src': 'what to copy', 'dst': 'destination folder or new path'}, 'change',
      paths=lambda a: [(a.get('src'), False), (a.get('dst'), True)], preview=lambda a: f'Copy {a.get("src")}  ->  {a.get("dst")}')
def copy(ctx, a):
    src = _real(ctx, a.get('src'))
    if not os.path.exists(src):
        raise ToolError(f'{src} does not exist.')
    dst = _dest(ctx, src, a.get('dst'))
    shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
    return {'ok': True, 'text': f'Copied to {dst}.', 'undo': {'op': 'trash', 'path': dst}}


@tool('rename', 'Rename a file or folder (new name only, no path).', {'path': 'item', 'new_name': 'new name'}, 'change',
      paths=lambda a: [(a.get('path'), True)], preview=lambda a: f'Rename {a.get("path")}  ->  {a.get("new_name")}')
def rename(ctx, a):
    src = _real(ctx, a.get('path'), True)
    new = str(a.get('new_name') or '').strip()
    if not new or any(c in new for c in '\\/:*?"<>|'):
        raise ToolError('The new name must be a plain file name.')
    if not os.path.exists(src):
        raise ToolError(f'{src} does not exist.')
    if src in policy_roots(ctx):
        raise ToolError('That folder is one of the allowed roots and cannot be renamed.')
    dst = os.path.join(os.path.dirname(src), new)
    if os.path.exists(dst):
        raise ToolError(f'{dst} already exists.')
    os.rename(src, dst)
    return {'ok': True, 'text': f'Renamed to {new}.', 'undo': {'op': 'move', 'from': dst, 'to': src}}


# ───────────────────────── danger tools (always approval) ─────────────────────────

def policy_roots(ctx):
    roots = {policy.known_folder(n) for n in policy.KNOWN} | {policy.home()}
    return roots | set(policy.allowed_roots(ctx['owner']))


@tool('delete', 'Delete a file or folder. It goes to Adion\'s trash (not permanent) and can be undone for 30 days.', {'path': 'item'}, 'danger',
      paths=lambda a: [(a.get('path'), True)], preview=lambda a: f'DELETE {a.get("path")} (kept in Adion\'s trash)')
def delete(ctx, a):
    real = _real(ctx, a.get('path'), True)
    if not os.path.exists(real):
        raise ToolError(f'{real} does not exist.')
    if real in policy_roots(ctx):
        raise ToolError('That folder is one of the allowed roots and cannot be deleted.')
    n, _ = _count(real)
    if n > 2000:
        raise ToolError(f'That is {n}+ files; too many to delete in one step.')
    dest = _to_trash(real, ctx.get('task_id'), ctx.get('step', 0))
    return {'ok': True, 'text': f'Deleted {real} ({n} file(s)); kept in Adion\'s trash.', 'undo': {'op': 'restore', 'from': dest, 'to': real}}


COMMANDS = {
    'git_status': (['git', 'status', '--short', '--branch'], 60),
    'git_log': (['git', 'log', '--oneline', '-n', '15'], 60),
    'git_diff': (['git', 'diff', '--stat'], 60),
    'git_pull': (['git', 'pull', '--ff-only'], 120),
    'npm_install': (['npm', 'install'], 300),
    'npm_run': (['npm', 'run', '{arg}'], 300),
    'pip_install_requirements': ([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 300),
}


@tool('run_command', 'Run ONE of these fixed commands in a project folder: ' + ', '.join(COMMANDS) + '. (npm_run takes the script name in "arg".)',
      {'command': 'one of the names above', 'cwd': 'project folder', 'arg': 'script name for npm_run'}, 'danger',
      paths=lambda a: [(a.get('cwd'), True)], preview=lambda a: f'Run {a.get("command")}{" " + str(a.get("arg")) if a.get("arg") else ""} in {a.get("cwd")}')
def run_command(ctx, a):
    name = str(a.get('command') or '')
    if name not in COMMANDS:
        raise ToolError(f'Only these commands are allowed: {", ".join(COMMANDS)}.')
    cwd = _real(ctx, a.get('cwd'), True)
    if not os.path.isdir(cwd):
        raise ToolError(f'{cwd} is not a folder.')
    argv, timeout = list(COMMANDS[name][0]), COMMANDS[name][1]
    if '{arg}' in argv:
        arg = str(a.get('arg') or '')
        if not re.fullmatch(r'[A-Za-z0-9:_-]{1,40}', arg):
            raise ToolError('The script name may only contain letters, numbers, - _ and :.')
        argv[argv.index('{arg}')] = arg
    exe = shutil.which(argv[0]) or argv[0]
    argv[0] = exe
    env = {k: v for k, v in os.environ.items() if not re.search(r'KEY|TOKEN|SECRET|PASSWORD|MONGO', k, re.I)}
    try:
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, encoding='utf-8', errors='replace')
    except FileNotFoundError:
        raise ToolError(f'{argv[0]} is not installed or not on PATH.')
    except subprocess.TimeoutExpired:
        raise ToolError(f'It did not finish within {timeout} seconds.')
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    return {'ok': r.returncode == 0, 'text': f'exit code {r.returncode}\n' + out[-3000:]}


def catalog():
    """The tool list shown to the model."""
    lines = []
    for t in TOOLS.values():
        ps = ', '.join(f'{k} ({v})' for k, v in t['params'].items()) or 'no arguments'
        lines.append(f'- {t["name"]} [{t["risk"]}]: {t["desc"]} Arguments: {ps}')
    return '\n'.join(lines)
