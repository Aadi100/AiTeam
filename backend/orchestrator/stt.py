"""
Speech-to-text that works in ANY language and tells you which one it heard: Whisper, running on this PC (faster-whisper).
No key, nothing leaves the machine. The first use downloads the model once (about 140 MB for "base").
Set WHISPER_MODEL=small for better accuracy (slower), or tiny for speed.
"""

import io
import os
import threading

MODEL_NAME = os.getenv('WHISPER_MODEL', 'base')
_model = None
_lock = threading.Lock()


class STTError(Exception):
    pass


def available():
    try:
        import faster_whisper  # noqa: F401
        import av  # noqa: F401
        return True
    except ImportError:
        return False


def _load():
    global _model
    with _lock:
        if _model is None:
            os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
            from faster_whisper import WhisperModel
            _model = WhisperModel(MODEL_NAME, device='cpu', compute_type='int8')
    return _model


def decode(raw):
    """Any audio the browser records (webm/opus, mp4, wav...) -> 16 kHz mono float32."""
    import av
    import numpy as np
    out = []
    try:
        with av.open(io.BytesIO(raw)) as cont:
            rs = av.AudioResampler(format='s16', layout='mono', rate=16000)
            for frame in cont.decode(audio=0):
                for f in (rs.resample(frame) or []):
                    out.append(f.to_ndarray().reshape(-1))
            for f in (rs.resample(None) or []):
                out.append(f.to_ndarray().reshape(-1))
    except Exception as e:  # noqa: BLE001
        raise STTError(f'Could not read that recording: {e}')
    if not out:
        raise STTError('The recording is empty.')
    return np.concatenate(out).astype('float32') / 32768.0


def transcribe(raw, language=None, hint=None):
    """-> {text, language, probability}. language = ISO 639-1 code to force, or None to detect.
    hint = the language of the conversation so far: used when the detection is unsure (short clips are often misjudged)."""
    if not available():
        raise STTError('Speech recognition for any language needs: pip install faster-whisper')
    audio = decode(raw)
    if len(audio) < 16000 * 0.3:
        return {'text': '', 'language': language or '', 'probability': 0.0}
    model = _load()
    opts = dict(beam_size=1, vad_filter=True, vad_parameters={'min_silence_duration_ms': 600}, condition_on_previous_text=False)
    segs, info = model.transcribe(audio, language=language or None, **opts)
    if not language and hint and info.language != hint and float(info.language_probability) < 0.6:
        segs, info = model.transcribe(audio, language=hint, **opts)
    segs = list(segs)
    text = ' '.join(s.text.strip() for s in segs if getattr(s, 'no_speech_prob', 0) < 0.8).strip()
    return {'text': text, 'language': info.language, 'probability': round(float(info.language_probability), 2)}
