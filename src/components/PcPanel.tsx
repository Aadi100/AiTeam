'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { OctagonX, Play, FolderPlus, Trash2, Undo2 } from 'lucide-react';
import { api, type PcActivity, type PcSettings } from '@/lib/api';
import { useApp } from '@/context/AppContext';

/** Side-panel tab: the emergency switch, trust mode, allowed folders and the activity log. */
export default function PcPanel() {
  const { pcVersion, setPcTaskId } = useApp();
  const [s, setS] = useState<PcSettings | null>(null);
  const [act, setAct] = useState<PcActivity | null>(null);
  const [path, setPath] = useState('');
  const [err, setErr] = useState('');

  const load = useCallback(() => {
    api<PcSettings>('/pc/settings').then(setS).catch(e => setErr(e instanceof Error ? e.message : 'Failed'));
    api<PcActivity>('/pc/activity?limit=40').then(setAct).catch(() => {});
  }, []);
  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id); }, [load, pcVersion]);

  const put = async (body: Partial<Pick<PcSettings, 'paused' | 'trust'>>) => { try { setS(await api<PcSettings>('/pc/settings', { method: 'PUT', json: body })); } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); } };
  const addFolder = async () => {
    try { setS(await api<PcSettings>('/pc/folders', { method: 'POST', json: { path } })); setPath(''); setErr(''); } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); }
  };
  const removeFolder = async (p: string) => { try { setS(await api<PcSettings>('/pc/folders', { method: 'DELETE', json: { path: p } })); } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); } };
  const undo = async (id: string) => { try { await api(`/pc/tasks/${id}/undo`, { method: 'POST', json: {} }); load(); } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); } };

  if (!s) return <p className="text-xs text-slate-500">{err || 'Loading…'}</p>;
  return (
    <div className="space-y-4">
      <button onClick={() => put({ paused: !s.paused })}
        className={`w-full flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition ${s.paused ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200 hover:bg-emerald-500/20' : 'border-rose-500/50 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20'}`}>
        {s.paused ? <><Play className="h-4 w-4" /> PC control is PAUSED. Turn on</> : <><OctagonX className="h-4 w-4" /> Pause all PC control</>}
      </button>

      <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer select-none">
        <input type="checkbox" className="mt-0.5" checked={s.trust} onChange={e => put({ trust: e.target.checked })} />
        <span><b>Trust mode</b>: let Adion create, copy, move and rename files inside allowed folders without asking. Deleting, running commands and opening programs <u>always</u> ask. Everything stays logged and undoable.</span>
      </label>

      <div>
        <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Folders Adion may use</p>
        <ul className="space-y-1 text-xs">
          <li className="flex justify-between gap-2 rounded border border-slate-800 px-2 py-1"><span className="break-all text-slate-300">{s.desktop}</span><span className="text-slate-500 shrink-0">Desktop</span></li>
          {s.folders.map(f => (
            <li key={f} className="flex items-center justify-between gap-2 rounded border border-slate-800 px-2 py-1">
              <span className="break-all text-slate-300">{f}</span>
              <button onClick={() => removeFolder(f)} title="Stop allowing" className="text-slate-500 hover:text-rose-300 shrink-0"><Trash2 className="h-3.5 w-3.5" /></button>
            </li>
          ))}
        </ul>
        <div className="mt-2 flex gap-1.5">
          <input value={path} onChange={e => setPath(e.target.value)} placeholder="Add a folder, e.g. Documents" onKeyDown={e => { if (e.key === 'Enter' && path.trim()) addFolder(); }}
            className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs outline-none focus:border-cyan-500" />
          <button onClick={addFolder} disabled={!path.trim()} className="rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-2 text-xs"><FolderPlus className="h-3.5 w-3.5" /></button>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">Any other folder: Adion asks you the first time. Passwords, keys and browser data are never allowed.</p>
      </div>

      {err && <p className="text-[11px] text-rose-400">{err}</p>}

      <div>
        <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Recent requests</p>
        {act?.tasks.length ? (
          <ul className="space-y-1.5">
            {act.tasks.slice(0, 8).map(t => (
              <li key={t.id} className="rounded-lg border border-slate-800 bg-slate-950/40 px-2.5 py-1.5 text-[11px]">
                <button onClick={() => setPcTaskId(t.id)} className="block w-full text-left">
                  <p className="truncate text-slate-200">{t.request}</p>
                  <p className="text-slate-500">{t.status.replace('_', ' ')} · {t.steps.length} step(s)</p>
                </button>
                {t.undoable > 0 && <button onClick={() => undo(t.id)} className="mt-1 flex items-center gap-1 text-violet-300 hover:text-violet-100"><Undo2 className="h-3 w-3" /> Undo {t.undoable}</button>}
              </li>
            ))}
          </ul>
        ) : <p className="text-xs text-slate-500">Nothing yet. Try: “Adion, open Spotify” or “find my invoices on the desktop”.</p>}
      </div>

      {act && act.actions.length > 0 && (
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Activity log</p>
          <ul className="space-y-1">
            {act.actions.slice(0, 25).map(a => (
              <li key={a.id} className="text-[11px] flex gap-1.5">
                <span className={a.ok ? 'text-emerald-400' : 'text-rose-400'}>{a.ok ? '●' : '✕'}</span>
                <span className="text-slate-400 break-all">{a.summary}{a.auto ? ' (auto)' : ''}{a.undone ? ' (undone)' : ''}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
