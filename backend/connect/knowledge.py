"""What Adion knows about an app: documents are cut into chunks and the best ones are found by keyword relevance (no model needed)."""

import re
import math
import uuid

from .models import KnowledgeDoc

STOP = set('a an the and or of to for in on with that this it is are be as at by from your my me i we you our please can could would should do does did not no yes how what when where why which who'.split())
MAX_DOC_CHARS = 200_000
MAX_DOCS_PER_APP = 60


def _tokens(text):
    return [w for w in re.findall(r'[^\W_]+', (text or '').lower()) if len(w) > 1 and w not in STOP]


def _windows(p, size, overlap):
    out, i = [], 0
    while i < len(p):
        end = min(len(p), i + size)
        if end < len(p):
            cut = max(p.rfind('. ', i, end), p.rfind(' ', i, end))
            if cut > i + size // 2:
                end = cut + 1
        out.append(p[i:end].strip())
        if end >= len(p):
            break
        i = max(end - overlap, i + 1)
    return [w for w in out if w]


def chunk(text, size=900, overlap=120):
    """Cut a document into pieces of about `size` characters, keeping paragraphs together where possible."""
    text = re.sub(r'[ \t]+', ' ', (text or '').strip())
    out, cur = [], ''
    for p in [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]:
        if len(p) > size:
            if cur:
                out.append(cur); cur = ''
            out.extend(_windows(p, size, overlap))
        elif len(cur) + len(p) + 2 <= size:
            cur = (cur + '\n\n' + p).strip()
        else:
            out.append(cur); cur = p
    if cur:
        out.append(cur)
    return [c for c in out if c.strip()]


def add_doc(app, title, text, kind='text'):
    text = (text or '').strip()[:MAX_DOC_CHARS]
    if not text:
        raise ValueError('There is no text to add.')
    if KnowledgeDoc.objects(app_id=app.app_id).count() >= MAX_DOCS_PER_APP:
        raise ValueError(f'At most {MAX_DOCS_PER_APP} documents per app.')
    return KnowledgeDoc(doc_id='kd_' + uuid.uuid4().hex[:10], app_id=app.app_id, client_id=app.client_id, title=(title or 'Untitled')[:120],
                        kind=kind, text=text, chunks=chunk(text)).save()


def retrieve(app_id, query, k=4, max_chars=3200):
    """The most relevant chunks of THIS app's knowledge (BM25-style). Returns [(title, text)]."""
    docs = list(KnowledgeDoc.objects(app_id=app_id))
    items = [(d.title, c) for d in docs for c in d.chunks]
    q = _tokens(query)
    if not items or not q:
        return []
    toks = [_tokens(t + ' ' + c) for t, c in items]
    n = len(items)
    avg = sum(len(t) for t in toks) / n or 1
    df = {}
    for ts in toks:
        for w in set(ts):
            df[w] = df.get(w, 0) + 1
    scored = []
    for (title, text), ts in zip(items, toks):
        if not ts:
            continue
        tf = {}
        for w in ts:
            tf[w] = tf.get(w, 0) + 1
        score = 0.0
        for w in set(q):
            if w in tf:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                score += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(ts) / avg))
        if score > 0:
            scored.append((score, title, text))
    scored.sort(reverse=True)
    out, total = [], 0
    for _, title, text in scored[:k]:
        if total + len(text) > max_chars:
            break
        out.append((title, text))
        total += len(text)
    return out
