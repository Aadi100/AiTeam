'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { ShieldCheck, Cpu, HardDrive, UserPlus, Settings, ExternalLink, Radio, Mic, MicOff, Volume2, VolumeX, History } from 'lucide-react';

export default function CockpitHeader() {
  const {
    targetPath,
    project,
    openFolderInExplorer,
    setIsAISettingsOpen,
    setIsAddPersonOpen,
    isHistoryOpen,
    setIsHistoryOpen,
    history,
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
            <span className="flex items-center gap-1 text-emerald-400">
              <ShieldCheck className="w-3 h-3" /> MongoDB Connected
            </span>
            <span>•</span>
            <span className="text-slate-300 font-medium">{people.length} People in Office</span>
            <span>•</span>
            <span className="text-cyan-400 font-mono text-[10px] bg-cyan-950/60 px-1.5 py-0.2 rounded border border-cyan-800/40">
              Free Open-Source Default
            </span>
          </p>
        </div>
      </div>

      {/* Target PC Disk Uplink Badge */}
      <div className="hidden md:flex items-center gap-2 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
        <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-slate-400">Target PC:</span>
        <span className="font-mono text-slate-200 max-w-[200px] xl:max-w-[280px] truncate" title={targetPath}>
          {targetPath}
        </span>
        {project.status === 'completed' && (
          <button
            onClick={() => openFolderInExplorer()}
            className="ml-1 text-cyan-400 hover:text-cyan-300 flex items-center gap-1 hover:underline text-[11px] cursor-pointer"
            title="Open in Windows Explorer"
          >
            <span>Open</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        )}
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

        {/* Mission Archive / History Button */}
        <button
          onClick={() => setIsHistoryOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700/70 text-slate-200 text-xs font-semibold shadow transition-all hover:border-slate-600 cursor-pointer"
          title="View all previously generated projects and reuse them"
        >
          <History className="w-3.5 h-3.5 text-cyan-400" />
          <span className="hidden sm:inline">History</span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">
            {history.length}
          </span>
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
