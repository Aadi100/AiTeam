"""
Text-to-speech and language detection for Adion's voice.

Voices: Microsoft Edge's neural voices through the `edge-tts` package. No API key, 300+ voices in 75 languages, natural
sounding, male and female. IMPORTANT: this sends the text Adion is about to speak to Microsoft's online speech service
(the same one Edge's "Read aloud" uses). The browser's own local voices stay available as the private alternative.

detect_lang(text) tells which language a piece of text is in (so Adion answers and speaks in the language you used).
pick_voice(lang, gender) picks the best voice for it. synth(...) returns MP3 bytes.
"""

import re
import time
import asyncio
import hashlib
import threading
from collections import OrderedDict

LANG_NAMES = {
    'af': 'Afrikaans', 'am': 'Amharic', 'ar': 'Arabic', 'az': 'Azerbaijani', 'bg': 'Bulgarian', 'bn': 'Bengali', 'bs': 'Bosnian',
    'ca': 'Catalan', 'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish', 'de': 'German', 'el': 'Greek', 'en': 'English', 'es': 'Spanish',
    'et': 'Estonian', 'fa': 'Persian', 'fi': 'Finnish', 'fil': 'Filipino', 'fr': 'French', 'ga': 'Irish', 'gl': 'Galician',
    'gu': 'Gujarati', 'he': 'Hebrew', 'hi': 'Hindi', 'hr': 'Croatian', 'hu': 'Hungarian', 'id': 'Indonesian', 'is': 'Icelandic',
    'it': 'Italian', 'iu': 'Inuktitut', 'ja': 'Japanese', 'jv': 'Javanese', 'ka': 'Georgian', 'kk': 'Kazakh', 'km': 'Khmer',
    'kn': 'Kannada', 'ko': 'Korean', 'lo': 'Lao', 'lt': 'Lithuanian', 'lv': 'Latvian', 'mk': 'Macedonian', 'ml': 'Malayalam',
    'mn': 'Mongolian', 'mr': 'Marathi', 'ms': 'Malay', 'mt': 'Maltese', 'my': 'Burmese', 'nb': 'Norwegian', 'ne': 'Nepali',
    'nl': 'Dutch', 'pl': 'Polish', 'ps': 'Pashto', 'pt': 'Portuguese', 'ro': 'Romanian', 'ru': 'Russian', 'si': 'Sinhala',
    'sk': 'Slovak', 'sl': 'Slovenian', 'so': 'Somali', 'sq': 'Albanian', 'sr': 'Serbian', 'su': 'Sundanese', 'sv': 'Swedish',
    'sw': 'Swahili', 'ta': 'Tamil', 'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ur': 'Urdu', 'uz': 'Uzbek',
    'vi': 'Vietnamese', 'zh': 'Chinese', 'zu': 'Zulu',
}
# which regional voice to prefer when a language has several
PREFERRED_LOCALE = {'en': 'en-US', 'hi': 'hi-IN', 'ur': 'ur-PK', 'ar': 'ar-SA', 'es': 'es-ES', 'pt': 'pt-BR', 'zh': 'zh-CN', 'fr': 'fr-FR',
                    'bn': 'bn-BD', 'de': 'de-DE', 'ta': 'ta-IN', 'sw': 'sw-KE', 'ms': 'ms-MY', 'nl': 'nl-NL', 'it': 'it-IT'}
FAVOURITES = {   # tried first for the automatic choice: clear, adult, natural
    'en': {'female': 'en-US-AriaNeural', 'male': 'en-US-GuyNeural'}, 'hi': {'female': 'hi-IN-SwaraNeural', 'male': 'hi-IN-MadhurNeural'},
    'ur': {'female': 'ur-PK-UzmaNeural', 'male': 'ur-PK-AsadNeural'}, 'ar': {'female': 'ar-SA-ZariyahNeural', 'male': 'ar-SA-HamedNeural'},
    'es': {'female': 'es-ES-ElviraNeural', 'male': 'es-ES-AlvaroNeural'}, 'fr': {'female': 'fr-FR-DeniseNeural', 'male': 'fr-FR-HenriNeural'},
    'de': {'female': 'de-DE-KatjaNeural', 'male': 'de-DE-ConradNeural'}, 'pt': {'female': 'pt-BR-FranciscaNeural', 'male': 'pt-BR-AntonioNeural'},
    'it': {'female': 'it-IT-ElsaNeural', 'male': 'it-IT-DiegoNeural'}, 'ru': {'female': 'ru-RU-SvetlanaNeural', 'male': 'ru-RU-DmitryNeural'},
    'ja': {'female': 'ja-JP-NanamiNeural', 'male': 'ja-JP-KeitaNeural'}, 'ko': {'female': 'ko-KR-SunHiNeural', 'male': 'ko-KR-InJoonNeural'},
    'zh': {'female': 'zh-CN-XiaoxiaoNeural', 'male': 'zh-CN-YunxiNeural'}, 'bn': {'female': 'bn-BD-NabanitaNeural', 'male': 'bn-BD-PradeepNeural'},
    'ta': {'female': 'ta-IN-PallaviNeural', 'male': 'ta-IN-ValluvarNeural'}, 'tr': {'female': 'tr-TR-EmelNeural', 'male': 'tr-TR-AhmetNeural'},
}
MAX_CHARS = 1500
DEFAULT_VOICE = 'en-US-AriaNeural'


class TTSError(Exception):
    pass


# ───────────────────────── voices ─────────────────────────
_voices = {'t': 0.0, 'v': []}
_vlock = threading.Lock()


def _friendly(short):
    n = short.split('-', 2)[-1].replace('Neural', '')
    return re.sub(r'Multilingual$', ' (multilingual)', n).strip()


def voices(force=False):
    """[{id, name, lang, locale, gender}] cached for 6 hours."""
    with _vlock:
        if not force and _voices['v'] and time.time() - _voices['t'] < 6 * 3600:
            return _voices['v']
        try:
            import edge_tts
            raw = asyncio.run(asyncio.wait_for(edge_tts.list_voices(), 15))
        except Exception as e:  # noqa: BLE001
            if _voices['v']:
                return _voices['v']
            raise TTSError(f'The voice service is not reachable: {e}')
        out = [{'id': v['ShortName'], 'name': _friendly(v['ShortName']), 'locale': v['Locale'], 'lang': v['Locale'].split('-')[0],
                'gender': v['Gender'].lower()} for v in raw]
        out.sort(key=lambda v: (LANG_NAMES.get(v['lang'], v['lang']), v['locale'], v['gender'], v['name']))
        _voices.update(t=time.time(), v=out)
        return out


def languages():
    counts = {}
    for v in voices():
        counts[v['lang']] = counts.get(v['lang'], 0) + 1
    return sorted(({'code': c, 'name': LANG_NAMES.get(c, c), 'count': n} for c, n in counts.items()), key=lambda x: x['name'])


def pick_voice(lang, gender='female', prefer=''):
    """The best voice for a language. `prefer` (a voice id) wins when it speaks that language."""
    vs = voices()
    if prefer:
        p = next((v for v in vs if v['id'] == prefer), None)
        if p and (not lang or p['lang'] == lang or 'multilingual' in p['name'].lower()):
            return p['id']
    if not any(v['lang'] == lang for v in vs):
        lang = 'en'
    fav = FAVOURITES.get(lang, {}).get(gender)
    if fav and any(v['id'] == fav for v in vs):
        return fav
    cands = [v for v in vs if v['lang'] == lang]
    loc = PREFERRED_LOCALE.get(lang)
    for pool in ([v for v in cands if v['gender'] == gender and v['locale'] == loc], [v for v in cands if v['gender'] == gender],
                 [v for v in cands if v['locale'] == loc], cands):
        pool = [v for v in pool if 'multilingual' not in v['name'].lower()] or pool
        if pool:
            return pool[0]['id']
    return DEFAULT_VOICE


# ───────────────────────── language detection ─────────────────────────
_SCRIPTS = [  # (first, last, language)
    (0x0900, 0x097F, 'hi'), (0x0980, 0x09FF, 'bn'), (0x0A00, 0x0A7F, 'pa'), (0x0A80, 0x0AFF, 'gu'), (0x0B80, 0x0BFF, 'ta'),
    (0x0C00, 0x0C7F, 'te'), (0x0C80, 0x0CFF, 'kn'), (0x0D00, 0x0D7F, 'ml'), (0x0D80, 0x0DFF, 'si'), (0x0E00, 0x0E7F, 'th'),
    (0x0E80, 0x0EFF, 'lo'), (0x1000, 0x109F, 'my'), (0x10A0, 0x10FF, 'ka'), (0x1780, 0x17FF, 'km'), (0x0370, 0x03FF, 'el'),
    (0x0590, 0x05FF, 'he'), (0xAC00, 0xD7AF, 'ko'), (0x3040, 0x30FF, 'ja'),
]
_URDU_ONLY = set('ٹڈڑںےھہۓ')
_PERSIAN = set('پچژگ')
ENGLISH_WORDS = set('the is are was you your what how why who when where to and of in it its i my me we please open find show tell can could would '
                    'do does did this that with for on at from have has be not hello hi thanks today'.split())
FUNCTION_WORDS = {
    'en': ENGLISH_WORDS,
    'es': set('el la los las de que y en un una es por con para como no pero muy hoy estoy estas está hola gracias mi tu amigo mio'.split()),
    'pt': set('o os as de que e em um uma é para com não mas muito hoje você voce está olá ola como meu minha obrigado tudo bem'.split()),
    'fr': set("le la les des et en un une est pour avec pas mais très bonjour comment vous je suis aujourd'hui merci ça j'ai c'est".split()),
    'de': set('der die das und ist nicht ein eine mit für auf wie geht ich sie heute guten tag danke bitte'.split()),
    'it': set('il lo la gli di che e in un una è per con non ma molto oggi ciao come stai grazie sono'.split()),
    'nl': set('de het een en is niet met voor hoe gaat het vandaag hallo dank je ik'.split()),
    'id': set('yang dan di ini itu dengan untuk tidak apa kabar hari selamat saya kamu terima kasih'.split()),
    'tr': set('ve bir bu için ile değil ama çok bugün merhaba nasılsın teşekkür ben sen'.split()),
}
_LATIN_CANDIDATES = ['en', 'es', 'fr', 'de', 'pt', 'it', 'nl', 'id', 'tr', 'pl', 'ro', 'sv', 'da', 'vi', 'fi', 'cs', 'hu', 'sw', 'ms', 'tl']


def detect_lang(text, hint=''):
    """ISO 639-1 code of the language of `text`. Script first (reliable), then statistics for Latin-script text."""
    t = re.sub(r'https?://\S+|[\d\W_]+', ' ', text or '', flags=re.UNICODE).strip()
    if not t:
        return hint or 'en'
    counts = {}
    for ch in t:
        o = ord(ch)
        for lo, hi, lg in _SCRIPTS:
            if lo <= o <= hi:
                counts[lg] = counts.get(lg, 0) + 1
                break
        else:
            if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F:
                counts['arabic'] = counts.get('arabic', 0) + 1
            elif 0x0400 <= o <= 0x04FF:
                counts['cyr'] = counts.get('cyr', 0) + 1
            elif 0x4E00 <= o <= 0x9FFF:
                counts['cjk'] = counts.get('cjk', 0) + 1
            elif ch.isalpha():
                counts['latin'] = counts.get('latin', 0) + 1
    if not counts:
        return hint or 'en'
    top = max(counts, key=counts.get)
    if counts.get('ja'):
        return 'ja'
    if top == 'cjk':
        return 'zh'
    if top == 'hi':
        return hint if hint in ('mr', 'ne') else 'hi'
    if top == 'cyr':
        return hint if hint in ('uk', 'bg', 'sr', 'kk', 'mk', 'mn') else ('uk' if set('іїєґ') & set(t.lower()) else 'ru')
    if top == 'arabic':
        chars = set(t)
        if chars & _URDU_ONLY:
            return 'ur'
        if chars & _PERSIAN:
            return 'fa' if hint != 'ur' else 'ur'
        return hint if hint in ('ur', 'fa', 'ps') else 'ar'
    if top != 'latin':
        return top
    words = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", t.lower())
    if not words:
        return hint or 'en'
    scores = {lg: sum(1 for w in words if w in fw) for lg, fw in FUNCTION_WORDS.items()}
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    if ranked[0][1] >= max(1, len(words) // 5) and (ranked[0][1] > ranked[1][1] or ranked[0][0] == 'en'):
        return ranked[0][0]
    if len(words) < 3 and not hint:
        return 'en'
    try:
        from langdetect import detect_langs, DetectorFactory
        DetectorFactory.seed = 0
        cands = [(l.lang, l.prob) for l in detect_langs(t) if l.lang in _LATIN_CANDIDATES]
        total = sum(p for _, p in cands)
        if cands and total >= 0.3 and cands[0][1] / total >= 0.6:
            return cands[0][0]
    except Exception:  # noqa: BLE001
        pass
    return hint or 'en'


# ───────────────────────── synthesis ─────────────────────────
_cache = OrderedDict()
_clock = threading.Lock()


def clean_text(text):
    t = re.sub(r'```.*?```', ' ', text or '', flags=re.S)
    t = re.sub(r'https?://\S+', ' link ', t)
    t = re.sub(r'[*#`_>|~]+', ' ', t)
    t = re.sub(r'\[(\d+)\]', ' ', t)              # citation marks like [1]
    return re.sub(r'\s+', ' ', t).strip()


async def _synth(text, voice, rate, pitch):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=f'{rate:+d}%', pitch=f'{pitch:+d}Hz')
    data = bytearray()
    async for chunk in comm.stream():
        if chunk['type'] == 'audio':
            data += chunk['data']
    return bytes(data)


def synth(text, voice, rate=0, pitch=0):
    """MP3 bytes for `text` spoken by `voice`. rate: -50..+100 (%), pitch: -50..+50 (Hz)."""
    text = clean_text(text)[:MAX_CHARS]
    if not text:
        raise TTSError('nothing to say')
    rate, pitch = max(-50, min(100, int(rate))), max(-50, min(50, int(pitch)))
    key = hashlib.sha1(f'{voice}|{rate}|{pitch}|{text}'.encode()).hexdigest()
    with _clock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    try:
        data = asyncio.run(asyncio.wait_for(_synth(text, voice, rate, pitch), 25))
    except Exception as e:  # noqa: BLE001
        raise TTSError(f'The voice service failed: {e}')
    if not data:
        raise TTSError('The voice service returned no audio.')
    with _clock:
        _cache[key] = data
        while len(_cache) > 60:
            _cache.popitem(last=False)
    return data
