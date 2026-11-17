"""
Adion learns from conversations, and keeps long conversations in view.

1. LEARNING. After a chat answer, one small extra model call reads what the USER said and writes down durable things worth knowing next time
   (their name, job, tools, preferences, corrections such as "stop using emojis"). Notes go into that person's own memory (never anyone else's),
   marked "learned" so they can see and delete them. Rules, enforced here and not only in the prompt:
     - only the user's own words are a source (never web pages, mail or the assistant's text, which could be written by someone else to plant a "fact");
     - nothing that looks like a secret (keys, passwords, card numbers) is ever saved;
     - near-duplicates are skipped, a changed fact replaces the old note, and a person's learned notes are capped;
     - each person can switch learning off (ADION_LEARN=0 switches it off for everyone).
2. LONG CHATS. Recent turns are sent in full, as many as fit a token budget (much larger than before). Older turns are folded into a rolling summary,
   refreshed in the background after answers, so a conversation of hundreds of messages still "remembers" its beginning.
"""

import os
import re
import json
import threading
from datetime import datetime

from . import llm

MAX_LEARNED = 150
MAX_FACTS_PER_CHAT = 3
SUMMARY_EVERY = 6            # fold older turns into the summary once this many have piled up
MAX_TURN_Q, MAX_TURN_A = 4000, 6000

PERSONAL = re.compile(r"\b(?:i|i'm|im|i've|ive|i'll|i'd|my|mine|me|we|our)\b|\bcall me\b|\bremember\b|\balways\b|\bnever\b|\bprefer\b|\bfrom now on\b|"
                      r"\bdon'?t\b|\bstop\b|\bactually\b|\bthat'?s (?:wrong|not)\b|\bno,? (?:i|it|that)\b|\binstead\b|\bplease (?:use|keep|make|write|reply)\b", re.I)
SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{10,}|tvly-\S+|AKIA[0-9A-Z]{12,}|\b\d{13,19}\b|pass(?:word|code|wd)|\bpin\b|\botp\b|secret|token|api[ _-]?key|cvv|\bssn\b|private key|seed phrase)", re.I)

LEARN_SYSTEM = """You keep a private notebook about ONE person so their assistant can serve them better next time.
Read what the USER said and write down only durable things worth remembering across future conversations:
- who they are and their situation (name, job, location, languages, projects, tools, people they mention and who they are to them),
- how they like to be answered (language, length, tone, format) and corrections of the assistant ("don't use emojis", "answer shorter"),
- lasting preferences and decisions about how they work.
NEVER save: one-off questions or tasks, facts about the world, anything the assistant said, secrets (keys, passwords, card numbers, codes),
or sensitive personal data (health, religion, politics, sexuality, finances) unless the user explicitly asked you to remember it.
Only what the USER said counts; the assistant's reply is shown for context only.
Each note is ONE standalone sentence that makes sense without the conversation (start with "The user ..." or the fact itself). At most 3 notes. Most messages deserve none.
If a note replaces an outdated one in EXISTING NOTES, give that note's number in "replaces".
Return ONLY JSON: {"facts": [{"text": "...", "kind": "preference|fact|correction", "replaces": null}]}   (an empty list when nothing is worth saving)"""

SUMMARY_SYSTEM = """You compress the older part of a chat between a user and their assistant Adion into a running summary, so the chat can go on without the old messages.
Keep: what the user wants and why, decisions made, names, numbers, files and links that matter, open questions, and the user's preferences about how to answer.
Drop: greetings, filler, and detail that no longer matters. Write plain notes (short bullet lines), at most 350 words, in the language of the chat.
Merge the NEW TURNS into SO FAR. Return only the updated summary."""


def enabled(owner):
    if os.getenv('ADION_LEARN', '1') == '0':
        return False
    from models import UserDocument
    row = UserDocument.objects(username=owner).first()
    return not row or row.learning is not False


def worth_learning(msg):
    t = (msg or '').strip()
    return len(t) >= 12 and bool(PERSONAL.search(t))


def _clean_fact(text):
    t = re.sub(r'\s+', ' ', str(text or '')).strip().strip('"')
    return t[:300] if 8 <= len(t) and not SECRET.search(t) else ''


def _same(a, b):
    from routes.memory import _words
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.6


def extract(spec, user_msg, answer, notes, ctx=None):
    """-> [{'text', 'kind', 'replaces'}] (already cleaned). Raises llm.LLMError."""
    numbered = '\n'.join(f'{i + 1}. {n.text}' for i, n in enumerate(notes)) or '(none)'
    prompt = (f'EXISTING NOTES:\n{numbered}\n\nASSISTANT REPLIED (context only, never a source): {str(answer or "")[:600]}\n\nUSER SAID: {user_msg[:2000]}')
    text, _, _ = llm.chat(spec, LEARN_SYSTEM, prompt, json_mode=True, max_output=400, ctx=dict(ctx or {}, purpose='learn'))
    data = llm.parse_json(text)
    out = []
    for f in (data.get('facts') if isinstance(data, dict) else None) or []:
        if not isinstance(f, dict):
            continue
        t = _clean_fact(f.get('text'))
        if t:
            r = f.get('replaces')
            out.append({'text': t, 'kind': 'preference' if f.get('kind') in ('preference', 'correction') else 'note',
                        'replaces': r if isinstance(r, int) and 1 <= r <= len(notes) else None})
    return out[:MAX_FACTS_PER_CHAT]


def apply(owner, facts, notes):
    """Save the new notes for this person. -> the texts that were added."""
    from models import MemoryDocument
    from routes.memory import remember
    added = []
    for f in facts:
        if any(_same(f['text'], n.text) for n in notes) or any(_same(f['text'], a) for a in added):
            continue
        if f['replaces']:
            old = notes[f['replaces'] - 1]
            if old.source == 'learned':          # never overwrite what the person typed themselves
                MemoryDocument.objects(mem_id=old.mem_id, owner=owner).delete()
        remember(f['text'], f['kind'], owner=owner, source='learned')
        added.append(f['text'])
    extra = MemoryDocument.objects(owner=owner, source='learned').order_by('-created_at').skip(MAX_LEARNED)
    for m in list(extra):
        m.delete()
    return added


def learn_from(spec, owner, user_msg, answer, ctx=None):
    """The whole learning step for one exchange. -> list of new notes. Never raises (learning must not break a chat)."""
    try:
        if not enabled(owner) or not worth_learning(user_msg):
            return []
        from routes.memory import visible
        notes = list(visible(owner).limit(40))
        return apply(owner, extract(spec, user_msg, answer, notes, ctx), notes)
    except Exception:  # noqa: BLE001
        return []


# ───────────────────────── long conversations ─────────────────────────

def history_budget(spec):
    """How many tokens of earlier conversation to send. Claude reads far more than DeepSeek, so it gets a bigger window."""
    env = os.getenv('ADION_HISTORY_TOKENS')
    if env and env.isdigit():
        return int(env)
    return 150_000 if (spec or {}).get('provider') == 'anthropic' else 28_000


def split_turns(turns, budget):
    """turns = [(question, answer)] oldest first -> (older, recent). Recent = the newest turns that fit the token budget (at most 40), in full."""
    keep, used = 0, 0
    for q, a in reversed(turns):
        cost = llm.count_tokens(q[:MAX_TURN_Q]) + llm.count_tokens(a[:MAX_TURN_A]) + 8
        if used + cost > budget or keep >= 40:
            break
        keep, used = keep + 1, used + cost
    cut = len(turns) - keep
    return turns[:cut], [(q[:MAX_TURN_Q], a[:MAX_TURN_A]) for q, a in turns[cut:]]


def get_summary(owner, thread_id):
    from models import ThreadSummaryDocument
    d = ThreadSummaryDocument.objects(owner=owner, thread_id=thread_id).first()
    return d.summary if d else ''


def _turns_text(turns):
    return '\n'.join(f'User: {q[:500]}\nAdion: {a[:900]}' for q, a in turns)


def refresh_summary(spec, owner, thread_id, turns, ctx=None):
    """Fold turns that no longer fit the window into the stored summary. Cheap when nothing new piled up. Never raises."""
    try:
        if os.getenv('ADION_LEARN', '1') == '0':
            return
        from models import ThreadSummaryDocument
        older, _ = split_turns(turns, history_budget(spec))
        doc = ThreadSummaryDocument.objects(owner=owner, thread_id=thread_id).first()
        covered = doc.covers if doc else 0
        if len(older) - covered < SUMMARY_EVERY:
            return
        text, _, _ = llm.chat(spec, SUMMARY_SYSTEM, f'SO FAR:\n{(doc.summary if doc else "") or "(nothing yet)"}\n\nNEW TURNS:\n{_turns_text(older[covered:])}',
                              json_mode=False, max_output=700, ctx=dict(ctx or {}, purpose='summary'))
        if text.strip():
            ThreadSummaryDocument.objects(owner=owner, thread_id=thread_id).update_one(set__summary=text.strip()[:3500], set__covers=len(older),
                                                                                     set__updated_at=datetime.utcnow(), upsert=True)
    except Exception:  # noqa: BLE001
        pass


def after_chat(spec, owner, thread_id, run_id, user_msg, answer, turns_fn=None):
    """Called once a chat answer is saved. Learns from it and refreshes the thread summary, in the background so the user is not kept waiting."""
    ctx = {'owner': owner, 'run_id': run_id}

    def work():
        learn_from(spec, owner, user_msg, answer, ctx)
        if thread_id and turns_fn:
            refresh_summary(spec, owner, thread_id, list(turns_fn()) + [(user_msg, answer)], ctx)

    if os.getenv('ADION_LEARN', '1') == '0':
        return
    if os.getenv('ADION_LEARN_SYNC') == '1':
        work()
    else:
        threading.Thread(target=work, daemon=True, name='learn-' + run_id).start()
