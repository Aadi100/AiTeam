'use client';

import React, { useState } from 'react';
import { Mic, MicOff, Play, Square, Loader2, FolderOpen } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { useVoice } from '@/lib/hooks';

export default function GoalConsole() {
  const { settings, updateSettings, startRun, cancelRun, snap, starting, error, clearError } = useApp();
  const [goal, setGoal] = useState('');
  const active = !!snap && (snap.run.status === 'planning' || snap.run.status === 'running');

  const { listening, interim, busy, voiceError, toggle } = useVoice(text => {
    setGoal(text);
    if (settings.autoRun && !active) startRun(text, 'voice');
  }, settings.openai);

  const submit = () => { if (goal.trim() && !active) startRun(goal.trim()); };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
      <div className="flex gap-2">
        <textarea
          value={listening && interim ? interim : goal}
          onChange={e => setGoal(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submit(); }}
          rows={3}
          placeholder="Describe what to build, e.g. “A real-time lead CRM with dashboard, pipeline board, contacts and analytics”…  (Ctrl+Enter to run)"
          className="flex-1 resize-none rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
        />
        <div className="flex flex-col gap-2">
          <button onClick={toggle} disabled={busy} title={listening ? 'Stop listening' : 'Speak your goal'}
            className={`h-11 w-11 rounded-xl border flex items-center justify-center ${listening ? 'bg-rose-600/20 border-rose-500 text-rose-300 animate-pulse' : 'border-slate-700 hover:border-cyan-500 text-slate-300'}`}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          </button>
          {active ? (
            <button onClick={cancelRun} title="Cancel run"
              className="h-11 w-11 rounded-xl bg-rose-600 hover:bg-rose-500 flex items-center justify-center">
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button onClick={submit} disabled={!goal.trim() || starting} title="Run agents"
              className="h-11 w-11 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 flex items-center justify-center">
              {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-xs">
        <label className="flex flex-col gap-1 lg:col-span-2">
          <span className="text-slate-400 flex items-center gap-1"><FolderOpen className="h-3 w-3" /> Output folder</span>
          <input value={settings.targetPath} onChange={e => updateSettings({ targetPath: e.target.value })}
            className="rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 outline-none focus:border-cyan-500 font-mono" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-slate-400">Planner model (strong)</span>
          <input value={settings.plannerModel} onChange={e => updateSettings({ plannerModel: e.target.value })}
            list="models" className="rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 outline-none focus:border-cyan-500" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-slate-400">Worker model (fast / local)</span>
          <input value={settings.workerModel} onChange={e => updateSettings({ workerModel: e.target.value })}
            list="models" className="rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 outline-none focus:border-cyan-500" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-slate-400">Token budget (0 = unlimited)</span>
          <input type="number" min={0} step={50000} value={settings.maxTokens}
            onChange={e => updateSettings({ maxTokens: Math.max(0, Number(e.target.value) || 0) })}
            className="rounded-lg bg-slate-950 border border-slate-700 px-2 py-1.5 outline-none focus:border-cyan-500" />
        </label>
        <label className="flex items-end gap-2 pb-1.5 text-slate-300 cursor-pointer select-none">
          <input type="checkbox" checked={settings.autoRun} onChange={e => updateSettings({ autoRun: e.target.checked })} />
          Start automatically after voice
        </label>
        <label className="flex items-start gap-2 text-slate-300 cursor-pointer select-none sm:col-span-2" title="Starts the generated Python app on a local port, requests /, and has a model fix what breaks. This EXECUTES generated code on this machine.">
          <input type="checkbox" className="mt-0.5" checked={settings.verify} onChange={e => updateSettings({ verify: e.target.checked })} />
          <span>Run &amp; auto-fix the result <span className="text-slate-500">(executes the generated app locally)</span></span>
        </label>
        <datalist id="models">
          <option value="claude-sonnet-5-5" /><option value="claude-opus-5-5" /><option value="claude-haiku-5-5" />
          <option value="gemini-2.5-flash" /><option value="gemini-2.5-pro" /><option value="gpt-4o" />
          <option value="ollama:llama3.2" /><option value="ollama:qwen2.5-coder" /><option value="ollama:mistral" />
        </datalist>
      </div>

      {(error || voiceError) && (
        <div className="flex items-start justify-between gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          <span>{error || voiceError}</span>
          <button onClick={clearError} className="text-rose-400 hover:text-rose-200">dismiss</button>
        </div>
      )}
    </section>
  );
}
