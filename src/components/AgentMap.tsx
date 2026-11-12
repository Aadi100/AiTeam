'use client';

import React from 'react';
import { Loader2, OctagonX, Pencil, CheckCircle2, AlertTriangle, MonitorSmartphone } from 'lucide-react';
import RunInteraction from '@/components/RunInteraction';
import Preview from '@/components/Preview';
import PcTaskCard from '@/components/PcTaskCard';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';
import VoiceOrb from '@/components/VoiceOrb';
import { useVoice } from '@/context/VoiceContext';
import { screenshotUrl, fmtCost, fmtDuration, fmtTokens, type AgentTask, type RunStatus, type TaskStatus } from '@/lib/api';
import { useNow } from '@/lib/hooks';

const DOT: Record<TaskStatus, string> = {
  queued: 'bg-slate-500', running: 'bg-sky-400 animate-pulse', waiting: 'bg-amber-400 animate-pulse', done: 'bg-emerald-400',
  failed: 'bg-rose-500', skipped: 'bg-amber-500', cancelled: 'bg-slate-600',
};
const RUN_DOT: Record<RunStatus, string> = {
  planning: 'bg-violet-400 animate-pulse', awaiting_input: 'bg-amber-400 animate-pulse', awaiting_approval: 'bg-amber-400 animate-pulse', running: 'bg-sky-400 animate-pulse', completed: 'bg-emerald-400',
  failed: 'bg-rose-500', cancelled: 'bg-slate-500',
};

const IDEAS = [
  { title: 'Lead CRM', goal: 'A real-time lead CRM with a dashboard, pipeline board, contacts, deals, analytics and settings.' },
  { title: 'Notes app', goal: 'A simple notes web app with a Flask backend: create, edit, search and delete notes, saved to a JSON file.' },
  { title: 'Landing page', goal: 'A modern landing page for a coffee shop with hero, menu, gallery, opening hours and a contact form.' },
  { title: 'Expense tracker', goal: 'A personal expense tracker with charts, categories and CSV import, using HTML, JavaScript and a small Python API.' },
];

function TaskCard({ t, nameOf, now, selected, onClick }: {
  t: AgentTask; nameOf: (id: string) => string; now: number; selected: boolean; onClick: () => void;
}) {
  const waiting = t.status === 'queued' && t.dependsOn.length > 0;
  return (
    <button onClick={onClick}
      className={`w-full text-left rounded-lg border px-3 py-2 transition ${t.replaced ? 'opacity-50 ' : ''}${selected ? 'border-cyan-500 bg-slate-800' : 'border-slate-800 bg-slate-900/70 hover:bg-slate-800/70'}`}>
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[t.status]}`} />
        <span className="text-sm text-slate-100 truncate">{t.title}</span>
        {t.kind !== 'module' && <span className="text-[10px] uppercase tracking-wide text-slate-500 border border-slate-700 rounded px-1">{t.kind}</span>}
      </div>
      <div className="mt-0.5 pl-[18px] text-[11px] text-slate-400 font-mono">
        {t.status === 'waiting' ? 'needs your answer' : t.status === 'queued' ? (waiting ? 'waiting' : 'queued') : fmtDuration(t.startedAt, t.endedAt, now)}
        {' · '}{fmtTokens(t.tokens)} tokens
        {t.attempts > 1 && <span className="text-amber-400"> · attempt {t.attempts}</span>}
        {t.replans > 0 && !t.replaced && <span className="text-violet-300"> · re-planned</span>}
      </div>
      {waiting && (
        <div className="pl-[18px] text-[11px] text-slate-500 truncate">after {t.dependsOn.map(nameOf).join(', ')}</div>
      )}
      {t.status === 'running' && t.lastLog && (
        <div className="pl-[18px] text-[11px] text-sky-300/80 truncate">{t.lastLog}</div>
      )}
      {t.replaced && <div className="pl-[18px] text-[11px] text-violet-300/90">replaced by the planner with smaller agents</div>}
      {!t.replaced && (t.status === 'failed' || t.status === 'skipped') && t.error && (
        <div className="pl-[18px] text-[11px] text-rose-300/90 truncate">{t.error}</div>
      )}
    </button>
  );
}

export default function AgentMap() {
  const { snap, selectedTaskId, selectTask, cancelRun, user, setPanel, setGoal, setContinueFrom, threadRuns } = useApp();
  const live = !!snap && (['planning', 'running'].includes(snap.run.status) ||
    snap.tasks.some(t => t.status === 'running'));
  const paused = !!snap && ['awaiting_input', 'awaiting_approval'].includes(snap.run.status);
  const now = useNow(live);
  const { isVoiceActive, isThinking, isSpeaking, speakText } = useVoice();

  if (!snap) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-800 bg-slate-900/20 px-6 py-10 text-center flex flex-col items-center gap-4">
        <VoiceOrb isActive={isVoiceActive || isThinking || isSpeaking} size={110} />
        <div>
          <p className="text-lg font-medium text-slate-100">Hi, I&apos;m Adion.</p>
          <p className="mt-1 text-sm text-slate-400 max-w-xl">
            Tell me what to build, by voice or text. I plan it, then spawn one agent per module, all working in parallel.
            You&apos;ll watch them live right here.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-2xl mt-2">
          {IDEAS.map(i => (
            <button key={i.title} onClick={() => setGoal(i.goal)}
              className="text-left rounded-xl border border-slate-800 bg-slate-900/60 hover:border-cyan-500/60 hover:bg-slate-900 px-4 py-3 transition group">
              <span className="block text-sm text-slate-200 group-hover:text-cyan-200">{i.title}</span>
              <span className="block text-[11px] text-slate-500 mt-0.5 line-clamp-2">{i.goal}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }
  const { run, tasks } = snap;
  const nameOf = (id: string) => tasks.find(t => t.id === id)?.title.replace(/^Build (the )?/i, '') || id;
  const done = tasks.filter(t => t.status === 'done' && !t.replaced).length;
  const pct = run.maxTokens ? Math.min(100, Math.round((run.tokens / run.maxTokens) * 100)) : 0;
  const running = tasks.filter(t => t.status === 'running').length;
  const roots = tasks.filter(t => !t.parentId);
  const childrenOf = (id: string) => tasks.filter(t => t.parentId === id);
  const startSuggested = async (s: { title: string; command: string; cwd: string }) => {
    try { await api('/jobs', { method: 'POST', json: s }); setPanel('jobs'); } catch { /* error shown in Background panel */ }
  };

  if (run.answer) {
    // earlier turns of the same conversation, oldest first
    const prev = threadRuns.filter(r => r.id !== run.id && (r.answer || r.pcTaskId) && (r.createdAt || '') < (run.createdAt || ''))
      .sort((a, b) => (a.createdAt || '').localeCompare(b.createdAt || ''));
    return (
      <div className="space-y-3">
        {prev.map(r => (
          <section key={r.id} className="rounded-2xl border border-slate-800/70 bg-slate-900/25 p-4">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">You</p>
            <p className="text-sm text-slate-300 whitespace-pre-wrap">{r.goal}</p>
            <p className="mt-3 text-[11px] uppercase tracking-wider text-slate-500">Adion</p>
            {r.pcTaskId ? <div className="mt-1"><PcTaskCard taskId={r.pcTaskId} /></div> : <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{r.answer}</p>}
            {r.sources?.length > 0 && <p className="mt-2 text-[11px] text-slate-500">Sources: {r.sources.map((s, i) => <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer" className="text-cyan-300/80 hover:underline mr-2">[{i + 1}] {s.title.slice(0, 40)}</a>)}</p>}
          </section>
        ))}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-slate-500">
          <span className="h-2 w-2 rounded-full bg-emerald-400" /> Adion · {fmtTokens(run.tokens)} tokens · {fmtCost(run.cost)}
        </div>
        <p className="mt-1 text-sm text-slate-400">{run.goal}</p>
        {run.attachments?.length > 0 && <p className="mt-1 text-[11px] text-slate-500">Attached: {run.attachments.map(a => a.name).join(', ')}</p>}
        <div className="mt-3 text-sm text-slate-100 leading-relaxed whitespace-pre-wrap">
          {run.answer}{!['completed', 'failed', 'cancelled'].includes(run.status) && <span className="inline-block w-1.5 h-4 -mb-0.5 ml-0.5 bg-cyan-400 animate-pulse" />}
        </div>
        {run.sources?.length > 0 && (
          <div className="mt-4 border-t border-slate-800 pt-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Sources</p>
            <ol className="space-y-1 text-xs">
              {run.sources.map((s, i) => (
                <li key={s.url} className="truncate"><span className="text-slate-500">[{i + 1}]</span>{' '}
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-cyan-300 hover:underline">{s.title}</a></li>
              ))}
            </ol>
          </div>
        )}
        {run.pcTaskId && <div className="mt-4"><PcTaskCard taskId={run.pcTaskId} /></div>}
        {run.status === 'completed' && !run.pcTaskId && <button onClick={() => speakText(run.answer)} className="mt-3 text-[11px] rounded border border-slate-700 hover:border-cyan-500 px-2 py-1 text-slate-300">Read aloud</button>}
      </section>
      </div>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <RunInteraction run={run} />
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Root node */}
        <div className="lg:w-80 shrink-0 lg:pt-1">
          <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 relative">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${RUN_DOT[run.status]}`} />
              <span className="text-sm font-semibold truncate">{run.projectName || run.goal.slice(0, 60)}</span>
            </div>
            <div className="mt-1 pl-[18px] text-[11px] text-slate-400 font-mono leading-relaxed">
              {run.status === 'planning' ? 'planning…' : run.status === 'awaiting_approval' ? 'plan ready: waiting for you' : run.status === 'awaiting_input' ? 'waiting for your answer' : `${done}/${tasks.filter(t => !t.replaced).length} done · ${running} running`}<br />
              {run.plannerModel} · {fmtTokens(run.tokens)} tokens
              {run.maxTokens > 0 && ` of ${fmtTokens(run.maxTokens)}`}
              <br />{fmtCost(run.cost)}{run.estimateTokens > 0 && ` · forecast ~${fmtTokens(run.estimateTokens)}`}{run.cacheHit > 0 && ` · ${fmtTokens(run.cacheHit)} cached`}
            </div>
            {run.maxTokens > 0 && (
              <div className="mt-2 ml-[18px] h-1 rounded bg-slate-800 overflow-hidden">
                <div className={`h-full ${pct > 85 ? 'bg-rose-500' : 'bg-cyan-500'}`} style={{ width: `${pct}%` }} />
              </div>
            )}
            <div className="hidden lg:block absolute top-1/2 -right-6 w-6 h-px bg-slate-700" />
          </div>
          {run.attachments?.length > 0 && <p className="mt-2 text-[11px] text-slate-500">Attached: {run.attachments.map(a => a.name).join(', ')}</p>}
          {run.summary && <p className="mt-3 text-xs text-slate-400 leading-relaxed">{run.summary}</p>}
          {run.reusedPlan && <p className="mt-1 text-[11px] text-violet-300/90">Modelled on your earlier plan: {run.reusedPlan}</p>}
          {run.plannerModel === 'deepseek-reasoner' && <p className="mt-1 text-[11px] text-slate-500">Planned with deep reasoning</p>}
          <p className="mt-2 text-[11px] text-slate-500 font-mono break-all">{run.targetPath}</p>
          {run.error && (
            <p className="mt-2 text-xs text-rose-300 flex gap-1.5"><OctagonX className="h-3.5 w-3.5 shrink-0 mt-0.5" />{run.error}</p>
          )}
          {!live && !paused && run.check && (run.check.url || run.check.skipped) && (
            <div className={`mt-4 rounded-lg border p-2.5 ${run.check.skipped ? 'border-slate-800' : run.check.ok ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
              <div className="flex items-center gap-1.5 text-xs font-medium text-slate-200">
                {run.check.skipped ? <MonitorSmartphone className="h-3.5 w-3.5 text-slate-500" /> : run.check.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />}
                Browser check {run.check.skipped ? 'skipped' : run.check.ok ? 'passed' : 'found problems'}
              </div>
              {run.check.skipped && <p className="mt-1 text-[11px] text-slate-500">{run.check.reason || 'Nothing to open in a browser.'}</p>}
              {(run.check.issues || []).slice(0, 6).map(i => (
                <p key={i.msg} className={`mt-1 text-[11px] ${i.level === 'error' ? 'text-rose-300' : 'text-amber-300'}`}>{i.msg}</p>
              ))}
              {run.check.screenshot && (
                <a href={screenshotUrl(run.id, run.endedAt || '')} target="_blank" rel="noopener noreferrer" className="block mt-2">
                  {/* eslint-disable-next-line @next/next/no-img-element -- authenticated screenshot straight from the API */}
                  <img src={screenshotUrl(run.id, run.endedAt || '')} alt="What the finished site looks like" className="w-full max-h-48 object-cover object-top rounded border border-slate-800" />
                </a>
              )}
            </div>
          )}
          {!live && !paused && run.status === 'completed' && run.mode !== undefined && tasks.length > 0 && (
            <button onClick={() => { setContinueFrom(run.id); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
              className="mt-3 flex items-center gap-1.5 text-xs rounded-md border border-violet-500/40 text-violet-200 px-2.5 py-1 hover:bg-violet-500/10">
              <Pencil className="h-3 w-3" /> Change this project
            </button>
          )}
          {!live && run.suggested.length > 0 && (
            <div className="mt-4 space-y-1.5">
              <p className="text-[11px] uppercase tracking-wider text-slate-500">Run the result</p>
              {run.suggested.map(s => (
                <div key={s.command} className="rounded-md border border-slate-800 bg-slate-950 p-2">
                  <div className="text-xs text-slate-200">{s.title}</div>
                  <code className="block text-[11px] text-slate-400 font-mono break-all">{s.command}</code>
                  {user?.role === 'admin' ? (
                    <button onClick={() => startSuggested(s)} className="mt-1.5 text-[11px] rounded bg-emerald-600 hover:bg-emerald-500 px-2 py-0.5">Start in Background</button>
                  ) : (
                    <p className="mt-1 text-[10px] text-slate-500">Run it in a terminal in {s.cwd}</p>
                  )}
                </div>
              ))}
            </div>
          )}
          {(live || paused) && (
            <button onClick={cancelRun} className="mt-3 text-xs rounded-md border border-rose-500/40 text-rose-300 px-2.5 py-1 hover:bg-rose-500/10">
              Cancel run
            </button>
          )}
        </div>

        {/* Children */}
        <div className="flex-1 min-w-0 relative lg:pl-6">
          <div className="hidden lg:block absolute left-0 top-5 bottom-5 w-px bg-slate-700" />
          {paused && tasks.length === 0 ? (
            <p className="text-sm text-slate-500 py-3">Nothing is built yet. Agents start after you confirm.</p>
          ) : run.status === 'planning' && tasks.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-violet-300 py-3">
              <Loader2 className="h-4 w-4 animate-spin" /> Planner is splitting the goal into modules…
            </div>
          ) : (
            <div className="space-y-2">
              {roots.map(t => (
                <div key={t.id} className="relative">
                  <div className="hidden lg:block absolute -left-6 top-5 w-6 h-px bg-slate-700" />
                  <TaskCard t={t} nameOf={nameOf} now={now} selected={t.id === selectedTaskId}
                    onClick={() => selectTask(t.id === selectedTaskId ? null : t.id)} />
                  {childrenOf(t.id).length > 0 && (
                    <div className="ml-5 mt-1.5 pl-4 border-l border-slate-700 space-y-1.5">
                      {childrenOf(t.id).map(c => (
                        <div key={c.id} className="relative">
                          <div className="absolute -left-4 top-5 w-4 h-px bg-slate-700" />
                          <TaskCard t={c} nameOf={nameOf} now={now} selected={c.id === selectedTaskId}
                            onClick={() => selectTask(c.id === selectedTaskId ? null : c.id)} />
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      {!live && !paused && run.status === 'completed' && tasks.length > 0 && <Preview key={run.id} runId={run.id} />}
    </section>
  );
}
