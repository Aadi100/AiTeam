"""
Web search for Adion. Provider-independent: callers use search(), the provider is chosen by SEARCH_PROVIDER
(default "tavily"). Adding Serper / Exa / Brave later means adding one function to PROVIDERS.

search(query, key) -> {"results": [{"title", "url", "content"}]}   (content is trimmed to save tokens)
needs_search(text)  -> True when the question is about something recent or changing.
"""

import os
import re
import requests

PROVIDER = os.getenv('SEARCH_PROVIDER', 'tavily').lower()
PRICE_PER_SEARCH = float(os.getenv('TAVILY_PRICE_PER_SEARCH', '0'))   # 0 = free plan; ~0.008 on pay-as-you-go
MAX_RESULTS = 4
SNIPPET_CHARS = 420          # ~100 tokens per result keeps the answer prompt small


class SearchError(Exception):
    pass


_recent = re.compile(
    r'\b(latest|current(?:ly)?|today|tonight|tomorrow|yesterday|right now|nowadays|news|recent(?:ly)?|this (?:week|month|year|season)|'
    r'breaking|trending|just (?:released|announced|launched)|new(?:est)? (?:version|release|model)|release date|'
    r'price of|stock|share price|weather|forecast|score|standings|schedule|exchange rate|net worth|'
    r'who (?:is|are) the (?:current |new )?(?:ceo|president|prime minister|owner|leader|head|champion)|'
    r'how much (?:is|does|are)|202[5-9])\b', re.I)


def needs_search(text):
    return bool(_recent.search(text or ''))


def _tavily(query, key):
    try:
        r = requests.post('https://api.tavily.com/search', timeout=25,
                          headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                          json={'query': query[:380], 'search_depth': 'basic', 'max_results': MAX_RESULTS,
                                'include_answer': False, 'include_raw_content': False})
    except requests.exceptions.RequestException as e:
        raise SearchError(f'network error: {e}')
    if r.status_code in (401, 403):
        raise SearchError('Tavily rejected the API key. Check it in Models & keys.')
    if r.status_code == 429 or r.status_code == 432 or r.status_code == 433:
        raise SearchError('Tavily usage limit reached for this plan.')
    if r.status_code >= 400:
        raise SearchError(f'Tavily HTTP {r.status_code}: {r.text[:160]}')
    out = []
    for item in (r.json().get('results') or [])[:MAX_RESULTS]:
        content = re.sub(r'\s+', ' ', item.get('content') or '').strip()
        if item.get('url') and content:
            out.append({'title': (item.get('title') or item['url'])[:120], 'url': item['url'], 'content': content[:SNIPPET_CHARS]})
    return {'results': out}


PROVIDERS = {'tavily': _tavily}


def search(query, key, ctx=None):
    if not key:
        raise SearchError('No Tavily API key')
    fn = PROVIDERS.get(PROVIDER)
    if not fn:
        raise SearchError(f'unknown search provider {PROVIDER}')
    res = fn(query, key)
    _record(ctx)
    return res


def _record(ctx):
    """One ledger row per search so the Usage tab can count them."""
    try:
        from models import UsageDocument, RunDocument
        ctx = ctx or {}
        UsageDocument(owner=ctx.get('owner', ''), run_id=ctx.get('run_id', ''), purpose='search', model=PROVIDER,
                      cost_usd=PRICE_PER_SEARCH).save()
        if ctx.get('run_id') and PRICE_PER_SEARCH:
            RunDocument.objects(run_id=ctx['run_id']).update_one(inc__cost_usd=PRICE_PER_SEARCH)
    except Exception:  # noqa: BLE001
        pass


def format_sources(results):
    """Compact block for the model prompt."""
    return '\n'.join(f'[{i}] {r["title"]} ({r["url"]})\n{r["content"]}' for i, r in enumerate(results, 1))
