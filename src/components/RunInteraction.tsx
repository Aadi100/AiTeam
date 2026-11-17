'use client';

import React, { useRef, useState } from 'react';
import { HelpCircle, ListChecks, Loader2, Rocket, MessageSquarePlus, XCircle, ChevronDown, CheckCircle2, LayoutDashboard, Database, Layers, Sparkles } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { fmtCost, type PlanModule, type Run, type RunQuestion } from '@/lib/api';

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

/** First sentence of the technical text, used when the planner gave no plain-language line. */
const firstSentence = (t: string) => (t.match(/^[^.!?]{12,200}[.!?]?/)?.[0] || t).trim().slice(0, 200);

/** Build order for people: modules grouped into phases; modules in one phase are built at the same time. */
function phases(mods: PlanModule[]): PlanModule[][] {
  const depth: Record<string, number> = {};
  const byKey = Object.fromEntries(mods.map(m => [m.key, m]));
  const d = (k: string, seen: string[] = []): number => {
    if (depth[k] !== undefined) return depth[k];
    if (seen.includes(k)) return 0;
    const m = byKey[k];
    depth[k] = 1 + Math.max(0, ...(m?.depends_on || []).filter(x => byKey[x]).map(x => d(x, [...seen, k])));
    return depth[k];
  };
  mods.forEach(m => d(m.key));
  const out: PlanModule[][] = [];
  mods.forEach(m => { (out[depth[m.key] - 1] ||= []).push(m); });
  return out.filter(Boolean);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="mt-4"><p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">{title}</p>{children}</div>;
}

/** The plan, waiting for "Start building": written for people first (what you get, screens, steps), with the technical details one click away. */
function PlanReview({ run }: { run: Run }) {
  const { approvePlan, revisePlan, rejectPlan } = useApp();
  const plan = run.plan;
  const mods = plan.modules || [];
  const ov = plan.overview;
  const [draft, setDraft] = useState<Record<string, Draft>>(
    () => Object.fromEntries(mods.map(m => [m.key, { title: m.title, description: m.description, removed: false }])));
  const [contract, setContract] = useState(plan.contract || '');
  const [showContract, setShowContract] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState('');
  const box = useRef<HTMLInputElement>(null);
  const kept = mods.filter(m => !draft[m.key]?.removed).length;
  const set = (k: string, p: Partial<Draft>) => setDraft(d => ({ ...d, [k]: { ...d[k], ...p } }));
  const run_ = async (what: string, fn: () => Promise<void>) => { setBusy(what); await fn(); setBusy(''); };
  const share = mods.length ? kept / mods.length : 1;
  const ask = (text: string) => { setFeedback(text); box.current?.focus(); };
  const steps = phases(mods);

  return (
    <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-b from-cyan-500/[0.06] to-transparent p-5 mb-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-2 text-sm font-semibold text-cyan-200"><ListChecks className="h-4 w-4" /> Your plan{plan.project_name ? `: ${plan.project_name}` : ''}</span>
        <span className="flex-1" />
        <span className="rounded-full border border-slate-700 px-2.5 py-0.5 text-[11px] text-slate-300">{kept} of {mods.length} steps</span>
        {run.estimateTokens > 0 && <span className="rounded-full border border-slate-700 px-2.5 py-0.5 text-[11px] text-slate-300 font-mono">≈ {fmtCost(run.estimateCost * share)} to build</span>}
        {run.cost > 0 && <span className="rounded-full border border-slate-800 px-2.5 py-0.5 text-[11px] text-slate-500 font-mono">{fmtCost(run.cost)} spent planning</span>}
      </div>
      {plan.summary && <p className="mt-3 text-[15px] leading-relaxed text-slate-100">{plan.summary}</p>}
      {(run.reusedPlan || run.plannerModel === 'deepseek-reasoner') && (
        <p className="mt-1 text-[11px] text-violet-300/90">
          {run.reusedPlan && `Modelled on your earlier plan "${run.reusedPlan}". `}{run.plannerModel === 'deepseek-reasoner' && 'Planned with deep reasoning.'}
        </p>
      )}

      {ov && ov.features.length > 0 && (
        <Section title="What you'll get">
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
            {ov.features.map(f => <li key={f} className="flex items-start gap-2 text-sm text-slate-200"><CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-emerald-400" /><span>{f}</span></li>)}
          </ul>
        </Section>)}

      {ov && (ov.screens.length > 0 || ov.data.length > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
          {ov.screens.length > 0 && <Section title="Screens"><ul className="space-y-1">{ov.screens.map(s => <li key={s} className="flex items-start gap-2 text-xs text-slate-300"><LayoutDashboard className="h-3.5 w-3.5 mt-0.5 shrink-0 text-sky-300" />{s}</li>)}</ul></Section>}
          {ov.data.length > 0 && <Section title="What it stores"><ul className="space-y-1">{ov.data.map(s => <li key={s} className="flex items-start gap-2 text-xs text-slate-300"><Database className="h-3.5 w-3.5 mt-0.5 shrink-0 text-violet-300" />{s}</li>)}</ul></Section>}
        </div>)}

      {ov && ov.stack.length > 0 && (
        <Section title="How it's built">
          <div className="flex flex-wrap gap-1.5">
            {ov.stack.map(s => <span key={s.area + s.choice} title={s.why} className="rounded-full border border-slate-700 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-200"><span className="text-slate-500">{s.area}:</span> {s.choice}</span>)}
          </div>
          {ov.stack.some(s => s.why) && <p className="mt-1 text-[11px] text-slate-500">{ov.stack.filter(s => s.why).map(s => `${s.choice}: ${s.why}`).join(' · ')}</p>}
        </Section>)}

      <Section title="The steps (uncheck any you don't want)">
        <div className="space-y-3">
          {steps.map((group, gi) => (
            <div key={gi}>
              <p className="mb-1 flex items-center gap-1.5 text-[11px] text-slate-500"><Layers className="h-3 w-3" />{steps.length > 1 ? `Step ${gi + 1}` : 'Built'}{group.length > 1 ? ` · ${group.length} parts built at the same time` : ''}</p>
              <div className={`grid gap-2 ${group.length > 1 ? 'sm:grid-cols-2' : ''}`}>
                {group.map(m => {
                  const dr = draft[m.key];
                  return (
                    <div key={m.key} className={`rounded-xl border p-3 transition ${dr.removed ? 'border-slate-800 opacity-45' : 'border-slate-700 bg-slate-900/60'}`}>
                      <div className="flex items-start gap-2">
                        <input type="checkbox" className="mt-1" checked={!dr.removed} onChange={e => set(m.key, { removed: !e.target.checked })} title="Include this step" />
                        <div className="flex-1 min-w-0">
                          <input className="w-full bg-transparent text-sm font-medium text-slate-100 outline-none border-b border-transparent focus:border-cyan-500"
                            value={dr.title} disabled={dr.removed} onChange={e => set(m.key, { title: e.target.value })} />
                          <p className="mt-1 text-xs text-slate-400 leading-relaxed">{m.plain || firstSentence(m.description)}</p>
                          {m.depends_on.length > 0 && <p className="mt-1 text-[11px] text-slate-500">starts after: {m.depends_on.map(k => draft[k]?.title.replace(/^Build (the )?/i, '') || k).join(', ')}</p>}
                        </div>
                      </div>
                      <button onClick={() => setOpen(o => ({ ...o, [m.key]: !o[m.key] }))} className="mt-2 flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300">
                        <ChevronDown className={`h-3 w-3 transition ${open[m.key] ? 'rotate-180' : ''}`} /> Technical instructions for the AI ({m.expects.length || 'some'} files in <span className="font-mono">{m.folder || '.'}/</span>)
                      </button>
                      {open[m.key] && <textarea className={`${field} mt-1.5 resize-y`} rows={4} value={dr.description} disabled={dr.removed} onChange={e => set(m.key, { description: e.target.value })} />}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {(run.assumptions?.length ?? 0) > 0 && (
        <Section title="I assumed this (press Change if it is wrong)">
          <ul className="space-y-1">
            {run.assumptions.map(a => (
              <li key={a} className="flex items-start gap-2 text-xs text-slate-300">
                <span className="mt-0.5 text-slate-600">•</span><span className="flex-1">{a}</span>
                <button onClick={() => ask(`Change this: ${a} → `)} className="shrink-0 text-[11px] text-cyan-300/80 hover:text-cyan-200 hover:underline">Change</button>
              </li>))}
          </ul>
        </Section>)}

      {ov && ov.ideas.length > 0 && (
        <Section title="Ideas to add (optional)">
          <div className="flex flex-wrap gap-1.5">
            {ov.ideas.map(i => <button key={i} onClick={() => ask(i)} className="flex items-center gap-1 rounded-full border border-dashed border-slate-600 hover:border-cyan-400 hover:text-cyan-200 px-2.5 py-1 text-xs text-slate-300 transition"><Sparkles className="h-3 w-3" />{i}</button>)}
          </div>
        </Section>)}

      <button onClick={() => setShowContract(s => !s)} className="mt-4 flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300">
        <ChevronDown className={`h-3 w-3 transition ${showContract ? 'rotate-180' : ''}`} /> Advanced: shared technical rules every agent follows
      </button>
      {showContract && <textarea className={`${field} mt-1.5 font-mono resize-y`} rows={7} value={contract} onChange={e => setContract(e.target.value)} />}

      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-slate-800 pt-4">
        <button disabled={!kept || !!busy}
          onClick={() => run_('go', () => approvePlan({ modules: mods.map(m => ({ key: m.key, ...draft[m.key] })), contract }))}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-5 py-2.5 text-sm font-medium transition">
          {busy === 'go' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />} Looks good, start building
        </button>
        <button disabled={!!busy} onClick={() => run_('no', rejectPlan)}
          className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 px-3 py-2 text-xs transition">
          <XCircle className="h-3.5 w-3.5" /> Reject
        </button>
        <span className="flex-1" />
        <span className="text-[11px] text-slate-500">Nothing is spent until you press start.</span>
      </div>
      <div className="mt-3 flex gap-2">
        <input ref={box} className={field} placeholder="Want something different? Describe the change, e.g. “add login”, “make it dark”, “drop the charts”" value={feedback}
          onChange={e => setFeedback(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && feedback.trim() && !busy) run_('rev', () => revisePlan(feedback.trim())); }} />
        <button disabled={!feedback.trim() || !!busy} onClick={() => run_('rev', () => revisePlan(feedback.trim()))}
          className="flex items-center gap-1.5 shrink-0 rounded-lg border border-slate-600 hover:border-cyan-500 disabled:opacity-40 px-3 text-xs transition">
          {busy === 'rev' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MessageSquarePlus className="h-3.5 w-3.5" />} Update plan
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
