"""Run every offline test (fake model, fake search, real headless browser, test database `devsquad_test`).
Spends no tokens and no search credits.   Usage:  python tests/run_all.py   (from the backend folder)"""
import glob, os, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
failed = []
for path in sorted(glob.glob(os.path.join(here, 'test_*.py'))):
    name = os.path.basename(path)
    print(f'\n=== {name} ===', flush=True)
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if not l.startswith('[OK]')]
    print('\n'.join(l for l in lines if l.startswith('FAIL') or 'passed' in l) or r.stdout[-800:] + r.stderr[-800:])
    if r.returncode:
        failed.append(name)
print('\nALL PASSED' if not failed else f'\nFAILED: {", ".join(failed)}')
sys.exit(1 if failed else 0)
