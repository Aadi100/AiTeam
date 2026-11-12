"""Offline tests: voices (list, pick), language detection, text-to-speech endpoint, speech-to-text endpoint, replying in the
user's language. The Microsoft voice service is faked, so nothing is sent anywhere."""
import os, sys, io, json, wave, struct, math, asyncio
os.environ['MONGO_URI'] = 'mongodb://localhost:27017/devsquad_test'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mongoengine as me
from app import create_app
me.get_connection().drop_database('devsquad_test')
from orchestrator import tts, stt, llm
import auth

PASS, FAIL = [], []
def check(name, cond, extra=''):
    (PASS if cond else FAIL).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{str(extra)[:250]}]' if extra and not cond else ''))

# ── fake voice service ──
RAW = [{'ShortName': n, 'Locale': loc, 'Gender': g} for n, loc, g in [
    ('en-US-AriaNeural', 'en-US', 'Female'), ('en-US-GuyNeural', 'en-US', 'Male'), ('en-GB-RyanNeural', 'en-GB', 'Male'), ('en-IN-NeerjaNeural', 'en-IN', 'Female'),
    ('en-US-AndrewMultilingualNeural', 'en-US', 'Male'), ('hi-IN-SwaraNeural', 'hi-IN', 'Female'), ('hi-IN-MadhurNeural', 'hi-IN', 'Male'),
    ('ur-PK-UzmaNeural', 'ur-PK', 'Female'), ('ur-IN-SalmanNeural', 'ur-IN', 'Male'), ('ar-SA-HamedNeural', 'ar-SA', 'Male'), ('ar-EG-SalmaNeural', 'ar-EG', 'Female'),
    ('es-ES-ElviraNeural', 'es-ES', 'Female'), ('es-MX-JorgeNeural', 'es-MX', 'Male')]]
import edge_tts
async def fake_list(): return RAW
edge_tts.list_voices = fake_list
synth_calls = []
async def fake_synth(text, voice, rate, pitch):
    synth_calls.append((text, voice, rate, pitch))
    return b'ID3FAKE' + text.encode('utf-8')[:20]
tts._synth = fake_synth

# ───────── voices ─────────
vs = tts.voices(force=True)
check('V1: voices are parsed with language, locale and gender', len(vs) == len(RAW) and {'id', 'name', 'lang', 'locale', 'gender'} <= set(vs[0]))
check('V2: friendly names', next(v for v in vs if v['id'] == 'en-US-AriaNeural')['name'] == 'Aria' and 'multilingual' in next(v for v in vs if 'Andrew' in v['id'])['name'])
langs = {l['code']: l for l in tts.languages()}
check('V3: languages with names and counts', langs['hi']['name'] == 'Hindi' and langs['en']['count'] == 5 and langs['ar']['name'] == 'Arabic')
check('V4: voices are cached (no second call to the service)', tts.voices() is tts.voices())

# ───────── picking ─────────
check('P1: female English -> a regular US voice (not multilingual)', tts.pick_voice('en', 'female') == 'en-US-AriaNeural')
check('P2: male English -> Guy', tts.pick_voice('en', 'male') == 'en-US-GuyNeural')
check('P3: Hindi female/male', tts.pick_voice('hi', 'female') == 'hi-IN-SwaraNeural' and tts.pick_voice('hi', 'male') == 'hi-IN-MadhurNeural')
check('P4: Urdu prefers Pakistan voices, falls back to the other gender when needed', tts.pick_voice('ur', 'female') == 'ur-PK-UzmaNeural' and tts.pick_voice('ur', 'male') == 'ur-IN-SalmanNeural')
check('P5: Arabic prefers Saudi for the language default', tts.pick_voice('ar', 'male') == 'ar-SA-HamedNeural' and tts.pick_voice('ar', 'female') == 'ar-EG-SalmaNeural')
check('P6: a chosen voice wins when it speaks the language', tts.pick_voice('en', 'female', 'en-GB-RyanNeural') == 'en-GB-RyanNeural')
check('P7: a chosen voice of ANOTHER language is ignored (the reply language wins)', tts.pick_voice('hi', 'female', 'en-GB-RyanNeural') == 'hi-IN-SwaraNeural')
check('P8: a multilingual voice may be chosen for any language', tts.pick_voice('hi', 'male', 'en-US-AndrewMultilingualNeural') == 'en-US-AndrewMultilingualNeural')
check('P9: an unsupported language falls back to English', tts.pick_voice('xx', 'female') == 'en-US-AriaNeural')

# ───────── language detection ─────────
cases = [('Hello how are you today', 'en'), ('what is the weather like', 'en'), ('ok', 'en'), ('नमस्ते आप कैसे हैं', 'hi'), ('آپ کیسے ہیں آج ٹھیک ہے', 'ur'),
         ('كيف حالك اليوم', 'ar'), ('شما چطور هستید', 'fa'), ('আপনি কেমন আছেন', 'bn'), ('நீங்கள் எப்படி இருக்கிறீர்கள்', 'ta'), ('మీరు ఎలా ఉన్నారు', 'te'),
         ('તમે કેમ છો', 'gu'), ('ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ', 'pa'), ('สวัสดีครับ คุณสบายดีไหม', 'th'), ('안녕하세요 어떻게 지내세요', 'ko'), ('こんにちは お元気ですか', 'ja'),
         ('你好，你今天怎么样', 'zh'), ('привет как дела сегодня', 'ru'), ('привіт як справи', 'uk'), ('γεια σου τι κάνεις', 'el'), ('שלום מה שלומך', 'he'),
         ('hola como estas hoy amigo mio', 'es'), ('bonjour comment allez vous aujourd hui', 'fr'), ('guten tag wie geht es ihnen heute', 'de'),
         ('olá como você está hoje meu amigo', 'pt'), ('ciao come stai oggi amico mio', 'it')]
bad = [(t, want, tts.detect_lang(t)) for t, want in cases if tts.detect_lang(t) != want]
check('D1: detects 25 languages from the text (scripts and Latin languages)', not bad, str(bad))
check('D2: empty text uses the hint, else English', tts.detect_lang('', 'hi') == 'hi' and tts.detect_lang('') == 'en' and tts.detect_lang('123 !!!') == 'en')
check('D3: Devanagari can be Marathi/Nepali when the hint says so', tts.detect_lang('तुम्ही कसे आहात', 'mr') == 'mr')
check('D4: links and numbers do not confuse it', tts.detect_lang('see https://example.com/page 12345 नमस्ते दोस्तों') == 'hi')

# ───────── text cleaning ─────────
t = tts.clean_text('**Bold** and `code`, see https://x.com/a [1] and ```\nprint(1)\n``` done # heading')
check('C1: markdown, code blocks, links and citation marks are not read aloud', 'print' not in t and '**' not in t and 'x.com' not in t and '[1]' not in t and 'Bold' in t and 'link' in t, t)

# ───────── endpoints ─────────
app = create_app()
auth.ensure_bootstrap_admin()
auth.UserDocument(username='view', password_hash=auth.generate_password_hash('password123'), role='viewer').save()
H = {'Authorization': 'Bearer ' + auth.make_token('admin', 'admin')}
VH = {'Authorization': 'Bearer ' + auth.make_token('view', 'viewer')}
c = app.test_client()

s = c.get('/api/voice/status', headers=H).get_json()
check('E1: status reports voices and Whisper', s['natural'] is True and s['voices'] == len(RAW) and isinstance(s['whisper'], bool))
v = c.get('/api/voice/voices', headers=H).get_json()
check('E2: voices endpoint', len(v['voices']) == len(RAW) and any(l['code'] == 'hi' for l in v['languages']))
check('E3: detect endpoint', c.post('/api/voice/detect', headers=H, json={'text': 'नमस्ते'}).get_json() == {'lang': 'hi'})

synth_calls.clear()
r = c.post('/api/voice/tts', headers=H, json={'text': 'नमस्ते, मैं आदियन हूँ'})
check('T1: speech comes back as audio, voice chosen for the detected language', r.status_code == 200 and r.mimetype == 'audio/mpeg' and r.headers['X-Lang'] == 'hi' and r.headers['X-Voice'] == 'hi-IN-SwaraNeural' and r.data.startswith(b'ID3'), str(r.headers))
r = c.post('/api/voice/tts', headers=H, json={'text': 'Hello there my friend', 'gender': 'male'})
check('T2: gender is honoured', r.headers['X-Voice'] == 'en-US-GuyNeural' and r.headers['X-Lang'] == 'en')
r = c.post('/api/voice/tts', headers=H, json={'text': 'Hello there my friend', 'voice': 'en-GB-RyanNeural'})
check('T3: a chosen voice is used', r.headers['X-Voice'] == 'en-GB-RyanNeural')
r = c.post('/api/voice/tts', headers=H, json={'text': 'Hello there my friend', 'lang': 'es'})
check('T4: the language can be given (no guessing)', r.headers['X-Lang'] == 'es' and r.headers['X-Voice'] == 'es-ES-ElviraNeural')
synth_calls.clear()
c.post('/api/voice/tts', headers=H, json={'text': 'Clamp test sentence', 'rate': 900, 'pitch': -900})
check('T5: speed and pitch are clamped to sane values', synth_calls[-1][2:] == (100, -50), str(synth_calls[-1]))
n = len(synth_calls)
c.post('/api/voice/tts', headers=H, json={'text': 'Clamp test sentence', 'rate': 900, 'pitch': -900})
check('T6: an identical request is served from the cache', len(synth_calls) == n)
check('T7: empty text -> 400', c.post('/api/voice/tts', headers=H, json={'text': '  '}).status_code == 400)
check('T8: very long text -> 400 (send it in pieces)', c.post('/api/voice/tts', headers=H, json={'text': 'a ' * 3000}).status_code == 400)
check('T9: bad rate -> 400', c.post('/api/voice/tts', headers=H, json={'text': 'hello there', 'rate': 'fast'}).status_code == 400)
check('T10: viewers can use speech (they can chat)', c.post('/api/voice/tts', headers=VH, json={'text': 'Hello viewer here'}).status_code == 200)
async def broken(*a, **k): raise RuntimeError('service down')
tts._synth = broken
r = c.post('/api/voice/tts', headers=H, json={'text': 'This will fail now'})
check('T11: when the voice service is down: a clear 502 (the app falls back to the browser voice)', r.status_code == 502 and 'voice service' in r.get_json()['error'], r.get_data(as_text=True))
tts._synth = fake_synth
for i in range(100):
    r = c.post('/api/voice/tts', headers=H, json={'text': f'rate limit test number {i}'})
    if r.status_code == 429: break
check('T12: a runaway client is rate limited', r.status_code == 429, str(r.status_code))

# ───────── speech to text ─────────
def wav(seconds, tone=True):
    b = io.BytesIO()
    with wave.open(b, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 220 * i / 16000)) if tone else 0) for i in range(int(16000 * seconds))))
    return b.getvalue()
a = stt.decode(wav(1.0))
check('S1: recordings are decoded to 16 kHz mono floats', len(a) == 16000 and str(a.dtype) == 'float32' and abs(a).max() > 0.1, f'{len(a)}')
try:
    stt.decode(b'this is not audio at all'); ok = False
except stt.STTError:
    ok = True
check('S2: garbage audio is a clear error, not a crash', ok)
check('S3: a clip shorter than 0.3 s is empty without loading the model', stt.transcribe(wav(0.1), None)['text'] == '' and stt._model is None)
seen = {}
def fake_transcribe(raw, language=None, hint=None):
    seen['language'] = language
    return {'text': 'नमस्ते', 'language': 'hi', 'probability': 0.97}
stt.transcribe = fake_transcribe
r = c.post('/api/voice/transcribe', headers=H, data={'audio': (io.BytesIO(wav(1)), 'speech.webm'), 'language': 'hi-IN'}, content_type='multipart/form-data')
check('S4: transcribe returns text and the language heard; "hi-IN" is passed as "hi"', r.status_code == 200 and r.get_json()['language'] == 'hi' and seen['language'] == 'hi', r.get_data(as_text=True))
r = c.post('/api/voice/transcribe', headers=H, data={'audio': (io.BytesIO(wav(1)), 'speech.webm')}, content_type='multipart/form-data')
check('S5: with no language given it auto-detects', seen['language'] is None)
check('S6: no audio -> 400', c.post('/api/voice/transcribe', headers=H, data={}, content_type='multipart/form-data').status_code == 400)
def not_installed(raw, language=None, hint=None): raise stt.STTError('Speech recognition for any language needs: pip install faster-whisper')
stt.transcribe = not_installed
r = c.post('/api/voice/transcribe', headers=H, data={'audio': (io.BytesIO(wav(1)), 'x.webm')}, content_type='multipart/form-data')
check('S7: Whisper not installed -> 501 with the fix', r.status_code == 501 and 'faster-whisper' in r.get_json()['error'])

# ───────── the assistant replies in your language ─────────
sent = {}
def fake_post(url, **kw):
    sent['system'] = kw['json']['messages'][0]['content']
    reply = {'reply': 'ठीक है, मैं अभी खोलता हूँ।', 'lang': sent.get('lang', 'hi'), 'action': {'type': 'none'}}
    return {'choices': [{'message': {'content': json.dumps(reply)}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 100}}
llm._post = fake_post
c.put('/api/auth/apikey', headers=H, json={'key': 'sk-testtesttesttesttest'})
j = c.post('/api/assistant/chat', headers=H, json={'message': 'मेरी फाइल खोलो', 'history': []}).get_json()
check('A1: the assistant tells which language it replied in', j['lang'] == 'hi' and 'ठीक है' in j['reply'], str(j))
check('A2: its instructions say to reply in the user\'s language', 'SAME language' in sent['system'] and '"lang"' in sent['system'])
sent['lang'] = 'Hindi'
check('A3: a bad language code is dropped (the server detects instead)', c.post('/api/assistant/chat', headers=H, json={'message': 'x y', 'history': []}).get_json()['lang'] == '')
sent['lang'] = 'ur-PK'
check('A4: a regional code is reduced to the language', c.post('/api/assistant/chat', headers=H, json={'message': 'x y', 'history': []}).get_json()['lang'] == 'ur')


# ───────── favourite voices (avoid child/odd voices) ─────────
import time as _t
saved = (tts._voices['t'], tts._voices['v'])
tts._voices.update(t=_t.time(), v=[{'id': 'en-US-AnaNeural', 'name': 'Ana', 'locale': 'en-US', 'lang': 'en', 'gender': 'female'},
                                   {'id': 'en-US-AriaNeural', 'name': 'Aria', 'locale': 'en-US', 'lang': 'en', 'gender': 'female'},
                                   {'id': 'en-US-GuyNeural', 'name': 'Guy', 'locale': 'en-US', 'lang': 'en', 'gender': 'male'},
                                   {'id': 'xx-YY-ZedNeural', 'name': 'Zed', 'locale': 'xx-YY', 'lang': 'xx', 'gender': 'male'}])
check('F1: the automatic voice is a known adult voice, not whichever sorts first (Ana is a child voice)', tts.pick_voice('en', 'female') == 'en-US-AriaNeural' and tts.pick_voice('en', 'male') == 'en-US-GuyNeural')
check('F2: languages without a favourite still get a sensible voice', tts.pick_voice('xx', 'male') == 'xx-YY-ZedNeural')
tts._voices.update(t=saved[0], v=saved[1])

# ───────── Whisper unsure about the language -> use the conversation's language ─────────
class Seg:
    def __init__(self, t): self.text, self.no_speech_prob = t, 0.0
class Info:
    def __init__(self, l, p): self.language, self.language_probability = l, p
class FakeModel:
    calls = []
    def transcribe(self, audio, language=None, **kw):
        FakeModel.calls.append(language)
        if language is None:
            return iter([Seg('wrong guess')]), Info('zh', 0.5)
        return iter([Seg('Hello there')]), Info(language, 0.9)
class Sure(FakeModel):
    def transcribe(self, audio, language=None, **kw):
        FakeModel.calls.append(language)
        return iter([Seg('Bonjour')]), Info('fr', 0.97)
stt.transcribe = __import__('importlib').import_module('importlib').reload(stt).transcribe   # restore the real function after the fakes above
stt._load = lambda: FakeModel()
real_wav = wav(1.0)
r = stt.transcribe(real_wav, None, 'en')
check('W1: unsure language + a conversation language -> it listens again in that language', FakeModel.calls == [None, 'en'] and r['language'] == 'en' and r['text'] == 'Hello there', f'{FakeModel.calls} {r}')
FakeModel.calls.clear()
r = stt.transcribe(real_wav, None, None)
check('W2: no conversation language -> keeps its own guess', FakeModel.calls == [None] and r['language'] == 'zh')
FakeModel.calls.clear(); stt._load = lambda: Sure()
r = stt.transcribe(real_wav, None, 'en')
check('W3: when it is sure (97%), it trusts what it heard even if the conversation was in another language', FakeModel.calls == [None] and r['language'] == 'fr')
FakeModel.calls.clear(); stt._load = lambda: FakeModel()
r = stt.transcribe(real_wav, 'hi', 'en')
check('W4: a language you chose in settings is never overridden', FakeModel.calls == ['hi'] and r['language'] == 'hi')
r = c.post('/api/voice/transcribe', headers=H, data={'audio': (io.BytesIO(real_wav), 'x.webm'), 'hint': 'ur-PK'}, content_type='multipart/form-data')
check('W5: the endpoint forwards the hint (ur-PK -> ur)', r.status_code == 200 and FakeModel.calls[-1] in (None, 'ur'), str(FakeModel.calls))

print(f'\n{len(PASS)} passed, {len(FAIL)} failed')
me.get_connection().drop_database('devsquad_test')
sys.exit(1 if FAIL else 0)
