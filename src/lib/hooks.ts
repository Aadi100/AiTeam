'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';

/** Re-renders every second while `active`, returning Date.now() (for live timers). */
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

interface SpeechRec {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
  start(): void; stop(): void;
}
type SpeechCtor = new () => SpeechRec;

/**
 * Voice input. Uses the browser's SpeechRecognition (Chrome/Edge) when available;
 * otherwise records audio and sends it to the backend Whisper endpoint (any browser).
 */
export function useVoice(onFinal: (text: string) => void, openaiKey: string) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const [busy, setBusy] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const recRef = useRef<SpeechRec | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const onFinalRef = useRef(onFinal);
  useEffect(() => { onFinalRef.current = onFinal; }, [onFinal]);

  const stop = useCallback(() => {
    recRef.current?.stop();
    if (mediaRef.current && mediaRef.current.state !== 'inactive') mediaRef.current.stop();
  }, []);

  const start = useCallback(async () => {
    setVoiceError(''); setInterim('');
    const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (Ctor) {
      const rec = new Ctor();
      rec.lang = navigator.language || 'en-US';
      rec.interimResults = true;
      rec.continuous = false;
      let finalText = '';
      rec.onresult = e => {
        let interimText = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) finalText += t; else interimText += t;
        }
        setInterim(interimText);
      };
      rec.onerror = e => setVoiceError(`Voice error: ${e.error}`);
      rec.onend = () => { setListening(false); setInterim(''); if (finalText.trim()) onFinalRef.current(finalText.trim()); };
      recRef.current = rec;
      rec.start();
      setListening(true);
      return;
    }
    // Fallback: record + server-side Whisper
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: Blob[] = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = e => chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        setListening(false); setBusy(true);
        try {
          const fd = new FormData();
          fd.append('audio', new Blob(chunks, { type: mr.mimeType }), 'speech.webm');
          if (openaiKey) fd.append('openaiKey', openaiKey);
          const r = await api<{ text: string }>('/voice/transcribe', { method: 'POST', body: fd });
          if (r.text.trim()) onFinalRef.current(r.text.trim());
        } catch (e) { setVoiceError(e instanceof Error ? e.message : 'Transcription failed'); }
        finally { setBusy(false); }
      };
      mediaRef.current = mr;
      mr.start();
      setListening(true);
    } catch { setVoiceError('Microphone unavailable or permission denied'); }
  }, [openaiKey]);

  const toggle = useCallback(() => (listening ? stop() : start()), [listening, start, stop]);
  return { listening, interim, busy, voiceError, toggle };
}
