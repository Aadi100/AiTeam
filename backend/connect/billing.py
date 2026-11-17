"""
Billing for connected apps. You (the owner) pay DeepSeek; every model call is written to the usage ledger with the client, app and
end user. A client is charged  your cost x markup  and can be capped per month.
"""

from datetime import datetime, timedelta

from models import UsageDocument
from .models import ConnectConfig, Client, ConnectApp


def config():
    c = ConnectConfig.objects(key='main').first()
    return c or ConnectConfig(key='main').save()


def price(cost):
    return round(cost * config().markup, 6)


def month_start():
    n = datetime.utcnow()
    return datetime(n.year, n.month, 1)


def _sum(**match):
    col = UsageDocument._get_collection()
    r = next(iter(col.aggregate([{'$match': match}, {'$group': {'_id': None, 'cost': {'$sum': '$cost_usd'}, 'in': {'$sum': '$tokens_in'},
                                                                'out': {'$sum': '$tokens_out'}, 'n': {'$sum': 1}}}])), {})
    return {'cost': r.get('cost', 0.0), 'tokens': r.get('in', 0) + r.get('out', 0), 'calls': r.get('n', 0)}


def month_spend(client_id='', app_id=''):
    """What the CLIENT owes this month for this client/app (our cost x markup)."""
    m = {'created_at': {'$gte': month_start()}}
    if app_id:
        m['app_id'] = app_id
    elif client_id:
        m['client_id'] = client_id
    return round(price(_sum(**m)['cost']), 6)


def caps(app):
    cfg = config()
    client = Client.objects(client_id=app.client_id).first()
    return {'app': app.monthly_cap_usd or 0.0, 'client': (client.cap_usd if client and client.cap_usd else cfg.default_cap_usd)}


def blocked(app):
    """A reason the assistant must not answer right now, or ''."""
    client = Client.objects(client_id=app.client_id).first()
    if not client or client.status != 'active':
        return 'This account is not active.'
    if not app.enabled:
        return 'This assistant is switched off.'
    c = caps(app)
    if c['app'] and month_spend(app_id=app.app_id) >= c['app']:
        return 'This assistant reached its monthly limit.'
    if c['client'] and month_spend(client_id=app.client_id) >= c['client']:
        return 'This account reached its monthly limit.'
    return ''


def summary(client_id, app_id='', days=30):
    since = datetime.utcnow() - timedelta(days=days)
    match = {'created_at': {'$gte': since}}
    match['app_id' if app_id else 'client_id'] = app_id or client_id
    col = UsageDocument._get_collection()
    tot = _sum(**match)
    by_day = [{'day': r['_id'], 'cost': round(price(r['c']), 6), 'tokens': r['t'], 'calls': r['n']} for r in col.aggregate([
        {'$match': match}, {'$group': {'_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                                       'c': {'$sum': '$cost_usd'}, 't': {'$sum': {'$add': ['$tokens_in', '$tokens_out']}}, 'n': {'$sum': 1}}},
        {'$sort': {'_id': 1}}])]
    by_app = []
    if not app_id:
        names = {a.app_id: a.name for a in ConnectApp.objects(client_id=client_id)}
        for r in col.aggregate([{'$match': match}, {'$group': {'_id': '$app_id', 'c': {'$sum': '$cost_usd'}, 'n': {'$sum': 1}}}, {'$sort': {'c': -1}}]):
            by_app.append({'appId': r['_id'], 'name': names.get(r['_id'], r['_id']), 'cost': round(price(r['c']), 6), 'calls': r['n']})
    cfg = config()
    return {'days': days, 'cost': round(price(tot['cost']), 6), 'tokens': tot['tokens'], 'calls': tot['calls'], 'byDay': by_day, 'byApp': by_app,
            'monthSpend': month_spend(client_id=client_id) if not app_id else month_spend(app_id=app_id), 'freeCredit': cfg.free_credit_usd,
            'defaultCap': cfg.default_cap_usd}
