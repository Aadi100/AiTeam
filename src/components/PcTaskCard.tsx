'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Laptop, Loader2, CheckCircle2, XCircle, ShieldAlert, Undo2, FolderLock, Clock, X } from 'lucide-react';
import { api, type PcTask, type PcStep } from '@/lib/api';
import { useApp } from '@/context/AppContext';

const RISK: Record<PcStep['risk'], string> = {
  read: 'text-slate-400 border-slate-700', low: 'text-slate-400 border-slate-700',
  change: 'text-amber-300 border-amber-500/40', danger: 'text-rose-300 border-rose-500/50',
};
const LIVE = ['planning', 'running'];
type Choice = 'once' | 'always' | 'deny';

function StepRow({ s }: { s: PcStep }) {
  const icon = s.status === 'ok' ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
    : s.status === 'error' || s.status === 'denied' ? <XCircle className="h-3.5 w-3.5 text-rose-400 shrink-0" />
    : s.status === 'skipped' ? <XCircle className="h-3.5 w-3.5 text-slate-600 shrink-0" />
    : <Clock className="h-3.5 w-3.5 text-slate-500 shrink-0" />;
  return (
    <li className="text-xs">
      <div className="flex items-start gap-2">
        <span className="mt-0.5">{icon}</span>
        <span className="flex-1 min-w-0 break-words text-slate-200">{s.preview}</span>
        {(s.risk === 'change' || s.risk === 'danger') && <span className={`shrink-0 rounded border px-1 text-[10px] uppercase ${RISK[s.risk]}`}>{s.risk}</span>}
      </div>
      {s.error && <p className="ml-5 text-[11px] text-rose-300 break-words">{s.error}</p>}
      {s.status === 'ok' && s.result && (s.risk === 'read') && (
        <details className="ml-5 mt-0.5">
          <summary className="cursor-pointer text-[11px] text-slate-500 hover:text-slate-300">show result</summary>
          <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-950 p-2 text-[11px] text-slate-300 whitespace-pre-wrap break-words">{s.result}</pre>
        </details>
      )}
    </li>
  );
}

/** One PC-control request: what Adion plans to do, the permission/approval controls, the result, and Undo. */
export default function PcTaskCard({ taskId, onClose }: { taskId: string; onClose?: () => void }) {
  const { refreshPc } = useApp();
  const [task, setTask] = useState<PcTask | null>(null);
  const [choice, setChoice] = useState<Record<string, Choice>>({});
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const [report, setReport] = useState('');

  const load = useCallback(() => { api<PcTask>(`/pc/tasks/${taskId}`).then(setTask).catch(e => setErr(e instanceof Error ? e.message : 'Failed')); }, [taskId]);
  useEffect(() => {
    load();
    const id = setInterval(() => load(), 1000);
    return () => clearInterval(id);
  }, [load]);

  const act = async (what: 'approve' | 'deny' | 'undo') => {
    if (!task) return;
    setBusy(what); setErr('');
    try {
      const t = await api<PcTask>(`/pc/tasks/${task.id}/${what}`, { method: 'POST', json: what === 'approve' ? { folders: choice } : {} });
      setTask(t);
      if (what === 'undo' && t.undoReport) setReport(`Undone: ${t.undoReport.undone}${t.undoReport.failed.length ? `, could not undo ${t.undoReport.failed.length}` : ''}`);
      refreshPc();
    } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); }
    setBusy('');
  };

  if (!task) return <div className="rounded-xl border border-slate-800 p-3 text-xs text-slate-500">{err || 'Loading…'}</div>;
  const waiting = task.status === 'awaiting_approval';
  const pending = task.steps.filter(s => s.status === 'pending');
  const allChosen = task.pendingFolders.every(f => choice[f]);
  const needsApprove = waiting && (task.pendingPhase === 'propose' || task.pendingFolders.length > 0);

  return (
    <div className={`rounded-xl border p-3 ${waiting ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-800 bg-slate-900/60'}`}>
      <div className="flex items-start gap-2">
        <Laptop className="h-4 w-4 mt-0.5 text-cyan-300 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-100 break-words">{task.request}</p>
          <p className="text-[11px] text-slate-500">
            {LIVE.includes(task.status) ? <span className="flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> working…</span>
              : task.status === 'awaiting_approval' ? 'waiting for you' : task.status}
          </p>
        </div>
        {onClose && <button onClick={onClose} title="Close" className="text-slate-500 hover:text-slate-200"><X className="h-4 w-4" /></button>}
      </div>

      {waiting && task.say && <p className="mt-2 text-sm text-slate-200">{task.pendingPhase === 'propose' ? 'Here is what I would do:' : task.say}</p>}

      {task.pendingFolders.length > 0 && (
        <div className="mt-2 space-y-2">
          {task.pendingFolders.map(f => (
            <div key={f} className="rounded-lg border border-slate-700 bg-slate-950/60 p-2">
              <p className="flex items-start gap-1.5 text-xs text-slate-200"><FolderLock className="h-3.5 w-3.5 mt-0.5 text-amber-300 shrink-0" /><span className="break-all">May I use <b>{f}</b>?</span></p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {([['once', 'Allow once'], ['always', 'Always allow'], ['deny', 'Not this folder']] as [Choice, string][]).map(([k, label]) => (
                  <button key={k} onClick={() => setChoice(c => ({ ...c, [f]: k }))}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] transition ${choice[f] === k ? (k === 'deny' ? 'border-rose-400 bg-rose-500/20 text-rose-100' : 'border-cyan-400 bg-cyan-500/20 text-cyan-100') : 'border-slate-700 text-slate-300 hover:border-cyan-500'}`}>{label}</button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {task.untrusted && waiting && (
        <p className="mt-2 flex items-start gap-1.5 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-[11px] text-amber-200">
          <ShieldAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" /> I planned this after reading file contents. Check the steps carefully: text inside a file can try to trick an assistant.
        </p>
      )}

      {task.steps.length > 0 && (
        <ul className="mt-2 space-y-1.5">{(waiting ? pending.concat(task.steps.filter(s => s.status !== 'pending')) : task.steps).slice(0, 40).map(s => <StepRow key={s.id} s={s} />)}</ul>
      )}

      {needsApprove && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => act('approve')} disabled={!!busy || !allChosen}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-3.5 py-1.5 text-xs font-medium transition">
            {busy === 'approve' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />} {task.pendingPhase === 'propose' ? 'Approve & run' : 'Continue'}
          </button>
          <button onClick={() => act('deny')} disabled={!!busy}
            className="rounded-lg border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 px-3 py-1.5 text-xs">Deny</button>
        </div>
      )}

      {!waiting && !LIVE.includes(task.status) && task.say && <p className={`mt-2 text-sm ${task.status === 'done' ? 'text-slate-100' : 'text-slate-300'}`}>{task.say}</p>}
      {task.undoable > 0 && !waiting && (
        <button onClick={() => act('undo')} disabled={!!busy}
          className="mt-2 flex items-center gap-1.5 rounded-lg border border-violet-500/40 text-violet-200 hover:bg-violet-500/10 px-3 py-1 text-xs">
          {busy === 'undo' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Undo2 className="h-3.5 w-3.5" />} Undo ({task.undoable})
        </button>
      )}
      {report && <p className="mt-1 text-[11px] text-violet-300">{report}</p>}
      {err && <p className="mt-1 text-[11px] text-rose-300">{err}</p>}
    </div>
  );
}
