'use client';

import React, { useState, useEffect } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Mic, MicOff, Send, Sparkles, Play, Loader2, ArrowRight } from 'lucide-react';

export default function VoiceChatConsole() {
  const {
    targetPath,
    executeParallelBuild,
    isExecuting,
    isVoiceActive,
    voiceTranscript,
    toggleVoiceListening,
    isAutoProcessVoice
  } = useOffice();

  const [prompt, setPrompt] = useState<string>('Create a simple notes website with dark mode, tags, and search');

  // Sync voice transcript to prompt when speaking
  useEffect(() => {
    if (voiceTranscript) {
      setPrompt(voiceTranscript);
    }
  }, [voiceTranscript]);

  const handleRun = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || isExecuting) return;

    await executeParallelBuild(prompt, targetPath);
  };

  const quickPrompts = [
    'Create a simple notes website with dark mode, tags, and search',
    'Build a Task Manager app with priority badges and local storage',
    'Create a Portfolio website with project showcase and contact form',
    'Build a Markdown Documentation viewer with search and syntax highlighting'
  ];

  return (
    <div className="bg-gradient-to-b from-slate-900/90 to-slate-950/95 border border-cyan-500/30 rounded-2xl p-5 shadow-2xl backdrop-blur-xl relative overflow-hidden">
      {/* Glowing Ambient Backdrop Accent */}
      <div className="absolute top-0 right-1/4 w-96 h-32 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-0 left-1/4 w-96 h-32 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>


      {/* Auto-Process Status Sub-bar */}
      <div className="relative z-10 mb-2 flex items-center justify-between px-1 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono uppercase text-slate-400 font-semibold tracking-wider">
            DIRECTIVE CONSOLE:
          </span>
          {isAutoProcessVoice && (
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800/60 flex items-center gap-1.5 shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Auto-Process Voice: Active (Hands-Free)
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-400 hidden sm:inline font-mono">
          Speaks &amp; processes automatically • Press Enter to run
        </span>
      </div>

      {/* Dual Voice & Chat Command Console */}
      <form onSubmit={handleRun} className="relative z-10 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Big Glowing Microphone Button (Voice Input) */}
          <button
            type="button"
            onClick={toggleVoiceListening}
            className={`relative flex items-center justify-center p-3 sm:px-4 rounded-xl border transition-all cursor-pointer ${
              isVoiceActive
                ? 'bg-rose-500/20 border-rose-500 text-rose-300 shadow-[0_0_20px_rgba(244,63,94,0.4)] animate-pulse'
                : 'bg-slate-900 hover:bg-slate-800 border-slate-700 text-slate-300 hover:text-cyan-400'
            }`}
            title={isVoiceActive ? 'Listening... Speak and it will process automatically' : 'Click to speak directive (Auto-processes without button click)'}
          >
            <div className="flex items-center gap-2">
              {isVoiceActive ? (
                <>
                  <MicOff className="w-5 h-5 text-rose-400" />
                  <span className="text-xs font-mono font-bold text-rose-400">LISTENING...</span>
                </>
              ) : (
                <>
                  <Mic className="w-5 h-5 text-cyan-400" />
                  <span className="text-xs font-mono font-medium hidden sm:inline">VOICE</span>
                </>
              )}
            </div>
          </button>

          {/* Text Input Prompt */}
          <div className="flex-1 relative">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isVoiceActive ? 'Listening to voice... will process automatically' : "Speak or type: 'Create a simple notes website'..."}
              disabled={isExecuting}
              className="w-full bg-slate-950/90 border border-slate-700 focus:border-cyan-400 rounded-xl px-4 py-3.5 text-sm text-white placeholder-slate-500 focus:outline-none shadow-inner font-sans"
            />
            {isVoiceActive && (
              <span className="absolute right-3 top-3.5 flex items-center gap-1.5 text-xs text-cyan-400 font-mono bg-slate-900/90 px-2 py-0.5 rounded border border-cyan-800">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
                Auto-processing on silence
              </span>
            )}
          </div>

          {/* Deploy Squad Button */}
          <button
            type="submit"
            disabled={isExecuting || !prompt.trim()}
            className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-emerald-500 hover:from-cyan-400 hover:to-emerald-400 text-white font-bold text-sm shadow-xl shadow-cyan-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shrink-0"
          >
            {isExecuting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>Squad Working...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>Deploy Squad</span>
                <ArrowRight className="w-4 h-4 opacity-70" />
              </>
            )}
          </button>
        </div>

        {/* Quick Example Prompt Chips */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-[11px] text-slate-500 font-mono">Try Example:</span>
          {quickPrompts.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setPrompt(p)}
              className="text-xs bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/50 text-slate-400 hover:text-cyan-300 px-3 py-1 rounded-lg transition-all text-left"
            >
              {p}
            </button>
          ))}
        </div>
      </form>
    </div>
  );
}
