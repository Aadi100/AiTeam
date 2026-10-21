'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Cpu, UserPlus, Settings, Radio, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';

export default function CockpitHeader() {
  const {
    setIsAISettingsOpen,
    setIsAddPersonOpen,
    people,
    isVoiceActive,
    toggleVoiceListening,
    isAudioReplyEnabled,
    toggleAudioReply
  } = useOffice();

  return (
    <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl sticky top-0 z-40 px-4 lg:px-8 py-3.5 flex flex-wrap items-center justify-between gap-4">
      {/* Brand & Orbital Status */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-600 to-emerald-500 p-0.5 shadow-lg shadow-cyan-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
            </div>
          </div>
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-slate-950 animate-ping"></span>
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-slate-950"></span>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-extrabold tracking-wider text-white uppercase flex items-center gap-1.5">
              <span>DEVSQUAD</span>
              <span className="text-cyan-400 font-mono text-xs px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/50">
                ORBITAL COCKPIT
              </span>
            </h1>
          </div>
          <p className="text-[11px] text-slate-400 flex items-center gap-2">
            <span className="text-slate-300 font-medium">{people.length} People in Office</span>
            <span>•</span>
            <span className="text-cyan-400 font-mono text-[10px] bg-cyan-950/60 px-1.5 py-0.2 rounded border border-cyan-800/40">
              Free Open-Source Default
            </span>
          </p>
        </div>
      </div>


      {/* Controls & Voice Triggers */}
      <div className="flex items-center gap-2.5">
        {/* Audio Speech Reply Toggle Button */}
        <button
          onClick={toggleAudioReply}
          className={`p-2 rounded-xl border transition-all cursor-pointer ${
            isAudioReplyEnabled
              ? 'bg-slate-900 text-cyan-400 border-cyan-500/50 shadow-sm shadow-cyan-500/20'
              : 'bg-slate-900/60 text-slate-500 border-slate-800 hover:text-slate-300'
          }`}
          title={isAudioReplyEnabled ? 'Voice Audio Reply is ON (Click to Mute)' : 'Voice Audio Reply is MUTED (Click to Enable)'}
        >
          {isAudioReplyEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Global Voice Mic Button in Header */}
        <button
          onClick={toggleVoiceListening}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer ${
            isVoiceActive
              ? 'bg-rose-500 text-white shadow-[0_0_15px_rgba(244,63,94,0.6)] animate-pulse'
              : 'bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-cyan-400 border border-slate-700/80'
          }`}
          title="Click to give voice command (or press Alt+V)"
        >
          {isVoiceActive ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5 text-cyan-400" />}
          <span className="hidden sm:inline">{isVoiceActive ? 'LISTENING' : 'VOICE'}</span>
        </button>

        {/* Add Person Button */}
        <button
          onClick={() => setIsAddPersonOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/70 text-slate-200 text-xs font-semibold shadow transition-all hover:border-slate-600 cursor-pointer"
        >
          <UserPlus className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden sm:inline">Add Person</span>
        </button>

        {/* AI Setup & Keys Button */}
        <button
          onClick={() => setIsAISettingsOpen(true)}
          className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-cyan-500/20 transition-all cursor-pointer"
        >
          <Cpu className="w-3.5 h-3.5 text-cyan-200" />
          <span className="hidden md:inline">AI Setup & Keys</span>
          <Settings className="w-3.5 h-3.5 opacity-70" />
        </button>
      </div>
    </header>
  );
}
