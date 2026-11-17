"""Offline tests: the planner's friendly overview (what you get, screens, stack, ideas) and per-step plain-language text."""
import os, sys, json
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
os.environ['ADION_LEARN'] = '0'      # learning has its own tests (test_learn.py); here it would consume the scripted model replies
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import llm, planner

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:300]}]' if extra and not cond else ''))

GOOD = {'type': 'build', 'project_name': 'Expense Tracker', 'summary': 'A tracker where you add expenses and see charts.',
        'overview': {'features': ['Add, edit and delete expenses', 'Import a CSV', '', 'See spending by category'], 'screens': ['Dashboard - totals and charts'],
                     'stack': [{'area': 'Frontend', 'choice': 'HTML + CSS + JS', 'why': 'No build step'}, {'area': '', 'choice': ''}, 'junk'],
                     'data': ['Expenses (date, amount, category)'], 'ideas': ['Add login so several people can use it'] + ['x'] * 10},
        'assumptions': ['Single user'], 'contract': {'stack': 'Flask'},
        'modules': [{'key': 'api', 'title': 'Build the API', 'plain': 'The part that saves your expenses.', 'description': 'Flask routes...', 'folder': 'backend', 'expects': ['app.py']},
                    {'key': 'ui', 'title': 'Build the pages', 'description': 'HTML pages...', 'folder': 'frontend', 'depends_on': ['api']},
                    {'key': 'charts', 'title': 'Build the charts', 'plain': 'Colourful charts.', 'description': 'Chart.js', 'folder': 'frontend/charts', 'depends_on': ['api']}]}
seen = []
def fake_post(url, **kw):
    seen.append(kw['json']); return {'choices': [{'message': {'content': json.dumps(GOOD)}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}
llm._post = fake_post
plan, ti, to = planner.make_plan({'model': 'deepseek-chat', 'key': 'sk-x', 'label': 'x'}, 'an expense tracker with charts')
ov = plan['overview']
check('P1: the plan carries a friendly overview', set(ov) == {'features', 'screens', 'stack', 'data', 'ideas'}, ov)
check('P2: empty and junk items are dropped', ov['features'] == ['Add, edit and delete expenses', 'Import a CSV', 'See spending by category'] and len(ov['stack']) == 1 and ov['stack'][0]['choice'] == 'HTML + CSS + JS', ov)
check('P3: ideas are capped at four', len(ov['ideas']) == 4)
check('P4: each step keeps its plain-language line (empty when the model gave none)', [m['plain'] for m in plan['modules']] == ['The part that saves your expenses.', '', 'Colourful charts.'], [m['plain'] for m in plan['modules']])
check('P5: the prompt asks for plain-language text, polish and ideas', all(w in seen[0]['messages'][0]['content'] for w in ('"overview"', '"plain"', 'senior product designer', 'empty states', '"ideas"')))
check('P6: dependencies and folders still work as before', plan['modules'][1]['depends_on'] == ['api'] and len({m['folder'] for m in plan['modules']}) == 3)
GOOD.pop('overview'); GOOD['modules'][0].pop('plain')
plan2, _, _ = planner.make_plan({'model': 'deepseek-chat', 'key': 'sk-x', 'label': 'x'}, 'an expense tracker with charts')
check('P7: a model that returns no overview still produces a valid plan (empty overview)', plan2['overview'] == {'features': [], 'screens': [], 'stack': [], 'data': [], 'ideas': []} and plan2['modules'][0]['plain'] == '')
print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
sys.exit(1 if FAIL else 0)
