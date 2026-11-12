'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, ArrowUp, Square, Loader2, FolderOpen, SlidersHorizontal, ChevronDown, Pencil, X, Paperclip, FileText, Image as ImageIcon, MessageSquarePlus } from 'lucide-react';
import VoiceOrb from '@/components/VoiceOrb';
import { useApp } from '@/context/AppContext';
import { useVoice } from '@/context/VoiceContext';
import { api, fmtCost, fmtTokens, ATTACH_ACCEPT, type Forecast } from '@/lib/api';

const KIND: Record<Forecast['kind'], string> = { chat: 'quick answer', pc: 'PC task', small: 'small build, 1 agent', large: 'full build', auto: 'full build' };

function greeting(): string {
  const h = new Date().getHours();
  return h < 5 ? 'Still up' : h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

const field = 'w-full rounded-lg bg-slate-950/80 border border-slate-800 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500 transition';

export default function GoalConsole() {
  const { settings, updateSettings, startRun, cancelRun, snap, starting, error, clearError, goal, setGoal, user, continueFrom, setContinueFrom, runs, attachments, uploading, addFiles, removeAttachment, newChat } = useApp();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const { isVoiceActive, isThinking, isSpeaking, voiceTranscript, voiceError, toggleVoiceListening,
    isAutoProcessVoice, toggleAutoProcessVoice } = useVoice();
  const [showOptions, setShowOptions] = useState(false);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [fcFor, setFcFor] = useState('');
  useEffect(() => {
    const g = goal.trim() || (attachments.length ? 'Summarize the attached file' : '');
    if (!g) return;
    const ids = attachments.map(a => a.id);
    const t = setTimeout(() => {
      api<Forecast>('/usage/estimate', { method: 'POST', json: { goal: g, verify: settings.verify, webSearch: settings.webSearch, attachments: ids } })
        .then(f => { setFc(f); setFcFor(g); }).catch(() => setFc(null));
    }, 500);
    return () => clearTimeout(t);
  }, [goal, attachments, settings.verify, settings.webSearch]);
  const effectiveGoal = goal.trim() || (attachments.length ? 'Summarize the attached file' + (attachments.length > 1 ? 's' : '') : '');
  const forecast = effectiveGoal && fc && fcFor === (goal.trim() || (attachments.length ? 'Summarize the attached file' : '')) ? fc : null;
  const active = !!snap && ['planning', 'running', 'awaiting_input', 'awaiting_approval'].includes(snap.run.status);
  const editing = continueFrom ? (runs.find(r => r.id === continueFrom)?.projectName || snap?.run.projectName || 'this project') : '';
  const orbActive = isVoiceActive || isThinking || isSpeaking || active;
  const text = isVoiceActive && voiceTranscript ? voiceTranscript : goal;

  const submit = () => { if (effectiveGoal && !active) startRun(effectiveGoal); };
  const summary = [
    settings.targetPath,
    `${settings.plannerModel} → ${settings.workerModel}`,
    settings.maxTokens ? `${(settings.maxTokens / 1000).toFixed(0)}k token budget` : 'no token limit',
    settings.verify ? 'run & auto-fix' : '',
  ].filter(Boolean).join('  ·  ');

  return (
    <section className="rounded-3xl border border-slate-800/80 bg-gradient-to-b from-slate-900/80 to-slate-900/30 p-5 sm:p-6 shadow-xl shadow-black/20">
      {snap && (
        <button onClick={newChat} title="Start a fresh conversation (Adion forgets this chat)"
          className="float-right flex items-center gap-1.5 rounded-lg border border-slate-700 px-2.5 py-1 text-[11px] text-slate-300 hover:border-cyan-500 hover:text-cyan-200 transition">
          <MessageSquarePlus className="h-3.5 w-3.5" /> New chat
        </button>
      )}
      <div className="flex items-center gap-5">
        <div className="hidden sm:block shrink-0"><VoiceOrb isActive={orbActive} size={84} /></div>
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight truncate">
            {greeting()}{user ? `, ${user.username}` : ''}.
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {isVoiceActive ? 'I’m listening…' : isThinking ? 'Thinking…' : isSpeaking ? 'Speaking…' : active ? 'Your agents are building. Watch them below.' : 'What should we build today?'}
          </p>
        </div>
      </div>

      {editing && (
        <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-violet-500/40 bg-violet-500/10 pl-3 pr-1.5 py-1 text-xs text-violet-200">
          <Pencil className="h-3 w-3" /> Changing: {editing}
          <button onClick={() => setContinueFrom('')} title="Start something new instead" className="rounded-full p-0.5 hover:bg-violet-500/30"><X className="h-3 w-3" /></button>
        </div>
      )}
      {/* Composer */}
      <div onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); addFiles(Array.from(e.dataTransfer.files)); }}
        className={`mt-5 rounded-2xl border bg-slate-950/70 transition ${dragging ? 'border-cyan-400 bg-cyan-500/5' : isVoiceActive ? 'border-rose-500/60 shadow-[0_0_30px_-8px_rgba(244,63,94,0.5)]' : 'border-slate-800 focus-within:border-cyan-500/70'}`}>
        <textarea
          value={text}
          onChange={e => setGoal(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
          rows={3}
          placeholder={attachments.length ? 'Ask about the attached file, or say what to build with it…' : editing ? 'Describe the change you want…' : 'Describe the app you want, attach a file, or press the mic and talk to Adion…'}
          className="w-full resize-none bg-transparent px-4 pt-3 text-sm outline-none placeholder:text-slate-600"
        />
        {(attachments.length > 0 || uploading) && (
          <div className="flex flex-wrap gap-1.5 px-3 pb-2">
            {attachments.map(a => (
              <span key={a.id} title={a.note || a.name}
                className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900 pl-2 pr-1 py-0.5 text-[11px] text-slate-300">
                {a.kind === 'image' ? <ImageIcon className="h-3 w-3 text-cyan-300" /> : <FileText className="h-3 w-3 text-slate-400" />}
                <span className="max-w-[10rem] truncate">{a.name}</span>
                <span className="text-slate-500">{a.kind === 'image' ? (a.chars > 0 ? 'OCR' : `${a.info.width}×${a.info.height}`) : `${Math.max(1, Math.round(a.size / 1024))} KB`}</span>
                <button onClick={() => removeAttachment(a.id)} title="Remove" className="rounded-full p-0.5 hover:bg-slate-700"><X className="h-3 w-3" /></button>
              </span>
            ))}
            {uploading && <span className="flex items-center gap-1.5 text-[11px] text-slate-500"><Loader2 className="h-3 w-3 animate-spin" /> reading file…</span>}
          </div>
        )}
        <div className="flex items-center justify-between gap-2 px-3 pb-2.5">
          <input ref={fileRef} type="file" multiple accept={ATTACH_ACCEPT} className="hidden"
            onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = ''; }} />
          <button onClick={() => fileRef.current?.click()} title="Attach files (documents, PDFs, pictures; drag and drop works too)"
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition">
            <Paperclip className="h-3.5 w-3.5" /> Attach
          </button>
          <button onClick={() => setShowOptions(o => !o)}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition">
            <SlidersHorizontal className="h-3.5 w-3.5" /> Options
            <ChevronDown className={`h-3 w-3 transition ${showOptions ? 'rotate-180' : ''}`} />
          </button>
          <div className="flex items-center gap-2">
            <span className="hidden md:inline text-[10px] text-slate-600">Enter to send · Shift+Enter for a new line</span>
            <button onClick={toggleVoiceListening} title="Talk to Adion (Alt+V)"
              className={`h-9 w-9 rounded-full border flex items-center justify-center transition ${isVoiceActive ? 'bg-rose-600/20 border-rose-500 text-rose-300 animate-pulse' : 'border-slate-700 text-slate-300 hover:border-cyan-500 hover:text-cyan-300'}`}>
              {isThinking ? <Loader2 className="h-4 w-4 animate-spin" /> : isVoiceActive ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </button>
            {active ? (
              <button onClick={cancelRun} title="Cancel run" className="h-9 w-9 rounded-full bg-rose-600 hover:bg-rose-500 flex items-center justify-center transition">
                <Square className="h-3.5 w-3.5 fill-current" />
              </button>
            ) : (
              <button onClick={submit} disabled={!effectiveGoal || starting || uploading} title="Send"
                className="h-9 w-9 rounded-full bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 flex items-center justify-center transition">
                {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
              </button>
            )}
          </div>
        </div>
      </div>

      {forecast && !active && (
        <p className="mt-2 px-1 text-[11px] text-cyan-300/80 font-mono" title="Forecast before running. Real cost is shown on the map and in the Usage tab.">
          ≈ {fmtTokens(forecast.tokens)} tokens · {fmtCost(forecast.cost)} · {KIND[forecast.kind]}
          {settings.maxTokens > 0 && forecast.high > settings.maxTokens && <span className="text-amber-300"> · may hit your {fmtTokens(settings.maxTokens)} budget</span>}
        </p>
      )}
      {!showOptions && <p className="mt-1 px-1 text-[11px] text-slate-600 truncate">{summary}</p>}

      {showOptions && (
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4 text-xs animate-fade-in">
          <label className="sm:col-span-2 space-y-1">
            <span className="text-slate-400 flex items-center gap-1"><FolderOpen className="h-3 w-3" /> Output folder</span>
            <input className={`${field} font-mono`} value={settings.targetPath} onChange={e => updateSettings({ targetPath: e.target.value })} />
          </label>
          <label className="space-y-1">
            <span className="text-slate-400">Planner model <span className="text-slate-600">(strong)</span></span>
            <input className={field} list="models" value={settings.plannerModel} onChange={e => updateSettings({ plannerModel: e.target.value })} />
          </label>
          <label className="space-y-1">
            <span className="text-slate-400">Worker model <span className="text-slate-600">(fast or local)</span></span>
            <input className={field} list="models" value={settings.workerModel} onChange={e => updateSettings({ workerModel: e.target.value })} />
          </label>
          <label className="space-y-1">
            <span className="text-slate-400">Token budget <span className="text-slate-600">(0 = unlimited)</span></span>
            <input className={field} type="number" min={0} step={50000} value={settings.maxTokens}
              onChange={e => updateSettings({ maxTokens: Math.max(0, Number(e.target.value) || 0) })} />
          </label>
          <div className="space-y-2 pt-1">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
              <input type="checkbox" checked={isAutoProcessVoice} onChange={toggleAutoProcessVoice} />
              Adion starts builds as soon as I ask
            </label>
            <label className="flex items-start gap-2 text-slate-300 cursor-pointer select-none"
              title="Questions about recent or changing things are searched automatically. This makes every question search the web (uses Tavily).">
              <input type="checkbox" className="mt-0.5" checked={settings.webSearch} onChange={e => updateSettings({ webSearch: e.target.checked })} />
              <span>Always search the web for answers <span className="text-slate-500">(Tavily)</span></span>
            </label>
            <label className="flex items-start gap-2 text-slate-300 cursor-pointer select-none"
              title="Shows the plan (modules, stack, assumptions) and waits for your Start building before spending tokens on agents. Applies to plans with 4+ modules.">
              <input type="checkbox" className="mt-0.5" checked={settings.reviewPlan} onChange={e => updateSettings({ reviewPlan: e.target.checked })} />
              <span>Show me the plan before building <span className="text-slate-500">(big projects)</span></span>
            </label>
            <label className="flex items-start gap-2 text-slate-300 cursor-pointer select-none"
              title="Big, multi-part goals are planned by DeepSeek's reasoning model: slower to plan, better architecture. Small goals always use the fast model.">
              <input type="checkbox" className="mt-0.5" checked={settings.deepPlan} onChange={e => updateSettings({ deepPlan: e.target.checked })} />
              <span>Deep planning for big projects <span className="text-slate-500">(slower, smarter)</span></span>
            </label>
            <label className="flex items-start gap-2 text-slate-300 cursor-pointer select-none"
              title="Starts the finished project, opens it in a real headless browser, and has a model fix errors, 404s and broken buttons. This EXECUTES generated code on this machine.">
              <input type="checkbox" className="mt-0.5" checked={settings.verify} onChange={e => updateSettings({ verify: e.target.checked })} />
              <span>Test in a real browser &amp; auto-fix <span className="text-slate-500">(runs the generated app)</span></span>
            </label>
          </div>
          <datalist id="models">
            <option value="deepseek-chat" /><option value="deepseek-reasoner" />
          </datalist>
        </div>
      )}

      {(error || voiceError) && (
        <div className="mt-3 flex items-start justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
          <span>{error || voiceError}</span>
          <button onClick={clearError} className="text-rose-400 hover:text-rose-200 shrink-0">dismiss</button>
        </div>
      )}
    </section>
  );
}
