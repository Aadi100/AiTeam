"""
File-safety layer. Every agent writes only inside its own folder under the run root.
Agents never choose shell commands; we run fixed, read-only syntax checks ourselves.
"""

import os
import re
import json
import shutil
import subprocess
import sys

MAX_FILE_BYTES = 400_000
MAX_FILES_PER_TASK = 40
BLOCKED_EXT = {'.exe', '.dll', '.bat', '.cmd', '.ps1', '.scr', '.msi', '.com', '.vbs', '.lnk'}

LANG = {'html': 'html', 'css': 'css', 'js': 'javascript', 'mjs': 'javascript', 'ts': 'typescript',
        'jsx': 'jsx', 'tsx': 'tsx', 'py': 'python', 'json': 'json', 'md': 'markdown',
        'txt': 'text', 'yml': 'yaml', 'yaml': 'yaml', 'sh': 'bash', 'sql': 'sql', 'svg': 'svg'}


class SandboxError(Exception):
    pass


def slug(text, default='module'):
    s = re.sub(r'[^a-zA-Z0-9_\-/]+', '-', (text or '').strip().lower()).strip('-/')
    s = re.sub(r'/{2,}', '/', s)
    return s or default


def expand_root(path):
    return os.path.abspath(os.path.expanduser(path))


def safe_join(root, *parts):
    """Join and verify the result stays inside root (blocks .., absolute paths, symlink escapes)."""
    root_real = os.path.realpath(root)
    rel = os.path.join(*[p for p in parts if p])
    if os.path.isabs(rel) or re.match(r'^[a-zA-Z]:', rel):
        raise SandboxError(f'absolute path not allowed: {rel}')
    target = os.path.realpath(os.path.join(root_real, rel))
    if os.path.commonpath([root_real, target]) != root_real:
        raise SandboxError(f'path escapes sandbox: {rel}')
    return target


def write_files(root, folder, files):
    """Write [{path, content}] under root/folder. Returns list of file records."""
    if len(files) > MAX_FILES_PER_TASK:
        raise SandboxError(f'too many files ({len(files)} > {MAX_FILES_PER_TASK})')
    written = []
    for f in files:
        rel = (f.get('path') or '').replace('\\', '/').strip().lstrip('/')
        content = f.get('content', '')
        if not rel or not isinstance(content, str):
            continue
        if os.path.splitext(rel)[1].lower() in BLOCKED_EXT:
            raise SandboxError(f'blocked file type: {rel}')
        if len(content.encode('utf-8')) > MAX_FILE_BYTES:
            raise SandboxError(f'file too large: {rel}')
        abs_path = safe_join(root, folder, rel)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8', newline='\n') as fp:
            fp.write(content)
        ext = rel.rsplit('.', 1)[-1].lower() if '.' in rel else 'text'
        written.append({'path': '/'.join(p for p in (folder, rel) if p), 'size': len(content.encode('utf-8')),
                        'language': LANG.get(ext, ext)})
    return written


def check_file(root, rel_path):
    """Return an error string for a syntactically broken file, else ''."""
    abs_path = safe_join(root, rel_path)
    ext = os.path.splitext(rel_path)[1].lower()
    try:
        if ext == '.py':
            r = subprocess.run([sys.executable, '-B', '-c',
                                'import sys;compile(open(sys.argv[1],encoding="utf-8").read(),sys.argv[1],"exec")',
                                abs_path], capture_output=True, text=True, timeout=30)
            return r.stderr.strip()[:600] if r.returncode else ''
        if ext in ('.js', '.mjs') and shutil.which('node'):
            r = subprocess.run(['node', '--check', abs_path], capture_output=True, text=True, timeout=30)
            return r.stderr.strip()[:600] if r.returncode else ''
        if ext == '.json':
            with open(abs_path, encoding='utf-8') as fp:
                json.load(fp)
    except json.JSONDecodeError as e:
        return f'invalid JSON: {e}'
    except subprocess.TimeoutExpired:
        return 'syntax check timed out'
    return ''


def tree(root, folder='', limit=200):
    """List files under root/folder as relative paths."""
    base = safe_join(root, folder) if folder else os.path.realpath(root)
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in ('node_modules', '.git', '__pycache__', 'venv')]
        for n in fn:
            out.append(os.path.relpath(os.path.join(dp, n), os.path.realpath(root)).replace('\\', '/'))
            if len(out) >= limit:
                return out
    return sorted(out)
