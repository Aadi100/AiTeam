'use client';

import React from 'react';
import { Loader2, OctagonX } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';
import { fmtDuration, fmtTokens, type AgentTask, type RunStatus, type TaskStatus } from '@/lib/api';
import { useNow } from '@/lib/hooks';

const DOT: Record<TaskStatus, string> = {
  queued: 'bg-slate-500', running: 'bg-sky-400 animate-pulse', done: 'bg-emerald-400',
  failed: 'bg-rose-500', skipped: 'bg-amber-500', cancelled: 'bg-slate-600',
};
const RUN_DOT: Record<RunStatus, string> = {
  planning: 'bg-violet-400 animate-pulse', running: 'bg-sky-400 animate-pulse', completed: 'bg-emerald-400',
  failed: 'bg-rose-500', cancelled: 'bg-slate-500',
};

function TaskCard({ t, nameOf, now, selected, onClick }: {
  t: AgentTask; nameOf: (id: string) => string; now: number; selected: boolean; onClick: () => void;
}) {
  const waiting = t.status === 'queued' && t.dependsOn.length > 0;
  return (
    <button onClick={onClick}
      className={`w-full text-left rounded-lg border px-3 py-2 transition ${selected ? 'border-cyan-500 bg-slate-800' : 'border-slate-800 bg-slate-900/70 hover:bg-slate-800/70'}`}>
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[t.status]}`} />
        <span className="text-sm text-slate-100 truncate">{t.title}</span>
        {t.kind !== 'module' && <span className="text-[10px] uppercase tracking-wide text-slate-500 border border-slate-700 rounded px-1">{t.kind}</span>}
      </div>
      <div className="mt-0.5 pl-[18px] text-[11px] text-slate-400 font-mono">
        {t.status === 'queued' ? (waiting ? 'waiting' : 'queued') : fmtDuration(t.startedAt, t.endedAt, now)}
        {' · '}{fmtTokens(t.tokens)} tokens
        {t.attempts > 1 && <span className="text-amber-400"> · attempt {t.attempts}</span>}
      </div>
      {waiting && (
        <div className="pl-[18px] text-[11px] text-slate-500 truncate">after {t.dependsOn.map(nameOf).join(', ')}</div>
      )}
      {t.status === 'running' && t.lastLog && (
        <div className="pl-[18px] text-[11px] text-sky-300/80 truncate">{t.lastLog}</div>
      )}
      {(t.status === 'failed' || t.status === 'skipped') && t.error && (
        <div className="pl-[18px] text-[11px] text-rose-300/90 truncate">{t.error}</div>
      )}
    </button>
  );
}

export default function AgentMap() {
  const { snap, selectedTaskId, selectTask, cancelRun, user, setPanel } = useApp();
  const live = !!snap && (['planning', 'running'].includes(snap.run.status) ||
    snap.tasks.some(t => t.status === 'running'));
  const now = useNow(live);

  if (!snap) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-800 p-10 text-center text-sm text-slate-500">
        No run selected. Describe a goal above: a planner will split it into modules and spawn one agent per module, working in parallel.
      </div>
    );
  }
  const { run, tasks } = snap;
  const nameOf = (id: string) => tasks.find(t => t.id === id)?.title.replace(/^Build (the )?/i, '') || id;
  const done = tasks.filter(t => t.status === 'done').length;
  const pct = run.maxTokens ? Math.min(100, Math.round((run.tokens / run.maxTokens) * 100)) : 0;
  const running = tasks.filter(t => t.status === 'running').length;
  const roots = tasks.filter(t => !t.parentId);
  const childrenOf = (id: string) => tasks.filter(t => t.parentId === id);
  const startSuggested = async (s: { title: string; command: string; cwd: string }) => {
    try { await api('/jobs', { method: 'POST', json: s }); setPanel('jobs'); } catch { /* error shown in Background panel */ }
  };

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Root node */}
        <div className="lg:w-80 shrink-0 lg:pt-1">
          <div className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 relative">
            <div className="flex items-center gap-2">
              <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${RUN_DOT[run.status]}`} />
              <span className="text-sm font-semibold truncate">{run.projectName || run.goal.slice(0, 60)}</span>
            </div>
            <div className="mt-1 pl-[18px] text-[11px] text-slate-400 font-mono leading-relaxed">
              {run.status === 'planning' ? 'planning…' : `${done}/${tasks.length} done · ${running} running`}<br />
              {run.plannerModel} · {fmtTokens(run.tokens)} tokens
              {run.maxTokens > 0 && ` of ${fmtTokens(run.maxTokens)}`}
            </div>
            {run.maxTokens > 0 && (
              <div className="mt-2 ml-[18px] h-1 rounded bg-slate-800 overflow-hidden">
                <div className={`h-full ${pct > 85 ? 'bg-rose-500' : 'bg-cyan-500'}`} style={{ width: `${pct}%` }} />
              </div>
            )}
            <div className="hidden lg:block absolute top-1/2 -right-6 w-6 h-px bg-slate-700" />
          </div>
          {run.summary && <p className="mt-3 text-xs text-slate-400 leading-relaxed">{run.summary}</p>}
          <p className="mt-2 text-[11px] text-slate-500 font-mono break-all">{run.targetPath}</p>
          {run.error && (
            <p className="mt-2 text-xs text-rose-300 flex gap-1.5"><OctagonX className="h-3.5 w-3.5 shrink-0 mt-0.5" />{run.error}</p>
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
          {live && (
            <button onClick={cancelRun} className="mt-3 text-xs rounded-md border border-rose-500/40 text-rose-300 px-2.5 py-1 hover:bg-rose-500/10">
              Cancel run
            </button>
          )}
        </div>

        {/* Children */}
        <div className="flex-1 min-w-0 relative lg:pl-6">
          <div className="hidden lg:block absolute left-0 top-5 bottom-5 w-px bg-slate-700" />
          {run.status === 'planning' && tasks.length === 0 ? (
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
    </section>
  );
}
