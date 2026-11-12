"""Server-side speech-to-text (Whisper) so voice works in every browser, not just Chromium."""

import os
import requests
from flask import Blueprint, request, jsonify

voice_bp = Blueprint('voice', __name__)


@voice_bp.route('/voice/transcribe', methods=['POST'])
def transcribe():
    f = request.files.get('audio')
    key = os.getenv('OPENAI_API_KEY', '')
    if not f:
        return jsonify({'error': 'audio file is required'}), 400
    if not key:
        return jsonify({'error': "The Whisper fallback needs OPENAI_API_KEY in backend/.env (Chrome and Edge use the browser's own speech recognition and need no key)"}), 400
    r = requests.post('https://api.openai.com/v1/audio/transcriptions',
                      headers={'Authorization': f'Bearer {key}'},
                      files={'file': (f.filename or 'audio.webm', f.stream, f.mimetype or 'audio/webm')},
                      data={'model': 'whisper-1'}, timeout=120)
    if r.status_code != 200:
        return jsonify({'error': f'Whisper failed: HTTP {r.status_code}'}), 502
    return jsonify({'text': r.json().get('text', '')})
