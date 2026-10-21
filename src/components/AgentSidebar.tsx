'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { UserPlus, Cpu, Loader2, Settings } from 'lucide-react';
import SatelliteRadar from './SatelliteRadar';

const AGENT_COLORS: Record<string, { border: string; text: string; bg: string; badge: string }> = {
  michael: { border: 'border-cyan-500/40', text: 'text-cyan-300', bg: 'bg-cyan-950/60', badge: 'LEAD FE' },
  dave:    { border: 'border-emerald-500/40', text: 'text-emerald-300', bg: 'bg-emerald-950/60', badge: 'LEAD BE' },
  rex:     { border: 'border-orange-500/40', text: 'text-orange-300', bg: 'bg-orange-950/60', badge: 'PC CTRL' },
  sarah:   { border: 'border-purple-500/40', text: 'text-purple-300', bg: 'bg-purple-950/60', badge: '' },
};

const DEFAULT_COLOR = { border: 'border-indigo-500/30', text: 'text-indigo-300', bg: 'bg-indigo-950/50', badge: '' };

function getColor(id: string) {
  return AGENT_COLORS[id] || DEFAULT_COLOR;
}

export default function AgentSidebar() {
  const { people, setIsAddPersonOpen, setIsAISettingsOpen } = useOffice();

  // Rex always first, then others in order
  const sorted = [
    ...people.filter((p) => p.id === 'rex'),
    ...people.filter((p) => p.id !== 'rex'),
  ];

  return (
    <aside className="w-64 xl:w-72 shrink-0 flex flex-col gap-3">
      {/* Mini Radar */}
      <SatelliteRadar />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <h2 className="text-[11px] font-bold tracking-widest uppercase text-slate-300 font-mono">
            Squad Roster
          </h2>
          <span className="text-[10px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
            {people.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsAISettingsOpen(true)}
            title="Agent model settings"
            className="p-1 rounded-lg text-slate-500 hover:text-cyan-400 hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsAddPersonOpen(true)}
            title="Add new agent"
            className="p-1 rounded-lg text-slate-500 hover:text-emerald-400 hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <UserPlus className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Agent List */}
      <div className="flex flex-col gap-2 overflow-y-auto max-h-[calc(100vh-12rem)] pr-0.5">
        {sorted.map((person) => {
          const c = getColor(person.id);
          const isWorking = person.status === 'coding';

          return (
            <div
              key={person.id}
              className={`bg-slate-900/80 border ${c.border} rounded-xl p-3 shadow-md backdrop-blur-md transition-all ${
                isWorking ? 'shadow-lg' : ''
              }`}
            >
              {/* Top row: avatar + name + status */}
              <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-base shrink-0">
                    {person.avatar || '🤖'}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1 flex-wrap">
                      <span className="text-xs font-bold text-white truncate">{person.name}</span>
                      {c.badge && (
                        <span className={`text-[9px] font-mono px-1 py-0.5 rounded ${c.bg} ${c.text} border ${c.border} shrink-0`}>
                          {c.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 truncate">{person.role}</p>
                  </div>
                </div>

                {isWorking ? (
                  <span className={`flex items-center gap-1 text-[9px] font-mono ${c.text} shrink-0`}>
                    <Loader2 className="w-2.5 h-2.5 animate-spin" />
                    ON
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    RDY
                  </span>
                )}
              </div>

              {/* Skills */}
              {person.skills.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {person.skills.slice(0, 3).map((s, i) => (
                    <span key={i} className="text-[9px] font-mono bg-slate-800 text-slate-400 border border-slate-700/60 px-1.5 py-0.5 rounded">
                      {s}
                    </span>
                  ))}
                  {person.skills.length > 3 && (
                    <span className="text-[9px] font-mono text-slate-500">+{person.skills.length - 3}</span>
                  )}
                </div>
              )}

              {/* Model chip */}
              <div className="flex items-center gap-1 pt-1.5 border-t border-slate-800">
                <Cpu className="w-2.5 h-2.5 text-slate-500 shrink-0" />
                <span className="text-[9px] font-mono text-slate-500 truncate">{person.model || 'gemini-3.8-flash'}</span>
              </div>

              {/* Status text */}
              {person.statusText && (
                <p className="text-[10px] text-slate-500 truncate mt-1" title={person.statusText}>
                  {person.statusText}
                </p>
              )}
            </div>
          );
        })}

        {/* Add Agent card */}
        <button
          onClick={() => setIsAddPersonOpen(true)}
          className="border border-dashed border-slate-800 hover:border-cyan-500/50 bg-slate-900/20 hover:bg-slate-900/50 rounded-xl p-3 flex items-center gap-2 text-slate-500 hover:text-cyan-400 transition-all cursor-pointer text-xs font-mono"
        >
          <UserPlus className="w-4 h-4 shrink-0" />
          <span>+ Add Agent</span>
        </button>
      </div>
    </aside>
  );
}
