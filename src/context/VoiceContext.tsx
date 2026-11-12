'use client';

/**
 * ADION voice layer.
 *  - Talk to it: it understands chat, questions about your builds, and commands (build / cancel / read a file / remember).
 *  - It answers out loud (SpeechSynthesis) and can read whole files aloud, sentence by sentence.
 *  - Hands-free loop: after it answers, it listens again until you go quiet (2 silences in a row).
 *  - Wake word: enable "Hey Adion" and just say "Adion, ..." any time (Chrome/Edge).
 *  - Barge-in: pressing the mic (or Alt+V / Ctrl+Space) while it talks stops it and listens to you.
 *  - Announces build progress by voice. Firefox/Safari fall back to server-side Whisper transcription.
 */

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, apiBytes } from '@/lib/api';
import { DEFAULT_PREFS, loadPrefs, savePrefs as savePrefsStore, pickBrowserVoice, playBuffer, splitSentences, SAMPLES, type VoicePrefs } from '@/lib/voice';
import { useApp } from '@/context/AppContext';

interface SpeechRec {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null; onerror: ((e: { error: string }) => void) | null;
  start(): void; stop(): void; abort(): void;
}
type SpeechCtor = new () => SpeechRec;

export interface VoiceMessage { id: number; role: 'user' | 'assistant'; text: string }

interface VoiceCtx {
  isVoiceActive: boolean;      // microphone open
  isThinking: boolean;         // waiting for the assistant
  isSpeaking: boolean;         // assistant talking
  voiceTranscript: string;
  voiceError: string;
  messages: VoiceMessage[];
  isAutoProcessVoice: boolean;
  isAudioReplyEnabled: boolean;
  isWakeWordEnabled: boolean;
  isConversationMode: boolean;
  toggleVoiceListening: () => void;
  toggleAutoProcessVoice: () => void;
  toggleAudioReply: () => void;
  toggleWakeWord: () => void;
  toggleConversationMode: () => void;
  sendText: (text: string) => void;
  speakText: (text: string, lang?: string) => Promise<void>;
  voicePrefs: VoicePrefs;
  setVoicePrefs: (patch: Partial<VoicePrefs>) => void;
  voiceStatus: { natural: boolean; whisper: boolean } | null;
  voiceSettingsOpen: boolean;
  setVoiceSettingsOpen: (v: boolean) => void;
  previewVoice: (lang?: string) => Promise<void>;
  stopSpeaking: () => void;
  clearMessages: () => void;
}

const Ctx = createContext<VoiceCtx | null>(null);
export const useVoice = () => {
  const c = useContext(Ctx);
  if (!c) throw new Error('useVoice must be used inside <VoiceProvider>');
  return c;
};

const PREFS_KEY = 'devsquad.voice.v2';
// speech engines often mishear a made-up name, so accept the common variants
const WAKE = /\b(?:adion|a\s?dion|adian|adeon|a\s?deon|addion|aidan|aiden|ad\s?ion)\b[\s,.!?:;-]*(.*)$/i;

interface ChatReply {
  reply: string; readout?: string; lang?: string;
  action: { type: 'none' | 'build' | 'cancel' | 'read_file' | 'remember' | 'pc'; goal?: string; taskId?: string };
}

export function VoiceProvider({ children }: { children: React.ReactNode }) {
  const { startRun, cancelRun, snap, setGoal, settings, setPcTaskId, authed } = useApp();
  const [isVoiceActive, setActive] = useState(false);
  const [isThinking, setThinking] = useState(false);
  const [isSpeaking, setSpeaking] = useState(false);
  const [voiceTranscript, setTranscript] = useState('');
  const [voiceError, setError] = useState('');
  const [messages, setMessages] = useState<VoiceMessage[]>([]);
  const [isAutoProcessVoice, setAuto] = useState(true);
  const [isAudioReplyEnabled, setAudio] = useState(true);
  const [isWakeWordEnabled, setWake] = useState(false);
  const [isConversationMode, setConv] = useState(true);
  const [voicePrefs, setVoicePrefsState] = useState<VoicePrefs>(DEFAULT_PREFS);
  const prefsRef = useRef<VoicePrefs>(DEFAULT_PREFS);
  const [voiceStatus, setVoiceStatus] = useState<{ natural: boolean; whisper: boolean } | null>(null);
  const [voiceSettingsOpen, setVoiceSettingsOpen] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playingRef = useRef<{ stop: () => void } | null>(null);
  const lastLangRef = useRef('');            // the language of the last thing you said or Adion said
  const warnedRef = useRef(false);
  const whisperRef = useRef<boolean | null>(null);   // is any-language listening installed on the server? (null = not known yet)
  const vadCleanupRef = useRef<() => void>(() => {});

  const recRef = useRef<SpeechRec | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const autoRef = useRef(true);
  const audioRef = useRef(true);
  const wakeRef = useRef(false);
  const convRef = useRef(true);
  const sessionRef = useRef(false);        // a manual hands-free session is in progress
  const missesRef = useRef(0);
  const busyRef = useRef(false);           // thinking or speaking
  const speakTokenRef = useRef(0);         // bumping this aborts any ongoing speech
  const msgId = useRef(1);
  const histRef = useRef<VoiceMessage[]>([]);
  const ctxRef = useRef({ startRun, cancelRun, setGoal, setPcTaskId, runId: '', model: '' });
  const listenRef = useRef<(kind: 'command' | 'wake') => void>(() => {});
  const processRef = useRef<(text: string) => Promise<void>>(async () => {});

  useEffect(() => {
    autoRef.current = isAutoProcessVoice;
    audioRef.current = isAudioReplyEnabled;
    wakeRef.current = isWakeWordEnabled;
    convRef.current = isConversationMode;
    histRef.current = messages;
    ctxRef.current = {
      startRun, cancelRun, setGoal, setPcTaskId, runId: snap?.run.id || '',
      model: settings.workerModel,
    };
  });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      if (raw) {
        const p = JSON.parse(raw) as { auto?: boolean; audio?: boolean; conv?: boolean };
        /* eslint-disable react-hooks/set-state-in-effect -- one-time restore from localStorage */
        if (typeof p.auto === 'boolean') setAuto(p.auto);
        if (typeof p.audio === 'boolean') setAudio(p.audio);
        if (typeof p.conv === 'boolean') setConv(p.conv);
        /* eslint-enable react-hooks/set-state-in-effect */
      }
    } catch { /* ignore */ }
  }, []);
  useEffect(() => {
    const p = loadPrefs();
    prefsRef.current = p;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time restore from localStorage
    setVoicePrefsState(p);
  }, []);
  useEffect(() => {
    if (!authed) return;
    api<{ natural: boolean; whisper: boolean }>('/voice/status').then(s => { whisperRef.current = s.whisper; setVoiceStatus(s); }).catch(() => setVoiceStatus(null));
  }, [authed]);
  const setVoicePrefs = useCallback((patch: Partial<VoicePrefs>) => {
    const next = { ...prefsRef.current, ...patch };
    prefsRef.current = next; setVoicePrefsState(next); savePrefsStore(next);
  }, []);

  const savePrefs = (auto: boolean, audio: boolean, conv: boolean) => {
    try { localStorage.setItem(PREFS_KEY, JSON.stringify({ auto, audio, conv })); } catch { /* ignore */ }
  };

  const addMsg = useCallback((role: 'user' | 'assistant', text: string) => {
    setMessages(m => [...m.slice(-49), { id: msgId.current++, role, text }]);
  }, []);

  // ───────── speech output: natural neural voices in any language, or this device's own voices ─────────
  const getAudioCtx = () => {
    if (!audioCtxRef.current) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      audioCtxRef.current = new AC();
    }
    if (audioCtxRef.current.state === 'suspended') audioCtxRef.current.resume().catch(() => { /* needs a click first */ });
    return audioCtxRef.current;
  };

  const detectLang = useCallback(async (text: string): Promise<string> => {
    try { return (await api<{ lang: string }>('/voice/detect', { method: 'POST', json: { text: text.slice(0, 400), hint: lastLangRef.current } })).lang || 'en'; }
    catch { return lastLangRef.current || 'en'; }
  }, []);

  const speakBrowser = useCallback(async (chunks: string[], lang: string, token: number) => {
    const synth = window.speechSynthesis;
    const p = prefsRef.current;
    const voice = pickBrowserVoice(synth.getVoices(), lang, p.gender, p.browserVoice);
    for (const c of chunks) {
      if (speakTokenRef.current !== token) break;
      await new Promise<void>(res => {
        const u = new SpeechSynthesisUtterance(c);
        u.rate = p.rate; u.pitch = 1 + p.pitch / 60;
        if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = lang;
        u.onend = () => res(); u.onerror = () => res();
        synth.speak(u);
      });
    }
  }, []);

  const speak = useCallback(async (text: string, lang0: string | undefined, force: boolean) => {
    if ((!audioRef.current && !force) || typeof window === 'undefined') return;
    const token = ++speakTokenRef.current;
    playingRef.current?.stop(); playingRef.current = null;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    const p0 = prefsRef.current;
    const chunks = splitSentences(text, p0.engine === 'natural' ? 300 : 220);
    if (!chunks.length) return;
    const lang = lang0 || await detectLang(text);
    if (speakTokenRef.current !== token) return;
    lastLangRef.current = lang;
    setSpeaking(true);
    try {
      const p = prefsRef.current;
      let useBrowser = p.engine === 'browser' || !(typeof AudioContext !== 'undefined' || 'webkitAudioContext' in window);
      let played = 0;
      if (!useBrowser) {
        try {
          const ctx = getAudioCtx();
          const fetchClip = (t: string) => apiBytes('/voice/tts', { text: t, lang, voice: p.voice, gender: p.gender, rate: Math.round((p.rate - 1) * 100), pitch: Math.round(p.pitch) })
            .then(b => ctx.decodeAudioData(b));
          let next = fetchClip(chunks[0]);
          for (let i = 0; i < chunks.length; i++) {
            const buf = await next;
            if (speakTokenRef.current !== token) break;
            next = i + 1 < chunks.length ? fetchClip(chunks[i + 1]) : Promise.resolve(buf);
            next.catch(() => { /* reported when awaited */ });
            const h = playBuffer(ctx, buf, p.style, 1);
            playingRef.current = h;
            await h.done;
            played = i + 1;
          }
        } catch (e) {
          if (speakTokenRef.current === token) {
            if (!warnedRef.current) { warnedRef.current = true; setError('The natural voice is not reachable, so I used your device voice. ' + (e instanceof Error ? e.message : '')); }
            useBrowser = true;
          }
        }
      }
      if (useBrowser && speakTokenRef.current === token && 'speechSynthesis' in window) await speakBrowser(chunks.slice(played), lang, token);
    } finally {
      if (speakTokenRef.current === token) setSpeaking(false);
    }
  }, [detectLang, speakBrowser]);

  const speakText = useCallback((text: string, lang?: string) => speak(text, lang, false), [speak]);
  const previewVoice = useCallback(async (lang?: string) => {
    const l = lang && SAMPLES[lang] ? lang : 'en';
    await speak(SAMPLES[l], l, true);
  }, [speak]);

  const stopSpeaking = useCallback(() => {
    speakTokenRef.current++;
    playingRef.current?.stop(); playingRef.current = null;
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, []);

  // ───────── microphone ─────────
  const killRec = useCallback(() => {
    vadCleanupRef.current();
    const r = recRef.current;
    recRef.current = null;
    if (r) { r.onend = null; r.onresult = null; r.onerror = null; try { r.abort(); } catch { /* ignore */ } }
    if (mediaRef.current && mediaRef.current.state !== 'inactive') { mediaRef.current.onstop = null; mediaRef.current.stop(); }
    setActive(false);
  }, []);

  /** After Adion finishes talking: go back to wake-word listening, keep the conversation going, or go idle. */
  const resume = useCallback(() => {
    if (wakeRef.current) listenRef.current('wake');
    else if (convRef.current && sessionRef.current && missesRef.current < 2) listenRef.current('command');
    else sessionRef.current = false;
  }, []);

  const handleAction = useCallback(async (res: ChatReply): Promise<string> => {
    const c = ctxRef.current;
    if (res.action.type === 'build' && res.action.goal) {
      c.setGoal(res.action.goal);
      if (autoRef.current) { await c.startRun(res.action.goal, 'voice'); return ''; }
      return ' I put it in the goal box. Press run when you are ready.';
    }
    if (res.action.type === 'cancel') { await c.cancelRun(); }
    if (res.action.type === 'pc' && res.action.taskId) { c.setPcTaskId(res.action.taskId); return ' I will ask before I change anything.'; }
    return '';
  }, []);

  const process = useCallback(async (text: string) => {
    killRec();
    const clean = text.trim();
    if (clean.length < 2) { resume(); return; }
    stopSpeaking();
    busyRef.current = true;
    setTranscript('');
    addMsg('user', clean);
    setThinking(true);
    let reply = '';
    let readout = '';
    let replyLang = '';
    try {
      const c = ctxRef.current;
      const res = await api<ChatReply>('/assistant/chat', {
        method: 'POST',
        json: { message: clean, history: histRef.current.slice(-8).map(m => ({ role: m.role, text: m.text })), runId: c.runId, model: c.model },
      });
      reply = res.reply;
      readout = res.readout || '';
      replyLang = res.lang || '';
      reply += await handleAction(res);
    } catch (e) {
      reply = e instanceof Error ? e.message : 'Something went wrong.';
    }
    setThinking(false);
    addMsg('assistant', reply);
    await speakText(reply, replyLang || undefined);
    if (readout) await speakText(readout, replyLang || undefined);
    busyRef.current = false;
    missesRef.current = 0;
    resume();
  }, [killRec, resume, stopSpeaking, addMsg, speakText, handleAction]);

  useEffect(() => { processRef.current = process; }, [process]);

  const listen = useCallback(async (kind: 'command' | 'wake') => {
    killRec();
    setError('');
    const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;

    const wanted = prefsRef.current.sttLang;
    const anyLanguage = kind === 'command' && wanted === 'auto' && (whisperRef.current !== false || !Ctor);   // no Whisper installed: fall back to English live recognition   // offline Whisper listens in any language
    if (Ctor && !anyLanguage) {
      const rec = new Ctor();
      rec.lang = kind === 'wake' || wanted === 'auto' ? 'en-US' : wanted;   // the wake word "Adion" is always listened for in English
      rec.interimResults = true;
      rec.continuous = kind === 'wake';
      let silenceTimer: ReturnType<typeof setTimeout> | null = null;
      let captured = '';
      let fired = false;
      const clear = () => { if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; } };
      const fire = (text: string) => {
        if (fired) return;
        fired = true; clear();
        processRef.current(text);
      };

      rec.onresult = e => {
        if (kind === 'wake') {
          for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            setTranscript(t);
            if (!e.results[i].isFinal) continue;
            const m = WAKE.exec(t);
            if (!m || fired) continue;
            fired = true;
            killRec();
            const cmd = m[1].trim();
            if (cmd.length > 2) processRef.current(cmd);
            else { busyRef.current = true; speakText('Yes?').then(() => { busyRef.current = false; sessionRef.current = true; missesRef.current = 0; listenRef.current('command'); }); }
          }
          return;
        }
        let text = ''; let isFinal = false;
        for (let i = 0; i < e.results.length; i++) {
          text += e.results[i][0].transcript;
          if (e.results[i].isFinal) isFinal = true;
        }
        captured = text; setTranscript(text);
        clear();
        if (text.trim().length > 3) {
          if (isFinal) fire(text);
          else silenceTimer = setTimeout(() => fire(captured), 1200);     // paused for 1.2s: go
        }
      };
      rec.onerror = e => {
        clear();
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
          setError('Microphone blocked. Allow it in the browser address bar.');
          setWake(false); wakeRef.current = false; sessionRef.current = false; setActive(false);
        }
      };
      rec.onend = () => {
        clear();
        if (recRef.current !== rec) return;
        recRef.current = null;
        setActive(false);
        if (fired) return;
        const spoken = captured.trim();
        if (kind === 'command') {
          if (spoken.length > 2) { fired = true; processRef.current(spoken); return; }
          missesRef.current++;                                              // silence: try once more, then stop
          if (convRef.current && sessionRef.current && missesRef.current < 2 && !busyRef.current) listenRef.current('command');
          else sessionRef.current = false;
        } else if (wakeRef.current && !busyRef.current) {
          setTimeout(() => { if (wakeRef.current && !busyRef.current && !recRef.current) listenRef.current('wake'); }, 300);
        }
      };
      recRef.current = rec;
      try { rec.start(); setActive(true); setTranscript(''); } catch { setError('Could not start the microphone'); }
      return;
    }

    // Any language (or Firefox/Safari): record until you stop talking, then Whisper on this PC transcribes it and tells the language
    if (kind === 'wake') { setError('Wake word needs Chrome or Edge. Use the mic button instead.'); setWake(false); wakeRef.current = false; return; }
    if (!navigator.mediaDevices?.getUserMedia) { setError('Microphone unavailable in this browser'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const actx = new AC();
      const analyser = actx.createAnalyser(); analyser.fftSize = 1024;
      actx.createMediaStreamSource(stream).connect(analyser);
      const samples = new Float32Array(analyser.fftSize);
      const chunks: Blob[] = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      let heard = false, stopped = false;
      const startedAt = Date.now();
      let quietSince = startedAt;
      const finish = () => { if (stopped) return; stopped = true; clearInterval(timer); if (mr.state !== 'inactive') mr.stop(); };
      const timer = setInterval(() => {
        analyser.getFloatTimeDomainData(samples);
        let sum = 0;
        for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
        const now = Date.now();
        if (Math.sqrt(sum / samples.length) > 0.02) { heard = true; quietSince = now; }
        if (heard && now - quietSince > 1400) finish();            // you stopped talking
        else if (!heard && now - startedAt > 7000) finish();       // nobody said anything
        else if (now - startedAt > 25000) finish();
      }, 120);
      const release = () => { clearInterval(timer); stream.getTracks().forEach(t => t.stop()); actx.close().catch(() => { /* closed */ }); vadCleanupRef.current = () => {}; };
      vadCleanupRef.current = () => { stopped = true; mr.onstop = null; if (mr.state !== 'inactive') mr.stop(); release(); };
      mr.onstop = async () => {
        release();
        setActive(false);
        if (!heard) {
          missesRef.current++;
          if (convRef.current && sessionRef.current && missesRef.current < 2 && !busyRef.current) listenRef.current('command'); else sessionRef.current = false;
          return;
        }
        setTranscript('Understanding what you said…');
        try {
          const fd = new FormData();
          fd.append('audio', new Blob(chunks, { type: mr.mimeType }), 'speech.webm');
          const fixed = prefsRef.current.sttLang;
          if (fixed && fixed !== 'auto') fd.append('language', fixed);
          if (lastLangRef.current) fd.append('hint', lastLangRef.current);
          const r = await api<{ text: string; language: string }>('/voice/transcribe', { method: 'POST', body: fd });
          if (r.language) lastLangRef.current = r.language;
          setTranscript('');
          if (r.text.trim().length > 1) await processRef.current(r.text);
          else { missesRef.current++; if (convRef.current && sessionRef.current && missesRef.current < 2 && !busyRef.current) listenRef.current('command'); else sessionRef.current = false; }
        } catch (e) { setTranscript(''); setError(e instanceof Error ? e.message : 'Transcription failed'); }
      };
      mediaRef.current = mr;
      mr.start(250); setActive(true); setTranscript('Listening, speak in any language…');
    } catch { setError('Microphone unavailable or permission denied'); }
  }, [killRec, speakText]);

  useEffect(() => { listenRef.current = listen; }, [listen]);

  // ───────── controls ─────────
  const toggleVoiceListening = useCallback(() => {
    if (isVoiceActive || isSpeaking || isThinking) {
      // barge-in / stop everything
      stopSpeaking(); killRec();
      sessionRef.current = false; busyRef.current = false;
      if (wakeRef.current) { wakeRef.current = false; setWake(false); }
      setThinking(false);
      return;
    }
    sessionRef.current = true; missesRef.current = 0;
    listenRef.current('command');
  }, [isVoiceActive, isSpeaking, isThinking, stopSpeaking, killRec]);

  const toggleWakeWord = useCallback(() => {
    const next = !wakeRef.current;
    wakeRef.current = next; setWake(next);
    if (next) { speakText('Wake word on. Just say Adion.').then(() => { if (wakeRef.current) listenRef.current('wake'); }); }
    else { killRec(); sessionRef.current = false; }
  }, [killRec, speakText]);

  const toggleAudioReply = useCallback(() => {
    const next = !audioRef.current;
    audioRef.current = next; setAudio(next); savePrefs(autoRef.current, next, convRef.current);
    if (next) speakText('Audio reply enabled.'); else stopSpeaking();
  }, [speakText, stopSpeaking]);

  const toggleAutoProcessVoice = useCallback(() => {
    const next = !autoRef.current;
    autoRef.current = next; setAuto(next); savePrefs(next, audioRef.current, convRef.current);
    speakText(next ? 'I will start builds as soon as you ask.' : 'I will wait for you to press run.');
  }, [speakText]);

  const toggleConversationMode = useCallback(() => {
    const next = !convRef.current;
    convRef.current = next; setConv(next); savePrefs(autoRef.current, audioRef.current, next);
    speakText(next ? 'Hands-free conversation on.' : 'Hands-free conversation off.');
  }, [speakText]);

  const sendText = useCallback((text: string) => { processRef.current(text); }, []);
  const clearMessages = useCallback(() => setMessages([]), []);

  // global hotkeys: Alt+V or Ctrl+Space
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.altKey && e.code === 'KeyV') || (e.ctrlKey && e.code === 'Space')) {
        e.preventDefault();
        toggleVoiceListening();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggleVoiceListening]);

  // stop the mic and speech when the page is closed
  useEffect(() => () => { killRec(); if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel(); }, [killRec]);

  // ───────── announce build progress (only runs we watched live, never when browsing history) ─────────
  const liveSeen = useRef<Set<string>>(new Set());
  const announced = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!snap) return;
    const { run, tasks } = snap;
    if (['planning', 'running', 'awaiting_input', 'awaiting_approval'].includes(run.status)) liveSeen.current.add(run.id);
    if (!liveSeen.current.has(run.id)) return;
    let key = ''; let text = '';
    if (run.status === 'awaiting_approval') {
      key = 'review'; text = `I have a plan with ${run.plan.modules?.length ?? 0} parts. Take a look and press Start building when you are happy.`;
    } else if (run.status === 'awaiting_input') {
      key = `ask${run.questions.filter(q => !q.answer).map(q => q.id).join('')}`; text = 'I need a quick answer from you before I continue.';
    } else if (run.status === 'running' && tasks.length > 0) {
      key = 'plan'; text = `Plan ready. ${tasks.filter(t => t.kind === 'module').length} agents are working in parallel.`;
    } else if (run.status === 'completed' && !tasks.some(t => t.status === 'running')) {
      key = 'done'; text = `Build complete! ${tasks.reduce((n, t) => n + t.fileCount, 0)} files created and saved to your folder.`;
      if (run.error) text += ' One check needs your attention.';
    } else if (run.status === 'failed' && !tasks.some(t => t.status === 'running')) {
      key = 'failed'; text = 'The build hit a problem. Check the agent map for details.';
    } else if (run.status === 'cancelled') { key = 'cancelled'; text = 'Run cancelled.'; }
    if (!key || announced.current.has(`${run.id}:${key}`)) return;
    announced.current.add(`${run.id}:${key}`);
    if (busyRef.current) return;                        // never talk over a conversation
    const wasWake = wakeRef.current && !!recRef.current;
    if (wasWake) killRec();
    speakText(text).then(() => { if (wasWake && wakeRef.current && !busyRef.current) listenRef.current('wake'); });
  }, [snap, speakText, killRec]);

  return (
    <Ctx.Provider value={{
      isVoiceActive, isThinking, isSpeaking, voiceTranscript, voiceError, messages, isAutoProcessVoice,
      isAudioReplyEnabled, isWakeWordEnabled, isConversationMode, toggleVoiceListening, toggleAutoProcessVoice,
      toggleAudioReply, toggleWakeWord, toggleConversationMode, sendText, speakText, stopSpeaking, clearMessages,
      voicePrefs, setVoicePrefs, voiceStatus, voiceSettingsOpen, setVoiceSettingsOpen, previewVoice,
    }}>
      {children}
    </Ctx.Provider>
  );
}
