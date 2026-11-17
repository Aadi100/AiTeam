'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Plug, Unplug, Loader2, Send, CheckCircle2, AlertTriangle, Blocks, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useApp } from '@/context/AppContext';

export interface IProvider { id: string; name: string; group: string; configured: boolean; review: string; caps: string[] }
export interface ILink { id: string; provider: string; email: string; createdAt: string }
interface Overview { mode: 'direct' | 'zapier'; providers: IProvider[]; links: ILink[] }

const msgOf = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong');

interface IServer { id: string; name: string; host: string; status: string; error: string; tools: { name: string; read: boolean; desc: string }[] }

/** Tool servers (MCP, for example a Zapier link): each person adds their own, so Adion acts only in their apps. */
function ToolServers({ canWrite, onCount }: { canWrite: boolean; onCount: (n: number) => void }) {
  const [list, setList] = useState<IServer[]>([]);
  const [form, setForm] = useState({ name: '', url: '', token: '' });
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState('');
  const [err, setErr] = useState('');
  const load = useCallback(() => { api<IServer[]>('/integrations/mcp').then(r => { setList(r); onCount(r.filter(x => x.status === 'ok').length); }).catch(() => undefined); }, [onCount]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    setBusy('add'); setErr('');
    try { await api('/integrations/mcp', { method: 'POST', json: form }); setForm({ name: '', url: '', token: '' }); setOpen(false); load(); }
    catch (e) { setErr(msgOf(e)); }
    setBusy('');
  };
  const refresh = async (id: string) => { setBusy(id); try { await api(`/integrations/mcp/${id}/refresh`, { method: 'POST', json: {} }); } catch (e) { setErr(msgOf(e)); } setBusy(''); load(); };
  const remove = async (s: IServer) => { if (confirm(`Remove "${s.name}"? Adion will no longer be able to use its tools.`)) { await api(`/integrations/mcp/${s.id}`, { method: 'DELETE' }).catch(() => undefined); load(); } };
  const box = 'w-full rounded-md bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs outline-none focus:border-cyan-500';
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Tool servers (Zapier and other MCP links)</p>
      <ul className="space-y-1.5">
        {list.map(s => (
          <li key={s.id} className="rounded-lg border border-slate-800 bg-slate-950/50 px-2.5 py-2">
            <div className="flex items-center gap-2">
              <Blocks className={`h-3.5 w-3.5 shrink-0 ${s.status === 'ok' ? 'text-emerald-400' : 'text-rose-400'}`} />
              <span className="flex-1 min-w-0"><span className="block text-xs text-slate-200 truncate">{s.name}</span>
                <span className="block text-[10px] text-slate-500">{s.host} · {s.status === 'ok' ? `${s.tools.length} tools (${s.tools.filter(t => !t.read).length} ask first)` : 'not working'}</span></span>
              <button onClick={() => refresh(s.id)} title="Check again" className="text-slate-500 hover:text-cyan-300">{busy === s.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}</button>
              <button onClick={() => remove(s)} title="Remove" className="text-slate-500 hover:text-rose-300"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
            {s.status !== 'ok' && s.error && <p className="mt-1 text-[10px] text-rose-300">{s.error}</p>}
          </li>))}
      </ul>
      {!open && <button onClick={() => setOpen(true)} disabled={!canWrite} className="mt-1.5 flex items-center gap-1 rounded-md border border-slate-700 hover:border-cyan-500 disabled:opacity-40 px-2.5 py-1 text-[11px]"><Blocks className="h-3 w-3" /> Add a tool server</button>}
      {open && (
        <div className="mt-1.5 space-y-1.5 rounded-lg border border-slate-800 bg-slate-900/40 p-2.5">
          <input className={box} placeholder="Name, e.g. My Zapier" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <input className={box} placeholder="Server link (https://...)" value={form.url} onChange={e => setForm({ ...form, url: e.target.value })} autoComplete="off" />
          <input className={box} type="password" placeholder="Token (only if the service gives one separately)" value={form.token} onChange={e => setForm({ ...form, token: e.target.value })} autoComplete="off" />
          <p className="text-[10px] text-slate-500 leading-relaxed">Zapier: open mcp.zapier.com, create a server, add the actions you want, then copy its link. Treat the link like a password: it is stored encrypted and never shown again. Adion asks you before it runs anything that sends or changes something.</p>
          {err && <p className="text-[11px] text-rose-300">{err}</p>}
          <div className="flex gap-2">
            <button onClick={add} disabled={busy === 'add' || !form.name.trim() || !form.url.trim()} className="flex items-center gap-1 rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-3 py-1 text-[11px] font-medium">{busy === 'add' && <Loader2 className="h-3 w-3 animate-spin" />} Connect</button>
            <button onClick={() => { setOpen(false); setErr(''); }} className="text-[11px] text-slate-400 hover:text-slate-200">Cancel</button>
          </div>
        </div>)}
    </div>
  );
}

/** Connect Gmail, Calendar, GitHub, Slack, Notion... with one button each, then just ask Adion. */
export default function AppsPanel() {
  const { setPcTaskId, user } = useApp();
  const [ov, setOv] = useState<Overview | null>(null);
  const [busy, setBusy] = useState('');
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const [ask, setAsk] = useState('');
  const [servers, setServers] = useState(0);
  const load = useCallback(() => { api<Overview>('/integrations').then(setOv).catch(e => setNote({ ok: false, text: msgOf(e) })); }, []);
  useEffect(() => { load(); }, [load]);
  // coming back from the service's "Allow" page
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const done = q.get('connected'), err = q.get('connect_error');
    if (done || err) {
      Promise.resolve().then(() => setNote(done ? { ok: true, text: `Connected ${q.get('as') || done}.` } : { ok: false, text: err || '' }));
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const connect = async (id: string) => {
    setBusy(id); setNote(null);
    try { const r = await api<{ url: string }>(`/integrations/connect/${id}`, { method: 'POST', json: {} }); window.location.assign(r.url); }
    catch (e) { setNote({ ok: false, text: msgOf(e) }); setBusy(''); }
  };
  const disconnect = async (l: ILink) => {
    if (!confirm(`Disconnect ${l.email}? Adion will no longer have access to it.`)) return;
    await api(`/integrations/links/${l.id}`, { method: 'DELETE' }).catch(() => undefined); load();
  };
  const send = async () => {
    const t = ask.trim(); if (!t) return;
    setBusy('ask'); setNote(null);
    try { const task = await api<{ id: string }>('/integrations/tasks', { method: 'POST', json: { request: t } }); setAsk(''); setPcTaskId(task.id); }
    catch (e) { setNote({ ok: false, text: msgOf(e) }); }
    setBusy('');
  };

  if (!ov) return <p className="text-xs text-slate-500">{note?.text || 'Loading…'}</p>;
  const groups = Array.from(new Set(ov.providers.map(p => p.group)));
  const name = (id: string) => ov.providers.find(p => p.id === id)?.name.split(' (')[0] || id;
  const canWrite = user?.role !== 'viewer';
  const zapier = ov.mode === 'zapier';
  const ready = zapier ? servers > 0 : ov.links.length > 0;
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-slate-300 mb-1.5">Ask Adion about your accounts</p>
        <div className="flex gap-1.5">
          <input className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs outline-none focus:border-cyan-500" placeholder="e.g. any unread mail from Sara?" value={ask}
            onChange={e => setAsk(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') send(); }} disabled={!ready} />
          <button onClick={send} disabled={!ask.trim() || busy === 'ask'} className="rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-2.5"><Send className="h-3.5 w-3.5" /></button>
        </div>
        <p className="mt-1 text-[11px] text-slate-500">{ready ? 'You can also just say it in the chat or by voice. Adion asks you before it sends or changes anything.' : zapier ? 'Add your Zapier link below first.' : 'Connect an account below first.'}</p>
      </div>

      {note && <p className={`flex items-start gap-1.5 rounded-lg border p-2 text-[11px] ${note.ok ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/5' : 'border-rose-500/40 text-rose-300 bg-rose-500/5'}`}>
        {note.ok ? <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" /> : <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />}<span className="break-words">{note.text}</span></p>}

      {!zapier && ov.links.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Connected</p>
          <ul className="space-y-1.5">
            {ov.links.map(l => (
              <li key={l.id} className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/50 px-2.5 py-1.5">
                <Plug className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                <span className="flex-1 min-w-0"><span className="block text-xs text-slate-200 truncate">{l.email}</span><span className="block text-[10px] text-slate-500">{name(l.provider)}</span></span>
                <button onClick={() => disconnect(l)} title="Disconnect" className="text-slate-500 hover:text-rose-300"><Unplug className="h-3.5 w-3.5" /></button>
              </li>))}
          </ul>
        </div>)}

      {!zapier && groups.map(g => (
        <div key={g}>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">{g}</p>
          <ul className="space-y-1.5">
            {ov.providers.filter(p => p.group === g).map(p => (
              <li key={p.id} className="rounded-lg border border-slate-800 bg-slate-900/40 px-2.5 py-2">
                <div className="flex items-center gap-2">
                  <span className="flex-1 min-w-0 text-xs text-slate-200">{p.name}</span>
                  {p.configured
                    ? <button onClick={() => connect(p.id)} disabled={!canWrite || busy === p.id} className="flex items-center gap-1 rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-2.5 py-1 text-[11px] font-medium">
                      {busy === p.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plug className="h-3 w-3" />} Connect</button>
                    : <span className="text-[10px] text-slate-500">{user?.role === 'admin' ? 'set up on the Owner tab' : 'not available yet'}</span>}
                </div>
                {p.review && p.configured && <p className="mt-1 text-[10px] text-amber-300/80">{p.review}</p>}
              </li>))}
          </ul>
        </div>))}

      {zapier && <ToolServers canWrite={canWrite} onCount={setServers} />}
    </div>
  );
}
