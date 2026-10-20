'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Mic, MicOff, Volume2, VolumeX, Sparkles, Radio } from 'lucide-react';

export default function GlobalVoiceBar() {
  const {
    isVoiceActive,
    toggleVoiceListening,
    voiceTranscript,
    isAudioReplyEnabled,
    toggleAudioReply,
    isExecuting,
    isAutoProcessVoice
  } = useOffice();

  return (
    <div className="fixed bottom-5 right-5 z-50 flex items-center gap-2">
      {/* Speech Transcript Floating Bubble (when speaking) */}
      {isVoiceActive && (
        <div className="bg-slate-900/95 border border-cyan-500/60 rounded-2xl px-4 py-2.5 shadow-2xl backdrop-blur-xl flex items-center gap-3 animate-fade-in max-w-sm sm:max-w-md">
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-3 bg-cyan-400 rounded-full animate-bounce"></span>
            <span className="w-1.5 h-5 bg-cyan-400 rounded-full animate-bounce delay-75"></span>
            <span className="w-1.5 h-2.5 bg-cyan-400 rounded-full animate-bounce delay-150"></span>
          </div>
          <div className="overflow-hidden">
            <div className="flex items-center gap-2">
              <p className="text-[10px] font-mono uppercase text-cyan-400 font-bold">
                Listening to voice...
              </p>
              {isAutoProcessVoice && (
                <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/80 px-1.5 py-0.2 rounded border border-emerald-800/60 flex items-center gap-1">
                  ⚡ Auto-Process
                </span>
              )}
            </div>
            <p className="text-xs text-white truncate max-w-xs font-sans mt-0.5">
              {voiceTranscript || 'Say: "Create a simple notes website"'}
            </p>
          </div>
        </div>
      )}

      {/* Floating Controller Dock */}
      <div className="bg-slate-900/90 border border-slate-700/80 hover:border-cyan-500/60 rounded-2xl p-1.5 shadow-2xl backdrop-blur-xl flex items-center gap-1.5 transition-all">
        {/* Audio Speech Reply Toggle (Mute / Unmute audio responses) */}
        <button
          onClick={toggleAudioReply}
          className={`p-2.5 rounded-xl transition-all cursor-pointer ${
            isAudioReplyEnabled
              ? 'bg-slate-800 text-cyan-300 hover:bg-slate-700'
              : 'bg-slate-800/40 text-slate-500 hover:text-slate-300'
          }`}
          title={isAudioReplyEnabled ? 'Audio Speech Reply is ON (Click to Mute)' : 'Audio Speech Reply is MUTED (Click to Enable)'}
        >
          {isAudioReplyEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Global Glowing Microphone Button */}
        <button
          onClick={toggleVoiceListening}
          className={`relative p-3 rounded-xl font-bold flex items-center gap-2 transition-all cursor-pointer ${
            isVoiceActive
              ? 'bg-gradient-to-r from-rose-500 to-pink-600 text-white shadow-[0_0_25px_rgba(244,63,94,0.6)] animate-pulse'
              : isExecuting
              ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
              : 'bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 hover:from-cyan-400 hover:to-emerald-400 text-white shadow-lg shadow-cyan-500/25'
          }`}
          title={isVoiceActive ? 'Listening... Speak and it will automatically build on pause' : 'Global Voice AI (Click or press Alt+V to speak - Auto-processes hands-free)'}
        >
          {isVoiceActive ? (
            <>
              <MicOff className="w-4 h-4 animate-spin" />
              <span className="text-xs font-mono tracking-wider font-extrabold pr-1">STOP VOICE</span>
            </>
          ) : (
            <>
              <Mic className="w-4 h-4" />
              <span className="text-xs font-mono tracking-wider font-extrabold pr-1">VOICE AI</span>
            </>
          )}

          {/* Hotkey Badge */}
          <span className="hidden sm:inline-block text-[9px] font-mono bg-black/40 px-1.5 py-0.5 rounded text-white/80 border border-white/20">
            Alt+V
          </span>
        </button>
      </div>
    </div>
  );
}
