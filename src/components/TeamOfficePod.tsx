'use client';

import React from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Person } from '@/types/office';
import { UserPlus, Sparkles, Cpu, CheckCircle2, Loader2 } from 'lucide-react';

export default function TeamOfficePod() {
  const { people, updatePersonModel, setIsAddPersonOpen, setIsAISettingsOpen } = useOffice();

  const availableModels = [
    { id: 'ollama:llama3', label: '🦙 Ollama + Llama 3 (Free Open-Source)' },
    { id: 'ollama:mistral', label: '🌪️ Ollama + Mistral (Free Open-Source)' },
    { id: 'ollama:qwen', label: '⚡ Ollama + Qwen (Free Open-Source)' },
    { id: 'ollama:gemma', label: '💎 Ollama + Gemma (Free Open-Source)' },
    { id: 'gemini-2.0-flash', label: 'Google Gemini 2.0 Flash' },
    { id: 'claude-3-5-sonnet', label: 'Anthropic Claude 3.5 Sonnet' },
    { id: 'gpt-4o', label: 'OpenAI GPT-4o' }
  ];

  return (
    <div className="space-y-3">
      {/* Pod Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span>
          <h2 className="text-xs font-bold tracking-widest uppercase text-slate-300 font-mono">
            THE OFFICE SQUAD // ACTIVE SPECIALISTS ({people.length})
          </h2>
        </div>
        <button
          onClick={() => setIsAddPersonOpen(true)}
          className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-mono hover:underline cursor-pointer"
        >
          <UserPlus className="w-3.5 h-3.5" />
          <span>+ Add Person to Office</span>
        </button>
      </div>

      {/* Grid of People Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {people.map((person) => {
          const isWorking = person.status === 'coding';

          return (
            <div
              key={person.id}
              className={`relative bg-slate-900/80 border rounded-2xl p-4 shadow-xl backdrop-blur-md transition-all flex flex-col justify-between ${
                isWorking
                  ? 'border-cyan-500 shadow-cyan-500/20 bg-slate-900'
                  : 'border-slate-800 hover:border-slate-700'
              }`}
            >
              <div>
                {/* Header: Avatar, Name, Role */}
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-xl shadow-inner">
                      {person.avatar || '🤖'}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h3 className="text-sm font-bold text-white tracking-tight">{person.name}</h3>
                        {person.id === 'michael' && (
                          <span className="text-[10px] bg-cyan-950 text-cyan-400 px-1.5 py-0.5 rounded border border-cyan-800/60 font-mono">
                            LEAD FE
                          </span>
                        )}
                        {person.id === 'dave' && (
                          <span className="text-[10px] bg-emerald-950 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-800/60 font-mono">
                            LEAD BE
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-400 font-medium">{person.role}</p>
                    </div>
                  </div>

                  {/* Status Indicator */}
                  <div className="flex items-center gap-1.5">
                    {isWorking ? (
                      <span className="flex items-center gap-1 text-[11px] font-mono text-cyan-400 bg-cyan-950/80 border border-cyan-800/80 px-2 py-0.5 rounded-full animate-pulse">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        CODING
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-950/80 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        READY
                      </span>
                    )}
                  </div>
                </div>

                {/* Assigned AI Model Selector */}
                <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-2.5 mb-3">
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1.5 font-mono">
                    <span className="flex items-center gap-1">
                      <Cpu className="w-3 h-3 text-cyan-400" />
                      Assigned AI Model:
                    </span>
                    <button
                      onClick={() => setIsAISettingsOpen(true)}
                      className="text-cyan-400 hover:text-cyan-300 hover:underline text-[10px]"
                    >
                      Keys
                    </button>
                  </div>
                  <select
                    value={person.model}
                    onChange={(e) => updatePersonModel(person.id, e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-cyan-500 font-sans cursor-pointer"
                  >
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Skills Chips */}
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {person.skills.slice(0, 3).map((skill, i) => (
                    <span
                      key={i}
                      className="text-[10px] font-mono bg-slate-800/80 text-slate-300 border border-slate-700/60 px-2 py-0.5 rounded-md"
                    >
                      {skill}
                    </span>
                  ))}
                  {person.skills.length > 3 && (
                    <span className="text-[10px] font-mono text-slate-500 self-center">
                      +{person.skills.length - 3}
                    </span>
                  )}
                </div>
              </div>

              {/* Footer: Live Task Status Text */}
              <div className="pt-2.5 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono truncate" title={person.statusText}>
                {person.statusText || 'Standing by for project directive...'}
              </div>
            </div>
          );
        })}

        {/* Add Person Quick Card */}
        <div
          onClick={() => setIsAddPersonOpen(true)}
          className="border border-dashed border-slate-800 hover:border-cyan-500/60 bg-slate-900/30 hover:bg-slate-900/60 rounded-2xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all group min-h-[190px]"
        >
          <div className="w-12 h-12 rounded-2xl bg-slate-800 group-hover:bg-cyan-950/60 border border-slate-700 group-hover:border-cyan-500/50 flex items-center justify-center text-slate-400 group-hover:text-cyan-400 transition-all mb-3 shadow">
            <UserPlus className="w-5 h-5" />
          </div>
          <h4 className="text-xs font-bold text-slate-200 group-hover:text-white uppercase tracking-wider font-mono">
            + Add Person to Office
          </h4>
          <p className="text-[11px] text-slate-500 mt-1 max-w-[200px]">
            Hire a QA, Mobile dev, Database engineer, or custom specialist.
          </p>
        </div>
      </div>
    </div>
  );
}
