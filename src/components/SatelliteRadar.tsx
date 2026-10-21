'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { HardDrive, Activity } from 'lucide-react';

export default function SatelliteRadar() {
  const { people, isExecuting, setIsAISettingsOpen } = useOffice();

  const michael = people.find((p) => p.id === 'michael');
  const dave    = people.find((p) => p.id === 'dave');
  const sarah   = people.find((p) => p.id === 'sarah');

  return (
    <div className="relative bg-slate-900/70 border border-slate-800/80 rounded-xl p-2.5 overflow-hidden">
      {/* subtle grid bg */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b0d_1px,transparent_1px),linear-gradient(to_bottom,#1e293b0d_1px,transparent_1px)] bg-[size:16px_16px] pointer-events-none" />

      <div className="relative z-10 flex items-center gap-3">
        {/* Mini radar circle */}
        <div className="relative w-24 h-24 shrink-0 rounded-full border border-cyan-500/30 bg-slate-950/80 shadow-[0_0_18px_rgba(6,182,212,0.12)] flex items-center justify-center overflow-hidden">
          {/* rings */}
          <div className="absolute w-[80%] h-[80%] rounded-full border border-cyan-500/20" />
          <div className="absolute w-[55%] h-[55%] rounded-full border border-cyan-500/15 border-dashed" />
          <div className="absolute w-[30%] h-[30%] rounded-full border border-cyan-500/25" />
          {/* crosshairs */}
          <div className="absolute w-full h-[1px] bg-cyan-500/15" />
          <div className="absolute h-full w-[1px] bg-cyan-500/15" />
          {/* sweep */}
          <div className="absolute inset-0 origin-center animate-[spin_4s_linear_infinite] pointer-events-none">
            <div className="w-1/2 h-1/2 bg-gradient-to-br from-cyan-400/20 via-cyan-400/5 to-transparent origin-bottom-right rounded-tl-full" />
          </div>
          {/* centre node */}
          <div className="relative z-20 flex flex-col items-center justify-center p-1 rounded-lg bg-slate-900 border border-cyan-500/40">
            <HardDrive className={`w-3.5 h-3.5 ${isExecuting ? 'text-amber-400 animate-bounce' : 'text-cyan-400'}`} />
            <span className="text-[7px] font-mono text-slate-400 mt-0.5">PC</span>
          </div>
          {/* Michael blip */}
          <div className="absolute top-[20%] right-[18%] z-20">
            <div className={`w-4 h-4 rounded-full bg-cyan-500/20 border ${michael?.status === 'coding' ? 'border-cyan-400 animate-ping' : 'border-cyan-500/60'} flex items-center justify-center text-[8px]`}>💻</div>
          </div>
          {/* Dave blip */}
          <div className="absolute bottom-[20%] left-[16%] z-20">
            <div className={`w-4 h-4 rounded-full bg-emerald-500/20 border ${dave?.status === 'coding' ? 'border-emerald-400 animate-ping' : 'border-emerald-500/60'} flex items-center justify-center text-[8px]`}>⚙️</div>
          </div>
          {/* Sarah blip */}
          {sarah && (
            <div className="absolute top-[26%] left-[18%] z-20">
              <div className="w-4 h-4 rounded-full bg-purple-500/20 border border-purple-400/60 flex items-center justify-center text-[8px]">🎨</div>
            </div>
          )}
          {/* AI orbit blip */}
          <div className="absolute top-[10%] left-[44%] z-20 cursor-pointer" onClick={() => setIsAISettingsOpen(true)} title="AI Settings">
            <div className="w-3.5 h-3.5 rounded-full bg-indigo-500/30 border border-indigo-400/60 flex items-center justify-center text-[7px] animate-pulse">🛰️</div>
          </div>
        </div>

        {/* Status info */}
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
            <span className="text-[10px] font-mono text-emerald-400 truncate">RADAR ACTIVE</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-cyan-500 shrink-0" />
            <span className={`text-[10px] font-mono truncate ${isExecuting ? 'text-amber-400' : 'text-slate-500'}`}>
              {isExecuting ? 'TRANSMITTING' : 'SYNC IDLE'}
            </span>
          </div>
          <div className="mt-1 space-y-0.5">
            {[
              { id: 'michael', label: 'Michael', color: 'bg-cyan-400',    person: michael },
              { id: 'dave',    label: 'Dave',    color: 'bg-emerald-400', person: dave },
              { id: 'sarah',   label: 'Sarah',   color: 'bg-purple-400',  person: sarah },
            ].map(({ id, label, color, person }) => person && (
              <div key={id} className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${person.status === 'coding' ? color + ' animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-[9px] font-mono text-slate-400 truncate">{label}</span>
                <span className={`ml-auto text-[8px] font-mono ${person.status === 'coding' ? 'text-cyan-400' : 'text-slate-600'}`}>
                  {person.status === 'coding' ? 'CODING' : 'READY'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
