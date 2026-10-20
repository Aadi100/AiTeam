'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Radio, Satellite, HardDrive, Wifi, Sparkles, Activity } from 'lucide-react';

export default function SatelliteRadar() {
  const { people, project, targetPath, isExecuting, aiKeys, setIsAISettingsOpen } = useOffice();
  const [hoveredStation, setHoveredStation] = useState<string | null>(null);

  const michael = people.find((p) => p.id === 'michael');
  const dave = people.find((p) => p.id === 'dave');
  const sarah = people.find((p) => p.id === 'sarah');

  return (
    <div className="relative bg-slate-900/60 border border-slate-800/90 rounded-2xl p-5 overflow-hidden shadow-2xl backdrop-blur-md">
      {/* Background Grid Pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b0f_1px,transparent_1px),linear-gradient(to_bottom,#1e293b0f_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none"></div>

      {/* Top Telemetry Header */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 mb-4 border-b border-slate-800/60 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping"></div>
          <h2 className="text-xs font-bold tracking-widest uppercase text-cyan-300 flex items-center gap-2">
            <Satellite className="w-3.5 h-3.5 text-cyan-400" />
            <span>ORBITAL SATELLITE RADAR & TEAM TRACKER</span>
          </h2>
        </div>

        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            RADAR LOCK: ACTIVE
          </span>
          <span className="hidden sm:inline text-slate-600">|</span>
          <span className="hidden sm:flex items-center gap-1 text-cyan-400">
            <Activity className="w-3 h-3" />
            PARALLEL SYNC: {isExecuting ? 'TRANSMITTING' : 'IDLE'}
          </span>
        </div>
      </div>

      {/* Main Radar Screen Layout */}
      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        {/* Left: The Circular Radar Canvas */}
        <div className="lg:col-span-7 flex justify-center py-2">
          <div className="relative w-64 h-64 sm:w-72 sm:h-72 md:w-80 md:h-80 rounded-full border border-cyan-500/30 bg-slate-950/90 shadow-[0_0_50px_rgba(6,182,212,0.15)] flex items-center justify-center overflow-hidden">
            {/* Concentric Radar Rings */}
            <div className="absolute w-[85%] h-[85%] rounded-full border border-cyan-500/20"></div>
            <div className="absolute w-[65%] h-[65%] rounded-full border border-cyan-500/15 border-dashed"></div>
            <div className="absolute w-[45%] h-[45%] rounded-full border border-cyan-500/25"></div>
            <div className="absolute w-[25%] h-[25%] rounded-full border border-cyan-500/30 border-dashed"></div>

            {/* Crosshair Lines */}
            <div className="absolute w-full h-[1px] bg-cyan-500/20"></div>
            <div className="absolute h-full w-[1px] bg-cyan-500/20"></div>
            <div className="absolute w-full h-[1px] bg-cyan-500/10 rotate-45"></div>
            <div className="absolute w-full h-[1px] bg-cyan-500/10 -rotate-45"></div>

            {/* 360° Rotating Radar Sweep Line */}
            <div className="absolute inset-0 origin-center animate-[spin_4s_linear_infinite] pointer-events-none">
              <div className="w-1/2 h-1/2 bg-gradient-to-br from-cyan-400/25 via-cyan-400/5 to-transparent origin-bottom-right rounded-tl-full"></div>
            </div>

            {/* Center Ground Node: User's PC Hard Drive */}
            <div
              className="relative z-20 flex flex-col items-center justify-center p-2 rounded-xl bg-slate-900 border border-cyan-500/40 shadow-lg cursor-pointer hover:border-cyan-400 transition-all"
              onMouseEnter={() => setHoveredStation('pc')}
              onMouseLeave={() => setHoveredStation(null)}
            >
              <HardDrive className={`w-5 h-5 ${isExecuting ? 'text-amber-400 animate-bounce' : 'text-cyan-400'}`} />
              <span className="text-[9px] font-mono font-bold text-slate-300 mt-0.5">LOCAL PC</span>
            </div>

            {/* Blip 1: Station Alpha - Michael (Frontend Specialist) */}
            <div
              className="absolute top-[22%] right-[22%] z-20 group cursor-pointer"
              onMouseEnter={() => setHoveredStation('michael')}
              onMouseLeave={() => setHoveredStation(null)}
            >
              <div className="relative">
                <div className={`w-7 h-7 rounded-full bg-cyan-500/20 border-2 ${michael?.status === 'coding' ? 'border-cyan-400 animate-ping' : 'border-cyan-500'} flex items-center justify-center text-xs shadow-lg shadow-cyan-500/40`}>
                  💻
                </div>
                <div className="absolute -bottom-5 -left-4 bg-slate-950/90 border border-cyan-500/50 rounded px-1.5 py-0.5 text-[9px] font-mono text-cyan-300 whitespace-nowrap">
                  MICHAEL // FE
                </div>
              </div>
            </div>

            {/* Blip 2: Station Beta - Dave (Backend Specialist) */}
            <div
              className="absolute bottom-[24%] left-[20%] z-20 group cursor-pointer"
              onMouseEnter={() => setHoveredStation('dave')}
              onMouseLeave={() => setHoveredStation(null)}
            >
              <div className="relative">
                <div className={`w-7 h-7 rounded-full bg-emerald-500/20 border-2 ${dave?.status === 'coding' ? 'border-emerald-400 animate-ping' : 'border-emerald-500'} flex items-center justify-center text-xs shadow-lg shadow-emerald-500/40`}>
                  ⚙️
                </div>
                <div className="absolute -bottom-5 -left-4 bg-slate-950/90 border border-emerald-500/50 rounded px-1.5 py-0.5 text-[9px] font-mono text-emerald-300 whitespace-nowrap">
                  DAVE // BE
                </div>
              </div>
            </div>

            {/* Blip 3: Station Gamma - Sarah (QA & UX) */}
            {sarah && (
              <div
                className="absolute top-[28%] left-[22%] z-20 group cursor-pointer"
                onMouseEnter={() => setHoveredStation('sarah')}
                onMouseLeave={() => setHoveredStation(null)}
              >
                <div className="relative">
                  <div className="w-6 h-6 rounded-full bg-purple-500/20 border border-purple-400 flex items-center justify-center text-[10px] shadow-lg shadow-purple-500/30">
                    🎨
                  </div>
                  <div className="absolute -bottom-4 -left-3 bg-slate-950/90 border border-purple-500/40 rounded px-1 py-0.2 text-[8px] font-mono text-purple-300 whitespace-nowrap">
                    SARAH // QA
                  </div>
                </div>
              </div>
            )}

            {/* Blip 4: AI Satellite Uplink (Gemini / Claude / OpenAI) */}
            <div
              className="absolute top-[12%] left-[45%] z-20 group cursor-pointer"
              onClick={() => setIsAISettingsOpen(true)}
              title="Click to configure AI Satellite Uplinks"
            >
              <div className="relative flex flex-col items-center">
                <div className="w-5 h-5 rounded-full bg-indigo-500/30 border border-indigo-400 flex items-center justify-center text-[10px] animate-pulse">
                  🛰️
                </div>
                <span className="text-[8px] font-mono text-indigo-300 bg-slate-950/90 px-1 rounded mt-0.5 border border-indigo-500/30">
                  AI ORBIT
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Live Mission Telemetry & Uplink Status */}
        <div className="lg:col-span-5 space-y-3">
          {/* Station Inspector Banner */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400 uppercase">Station Inspection:</span>
              <span className="text-cyan-400 font-bold">
                {hoveredStation === 'michael' && 'ORBITAL STATION ALPHA [MICHAEL]'}
                {hoveredStation === 'dave' && 'ORBITAL STATION BETA [DAVE]'}
                {hoveredStation === 'sarah' && 'ORBITAL STATION GAMMA [SARAH]'}
                {hoveredStation === 'pc' && 'GROUND NODE [LOCAL HARD DRIVE]'}
                {!hoveredStation && (isExecuting ? 'PARALLEL SYNCHRONIZATION ACTIVE' : 'SYSTEM STANDBY')}
              </span>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {hoveredStation === 'michael' &&
                `Michael handles Frontend Architecture, UI/UX, modern responsive HTML5/Tailwind, and state management. Powered by ${michael?.model || 'Gemini'}.`}
              {hoveredStation === 'dave' &&
                `Dave handles Backend Systems, Python Flask REST endpoints, MongoDB/JSON schemas, and CORS security. Powered by ${dave?.model || 'Claude'}.`}
              {hoveredStation === 'sarah' &&
                `Sarah handles Accessibility, UI styling reviews, and system sanity tests.`}
              {hoveredStation === 'pc' &&
                `Direct disk pipeline saving generated project code straight to: ${targetPath}`}
              {!hoveredStation &&
                `Michael and Dave operate in parallel. When a directive is given via voice or chat, both stations generate code concurrently and save the files to your PC.`}
            </p>
          </div>

          {/* AI Satellite Uplinks List */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Wifi className="w-3.5 h-3.5 text-cyan-400" />
                AI SATELLITE LINKS
              </span>
              <button
                onClick={() => setIsAISettingsOpen(true)}
                className="text-[10px] text-cyan-400 hover:text-cyan-300 underline font-mono cursor-pointer"
              >
                Configure Keys
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center justify-between bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                <span className="text-slate-300 font-medium">🦙 Llama 3</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                  FREE / DEFAULT
                </span>
              </div>
              <div className="flex items-center justify-between bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                <span className="text-slate-300 font-medium">🌪️ Mistral</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                  FREE / DEFAULT
                </span>
              </div>
              <div className="flex items-center justify-between bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                <span className="text-slate-300 font-medium">⚡ Qwen 2.5</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                  FREE / OLLAMA
                </span>
              </div>
              <div className="flex items-center justify-between bg-slate-900/80 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                <span className="text-slate-300 font-medium">💎 Gemma 2</span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-800">
                  FREE / OLLAMA
                </span>
              </div>
            </div>
          </div>

          {/* Local Target Path Quick Bar */}
          <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 truncate">
              <HardDrive className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="text-slate-400 shrink-0">Disk Output:</span>
              <span className="font-mono text-slate-200 truncate">{targetPath}</span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-800/60 px-2 py-0.5 rounded shrink-0">
              Direct PC Write
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
