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


_skip = re.compile(r"^(?:hi|hello|hey|thanks|thank you|ok|okay|yes|no|yep|cool|great|nice|bye|good (?:morning|evening|night))\b[\s!.?]*$", re.I)
_task = re.compile(r"^(?:please |can you |could you )?(?:explain|define|write|translate|summari[sz]e|rewrite|rephrase|correct|fix|calculate|solve|"
                   r"brainstorm|draft|give me (?:an? )?(?:example|idea))\b", re.I)
_lookup = re.compile(r"\b(?:who|whom|whose|what|which|when|where|how is|how are|how was|how did|tell me about|information|info|details|news|"
                     r"search|look ?up|google|browse|find out|research|go read|read about|real information|profile|"
                     r"how (?:old|many|much|long|tall|far|big|rich)|born|died|age|biography|career|married|net worth)\b", re.I)


def should_search(text, always=False):
    """Look the answer up on the web? Yes for factual questions and explicit requests, no for greetings and writing tasks.
    (Costs one Tavily search; the free plan covers about 1,000 a month.)"""
    g = (text or '').strip()
    if always:
        return True
    if not g or _skip.match(g) or _task.match(g):
        return False
    if needs_search(g):
        return True
    return len(g.split()) >= 2 and bool(_lookup.search(g))


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


def _record(ctx, cost=None, model=None):
    """One ledger row per search so the Usage tab can count them."""
    cost = PRICE_PER_SEARCH if cost is None else cost
    try:
        from models import UsageDocument, RunDocument
        ctx = ctx or {}
        UsageDocument(owner=ctx.get('owner', ''), run_id=ctx.get('run_id', ''), purpose='search', model=model or PROVIDER,
                      cost_usd=cost).save()
        if ctx.get('run_id') and cost:
            RunDocument.objects(run_id=ctx['run_id']).update_one(inc__cost_usd=cost)
    except Exception:  # noqa: BLE001
        pass


# Tavily is for DeepSeek. When Claude is answering it searches with its own built-in web search instead, so no Tavily key is needed.
CLAUDE_PRICE_PER_SEARCH = float(os.getenv('CLAUDE_PRICE_PER_SEARCH', '0.01'))     # $10 per 1,000 searches


def uses_claude(spec):
    return (spec or {}).get('provider') == 'anthropic'


def available(spec, tavily_key):
    """Can this model search the web right now?"""
    return bool((spec or {}).get('key')) if uses_claude(spec) else bool(tavily_key)


def search_for(spec, query, tavily_key, ctx=None):
    """Search with whatever fits the model that is answering: Claude's own search for Claude, Tavily for DeepSeek."""
    if not uses_claude(spec):
        return search(query, tavily_key, ctx)
    from orchestrator import claude_llm, llm
    try:
        res, n = claude_llm.web_search(spec, query, ctx)
    except llm.LLMError as e:
        raise SearchError(str(e))
    _record(ctx, cost=CLAUDE_PRICE_PER_SEARCH * max(1, n), model='claude-web-search')
    return res


def format_sources(results):
    """Compact block for the model prompt."""
    return '\n'.join(f'[{i}] {r["title"]} ({r["url"]})\n{r["content"]}' for i, r in enumerate(results, 1))


def source_links(results):
    """The links to show the user (a search summary is not a page, so it is left out)."""
    return [{'title': r['title'], 'url': r['url']} for r in results if not r.get('summary')]
