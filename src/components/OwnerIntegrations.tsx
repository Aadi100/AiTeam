'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';

interface Svc { id: string; name: string; group: string; configured: boolean; clientIdHint?: string; redirectUri?: string; setup?: string[]; console?: string; review: string }

const inp = 'w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500';

function Row({ s, onChange }: { s: Svc; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [id, setId] = useState('');
  const [secret, setSecret] = useState('');
  const [msg, setMsg] = useState('');
  const [copied, setCopied] = useState(false);
  const save = async () => {
    try { await api(`/integrations/config/${s.id}`, { method: 'PUT', json: { clientId: id, clientSecret: secret } }); setId(''); setSecret(''); setMsg('Saved.'); onChange(); }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  const remove = async () => { await api(`/integrations/config/${s.id}`, { method: 'DELETE' }).catch(() => undefined); setMsg('Removed.'); onChange(); };
  return (
    <li className="rounded-lg border border-slate-800 bg-slate-950/40">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-2 px-3 py-2 text-left">
        {open ? <ChevronDown className="h-3.5 w-3.5 text-slate-500" /> : <ChevronRight className="h-3.5 w-3.5 text-slate-500" />}
        <span className="flex-1 text-xs text-slate-200">{s.name}</span>
        <span className={`text-[10px] ${s.configured ? 'text-emerald-400' : 'text-slate-500'}`}>{s.configured ? `set up · ${s.clientIdHint}` : 'not set up'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2">
          <ol className="list-decimal pl-5 space-y-0.5 text-[11px] text-slate-400">{s.setup?.map((t, i) => <li key={i}>{t}</li>)}</ol>
          {s.console && <a href={s.console} target="_blank" rel="noreferrer" className="text-[11px] text-cyan-300 hover:underline">Open the developer page</a>}
          <div>
            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Redirect URI to register</p>
            <div className="flex items-center gap-2"><code className="flex-1 break-all rounded bg-slate-900 px-2 py-1 text-[11px] text-cyan-200">{s.redirectUri}</code>
              <button onClick={() => { navigator.clipboard?.writeText(s.redirectUri || '').then(() => { setCopied(true); setTimeout(() => setCopied(false), 1200); }).catch(() => undefined); }}
                className="rounded border border-slate-700 px-2 py-1 text-[11px] text-slate-300 flex items-center gap-1">{copied ? <><Check className="h-3 w-3" /> copied</> : <><Copy className="h-3 w-3" /> copy</>}</button></div>
          </div>
          {s.review && <p className="text-[11px] text-amber-300/80">{s.review}</p>}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <input className={inp} placeholder="Client ID" value={id} onChange={e => setId(e.target.value)} autoComplete="off" />
            <input className={inp} type="password" placeholder="Client secret" value={secret} onChange={e => setSecret(e.target.value)} autoComplete="new-password" />
          </div>
          <div className="flex items-center gap-3">
            <button onClick={save} disabled={!id || !secret} className="rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-3 py-1 text-xs">Save</button>
            {s.configured && <button onClick={remove} className="text-xs text-rose-300 hover:text-rose-200">Remove</button>}
            {msg && <span className="text-[11px] text-slate-400">{msg}</span>}
          </div>
        </div>)}
    </li>
  );
}

/** Owner only: each service is set up once here; then every user just presses Connect. */
export default function OwnerIntegrations() {
  const [list, setList] = useState<Svc[]>([]);
  const [mode, setMode] = useState<'direct' | 'zapier'>('direct');
  const [err, setErr] = useState('');
  const load = useCallback(() => { api<{ mode: 'direct' | 'zapier'; providers: Svc[] }>('/integrations').then(r => { setList(r.providers); setMode(r.mode); }).catch(() => undefined); }, []);
  useEffect(() => { load(); }, [load]);
  const pick = async (m: 'direct' | 'zapier') => {
    try { await api('/integrations/mode', { method: 'PUT', json: { mode: m } }); setMode(m); setErr(''); } catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); }
  };
  const groups = Array.from(new Set(list.map(s => s.group)));
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-3">
      <div className="space-y-2">
        <p className="text-sm text-slate-200">How do people connect their apps?</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {([['direct', 'Connect buttons', 'Google, GitHub, Slack and more, each with its own Connect button. Free, no limits. You set each service up once below.'],
             ['zapier', 'Zapier (tool servers)', 'Everyone pastes their own Zapier link and gets thousands of apps. No set-up below, but the Zapier free plan is small.']] as const).map(([id, name, line]) => (
            <button key={id} onClick={() => pick(id)} className={`text-left rounded-lg border p-2.5 transition ${mode === id ? 'border-cyan-500 bg-cyan-500/10' : 'border-slate-700 hover:border-slate-500'}`}>
              <span className="block text-xs font-medium text-slate-100">{mode === id ? '● ' : '○ '}{name}</span>
              <span className="block mt-0.5 text-[11px] text-slate-400 leading-snug">{line}</span>
            </button>))}
        </div>
        <p className="text-[11px] text-slate-500">Only the chosen way is shown to members. Switching never deletes what people already connected.</p>
        {err && <p className="text-[11px] text-rose-300">{err}</p>}
      </div>
      {mode === 'direct' && <div>
        <p className="text-sm text-slate-200">Service set-up for connected apps (one time, owner only)</p>
        <p className="text-xs text-slate-500">This is NOT where you connect your accounts. Each service (Google, Slack…) requires the owner to register Adion with it once and paste its client ID and secret here.
          After that, you and every member connect your own accounts with one Connect button: <b className="text-slate-300">Assistant tab → side panel → Apps</b>.</p>
      </div>}
      {mode === 'direct' && groups.map(g => (
        <div key={g}><p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">{g}</p>
          <ul className="space-y-1.5">{list.filter(s => s.group === g).map(s => <Row key={s.id} s={s} onChange={load} />)}</ul></div>))}
      {mode === 'zapier' && <p className="text-xs text-slate-400">Nothing to set up here. Each person opens <b className="text-slate-300">Assistant tab → side panel → Apps</b> and pastes their own Zapier link (mcp.zapier.com → create a server → add actions → copy the link).</p>}
    </div>
  );
}
