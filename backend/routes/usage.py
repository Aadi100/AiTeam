"""
Token calculator.

GET  /api/usage?days=30      what was spent: totals, per day, per purpose, per run, cache savings
POST /api/usage/estimate     {goal, verify} -> forecast of tokens and USD before running anything
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from models import UsageDocument, RunDocument
from orchestrator import router, llm
from auth import current_user, is_admin

usage_bp = Blueprint('usage', __name__)


def _scope():
    # members see their own spend; admins see everything on this server
    return {} if is_admin() else {'owner': current_user()['u']}


@usage_bp.route('/usage', methods=['GET'])
def usage():
    days = max(1, min(365, request.args.get('days', 30, type=int)))
    since = datetime.utcnow() - timedelta(days=days)
    match = {'created_at': {'$gte': since}, **_scope()}
    col = UsageDocument._get_collection()

    tot = next(iter(col.aggregate([{'$match': match}, {'$group': {
        '_id': None, 'calls': {'$sum': 1}, 'in': {'$sum': '$tokens_in'}, 'hit': {'$sum': '$cache_hit'},
        'out': {'$sum': '$tokens_out'}, 'cost': {'$sum': '$cost_usd'}, 'saved': {'$sum': '$saved_usd'}}}])), {})
    by_day = [{'day': r['_id'], 'tokens': r['t'], 'cost': round(r['c'], 5), 'calls': r['n']} for r in col.aggregate([
        {'$match': match},
        {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                    't': {'$sum': {'$add': ['$tokens_in', '$tokens_out']}}, 'c': {'$sum': '$cost_usd'}, 'n': {'$sum': 1}}},
        {'$sort': {'_id': 1}}])]
    by_purpose = [{'purpose': r['_id'], 'tokens': r['t'], 'cost': round(r['c'], 5), 'calls': r['n']} for r in col.aggregate([
        {'$match': match},
        {'$group': {'_id': '$purpose', 't': {'$sum': {'$add': ['$tokens_in', '$tokens_out']}},
                    'c': {'$sum': '$cost_usd'}, 'n': {'$sum': 1}}},
        {'$sort': {'c': -1}}])]
    run_rows = list(col.aggregate([
        {'$match': {**match, 'run_id': {'$ne': ''}}},
        {'$group': {'_id': '$run_id', 't': {'$sum': {'$add': ['$tokens_in', '$tokens_out']}}, 'c': {'$sum': '$cost_usd'},
                    'last': {'$max': '$created_at'}}},
        {'$sort': {'last': -1}}, {'$limit': 15}]))
    goals = {r.run_id: (r.goal, r.status, r.estimate_tokens) for r in RunDocument.objects(run_id__in=[x['_id'] for x in run_rows])}
    runs = [{'id': r['_id'], 'goal': goals.get(r['_id'], ('', '', 0))[0][:80], 'status': goals.get(r['_id'], ('', '', 0))[1],
             'tokens': r['t'], 'cost': round(r['c'], 5), 'estimate': goals.get(r['_id'], ('', '', 0))[2]} for r in run_rows]

    tin = tot.get('in', 0)
    return jsonify({
        'days': days,
        'calls': tot.get('calls', 0), 'tokensIn': tin, 'tokensOut': tot.get('out', 0),
        'tokens': tin + tot.get('out', 0), 'cacheHit': tot.get('hit', 0),
        'cacheRate': round(tot.get('hit', 0) / tin, 3) if tin else 0,
        'cost': round(tot.get('cost', 0), 5), 'saved': round(tot.get('saved', 0), 5),
        'byDay': by_day, 'byPurpose': by_purpose, 'runs': runs,
        'prices': {'hit': llm.PRICE_HIT, 'miss': llm.PRICE_MISS, 'out': llm.PRICE_OUT},
    })


@usage_bp.route('/usage/estimate', methods=['POST'])
def estimate():
    b = request.get_json(silent=True) or {}
    goal = (b.get('goal') or '').strip()
    if not goal:
        return jsonify({'error': 'goal is required'}), 400
    extra = 0
    try:
        from orchestrator import files, llm
        extra = sum(llm.count_tokens(files.prompt_block([u]))
                    for u in files.get_many(b.get('attachments'), current_user()['u']))
    except Exception:  # noqa: BLE001 - a forecast must never fail
        extra = 0
    return jsonify(router.forecast(goal, verify=bool(b.get('verify')), web_search=bool(b.get('webSearch')), extra_tokens=extra))
