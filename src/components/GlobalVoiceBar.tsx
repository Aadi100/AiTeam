'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Ear, EarOff, MessageSquare, Repeat, Send, X, Loader2 } from 'lucide-react';
import { useVoice } from '@/context/VoiceContext';
import { useApp } from '@/context/AppContext';
import VoiceOrb from '@/components/VoiceOrb';

export default function GlobalVoiceBar() {
  const {
    isVoiceActive, isThinking, isSpeaking, voiceTranscript, voiceError, messages,
    isAudioReplyEnabled, isAutoProcessVoice, isWakeWordEnabled, isConversationMode,
    toggleVoiceListening, toggleAudioReply, toggleWakeWord, toggleConversationMode,
    sendText, stopSpeaking, clearMessages,
  } = useVoice();
  const { snap } = useApp();
  const executing = !!snap && ['planning', 'running'].includes(snap.run.status);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, open, isThinking]);

  const busy = isVoiceActive || isThinking || isSpeaking;
  const status = isVoiceActive ? 'Listening…' : isThinking ? 'Thinking…' : isSpeaking ? 'Speaking…' : isWakeWordEnabled ? 'Say “Adion”' : 'Adion';

  const send = () => { const t = text.trim(); if (t) { sendText(t); setText(''); } };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2">
      {/* Conversation panel */}
      {open && (
        <div className="w-[calc(100vw-2.5rem)] sm:w-96 h-[26rem] rounded-2xl border border-slate-700 bg-slate-950/95 backdrop-blur-xl shadow-2xl flex flex-col animate-fade-in">
          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <VoiceOrb isActive={busy} size={30} />
              <div>
                <p className="text-sm font-semibold leading-none">Adion</p>
                <p className="text-[10px] text-slate-400 font-mono mt-0.5">{status}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-slate-400">
              <button onClick={clearMessages} className="hover:text-white">clear</button>
              <button onClick={() => setOpen(false)} className="hover:text-white"><X className="h-4 w-4" /></button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {messages.length === 0 && (
              <p className="text-xs text-slate-500 leading-relaxed">
                Ask me anything: &ldquo;how is the build going?&rdquo;, &ldquo;read the README&rdquo;, &ldquo;remember I like dark themes&rdquo;,
                or &ldquo;build me a notes app&rdquo;. Press the mic or say <b>Adion</b> with the ear on.
              </p>
            )}
            {messages.map(m => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed ${m.role === 'user' ? 'bg-cyan-600/90 text-white' : 'bg-slate-800 text-slate-100'}`}>
                  {m.text}
                </div>
              </div>
            ))}
            {isThinking && <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-3 w-3 animate-spin" /> thinking…</div>}
            <div ref={endRef} />
          </div>
          <div className="flex gap-2 p-2 border-t border-slate-800">
            <input value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') send(); }}
              placeholder="Type to Adion…" className="flex-1 rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500" />
            <button onClick={send} disabled={!text.trim()} className="rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-2.5"><Send className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        {/* Live transcript bubble */}
        {(isVoiceActive || voiceError) && !open && (
          <div className="bg-slate-900/95 border border-cyan-500/60 rounded-2xl px-4 py-2.5 shadow-2xl backdrop-blur-xl flex items-center gap-3 animate-fade-in max-w-sm sm:max-w-md">
            <div className="flex items-center gap-1">
              <span className="w-1.5 h-3 bg-cyan-400 rounded-full animate-bounce"></span>
              <span className="w-1.5 h-5 bg-cyan-400 rounded-full animate-bounce delay-75"></span>
              <span className="w-1.5 h-2.5 bg-cyan-400 rounded-full animate-bounce delay-150"></span>
            </div>
            <div className="overflow-hidden">
              <div className="flex items-center gap-2">
                <p className="text-[10px] font-mono uppercase text-cyan-400 font-bold">{voiceError ? 'Voice problem' : 'Adion is listening…'}</p>
                {isAutoProcessVoice && !voiceError && (
                  <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/80 px-1.5 rounded border border-emerald-800/60">⚡ Auto</span>
                )}
              </div>
              <p className={`text-xs truncate max-w-xs font-sans mt-0.5 ${voiceError ? 'text-rose-300' : 'text-white'}`}>
                {voiceError || voiceTranscript || 'Say: "Build me a simple notes website"'}
              </p>
            </div>
          </div>
        )}

        {/* Floating controller dock */}
        <div className="bg-slate-900/90 border border-slate-700/80 hover:border-cyan-500/60 rounded-2xl p-1.5 shadow-2xl backdrop-blur-xl flex items-center gap-1.5 transition-all">
          <button onClick={() => setOpen(o => !o)} title="Chat with Adion"
            className={`p-2.5 rounded-xl cursor-pointer ${open ? 'bg-cyan-900/60 text-cyan-200' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}>
            <MessageSquare className="w-4 h-4" />
          </button>
          <button onClick={toggleWakeWord} title={isWakeWordEnabled ? 'Wake word ON: just say “Adion” (click to turn off)' : 'Turn on wake word: say “Adion” any time (Chrome/Edge)'}
            className={`p-2.5 rounded-xl cursor-pointer ${isWakeWordEnabled ? 'bg-emerald-900/60 text-emerald-300 ring-1 ring-emerald-500/60' : 'bg-slate-800/40 text-slate-500 hover:text-slate-300'}`}>
            {isWakeWordEnabled ? <Ear className="w-4 h-4" /> : <EarOff className="w-4 h-4" />}
          </button>
          <button onClick={toggleConversationMode} title={isConversationMode ? 'Hands-free conversation ON: I keep listening after I answer' : 'Hands-free conversation OFF: one question at a time'}
            className={`p-2.5 rounded-xl cursor-pointer hidden sm:block ${isConversationMode ? 'bg-slate-800 text-cyan-300 hover:bg-slate-700' : 'bg-slate-800/40 text-slate-500 hover:text-slate-300'}`}>
            <Repeat className="w-4 h-4" />
          </button>
          <button onClick={isSpeaking ? stopSpeaking : toggleAudioReply}
            title={isSpeaking ? 'Stop talking' : isAudioReplyEnabled ? 'Spoken replies ON (click to mute)' : 'Spoken replies MUTED (click to enable)'}
            className={`p-2.5 rounded-xl cursor-pointer ${isAudioReplyEnabled ? 'bg-slate-800 text-cyan-300 hover:bg-slate-700' : 'bg-slate-800/40 text-slate-500 hover:text-slate-300'}`}>
            {isAudioReplyEnabled ? <Volume2 className={`w-4 h-4 ${isSpeaking ? 'animate-pulse' : ''}`} /> : <VolumeX className="w-4 h-4" />}
          </button>

          <button onClick={toggleVoiceListening}
            title={busy ? 'Stop (Alt+V)' : 'Talk to Adion (Alt+V or Ctrl+Space)'}
            className={`relative p-3 rounded-xl font-bold flex items-center gap-2 transition-all cursor-pointer ${
              busy
                ? 'bg-gradient-to-r from-rose-500 to-pink-600 text-white shadow-[0_0_25px_rgba(244,63,94,0.6)] animate-pulse'
                : executing
                ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                : 'bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 hover:from-cyan-400 hover:to-emerald-400 text-white shadow-lg shadow-cyan-500/25'
            }`}>
            {busy ? (<><MicOff className="w-4 h-4" /><span className="text-xs font-mono tracking-wider font-extrabold pr-1">STOP</span></>)
                  : (<><Mic className="w-4 h-4" /><span className="text-xs font-mono tracking-wider font-extrabold pr-1">ADION</span></>)}
            <span className="hidden sm:inline-block text-[9px] font-mono bg-black/40 px-1.5 py-0.5 rounded text-white/80 border border-white/20">Alt+V</span>
          </button>
        </div>
      </div>
    </div>
  );
}
