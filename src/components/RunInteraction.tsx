'use client';

import React, { useState } from 'react';
import { HelpCircle, ListChecks, Loader2, Rocket, MessageSquarePlus, XCircle, ChevronDown } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { fmtCost, fmtTokens, type Run, type RunQuestion } from '@/lib/api';

const field = 'w-full rounded-lg bg-slate-950/80 border border-slate-800 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500 transition';

/** Questions from the planner (before building) or from an agent (mid-build). Answers resume the run. */
function Questions({ run }: { run: Run }) {
  const { answerQuestions } = useApp();
  const open = run.questions.filter(q => !q.answer);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const ready = open.every(q => (vals[q.id] || '').trim());
  const submit = async () => { setBusy(true); await answerQuestions(vals); setBusy(false); };
  const fromAgent = open.some(q => q.taskId);
  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 mb-4">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-200">
        <HelpCircle className="h-4 w-4" /> {fromAgent ? 'An agent needs your answer' : 'A few quick questions before I build'}
      </div>
      <div className="mt-3 space-y-3">
        {open.map((q: RunQuestion) => (
          <div key={q.id}>
            <p className="text-sm text-slate-100">{q.q}</p>
            {q.agent && <p className="text-[11px] text-slate-500">asked by: {q.agent}</p>}
            {q.options.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {q.options.map(o => (
                  <button key={o} onClick={() => setVals(v => ({ ...v, [q.id]: o }))}
                    className={`rounded-full border px-2.5 py-0.5 text-xs transition ${vals[q.id] === o ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100' : 'border-slate-700 text-slate-300 hover:border-cyan-500'}`}>{o}</button>
                ))}
              </div>
            )}
            <input className={`${field} mt-1.5`} placeholder={q.options.length ? 'or type your own answer' : 'Your answer'} value={vals[q.id] || ''}
              onChange={e => setVals(v => ({ ...v, [q.id]: e.target.value }))}
              onKeyDown={e => { if (e.key === 'Enter' && ready && !busy) submit(); }} />
          </div>
        ))}
      </div>
      <button onClick={submit} disabled={!ready || busy}
        className="mt-3 flex items-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-3.5 py-1.5 text-xs font-medium transition">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />} Continue
      </button>
    </div>
  );
}

interface Draft { title: string; description: string; removed: boolean }

/** The plan, waiting for "Start building". Everything is editable; nothing is spent until you confirm. */
function PlanReview({ run }: { run: Run }) {
  const { approvePlan, revisePlan, rejectPlan } = useApp();
  const plan = run.plan;
  const mods = plan.modules || [];
  const [draft, setDraft] = useState<Record<string, Draft>>(
    () => Object.fromEntries(mods.map(m => [m.key, { title: m.title, description: m.description, removed: false }])));
  const [contract, setContract] = useState(plan.contract || '');
  const [showContract, setShowContract] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState('');
  const kept = mods.filter(m => !draft[m.key]?.removed).length;
  const set = (k: string, p: Partial<Draft>) => setDraft(d => ({ ...d, [k]: { ...d[k], ...p } }));
  const run_ = async (what: string, fn: () => Promise<void>) => { setBusy(what); await fn(); setBusy(''); };
  const share = mods.length ? kept / mods.length : 1;

  return (
    <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/5 p-4 mb-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-2 text-sm font-medium text-cyan-200"><ListChecks className="h-4 w-4" /> Review the plan</span>
        <span className="text-[11px] font-mono text-slate-400">
          {mods.length} modules{run.estimateTokens > 0 && ` · about ${fmtTokens(Math.round(run.estimateTokens * share))} tokens · ${fmtCost(run.estimateCost * share)} to build`}
          {run.cost > 0 && ` · ${fmtCost(run.cost)} spent planning`}
        </span>
      </div>
      {plan.summary && <p className="mt-2 text-sm text-slate-200">{plan.summary}</p>}
      {(run.reusedPlan || run.plannerModel === 'deepseek-reasoner') && (
        <p className="mt-1 text-[11px] text-violet-300/90">
          {run.reusedPlan && `Modelled on your earlier plan "${run.reusedPlan}". `}{run.plannerModel === 'deepseek-reasoner' && 'Planned with deep reasoning.'}
        </p>
      )}

      {(run.assumptions?.length ?? 0) > 0 && (
        <div className="mt-3">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">I assumed (tell me if wrong)</p>
          <ul className="mt-1 space-y-0.5 text-xs text-slate-300 list-disc pl-4">
            {run.assumptions.map(a => <li key={a}>{a}</li>)}
          </ul>
        </div>
      )}

      <div className="mt-3 space-y-2">
        {mods.map(m => {
          const d = draft[m.key];
          return (
            <div key={m.key} className={`rounded-lg border p-2.5 transition ${d.removed ? 'border-slate-800 opacity-45' : 'border-slate-700 bg-slate-900/60'}`}>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={!d.removed} onChange={e => set(m.key, { removed: !e.target.checked })} title="Include this module" />
                <input className="flex-1 bg-transparent text-sm font-medium text-slate-100 outline-none border-b border-transparent focus:border-cyan-500"
                  value={d.title} disabled={d.removed} onChange={e => set(m.key, { title: e.target.value })} />
                <span className="text-[10px] font-mono text-slate-500 shrink-0">{m.folder}/</span>
              </div>
              <textarea className={`${field} mt-1.5 resize-y`} rows={2} value={d.description} disabled={d.removed}
                onChange={e => set(m.key, { description: e.target.value })} />
              {m.depends_on.length > 0 && <p className="mt-1 text-[11px] text-slate-500">after: {m.depends_on.map(k => draft[k]?.title.replace(/^Build (the )?/i, '') || k).join(', ')}</p>}
            </div>
          );
        })}
      </div>

      <button onClick={() => setShowContract(s => !s)} className="mt-3 flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200">
        <ChevronDown className={`h-3 w-3 transition ${showContract ? 'rotate-180' : ''}`} /> Shared rules every agent follows (stack, files, routes)
      </button>
      {showContract && <textarea className={`${field} mt-1.5 font-mono resize-y`} rows={7} value={contract} onChange={e => setContract(e.target.value)} />}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button disabled={!kept || !!busy}
          onClick={() => run_('go', () => approvePlan({ modules: mods.map(m => ({ key: m.key, ...draft[m.key] })), contract }))}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-4 py-2 text-sm font-medium transition">
          {busy === 'go' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />} Start building
        </button>
        <button disabled={!!busy} onClick={() => run_('no', rejectPlan)}
          className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 px-3 py-2 text-xs transition">
          <XCircle className="h-3.5 w-3.5" /> Reject
        </button>
      </div>
      <div className="mt-3 flex gap-2">
        <input className={field} placeholder="Or ask the planner for changes, e.g. “add a reports page, drop the settings module”" value={feedback}
          onChange={e => setFeedback(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && feedback.trim() && !busy) run_('rev', () => revisePlan(feedback.trim())); }} />
        <button disabled={!feedback.trim() || !!busy} onClick={() => run_('rev', () => revisePlan(feedback.trim()))}
          className="flex items-center gap-1.5 shrink-0 rounded-lg border border-slate-600 hover:border-cyan-500 disabled:opacity-40 px-3 text-xs transition">
          {busy === 'rev' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquarePlus className="h-3.5 w-3.5" />} Revise plan
        </button>
      </div>
    </div>
  );
}

export default function RunInteraction({ run }: { run: Run }) {
  if (run.status === 'awaiting_input' && run.questions.some(q => !q.answer)) {
    return <Questions key={run.questions.filter(q => !q.answer).map(q => q.id).join(',')} run={run} />;
  }
  if (run.status === 'awaiting_approval' && (run.plan.modules?.length ?? 0) > 0) {
    // re-created whenever the planner produces a new plan, so the editable draft always matches it
    return <PlanReview key={(run.plan.modules || []).map(m => m.key + m.title).join('|')} run={run} />;
  }
  return null;
}
