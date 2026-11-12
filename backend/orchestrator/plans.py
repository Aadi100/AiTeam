"""
Plan memory: remember plans that led to finished, error-free builds and offer the closest one as an example
the next time a similar goal comes in. Matching is plain keyword overlap (no model call, no tokens).
"""

import re
from models import PlanMemoryDocument

STOP = set("""a an the and or of to for in on with that this it is are be as at by from into your my me i we you our
build create make generate develop write app application website web site page simple small basic new using use want need
please can could would should some any all just very also like have has get set add""".split())
MIN_SCORE = 0.3
KEEP_PER_OWNER = 100


def _words(text):
    return {w for w in re.findall(r'[a-z0-9]+', (text or '').lower()) if len(w) > 2 and w not in STOP}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def save(run, tasks):
    """Call after a build finished cleanly. Stores (or refreshes) the plan that actually worked."""
    mods = [t for t in tasks if t.kind == 'module' and not t.replaced and not t.parent_id]
    if run.mode != 'build' or len(mods) < 2 or run.error or run.revisions > 1 or any(t.status != 'done' for t in mods):
        return None
    title_of = {t.task_id: t.title for t in mods}
    words = sorted(_words(run.goal) | _words(run.project_name))[:40]
    doc_modules = [{'title': t.title, 'folder': t.folder, 'description': t.description[:220], 'expects': t.expects,
                    'depends': [title_of[d] for d in t.depends_on if d in title_of]} for t in mods]
    for old in PlanMemoryDocument.objects(owner=run.owner):          # the same kind of project: refresh, don't pile up
        if _jaccard(set(old.words), set(words)) >= 0.6:
            old.update(set__goal=run.goal, set__project_name=run.project_name, set__summary=run.summary,
                       set__contract=run.contract[:2500], set__modules=doc_modules, set__words=words)
            return old
    doc = PlanMemoryDocument(owner=run.owner, goal=run.goal, project_name=run.project_name, summary=run.summary,
                             contract=run.contract[:2500], modules=doc_modules, words=words).save()
    extra = PlanMemoryDocument.objects(owner=run.owner).order_by('-created_at').skip(KEEP_PER_OWNER)
    for d in extra:
        d.delete()
    return doc


def similar(goal, owner):
    """The best earlier plan for this goal, or None."""
    gw = _words(goal)
    best, score = None, 0.0
    for d in PlanMemoryDocument.objects(owner=owner):
        s = _jaccard(gw, set(d.words)) + min(d.uses, 5) * 0.01
        if s > score:
            best, score = d, s
    if best and score >= MIN_SCORE:
        best.update(inc__uses=1)
        return best
    return None


def brief(doc):
    """Compact text for the planner prompt (about 400-600 tokens)."""
    mods = '\n'.join(f"- {m['title']} [{m['folder']}]"
                     + (f" after: {', '.join(m['depends'])}" if m['depends'] else '') + f": {m['description'][:140]}"
                     for m in doc.modules)
    return f"{doc.project_name} ({doc.goal[:160]})\nsummary: {doc.summary[:300]}\ncontract:\n{doc.contract[:1200]}\nmodules:\n{mods}"
