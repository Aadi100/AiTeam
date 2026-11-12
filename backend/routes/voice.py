"""
Voice API.

GET  /api/voice/status       what is available (natural voices, local Whisper)
GET  /api/voice/voices       every voice: [{id, name, lang, locale, gender}] + the languages
POST /api/voice/tts          {text, voice?, lang?, gender?, rate?, pitch?} -> audio/mpeg (the voice is picked for the language)
POST /api/voice/detect       {text, hint?} -> {lang}
POST /api/voice/transcribe   multipart "audio" (+ "language") -> {text, language}  (local Whisper, any language)
"""

import time
from collections import defaultdict, deque
from flask import Blueprint, request, jsonify, Response

from orchestrator import tts, stt
from auth import current_user

voice_bp = Blueprint('voice', __name__)
_hits = defaultdict(deque)


def _limited(kind, per_minute):
    key = (current_user()['u'], kind)
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        return True
    q.append(now)
    return False


@voice_bp.route('/voice/status', methods=['GET'])
def status():
    try:
        n = len(tts.voices())
    except tts.TTSError:
        n = 0
    return jsonify({'natural': n > 0, 'voices': n, 'whisper': stt.available(), 'whisperModel': stt.MODEL_NAME})


@voice_bp.route('/voice/voices', methods=['GET'])
def list_voices():
    try:
        return jsonify({'voices': tts.voices(), 'languages': tts.languages()})
    except tts.TTSError as e:
        return jsonify({'error': str(e), 'voices': [], 'languages': []}), 502


@voice_bp.route('/voice/detect', methods=['POST'])
def detect():
    b = request.get_json(silent=True) or {}
    return jsonify({'lang': tts.detect_lang(str(b.get('text') or '')[:600], str(b.get('hint') or ''))})


@voice_bp.route('/voice/tts', methods=['POST'])
def speak():
    b = request.get_json(silent=True) or {}
    text = str(b.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'text is required'}), 400
    if len(text) > tts.MAX_CHARS * 2:
        return jsonify({'error': 'text is too long; send it in pieces'}), 400
    if _limited('tts', 90):
        return jsonify({'error': 'too many speech requests; wait a moment'}), 429
    try:
        lang = str(b.get('lang') or '') or tts.detect_lang(text)
        voice = tts.pick_voice(lang, 'male' if b.get('gender') == 'male' else 'female', str(b.get('voice') or ''))
        data = tts.synth(text, voice, int(b.get('rate') or 0), int(b.get('pitch') or 0))
    except tts.TTSError as e:
        return jsonify({'error': str(e)}), 502
    except (TypeError, ValueError):
        return jsonify({'error': 'rate and pitch must be numbers'}), 400
    return Response(data, mimetype='audio/mpeg', headers={'X-Voice': voice, 'X-Lang': lang, 'Cache-Control': 'no-store',
                                                           'Access-Control-Expose-Headers': 'X-Voice, X-Lang'})


@voice_bp.route('/voice/transcribe', methods=['POST'])
def transcribe():
    f = request.files.get('audio')
    if f is None:
        return jsonify({'error': 'no audio uploaded'}), 400
    if _limited('stt', 40):
        return jsonify({'error': 'too many recordings; wait a moment'}), 429
    lang = (request.form.get('language') or '').split('-')[0].lower() or None
    try:
        hint = (request.form.get('hint') or '').split('-')[0].lower() or None
        return jsonify(stt.transcribe(f.read(12 * 1024 * 1024), lang, hint))
    except stt.STTError as e:
        return jsonify({'error': str(e)}), 501 if 'faster-whisper' in str(e) else 400
    except Exception as e:  # noqa: BLE001 - model download / decoding problems must not crash the server
        return jsonify({'error': f'Speech recognition failed: {type(e).__name__}: {str(e)[:160]}'}), 500
