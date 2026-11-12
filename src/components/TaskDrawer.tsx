'use client';

import React, { useEffect, useState } from 'react';
import { X, FileText, Volume2 } from 'lucide-react';
import { useVoice } from '@/context/VoiceContext';
import { useApp } from '@/context/AppContext';
import { api, fmtTokens, type AgentTask } from '@/lib/api';

const LEVEL: Record<string, string> = {
  info: 'text-slate-300', ok: 'text-emerald-300', warn: 'text-amber-300', error: 'text-rose-300',
};

export default function TaskDrawer() {
  const { selectedTaskId } = useApp();
  return selectedTaskId ? <DrawerBody key={selectedTaskId} /> : null;
}

function DrawerBody() {
  const { snap, selectedTaskId, selectTask, retryTask } = useApp();
  const { speakText } = useVoice();
  const [detail, setDetail] = useState<AgentTask | null>(null);
  const [file, setFile] = useState<{ path: string; content: string } | null>(null);
  const summary = snap?.tasks.find(t => t.id === selectedTaskId);
  // refetch whenever the live snapshot says this task changed
  const stamp = summary ? `${summary.status}:${summary.tokens}:${summary.fileCount}:${summary.lastLog}` : '';

  useEffect(() => {
    if (!snap || !selectedTaskId) return;
    let cancelled = false;
    api<AgentTask>(`/runs/${snap.run.id}/tasks/${selectedTaskId}`).then(d => { if (!cancelled) setDetail(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, [snap?.run.id, selectedTaskId, stamp]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!snap || !selectedTaskId || !summary) return null;
  const d = detail && detail.id === selectedTaskId ? detail : null;

  const openFile = async (path: string) => {
    try { setFile(await api(`/runs/${snap.run.id}/tasks/${selectedTaskId}/file?path=${encodeURIComponent(path)}`)); }
    catch { setFile({ path, content: '(could not read file)' }); }
  };

  return (
    <aside className="fixed inset-y-0 right-0 w-full sm:w-[460px] z-40 bg-slate-950 border-l border-slate-800 shadow-2xl flex flex-col">
      <header className="flex items-start justify-between gap-3 p-4 border-b border-slate-800">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold truncate">{summary.title}</h2>
          <p className="text-[11px] text-slate-400 font-mono mt-0.5">
            {summary.status} · {summary.model || 'no model yet'} · {fmtTokens(summary.tokensIn)} in / {fmtTokens(summary.tokensOut)} out
          </p>
          {summary.folder && <p className="text-[11px] text-slate-500 font-mono">writes only in {summary.folder}/</p>}
        </div>
        <button onClick={() => selectTask(null)} className="text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-5 text-sm">
        {summary.description && <p className="text-xs text-slate-400 leading-relaxed">{summary.description}</p>}
        {summary.summary && <p className="text-xs text-emerald-300/90">{summary.summary}</p>}
        <button onClick={() => speakText(`${summary.title}. Status ${summary.status}. ${summary.summary || ''} ${summary.error || ''}`)}
          className="flex items-center gap-1.5 text-xs text-cyan-300 hover:text-cyan-200"><Volume2 className="h-3.5 w-3.5" /> Ask Adion to read this</button>
        {summary.error && <p className="text-xs text-rose-300 break-words">{summary.error}</p>}
        {['failed', 'skipped', 'cancelled'].includes(summary.status) &&
          !['planning', 'running'].includes(snap.run.status) && (
          <button onClick={() => retryTask(summary.id)}
            className="rounded-md bg-amber-600 hover:bg-amber-500 px-3 py-1.5 text-xs font-medium">
            Retry this agent{summary.status !== 'failed' ? ' (and what was blocked)' : ''}
          </button>
        )}

        <div>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Files ({d?.files?.length ?? summary.fileCount})</h3>
          <ul className="space-y-1">
            {(d?.files || []).map(f => (
              <li key={f.path}>
                <button onClick={() => openFile(f.path)} className="flex items-center gap-2 text-xs text-cyan-300 hover:underline">
                  <FileText className="h-3 w-3" />{f.path}<span className="text-slate-500">{(f.size / 1024).toFixed(1)} KB</span>
                </button>
              </li>
            ))}
          </ul>
          {file && (
            <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900">
              <div className="flex justify-between px-3 py-1.5 border-b border-slate-800 text-[11px] text-slate-400 font-mono">
                {file.path}<span className="flex gap-3"><button onClick={() => speakText(file.content.slice(0, 2500))} title="Read aloud">read aloud</button><button onClick={() => setFile(null)}>close</button></span>
              </div>
              <pre className="p-3 text-[11px] leading-relaxed overflow-auto max-h-80 text-slate-200 font-mono whitespace-pre">{file.content}</pre>
            </div>
          )}
        </div>

        <div>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Log</h3>
          <div className="space-y-1 font-mono text-[11px]">
            {(d?.log || []).map((l, i) => (
              <div key={i} className={LEVEL[l.level] || 'text-slate-300'}>
                <span className="text-slate-600">{new Date(l.t).toLocaleTimeString()} </span>{l.msg}
              </div>
            ))}
            {!d?.log?.length && <div className="text-slate-600">no log yet</div>}
          </div>
        </div>
      </div>
    </aside>
  );
}
