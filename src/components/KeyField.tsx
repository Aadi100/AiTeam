'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface Info { set: boolean; hint: string; shared: boolean }

/** One API key, stored encrypted in the server database. The key is never kept in the browser. */
export default function KeyField({ title, endpoint, placeholder, minLen, help, missing, active }: {
  title: string; endpoint: string; placeholder: string; minLen: number; help: React.ReactNode; missing: string; active: boolean;
}) {
  const [info, setInfo] = useState<Info | null>(null);
  const [val, setVal] = useState('');
  const [msg, setMsg] = useState('');
  const load = useCallback(() => { api<Info>(endpoint).then(setInfo).catch(() => setInfo(null)); }, [endpoint]);
  useEffect(() => { if (active) load(); }, [active, load]);
  const save = async () => {
    try { await api(endpoint, { method: 'PUT', json: { key: val } }); setVal(''); setMsg('Saved, encrypted in the database'); load(); }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  const remove = async () => {
    try { await api(endpoint, { method: 'DELETE' }); setMsg('Removed'); load(); }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  return (
    <div className="text-xs space-y-1.5">
      <span className="text-slate-300">{title}</span>
      {info?.set && <p className="text-emerald-400 font-mono">Saved: {info.hint} <button onClick={remove} className="ml-2 text-rose-300 hover:text-rose-200 font-sans">remove</button></p>}
      {info && !info.set && info.shared && <p className="text-slate-400">Using the shared team key set by an admin. You can add your own below.</p>}
      {info && !info.set && !info.shared && <p className="text-amber-300">{missing}</p>}
      <div className="flex gap-2">
        <input type="password" autoComplete="off" placeholder={placeholder} value={val} onChange={e => setVal(e.target.value)}
          className="flex-1 rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-2 outline-none focus:border-cyan-500 font-mono" />
        <button onClick={save} disabled={val.trim().length < minLen} className="rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-3 text-xs font-medium">Save</button>
      </div>
      <span className="block text-slate-500">{help} {msg}</span>
    </div>
  );
}
