"""
Router + token forecaster.

classify(goal) decides, with plain code (zero tokens), how much machinery a request needs:
    chat   -> a question or conversation: one short call, no planner, no agents
    small  -> a small, self-contained build: ONE agent, no planner / critic / review
    large  -> a real project: planner, parallel agents, review
    auto   -> unclear: the planner itself decides (it can still answer or ask questions)

forecast(...) predicts tokens and cost BEFORE spending them, using the same pricing as the ledger.
"""

import re
from .llm import count_tokens, cost_usd
from .search import needs_search

BUILD_VERBS = r'build|create|make|generate|develop|code|program|implement|scaffold|set\s*up|design|write\s+(?:me\s+)?(?:an?|the)\s+\w*\s*(?:app|script|site|page|tool|api|bot|program|game|function|component)|add\s+(?:a|an|the)|fix|refactor|convert|port\s+to|clone'
BUILD_NOUNS = r'app|application|website|web\s*site|site|page|landing|dashboard|api|backend|frontend|script|tool|bot|game|crm|extension|plugin|cli|calculator|tracker|portfolio|blog|store|shop|platform|system|service|component|widget|form|database|schema|server'
QUESTION_START = r'who|whom|whose|what|when|where|why|how|which|is|are|was|were|do|does|did|can|could|should|would|will|explain|tell\s+me|define|describe|summari[sz]e|compare|list|give\s+me|translate|meaning\s+of|difference\s+between'
BIG_WORDS = r'crm|erp|dashboard|platform|marketplace|multi|full[- ]?stack|complete|admin|auth|login|database|real[- ]?time|analytics|e-?commerce|authentication|payments?|microservice|saas|management\s+system'
SMALL_WORDS = r'simple|basic|small|tiny|quick|single|one[- ]page|landing\s+page|calculator|to-?do|counter|timer|clock|stopwatch|script|snippet|function|hello'

_build = re.compile(rf'\b(?:{BUILD_VERBS})\b', re.I)
_noun = re.compile(rf'\b(?:{BUILD_NOUNS})\b', re.I)
_question = re.compile(rf'^\s*(?:hey|hi|hello|ok|so|please|adion)?[\s,.!]*(?:{QUESTION_START})\b', re.I)
_big = re.compile(rf'\b(?:{BIG_WORDS})\b', re.I)
_small = re.compile(rf'\b(?:{SMALL_WORDS})\b', re.I)


_polite = re.compile(r'^\s*(?:(?:hey|hi|hello|ok|okay|so|please|adion|kindly)[\s,.!]*)*(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|i\s+(?:want|need)\s+you\s+to\s+|i(?:.d|\s+would)\s+like\s+you\s+to\s+)?', re.I)
_starts_build = re.compile(rf'^(?:{BUILD_VERBS})', re.I)


_pc_place = re.compile(r"\b(?:my|the|this)\s+(?:desktop|downloads?|documents?|pictures?|photos|music|videos|pc|computer|laptop|files?|folders?|screen|speakers?|volume|battery|disk|drive)\b|\bon (?:the )?desktop\b|\b[a-z]:[\\/]", re.I)
_pc_verb = re.compile(r"\b(?:open|launch|find|search|look for|list|show|move|copy|rename|delete|remove|trash|organi[sz]e|tidy|clean|sort|read|summari[sz]e|lock|mute|unmute|check|play|pause|skip|put|create|make|save)\b", re.I)
_pc_start = re.compile(r"^(?:hey |ok |please |adion[, ]*)*(?:open|launch|lock|mute|unmute|pause|play|skip|turn (?:up|down)|set (?:the )?volume|search my|find my|list my|show my|move my|delete my|rename my|tidy|organi[sz]e my|clean up my)\b", re.I)
_pc_system = re.compile(r"\b(?:how much (?:disk|space|memory|ram|battery)|what(?:'s| is) (?:running|my battery|my cpu)|system (?:info|status)|git status)\b", re.I)
_question_about_code = re.compile(r"^(?:how (?:do|can|to|would)|why|what is|explain)\b", re.I)


def is_pc_request(goal):
    """Plain-code check: does this ask Adion to do something on the user's PC (files, apps, volume...)?"""
    g = (goal or '').strip()
    if _question_about_code.match(g) and not _pc_place.search(g):
        return False
    if _pc_system.search(g):
        return True
    if re.match(r'^(?:hey |ok |please |adion[, ]*)*open (?:a|an) (?:new )?(?:ticket|account|issue|pr|pull request|case|bug)\b', g, re.I):
        return False
    if re.match(r"^(?:hey |ok |please |adion[, ]*)*(?:what(?:'s| is| are)|which|show|list|tell me|how many)\b", g, re.I) and re.search(
            r'\b(?:in|on|inside|from)\s+(?:my|the)\s+(?:desktop|downloads?|documents?|pictures?|music|videos|pc|computer|laptop)\b', g, re.I):
        return True
    if _pc_place.search(g) and re.search(r'\b(?:files?|folders?|apps?|programs?|space|storage|running|installed)\b', g, re.I) \
            and not (_build.search(g) and _noun.search(g)):
        return True
    if _pc_start.match(g) and not (_build.search(g) and _noun.search(g)):
        return True
    return bool(_pc_place.search(g) and _pc_verb.search(g) and not (_build.search(g) and _noun.search(g)))


def classify(goal):
    g = (goal or '').strip()
    if is_pc_request(g):
        return 'pc'
    words = len(g.split())
    core = g[_polite.match(g).end():] if _polite.match(g) else g
    wants_build = bool(_build.search(g)) and bool(_noun.search(g))
    # a question word up front ("how do I build a website") is a question, even if it mentions building
    if _question.match(core) and not _starts_build.match(core):
        return 'chat'
    if not wants_build:
        return 'chat' if (g.endswith('?') or words <= 3) else 'auto'
    if _big.search(g) or words > 40:
        return 'large'
    if _small.search(g) and words <= 30:
        return 'small'
    return 'auto' if words > 12 else 'small'


def is_hard(goal):
    """Big, multi-part goals are worth the slower reasoner model for planning; everything else is not."""
    g = goal or ''
    words = len(g.split())
    bigs = {m.group(0).lower() for m in _big.finditer(g)}
    return words >= 25 or len(bigs) >= 4


# ── forecast ─────────────────────────────────────────────────────────────────
SYS_PLANNER, SYS_WORKER = 900, 350        # prompt sizes of the fixed system prompts (tokens)
OUT_PLAN, OUT_AGENT, OUT_REVIEW = 1800, 2400, 800
RETRY_FACTOR = 1.25                        # some passes need a self-correction round


def _row(tin, hit_share, tout):
    hit = round(tin * hit_share)
    return {'in': tin, 'out': tout, 'hit': hit, 'cost': cost_usd(hit, tin - hit, tout)}


def forecast(goal, kind=None, module_descs=None, contract_text=None, verify=False, web_search=False):
    """Returns {kind, modules, tokens, low, high, cost, costLow, costHigh, parts:[{name,tokens,cost}]}."""
    kind = kind or classify(goal)
    g = count_tokens(goal)
    parts = []
    if kind == 'chat':
        web = needs_search(goal) or web_search
        parts.append(('Answer + web sources' if web else 'Answer', _row(120 + g + (480 if web else 0), 0.0, 350)))
        n = 0
    elif kind == 'pc':
        n = 0
        parts.append(('PC control', _row(2 * (SYS_PLANNER + g), 0.0, 400)))
    elif kind == 'small':
        n = 1
        parts.append(('Agent', _row(SYS_WORKER + 160 + g, 0.0, int(OUT_AGENT * RETRY_FACTOR))))
    else:
        if module_descs is not None:
            n = len(module_descs)
            contract = count_tokens(contract_text or '')
            descs = [count_tokens(d) + 40 for d in module_descs]
        else:
            n = 2 if kind == 'edit' else min(10, max(4, 3 + len((goal or '').split()) // 12))
            contract = 900
            descs = [260] * n
            parts.append(('Planner', _row(SYS_PLANNER + g, 0.0, OUT_PLAN)))
        if module_descs is not None:
            parts.append(('Planner (done)', _row(0, 0.0, 0)))
        shared = SYS_WORKER + contract + g
        agents_in = sum(shared + d + 150 for d in descs)
        # every agent after the first re-sends the same prefix, which DeepSeek serves from cache
        hit_share = 0 if n <= 1 else (shared * (n - 1)) / max(1, agents_in)
        parts.append((f'{n} agents', _row(agents_in, hit_share, int(OUT_AGENT * n * RETRY_FACTOR))))
        if n >= 5:
            parts.append(('Critic', _row(contract + n * 120 + 300, 0.0, 250)))
        parts.append(('Review', _row(contract + n * 90 + 400, 0.5, OUT_REVIEW)))
        if verify:
            parts.append(('Run & fix', _row(2500, 0.0, 1200)))
    out = [{'name': k, 'tokens': v['in'] + v['out'], 'cost': round(v['cost'], 5)} for k, v in parts if v['in'] + v['out']]
    tokens = sum(p['tokens'] for p in out)
    cost = sum(p['cost'] for p in out)
    return {'kind': kind, 'modules': n, 'tokens': tokens, 'low': int(tokens * 0.7), 'high': int(tokens * 1.7),
            'cost': round(cost, 5), 'costLow': round(cost * 0.7, 5), 'costHigh': round(cost * 1.7, 5), 'parts': out}
