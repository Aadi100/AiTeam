"""
Integration verification and "run the result" suggestions.

detect_commands(root) finds how to start the generated project (Flask/Python entry, Node, or static HTML).
smoke_test(root)      actually starts it on a free port and requests "/" (opt-in: executes generated code).
"""

import os
import re
import sys
import time
import socket
import subprocess
import urllib.request
import urllib.error

from . import sandbox

PY_ENTRIES = ('app.py', 'main.py', 'server.py', 'run.py', 'wsgi.py')


def _free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _find(root, names):
    hits = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ('node_modules', '.git', '__pycache__', 'venv', '.venv')]
        for n in fn:
            if n in names:
                hits.append(os.path.join(dp, n))
    return sorted(hits, key=lambda p: (p.count(os.sep), p))


def detect_commands(root):
    """Return [{title, command, cwd}] — best guesses for starting the project."""
    out = []
    for path in _find(root, PY_ENTRIES)[:2]:
        d = os.path.dirname(path)
        name = os.path.basename(path)
        has_req = os.path.exists(os.path.join(d, 'requirements.txt')) or os.path.exists(os.path.join(root, 'requirements.txt'))
        req = os.path.join(d, 'requirements.txt') if os.path.exists(os.path.join(d, 'requirements.txt')) else os.path.join(root, 'requirements.txt')
        cmd = (f'python -m pip install -r "{req}" && ' if has_req else '') + f'python {name}'
        out.append({'title': f'Run {os.path.relpath(d, root) if d != root else "project"} ({name})', 'command': cmd, 'cwd': d})
    for path in _find(root, ('package.json',))[:2]:
        d = os.path.dirname(path)
        try:
            import json
            scripts = json.load(open(path, encoding='utf-8')).get('scripts', {})
        except Exception:  # noqa: BLE001
            scripts = {}
        for s in ('dev', 'start'):
            if s in scripts:
                out.append({'title': f'npm run {s} ({os.path.relpath(d, root) if d != root else "project"})',
                            'command': f'npm install && npm run {s}', 'cwd': d})
                break
    if not out:
        for path in _find(root, ('index.html',))[:1]:
            d = os.path.dirname(path)
            out.append({'title': 'Serve static site on :8080', 'command': f'"{sys.executable}" -m http.server 8080', 'cwd': d})
    return out


def _wait_port(port, proc, timeout=12):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def smoke_test(root):
    """
    Start the project's Python entry (PORT/FLASK_RUN_PORT set) and GET /.
    Returns (ok: bool, report: str). Report holds the error text for an LLM to fix.
    """
    entries = _find(root, PY_ENTRIES)
    if not entries:
        return True, 'No Python entry point found; nothing to execute.'
    path = entries[0]
    d, name = os.path.dirname(path), os.path.basename(path)
    # make Flask apps that hard-code a port still bind to ours: pass PORT and patch via env where possible
    port = _free_port()
    # never hand the server's secrets (API keys, passwords, tokens) to generated code
    safe = {k: v for k, v in os.environ.items() if not re.search(r'KEY|TOKEN|SECRET|PASSWORD|MONGO', k, re.I)}
    env = {**safe, 'PORT': str(port), 'FLASK_RUN_PORT': str(port), 'PYTHONUNBUFFERED': '1', 'FLASK_DEBUG': '0'}
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    proc = subprocess.Popen([sys.executable, '-B', '-c',
                             _RUNNER, name, str(port)], cwd=d, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=flags)
    try:
        if not _wait_port(port, proc):
            out = ''
            if proc.poll() is not None:
                out = (proc.stdout.read() or '')[-1800:]
            return False, f'`python {name}` (in {os.path.relpath(d, root)}) did not start listening.\n{out}'
        try:
            r = urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=8)
            return True, f'GET / -> HTTP {r.status}'
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                return False, f'GET / -> HTTP {e.code} from {name}'
            return False, f'GET / -> HTTP {e.code} (the app starts but has no working root page; users expect the app at /)'
        except Exception as e:  # noqa: BLE001
            return False, f'GET / failed: {e}'
    finally:
        if sys.platform == 'win32':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)], capture_output=True)
        else:
            proc.kill()


# Runs the entry file as __main__, but forces any app.run(...) call to our port and disables the reloader.
_RUNNER = r'''
import sys, runpy
name, port = sys.argv[1], int(sys.argv[2])
try:
    import flask
    _orig = flask.Flask.run
    def _run(self, *a, **k):
        return _orig(self, host="127.0.0.1", port=port, debug=False, use_reloader=False)
    flask.Flask.run = _run
except ImportError:
    pass
runpy.run_path(name, run_name="__main__")
'''


def project_files_for_fix(root, report, limit_chars=14000):
    """Collect likely-relevant source files (entry files first) to show the fixer."""
    paths = _find(root, PY_ENTRIES) + _find(root, ('index.html',))
    seen, parts, total = set(), [], 0
    for p in paths:
        rel = os.path.relpath(p, root).replace('\\', '/')
        if rel in seen:
            continue
        seen.add(rel)
        try:
            text = open(p, encoding='utf-8').read()
        except OSError:
            continue
        chunk = f'--- {rel}\n{text}\n'
        if total + len(chunk) > limit_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return '\n'.join(parts), sorted(seen)


def verify_tree(root):
    """All files present (for the fixer to know what exists)."""
    return sandbox.tree(root)
