'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, LogOut, FolderKanban, Boxes, Loader2, ArrowLeft } from 'lucide-react';
import { api, setToken } from '@/lib/api';
import { papi, getPortalToken, setPortalToken, fmtUsd, type PApp, type PClient, type PProject, type PUsage } from '@/lib/portal';
import AppDetail from '@/components/portal/AppDetail';

const input = 'w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500';
const btn = 'rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-4 py-2 text-sm font-medium transition';
const card = 'rounded-xl border border-slate-800 bg-slate-900/50 p-4';
const msgOf = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong');

// ───────────────────────── sign in / sign up ─────────────────────────
function Auth({ onDone, onOwner, embedded }: { embedded: boolean; onDone: (c: PClient) => void; onOwner: () => Promise<void> }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [f, setF] = useState({ name: '', email: '', password: '' });
  const [err, setErr] = useState('');
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(''); setInfo('');
    try {
      // A username without "@" is the Adion owner's own login (the same one as the main Adion screen).
      if (mode === 'login' && !f.email.includes('@')) {
        const o = await api<{ token: string; user: { role: string } }>('/auth/login', { method: 'POST', json: { username: f.email, password: f.password } });
        if (o.user.role !== 'admin') throw new Error('Only the Adion owner (admin) can sign in with a username here.');
        setToken(o.token); await onOwner(); setBusy(false); return;
      }
      const r = await papi<{ token?: string; client?: PClient; pending?: boolean; message?: string }>(`/${mode}`, { method: 'POST', json: f });
      if (r.pending) setInfo(r.message || 'Waiting for approval.');
      else if (r.token && r.client) { setPortalToken(r.token); onDone(r.client); }
    } catch (x) { setErr(msgOf(x)); }
    setBusy(false);
  };
  return (
    <div className={(embedded ? 'py-10' : 'min-h-screen') + ' flex items-center justify-center px-4'}>
      <form onSubmit={submit} className="w-full max-w-sm space-y-3">
        <h1 className="text-2xl font-semibold">Adion <span className="text-cyan-400">Connect</span></h1>
        <p className="text-sm text-slate-400">Add an assistant to your own app or website. It knows only your app and helps only your users.</p>
        {mode === 'signup' && <input className={input} placeholder="Your name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />}
        <input className={input} type={mode === 'signup' ? 'email' : 'text'} placeholder={mode === 'signup' ? 'Email' : 'Email (owner: your admin username)'} autoComplete="username" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <input className={input} type="password" placeholder="Password (8+ characters)" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
        {err && <p className="text-xs text-rose-400">{err}</p>}
        {info && <p className="text-xs text-emerald-300">{info}</p>}
        <button className={btn + ' w-full'} disabled={busy || !f.email || !f.password}>{busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        <button type="button" className="w-full text-xs text-slate-400 hover:text-cyan-300" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setErr(''); setInfo(''); }}>
          {mode === 'login' ? 'New here? Create an account' : 'Have an account? Sign in'}</button>
      </form>
    </div>
  );
}

// ───────────────────────── owner console ─────────────────────────
interface OSummary { clients: number; apps: number; monthCost: number; monthRevenue: number; monthCalls: number; top: { clientId: string; email: string; cost: number; price: number; calls: number }[] }
interface OClient { id: string; email: string; name: string; status: string; capUsd: number; apps: number; monthPrice: number }
interface OConfig { markup: number; defaultCapUsd: number; freeCreditUsd: number; signup: 'open' | 'approval' | 'closed' }

export function Owner() {
  const [sum, setSum] = useState<OSummary | null>(null);
  const [clients, setClients] = useState<OClient[]>([]);
  const [cfg, setCfg] = useState<OConfig | null>(null);
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState('');
  const load = useCallback(() => {
    api<OSummary>('/platform/owner/summary').then(setSum).catch(e => setErr(msgOf(e)));
    api<OClient[]>('/platform/owner/clients').then(setClients).catch(() => undefined);
    api<OConfig>('/platform/owner/config').then(setCfg).catch(() => undefined);
  }, []);
  useEffect(() => { load(); }, [load]);
  const setClient = async (id: string, body: Record<string, unknown>) => { try { await api(`/platform/owner/clients/${id}`, { method: 'PUT', json: body }); load(); } catch (e) { setErr(msgOf(e)); } };
  const saveCfg = async () => { if (!cfg) return; try { setCfg(await api<OConfig>('/platform/owner/config', { method: 'PUT', json: cfg })); setSaved('Saved.'); setTimeout(() => setSaved(''), 1500); } catch (e) { setErr(msgOf(e)); } };
  if (err && !sum) return <p className="text-sm text-rose-400">{err}</p>;
  return (
    <div className="space-y-5">
      {sum && <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[['Clients', String(sum.clients)], ['Apps', String(sum.apps)], ['My cost (month)', fmtUsd(sum.monthCost)], ['Billed (month)', fmtUsd(sum.monthRevenue)], ['Messages', String(sum.monthCalls)]].map(([k, v]) => (
          <div key={k} className={card}><p className="text-[10px] uppercase tracking-wider text-slate-500">{k}</p><p className="text-lg font-semibold font-mono text-cyan-300">{v}</p></div>))}
      </div>}
      {cfg && <div className={card}>
        <p className="text-sm text-slate-200 mb-2">Pricing &amp; sign-up</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-slate-400">
          <label>Markup × <input className={input} value={cfg.markup} onChange={e => setCfg({ ...cfg, markup: Number(e.target.value) || 1 })} /></label>
          <label>Default monthly cap $ <input className={input} value={cfg.defaultCapUsd} onChange={e => setCfg({ ...cfg, defaultCapUsd: Number(e.target.value) || 0 })} /></label>
          <label>Included credit $ <input className={input} value={cfg.freeCreditUsd} onChange={e => setCfg({ ...cfg, freeCreditUsd: Number(e.target.value) || 0 })} /></label>
          <label>Sign-up <select className={input} value={cfg.signup} onChange={e => setCfg({ ...cfg, signup: e.target.value as OConfig['signup'] })}><option value="open">Open</option><option value="approval">Needs my approval</option><option value="closed">Closed</option></select></label>
        </div>
        <div className="mt-3 flex items-center gap-3"><button className={btn} onClick={saveCfg}>Save</button>{saved && <span className="text-xs text-emerald-300">{saved}</span>}</div>
      </div>}
      <div className={card}>
        <p className="text-sm text-slate-200 mb-2">Clients</p>
        <div className="overflow-x-auto"><table className="w-full text-xs">
          <thead className="text-left text-slate-500"><tr><th className="py-1">Email</th><th>Apps</th><th>Month</th><th>Cap $</th><th>Status</th></tr></thead>
          <tbody>{clients.map(c => (
            <tr key={c.id} className="border-t border-slate-800 text-slate-300">
              <td className="py-1.5">{c.email}</td><td>{c.apps}</td><td className="font-mono">{fmtUsd(c.monthPrice)}</td>
              <td><input className="w-16 rounded bg-slate-950 border border-slate-800 px-1 py-0.5" defaultValue={c.capUsd || ''} placeholder="default" onBlur={e => { const v = Number(e.target.value) || 0; if (v !== c.capUsd) setClient(c.id, { capUsd: v }); }} /></td>
              <td><select className="rounded bg-slate-950 border border-slate-800 px-1 py-0.5" value={c.status} onChange={e => setClient(c.id, { status: e.target.value })}><option value="active">active</option><option value="pending">pending</option><option value="blocked">blocked</option></select></td>
            </tr>))}</tbody></table></div>
        {clients.length === 0 && <p className="text-xs text-slate-500 mt-2">No clients yet.</p>}
      </div>
    </div>
  );
}

// ───────────────────────── workspace ─────────────────────────
function Workspace({ client, onLogout, embedded }: { client: PClient; onLogout: () => void; embedded: boolean }) {
  const [projects, setProjects] = useState<PProject[]>([]);
  const [sel, setSel] = useState('');
  const [secret, setSecret] = useState('');
  const [view, setView] = useState<'apps' | 'owner'>('apps');
  const [isOwner, setIsOwner] = useState(false);
  const [usage, setUsage] = useState<PUsage | null>(null);
  const [err, setErr] = useState('');
  const [newProject, setNewProject] = useState('');
  const [newApp, setNewApp] = useState<{ pid: string; name: string; platform: string } | null>(null);

  const load = useCallback(() => {
    papi<PProject[]>('/projects').then(setProjects).catch(e => setErr(msgOf(e)));
    papi<PUsage>('/usage?days=30').then(setUsage).catch(() => undefined);
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api('/platform/owner/config').then(() => setIsOwner(true)).catch(() => setIsOwner(false)); }, []);

  const app = projects.flatMap(p => p.apps).find(a => a.id === sel);
  const patchApp = (a: PApp) => setProjects(ps => ps.map(p => ({ ...p, apps: p.apps.map(x => (x.id === a.id ? a : x)) })));
  const addProject = async () => {
    if (!newProject.trim()) return;
    try { await papi('/projects', { method: 'POST', json: { name: newProject } }); setNewProject(''); load(); } catch (e) { setErr(msgOf(e)); }
  };
  const addApp = async () => {
    if (!newApp || !newApp.name.trim()) return;
    try {
      const r = await papi<{ app: PApp; secretKey: string }>(`/projects/${newApp.pid}/apps`, { method: 'POST', json: { name: newApp.name, platform: newApp.platform } });
      setNewApp(null); setSecret(r.secretKey); setSel(r.app.id); load();
    } catch (e) { setErr(msgOf(e)); }
  };

  return (
    <div className={embedded ? '' : 'min-h-screen'}>
      <header className="flex items-center gap-3 border-b border-slate-800 px-4 py-3">
        {!embedded && <Link href="/" className="text-slate-400 hover:text-cyan-300" title="Back to Adion"><ArrowLeft className="h-4 w-4" /></Link>}
        <h1 className="font-semibold">Adion <span className="text-cyan-400">Connect</span>{isOwner && <span className="text-xs text-amber-300 ml-1.5">owner</span>}</h1>
        {isOwner && !embedded && <Link href="/" className="text-xs rounded-lg border border-cyan-500/40 text-cyan-200 px-2.5 py-1 hover:bg-cyan-500/10">Open Adion assistant</Link>}
        <span className="flex-1" />
        {usage && <span className="hidden sm:inline text-xs text-slate-400">This month: <b className="text-slate-200 font-mono">{fmtUsd(usage.monthSpend)}</b></span>}
        {isOwner && !embedded && <button onClick={() => setView(view === 'owner' ? 'apps' : 'owner')} className="text-xs rounded-lg border border-slate-700 px-2.5 py-1 hover:border-cyan-500">{view === 'owner' ? 'My apps' : 'Owner console'}</button>}
        <span className="hidden sm:inline text-xs text-slate-500">{client.email}</span>
        <button onClick={onLogout} title="Sign out" className="text-slate-400 hover:text-rose-300"><LogOut className="h-4 w-4" /></button>
      </header>
      {err && <p className="px-4 pt-3 text-xs text-rose-400">{err}</p>}
      {view === 'owner' ? <div className="mx-auto max-w-5xl p-4"><Owner /></div> : (
        <div className="mx-auto max-w-6xl p-4 grid grid-cols-1 md:grid-cols-[16rem_1fr] gap-6">
          <aside className="space-y-4">
            {projects.map(p => (
              <div key={p.id}>
                <p className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-slate-500 mb-1"><FolderKanban className="h-3.5 w-3.5" /> {p.name}
                  <span className="flex-1" /><button title="Delete project" className="normal-case text-[10px] text-slate-600 hover:text-rose-300" onClick={async () => { if (confirm(`Delete project "${p.name}" with all its apps?`)) { await papi(`/projects/${p.id}`, { method: 'DELETE' }).catch(() => undefined); if (p.apps.some(a => a.id === sel)) setSel(''); load(); } }}>delete</button></p>
                <ul className="space-y-1">
                  {p.apps.map(a => (
                    <li key={a.id}><button onClick={() => { setSel(a.id); if (a.id !== sel) setSecret(''); }} className={`w-full flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition ${sel === a.id ? 'bg-cyan-500/15 text-cyan-100' : 'text-slate-300 hover:bg-slate-800/60'}`}>
                      <Boxes className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{a.name}</span>{!a.enabled && <span className="text-[10px] text-slate-500">off</span>}</button></li>))}
                  {newApp?.pid === p.id ? (
                    <li className="space-y-1.5 pt-1">
                      <input autoFocus className={input} placeholder="App name" value={newApp.name} onChange={e => setNewApp({ ...newApp, name: e.target.value })} onKeyDown={e => { if (e.key === 'Enter') addApp(); }} />
                      <select className={input} value={newApp.platform} onChange={e => setNewApp({ ...newApp, platform: e.target.value })}><option value="web">Website / React / Next.js</option><option value="react-native">Mobile app (React Native)</option><option value="other">Other / my own server</option></select>
                      <div className="flex gap-2"><button className={btn + ' !px-3 !py-1 text-xs'} onClick={addApp}>Create</button><button className="text-xs text-slate-400" onClick={() => setNewApp(null)}>Cancel</button></div>
                    </li>
                  ) : <li><button onClick={() => setNewApp({ pid: p.id, name: '', platform: 'web' })} className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-slate-500 hover:text-cyan-300"><Plus className="h-3 w-3" /> Add app</button></li>}
                </ul>
              </div>))}
            <div className="flex gap-2"><input className={input} placeholder="New project" value={newProject} onChange={e => setNewProject(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addProject(); }} />
              <button className={btn + ' !px-3'} onClick={addProject} disabled={!newProject.trim()}><Plus className="h-4 w-4" /></button></div>
          </aside>
          <main className="min-w-0">
            {app ? <AppDetail key={app.id} app={app} secret={secret} setSecret={setSecret} onChange={patchApp}
              onDelete={async () => { await papi(`/apps/${app.id}`, { method: 'DELETE' }).catch(() => undefined); setSel(''); load(); }} />
              : <div className={card}><p className="text-sm text-slate-200">{projects.length === 0 ? 'Start by creating a project (for example "My Finance App"), then add an app inside it.' : 'Pick an app on the left, or add a new one.'}</p>
                <p className="mt-2 text-xs text-slate-500">A project groups your apps. Each app (website, mobile app…) gets its own keys, knowledge and rules.</p></div>}
          </main>
        </div>)}
    </div>
  );
}

export default function ConnectHub({ embedded = false }: { embedded?: boolean }) {
  const [client, setClient] = useState<PClient | null>(null);
  const [ready, setReady] = useState(false);
  // The owner (Adion admin) gets a normal workspace of their own, plus the Owner console button.
  const enterOwner = useCallback(async () => {
    const r = await api<{ token: string; client: PClient }>('/platform/owner/client-token', { method: 'POST', json: {} });
    setPortalToken(r.token); setClient(r.client);
  }, []);
  useEffect(() => {
    (getPortalToken() ? papi<PClient>('/me') : Promise.reject(new Error('no token')))
      .catch(() => { setPortalToken(''); return enterOwner().then(() => null); })   // already signed in to Adion as admin?
      .then(c => { if (c) setClient(c); }).catch(() => undefined).finally(() => setReady(true));
  }, [enterOwner]);
  if (!ready) return <div className={(embedded ? 'h-64' : 'min-h-screen') + ' flex items-center justify-center text-slate-500'}><Loader2 className="h-5 w-5 animate-spin" /></div>;
  if (!client) return <Auth embedded={embedded} onDone={setClient} onOwner={() => enterOwner()} />;
  return <Workspace embedded={embedded} client={client} onLogout={() => { setPortalToken(''); setClient(null); }} />;
}
