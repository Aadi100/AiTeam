'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Copy, Check, Trash2, Upload, Send, Loader2, KeyRound, RefreshCw, ShieldCheck, Eye, Zap } from 'lucide-react';
import { papi, fmtUsd, type PApp, type PAction, type PParam, type PConv, type PDoc, type PPending, type PReply, type PUsage } from '@/lib/portal';
import Markdown from '@/components/portal/Markdown';

const input = 'w-full rounded-lg bg-slate-950 border border-slate-700 px-2.5 py-1.5 text-sm outline-none focus:border-cyan-500';
const btn = 'rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-3 py-1.5 text-xs font-medium transition';
const ghost = 'rounded-lg border border-slate-700 hover:border-cyan-500 px-3 py-1.5 text-xs text-slate-300 transition';
const card = 'rounded-xl border border-slate-800 bg-slate-900/50 p-4';
const label = 'block text-[11px] uppercase tracking-wider text-slate-500 mb-1';
const msgOf = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong');

function CopyBtn({ text, what = 'copy' }: { text: string; what?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1400); }).catch(() => { /* blocked */ }); }} className={ghost + ' flex items-center gap-1'}>
      {done ? <><Check className="h-3 w-3" /> copied</> : <><Copy className="h-3 w-3" /> {what}</>}
    </button>
  );
}

// ───────────────────────── Overview ─────────────────────────
function Overview({ app, onChange, secret, setSecret }: { app: PApp; onChange: (a: PApp) => void; secret: string; setSecret: (s: string) => void }) {
  const [err, setErr] = useState('');
  const rotate = async () => {
    if (!confirm('Create a new secret key? The old one stops working immediately.')) return;
    try { setSecret((await papi<{ secretKey: string }>(`/apps/${app.id}/rotate-secret`, { method: 'POST', json: {} })).secretKey); } catch (e) { setErr(msgOf(e)); }
  };
  const toggle = async () => { try { onChange(await papi<PApp>(`/apps/${app.id}`, { method: 'PUT', json: { enabled: !app.enabled } })); } catch (e) { setErr(msgOf(e)); } };
  return (
    <div className="space-y-4">
      <div className={card}>
        <p className={label}>Public key (safe to put in your website or mobile app)</p>
        <div className="flex items-center gap-2"><code className="flex-1 break-all rounded bg-slate-950 px-2 py-1.5 text-xs text-cyan-200">{app.publicKey}</code><CopyBtn text={app.publicKey} /></div>
        <p className={label + ' mt-4'}>Secret key (only for YOUR server: it creates sign-in tickets for your users)</p>
        {secret ? (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-3">
            <p className="text-xs text-amber-200 mb-2">Copy it now. For safety it is shown only once.</p>
            <div className="flex items-center gap-2"><code className="flex-1 break-all rounded bg-slate-950 px-2 py-1.5 text-xs text-amber-100">{secret}</code><CopyBtn text={secret} /></div>
          </div>
        ) : (
          <div className="flex items-center gap-2"><code className="rounded bg-slate-950 px-2 py-1.5 text-xs text-slate-400">{app.secretPrefix}••••••••••••</code>
            <button onClick={rotate} className={ghost + ' flex items-center gap-1'}><RefreshCw className="h-3 w-3" /> New secret key</button></div>
        )}
        {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      </div>
      <div className={card + ' flex items-center justify-between gap-3'}>
        <div><p className="text-sm text-slate-200">Assistant is {app.enabled ? 'ON' : 'OFF'}</p><p className="text-xs text-slate-500">Switch it off to stop answering immediately.</p></div>
        <button onClick={toggle} className={app.enabled ? ghost : btn}>{app.enabled ? 'Switch off' : 'Switch on'}</button>
      </div>
      <div className={card}>
        <p className="text-sm text-slate-200 mb-1">Quick start</p>
        <ol className="list-decimal pl-5 space-y-1 text-xs text-slate-400">
          <li><b className="text-slate-300">Knowledge:</b> add your app&apos;s description, guides and FAQ.</li>
          <li><b className="text-slate-300">Actions:</b> import your API documentation, or add actions your app runs itself.</li>
          <li><b className="text-slate-300">Access &amp; rules:</b> pick what Adion may do and which websites may use the key.</li>
          <li><b className="text-slate-300">Test chat:</b> try it here.</li>
          <li><b className="text-slate-300">Guide:</b> copy the code into your website or mobile app.</li>
        </ol>
      </div>
    </div>
  );
}

// ───────────────────────── Knowledge ─────────────────────────
function Knowledge({ app }: { app: PApp }) {
  const [docs, setDocs] = useState<PDoc[]>([]);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const load = useCallback(() => { papi<PDoc[]>(`/apps/${app.id}/knowledge`).then(setDocs).catch(e => setErr(msgOf(e))); }, [app.id]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    setBusy(true); setErr('');
    try { await papi(`/apps/${app.id}/knowledge`, { method: 'POST', json: { title: title || 'Notes', text } }); setTitle(''); setText(''); load(); } catch (e) { setErr(msgOf(e)); }
    setBusy(false);
  };
  const upload = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true); setErr('');
    try { const fd = new FormData(); fd.append('file', f); await papi(`/apps/${app.id}/knowledge`, { method: 'POST', body: fd }); load(); } catch (e) { setErr(msgOf(e)); }
    setBusy(false);
  };
  return (
    <div className="space-y-4">
      <div className={card}>
        <p className="text-sm text-slate-200">Teach Adion about your app</p>
        <p className="text-xs text-slate-500 mb-3">Describe what the app is, how things work, prices and policies. Adion answers only from this (and your actions), and says &quot;I don&apos;t know&quot; otherwise.</p>
        <input className={input + ' mb-2'} placeholder="Title (optional), e.g. Refund policy" value={title} onChange={e => setTitle(e.target.value)} />
        <textarea className={input + ' resize-y'} rows={6} placeholder="Paste text here…" value={text} onChange={e => setText(e.target.value)} />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button className={btn} disabled={busy || !text.trim()} onClick={add}>Add text</button>
          <input ref={fileRef} type="file" accept=".txt,.md,.pdf,.docx,.csv,.json" className="hidden" onChange={e => { upload(e.target.files?.[0]); e.target.value = ''; }} />
          <button className={ghost + ' flex items-center gap-1'} onClick={() => fileRef.current?.click()} disabled={busy}><Upload className="h-3 w-3" /> Upload a file (PDF, Word, text)</button>
          {busy && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
        </div>
        {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      </div>
      <ul className="space-y-2">
        {docs.map(d => (
          <li key={d.id} className={card + ' flex items-start gap-3'}>
            <div className="flex-1 min-w-0"><p className="text-sm text-slate-200 truncate">{d.title}</p><p className="text-[11px] text-slate-500">{d.kind} · {d.chars.toLocaleString()} characters · {d.chunks} pieces</p>
              <p className="mt-1 text-xs text-slate-400 line-clamp-2">{d.preview}</p></div>
            <button title="Delete" onClick={async () => { await papi(`/apps/${app.id}/knowledge/${d.id}`, { method: 'DELETE' }).catch(() => undefined); load(); }} className="text-slate-500 hover:text-rose-300"><Trash2 className="h-4 w-4" /></button>
          </li>
        ))}
        {docs.length === 0 && <p className="text-xs text-slate-500">Nothing yet.</p>}
      </ul>
    </div>
  );
}

// ───────────────────────── Actions ─────────────────────────
const RISK: Record<string, string> = { read: 'text-emerald-300 border-emerald-500/40', write: 'text-amber-300 border-amber-500/40', danger: 'text-rose-300 border-rose-500/40' };

const TYPES = ['string', 'number', 'integer', 'boolean', 'object', 'array'];
/** "amount:number*, note:string" <-> params. A trailing * means required. */
const paramsToText = (a: PAction) => a.params.map(p => `${p.name}:${p.type}${p.required ? '*' : ''}`).join(', ');
function textToParams(t: string, a: PAction): PParam[] {
  return t.split(',').map(s => s.trim()).filter(Boolean).map(s => {
    const req = s.endsWith('*'); const [n, ty] = s.replace(/\*$/, '').split(':').map(x => x.trim());
    const old = a.params.find(p => p.name === n);
    return { name: n, in: old?.in || (a.mode === 'api' && a.method === 'GET' ? 'query' : 'body'), type: TYPES.includes(ty) ? ty : 'string', required: req, description: old?.description || '' };
  });
}

function Actions({ app, onChange }: { app: PApp; onChange: (a: PApp) => void }) {
  const [list, setList] = useState<PAction[]>([]);
  const [src, setSrc] = useState('');
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');
  const [nf, setNf] = useState({ name: '', description: '', mode: 'client' as 'api' | 'client', method: 'GET', path: '', risk: 'read' });
  const fileRef = useRef<HTMLInputElement>(null);
  const load = useCallback(() => { papi<PAction[]>(`/apps/${app.id}/actions`).then(setList).catch(e => setErr(msgOf(e))); }, [app.id]);
  useEffect(() => { load(); }, [load]);
  const patch = async (a: PAction, body: Record<string, unknown>) => {
    try { const u = await papi<PAction>(`/apps/${app.id}/actions/${a.id}`, { method: 'PUT', json: body }); setList(l => l.map(x => (x.id === a.id ? u : x))); } catch (e) { setErr(msgOf(e)); }
  };
  const doImport = async (text: string) => {
    setErr(''); setNote('');
    try { const r = await papi<{ imported: number }>(`/apps/${app.id}/actions/import`, { method: 'POST', json: { source: text } }); setNote(`Imported ${r.imported} actions. They are switched OFF until you enable them.`); setSrc(''); load(); onChange(await papi<PApp>(`/apps/${app.id}`)); } catch (e) { setErr(msgOf(e)); }
  };
  const create = async () => {
    setErr('');
    try { await papi(`/apps/${app.id}/actions`, { method: 'POST', json: nf }); setNf({ ...nf, name: '', description: '', path: '' }); load(); } catch (e) { setErr(msgOf(e)); }
  };
  return (
    <div className="space-y-4">
      <div className={card}>
        <p className="text-sm text-slate-200">Import from your API documentation</p>
        <p className="text-xs text-slate-500 mb-2">Paste or upload an OpenAPI / Swagger file (JSON or YAML) or a Postman collection. Every endpoint becomes an action.</p>
        <textarea className={input + ' font-mono text-xs resize-y'} rows={4} placeholder="Paste your OpenAPI / Swagger / Postman JSON or YAML here…" value={src} onChange={e => setSrc(e.target.value)} />
        <div className="mt-2 flex flex-wrap gap-2">
          <button className={btn} disabled={!src.trim()} onClick={() => doImport(src)}>Import</button>
          <input ref={fileRef} type="file" accept=".json,.yaml,.yml" className="hidden" onChange={async e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) doImport(await f.text()); }} />
          <button className={ghost} onClick={() => fileRef.current?.click()}>Upload a file</button>
          <button className={ghost} onClick={async () => { await papi(`/apps/${app.id}/actions/bulk`, { method: 'POST', json: { enable: true, onlyRead: true } }).catch(() => undefined); load(); }}>Enable all read-only actions</button>
        </div>
        {note && <p className="mt-2 text-xs text-emerald-300">{note}</p>}
        {err && <p className="mt-2 text-xs text-rose-400">{err}</p>}
      </div>
      <div className={card}>
        <p className="text-sm text-slate-200 mb-2">Add an action by hand</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input className={input} placeholder="name, e.g. add_transaction" value={nf.name} onChange={e => setNf({ ...nf, name: e.target.value })} />
          <input className={input} placeholder="what it does (Adion reads this)" value={nf.description} onChange={e => setNf({ ...nf, description: e.target.value })} />
          <select className={input} value={nf.mode} onChange={e => setNf({ ...nf, mode: e.target.value as 'api' | 'client' })}>
            <option value="client">Runs inside my app (nothing leaves the app)</option><option value="api">Adion calls my server (API)</option></select>
          <select className={input} value={nf.risk} onChange={e => setNf({ ...nf, risk: e.target.value })}><option value="read">Reads data</option><option value="write">Changes data</option><option value="danger">Risky (delete, transfer…)</option></select>
          {nf.mode === 'api' && <><select className={input} value={nf.method} onChange={e => setNf({ ...nf, method: e.target.value })}>{['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m}>{m}</option>)}</select>
            <input className={input} placeholder="/path/{id}" value={nf.path} onChange={e => setNf({ ...nf, path: e.target.value })} /></>}
        </div>
        <button className={btn + ' mt-2'} disabled={!nf.name.trim()} onClick={create}>Add action</button>
        <p className="mt-1 text-[11px] text-slate-500">After adding, fill in its Inputs below (e.g. amount:number*, note:string). In-app actions are registered in your app code (see Guide).</p>
      </div>
      <ul className="space-y-2">
        {list.map(a => (
          <li key={a.id} className={card}>
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-sm text-cyan-200">{a.name}</code>
              <span className={`rounded border px-1.5 text-[10px] uppercase ${RISK[a.risk]}`}>{a.risk}</span>
              <span className="text-[11px] text-slate-500">{a.mode === 'api' ? `${a.method} ${a.path}` : 'in-app'}</span>
              <span className="flex-1" />
              <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer"><input type="checkbox" checked={a.enabled} onChange={e => patch(a, { enabled: e.target.checked })} /> On</label>
              <button title="Delete" onClick={async () => { await papi(`/apps/${app.id}/actions/${a.id}`, { method: 'DELETE' }).catch(() => undefined); load(); }} className="text-slate-500 hover:text-rose-300"><Trash2 className="h-4 w-4" /></button>
            </div>
            <input className={input + ' mt-2 text-xs'} defaultValue={a.description} placeholder="Describe it so Adion knows when to use it" onBlur={e => { if (e.target.value !== a.description) patch(a, { description: e.target.value }); }} />
            <label className="mt-2 flex items-center gap-1 text-[11px] text-slate-400">Inputs:
              <input className="flex-1 rounded bg-slate-950 border border-slate-800 px-1.5 py-0.5 text-[11px] font-mono outline-none focus:border-cyan-500" defaultValue={paramsToText(a)} placeholder="amount:number*, note:string   (* = required)"
                onBlur={e => { if (e.target.value !== paramsToText(a)) patch(a, { params: textToParams(e.target.value, a) }); }} />
              <select className="rounded bg-slate-950 border border-slate-800 px-1 py-0.5" value={a.risk} onChange={e => patch(a, { risk: e.target.value })}>
                <option value="read">reads</option><option value="write">changes</option><option value="danger">risky</option></select></label>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
              <label className="flex items-center gap-1 cursor-pointer"><input type="checkbox" checked={a.neverAi} onChange={e => patch(a, { neverAi: e.target.checked })} /> Never by AI</label>
              <label className="flex items-center gap-1 cursor-pointer"><input type="checkbox" checked={a.requiresUser} onChange={e => patch(a, { requiresUser: e.target.checked })} /> Signed-in users only</label>
              <label className="flex items-center gap-1 flex-1 min-w-[12rem]">Hide fields:
                <input className="flex-1 rounded bg-slate-950 border border-slate-800 px-1.5 py-0.5 text-[11px] outline-none focus:border-cyan-500" defaultValue={a.hideFields.join(', ')} placeholder="e.g. password, card_number"
                  onBlur={e => patch(a, { hideFields: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} /></label>
            </div>
          </li>
        ))}
        {list.length === 0 && <p className="text-xs text-slate-500">No actions yet. Without actions Adion can only answer questions.</p>}
      </ul>
    </div>
  );
}

// ───────────────────────── Access & rules ─────────────────────────
const LEVELS: { id: PApp['accessLevel']; title: string; text: string }[] = [
  { id: 'limited', title: 'Limited', text: 'Reads only. Adion answers and shows data but changes nothing.' },
  { id: 'standard', title: 'Standard', text: 'Also changes data, but every change asks the user to confirm first.' },
  { id: 'complete', title: 'Complete', text: 'Also risky actions (delete, transfer). These still always ask to confirm.' },
];

function Access({ app, onChange }: { app: PApp; onChange: (a: PApp) => void }) {
  const [f, setF] = useState({ name: app.name, persona: app.persona, greeting: app.greeting, description: app.description, rules: app.rules, language: app.language,
    strictScope: app.strictScope, accessLevel: app.accessLevel, origins: app.allowedOrigins.join('\n'), allowNative: app.allowNative, apiBaseUrl: app.apiBaseUrl,
    apiAuth: app.apiAuth, headerName: '', headerValue: '', monthlyCapUsd: String(app.monthlyCapUsd || '') });
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const save = async () => {
    setErr(''); setMsg('');
    const body: Record<string, unknown> = { name: f.name, persona: f.persona, greeting: f.greeting, description: f.description, rules: f.rules, language: f.language || 'auto',
      strictScope: f.strictScope, accessLevel: f.accessLevel, allowedOrigins: f.origins.split('\n').map(s => s.trim()).filter(Boolean), allowNative: f.allowNative,
      apiBaseUrl: f.apiBaseUrl, apiAuth: f.apiAuth, monthlyCapUsd: Number(f.monthlyCapUsd) || 0 };
    if (f.headerName.trim() && f.headerValue.trim()) body.apiHeaders = { [f.headerName.trim()]: f.headerValue.trim() };
    try { onChange(await papi<PApp>(`/apps/${app.id}`, { method: 'PUT', json: body })); setMsg('Saved.'); setF(x => ({ ...x, headerName: '', headerValue: '' })); } catch (e) { setErr(msgOf(e)); }
  };
  return (
    <div className="space-y-4">
      <div className={card + ' grid grid-cols-1 sm:grid-cols-2 gap-3'}>
        <div><span className={label}>App name</span><input className={input} value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></div>
        <div><span className={label}>Assistant name (optional)</span><input className={input} placeholder="e.g. Penny" value={f.persona} onChange={e => setF({ ...f, persona: e.target.value })} /></div>
        <div className="sm:col-span-2"><span className={label}>First message</span><input className={input} placeholder="Hi! How can I help?" value={f.greeting} onChange={e => setF({ ...f, greeting: e.target.value })} /></div>
        <div className="sm:col-span-2"><span className={label}>What is your app? (Adion reads this first)</span><textarea className={input} rows={3} value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
        <div className="sm:col-span-2"><span className={label}>Rules Adion must follow</span><textarea className={input} rows={3} placeholder="e.g. Never promise refunds. Always ask for the order number." value={f.rules} onChange={e => setF({ ...f, rules: e.target.value })} /></div>
        <div><span className={label}>Reply language</span><input className={input} placeholder="auto = the user's language" value={f.language} onChange={e => setF({ ...f, language: e.target.value })} /></div>
        <label className="flex items-center gap-2 text-sm text-slate-300 mt-5"><input type="checkbox" checked={f.strictScope} onChange={e => setF({ ...f, strictScope: e.target.checked })} /> Only talk about this app</label>
      </div>

      <div className={card}>
        <p className="text-sm text-slate-200 mb-2 flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-cyan-300" /> What may Adion do?</p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {LEVELS.map(l => (
            <button key={l.id} onClick={() => setF({ ...f, accessLevel: l.id })} className={`text-left rounded-lg border p-3 transition ${f.accessLevel === l.id ? 'border-cyan-400 bg-cyan-500/10' : 'border-slate-800 hover:border-slate-600'}`}>
              <span className="block text-sm text-slate-100">{l.title}</span><span className="block text-[11px] text-slate-400 mt-1">{l.text}</span></button>))}
        </div>
      </div>

      <div className={card + ' space-y-3'}>
        <p className="text-sm text-slate-200">Where can the assistant run?</p>
        <div><span className={label}>Allowed websites (one per line)</span>
          <textarea className={input + ' font-mono text-xs'} rows={3} placeholder={'https://myapp.com\nhttps://*.myapp.com\nhttp://localhost:3000'} value={f.origins} onChange={e => setF({ ...f, origins: e.target.value })} />
          <p className="text-[11px] text-slate-500 mt-1">A website not on this list cannot use your public key.</p></div>
        <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={f.allowNative} onChange={e => setF({ ...f, allowNative: e.target.checked })} /> Allow mobile apps and servers (they send no website address)</label>
      </div>

      <div className={card + ' space-y-3'}>
        <p className="text-sm text-slate-200">API connection (only if Adion should call YOUR server)</p>
        <div><span className={label}>API address</span><input className={input} placeholder="https://api.myapp.com/v1" value={f.apiBaseUrl} onChange={e => setF({ ...f, apiBaseUrl: e.target.value })} /></div>
        <div><span className={label}>How does Adion log in to your API?</span>
          <select className={input} value={f.apiAuth} onChange={e => setF({ ...f, apiAuth: e.target.value as PApp['apiAuth'] })}>
            <option value="forward">With the signed-in user&apos;s own token (your app passes it with each chat)</option>
            <option value="header">With a fixed header, such as a service key</option><option value="none">No login</option></select></div>
        {f.apiAuth === 'header' && (
          <div className="grid grid-cols-2 gap-2"><input className={input} placeholder="Header name, e.g. X-Api-Key" value={f.headerName} onChange={e => setF({ ...f, headerName: e.target.value })} />
            <input className={input} type="password" placeholder={app.hasApiHeaders ? 'saved (enter a new value to replace)' : 'Header value'} value={f.headerValue} onChange={e => setF({ ...f, headerValue: e.target.value })} /></div>)}
        <div><span className={label}>Monthly spending limit for this app (USD, 0 = account limit only)</span><input className={input} value={f.monthlyCapUsd} onChange={e => setF({ ...f, monthlyCapUsd: e.target.value })} /></div>
      </div>
      <div className="flex items-center gap-3"><button className={btn} onClick={save}>Save changes</button>{msg && <span className="text-xs text-emerald-300">{msg}</span>}{err && <span className="text-xs text-rose-400">{err}</span>}</div>
    </div>
  );
}

// ───────────────────────── Test chat ─────────────────────────
interface Line { role: 'user' | 'assistant' | 'error'; text: string }

function TestChat({ app }: { app: PApp }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PPending[]>([]);
  const [anon, setAnon] = useState(false);
  const [userToken, setUserToken] = useState('');
  const [mock, setMock] = useState<Record<string, string>>({});
  const conv = useRef('');
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [lines, pending]);

  const base = `/apps/${app.id}/test-chat`;
  const apply = (r: PReply) => { conv.current = r.conversationId; if (r.reply) setLines(l => [...l, { role: 'assistant', text: r.reply }]); setPending(r.pending); };
  const call = async (path: string, body: Record<string, unknown>) => {
    setBusy(true);
    try { apply(await papi<PReply>(base + path, { method: 'POST', json: { ...body, conversationId: conv.current || undefined, anonymous: anon, userToken: userToken || undefined } })); }
    catch (e) { setLines(l => [...l, { role: 'error', text: msgOf(e) }]); }
    setBusy(false);
  };
  const send = () => { const t = text.trim(); if (!t || busy) return; setText(''); setLines(l => [...l, { role: 'user', text: t }]); setPending([]); call('', { message: t }); };
  return (
    <div className="space-y-3">
      <div className={card + ' flex flex-wrap items-center gap-4 text-xs text-slate-300'}>
        <label className="flex items-center gap-1.5 cursor-pointer"><input type="checkbox" checked={anon} onChange={e => { setAnon(e.target.checked); conv.current = ''; setLines([]); setPending([]); }} /> Try as a visitor who is not signed in</label>
        <label className="flex items-center gap-1.5 flex-1 min-w-[14rem]">User token (for API connection tests):
          <input className="flex-1 rounded bg-slate-950 border border-slate-800 px-1.5 py-1 text-xs outline-none focus:border-cyan-500" type="password" value={userToken} onChange={e => setUserToken(e.target.value)} placeholder="optional" /></label>
        <button className={ghost} onClick={() => { conv.current = ''; setLines([]); setPending([]); }}>New chat</button>
      </div>
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 h-[26rem] overflow-y-auto p-3 space-y-2">
        {lines.length === 0 && <p className="text-xs text-slate-500">{app.greeting || `Say something to ${app.persona || app.name}…`}</p>}
        {lines.map((l, i) => (
          <div key={i} className={`flex ${l.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${l.role === 'user' ? 'bg-cyan-600 text-white' : l.role === 'error' ? 'bg-rose-950 text-rose-200' : 'bg-slate-800 text-slate-100'}`}>{l.text}</div>
          </div>))}
        {pending.map(p => (
          <div key={p.callId} className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
            {p.needsConfirm ? (
              <>
                <p className="text-[11px] uppercase tracking-wider text-amber-300">Please confirm</p>
                <p className="mt-1 text-slate-100">{p.summary}</p>
                <div className="mt-2 flex gap-2">
                  <button className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1 text-xs" disabled={busy}
                    onClick={() => (p.kind === 'confirm' ? call('/confirm', { decisions: [{ callId: p.callId, approve: true }] })
                      : call('/result', { results: [{ callId: p.callId, result: safeJson(mock[p.callId]) }] }))}>Confirm</button>
                  <button className="rounded-lg border border-slate-600 px-3 py-1 text-xs" disabled={busy}
                    onClick={() => (p.kind === 'confirm' ? call('/confirm', { decisions: [{ callId: p.callId, approve: false }] }) : call('/result', { results: [{ callId: p.callId, approve: false }] }))}>Cancel</button>
                </div>
              </>
            ) : <p className="text-slate-300">Waiting for your app to run <code className="text-cyan-200">{p.name}</code></p>}
            {p.kind === 'client' && (
              <div className="mt-2"><p className="text-[11px] text-slate-400">In your real app, your own code runs <code>{p.name}</code>. Here, type the result it would return (JSON) to test:</p>
                <textarea className={input + ' mt-1 font-mono text-xs'} rows={2} placeholder='{"ok": true}' value={mock[p.callId] || ''} onChange={e => setMock({ ...mock, [p.callId]: e.target.value })} />
                {!p.needsConfirm && <button className={btn + ' mt-1'} disabled={busy} onClick={() => call('/result', { results: [{ callId: p.callId, result: safeJson(mock[p.callId]) }] })}>Send result</button>}
              </div>)}
          </div>))}
        {busy && <div className="flex items-center gap-2 text-xs text-slate-400"><Loader2 className="h-3 w-3 animate-spin" /> thinking…</div>}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2">
        <input className={input} placeholder="Ask something…" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') send(); }} />
        <button className={btn + ' flex items-center gap-1'} onClick={send} disabled={busy || !text.trim()}><Send className="h-3.5 w-3.5" /> Send</button>
      </div>
      <p className="text-[11px] text-slate-500">Test chats use your real knowledge and actions and count toward usage. The portal tester acts as a signed-in user.</p>
    </div>
  );
}
function safeJson(t?: string): unknown { try { return t ? JSON.parse(t) : { ok: true }; } catch { return t; } }

// ───────────────────────── Conversations ─────────────────────────
function Convs({ app }: { app: PApp }) {
  const [list, setList] = useState<PConv[]>([]);
  const [open, setOpen] = useState<PConv | null>(null);
  const load = useCallback(() => { papi<PConv[]>(`/apps/${app.id}/conversations`).then(setList).catch(() => setList([])); }, [app.id]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <ul className="space-y-2">
        {list.map(c => (
          <li key={c.id}><button onClick={() => papi<PConv>(`/apps/${app.id}/conversations/${c.id}`).then(setOpen)} className={card + ' w-full text-left hover:border-cyan-500/50'}>
            <p className="text-sm text-slate-200 truncate">{c.title || '(empty)'}</p><p className="text-[11px] text-slate-500">{c.endUser} · {c.count} messages</p></button></li>))}
        {list.length === 0 && <p className="text-xs text-slate-500">No conversations yet.</p>}
      </ul>
      <div>
        {open ? (
          <div className={card + ' space-y-2'}>
            <div className="flex items-center justify-between"><p className="text-xs text-slate-400">{open.endUser}</p>
              <button className="text-slate-500 hover:text-rose-300" title="Delete" onClick={async () => { await papi(`/apps/${app.id}/conversations/${open.id}`, { method: 'DELETE' }).catch(() => undefined); setOpen(null); load(); }}><Trash2 className="h-4 w-4" /></button></div>
            {(open.messages || []).map((m, i) => <p key={i} className={`text-sm whitespace-pre-wrap ${m.role === 'user' ? 'text-cyan-200' : 'text-slate-200'}`}><b>{m.role === 'user' ? 'User' : 'Assistant'}:</b> {m.text}</p>)}
          </div>) : <p className="text-xs text-slate-500">Pick a conversation.</p>}
      </div>
    </div>
  );
}

// ───────────────────────── Usage ─────────────────────────
function UsageTab({ app }: { app: PApp }) {
  const [u, setU] = useState<PUsage | null>(null);
  useEffect(() => { papi<PUsage>(`/apps/${app.id}/usage?days=30`).then(setU).catch(() => setU(null)); }, [app.id]);
  if (!u) return <p className="text-xs text-slate-500">Loading…</p>;
  const max = Math.max(1e-9, ...u.byDay.map(d => d.cost));
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[['Last 30 days', fmtUsd(u.cost)], ['This month', fmtUsd(u.monthSpend)], ['Messages', String(u.calls)], ['Tokens', u.tokens.toLocaleString()]].map(([k, v]) => (
          <div key={k} className={card}><p className="text-[10px] uppercase tracking-wider text-slate-500">{k}</p><p className="text-lg font-semibold font-mono text-cyan-300">{v}</p></div>))}
      </div>
      <p className="text-xs text-slate-400">Limits: this app {u.caps?.app ? fmtUsd(u.caps.app) : 'no own limit'} · your account {u.caps?.client ? fmtUsd(u.caps.client) : 'none'} per month. Included credit: {fmtUsd(u.freeCredit)}.</p>
      {u.byDay.length > 0 && <div className="flex items-end gap-1 h-24">{u.byDay.map(d => <div key={d.day} title={`${d.day}: ${fmtUsd(d.cost)}`} className="flex-1 min-w-[3px] rounded-t bg-cyan-500/70" style={{ height: `${Math.max(6, (d.cost / max) * 100)}%` }} />)}</div>}
    </div>
  );
}

// ───────────────────────── Guide ─────────────────────────
function Guide({ app }: { app: PApp }) {
  const [plat, setPlat] = useState('');
  const [data, setData] = useState<{ platform: string; platforms: { id: string; name: string }[]; markdown: string } | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => { papi<typeof data>(`/apps/${app.id}/docs${plat ? `?platform=${plat}` : ''}`).then(setData).catch(e => setErr(msgOf(e))); }, [app.id, plat]);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">{data?.platforms.map(p => (
        <button key={p.id} onClick={() => setPlat(p.id)} className={`rounded-full border px-3 py-1 text-xs ${(plat || data.platform) === p.id ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100' : 'border-slate-700 text-slate-300 hover:border-cyan-500'}`}>{p.name}</button>))}</div>
      {err && <p className="text-xs text-rose-400">{err}</p>}
      <div className={card}>{data ? <Markdown text={data.markdown} /> : <p className="text-xs text-slate-500">Loading…</p>}</div>
    </div>
  );
}

// ───────────────────────── shell ─────────────────────────
const TABS = [['overview', 'Overview', KeyRound], ['knowledge', 'Knowledge', Eye], ['actions', 'Actions', Zap], ['access', 'Access & rules', ShieldCheck], ['test', 'Test chat', Send],
  ['conversations', 'Conversations', Eye], ['usage', 'Usage', Eye], ['guide', 'Guide', Copy]] as const;

export default function AppDetail({ app, secret, setSecret, onChange, onDelete }: { app: PApp; secret: string; setSecret: (s: string) => void; onChange: (a: PApp) => void; onDelete: () => void }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('overview');
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold">{app.name}</h2>
        <span className={`rounded-full border px-2 py-0.5 text-[11px] ${app.enabled ? 'border-emerald-500/40 text-emerald-300' : 'border-slate-600 text-slate-400'}`}>{app.enabled ? 'on' : 'off'}</span>
        <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400">{app.accessLevel}</span>
        <span className="flex-1" />
        <button className="text-xs text-slate-500 hover:text-rose-300 flex items-center gap-1" onClick={() => { if (confirm(`Delete "${app.name}" and everything in it (knowledge, actions, conversations)?`)) onDelete(); }}><Trash2 className="h-3.5 w-3.5" /> Delete app</button>
      </div>
      <div className="flex flex-wrap gap-1 border-b border-slate-800 mb-4">
        {TABS.map(([id, name]) => (
          <button key={id} onClick={() => setTab(id)} className={`px-3 py-2 text-xs transition ${tab === id ? 'text-cyan-300 border-b-2 border-cyan-400' : 'text-slate-400 hover:text-slate-200'}`}>{name}</button>))}
      </div>
      {tab === 'overview' && <Overview app={app} onChange={onChange} secret={secret} setSecret={setSecret} />}
      {tab === 'knowledge' && <Knowledge app={app} />}
      {tab === 'actions' && <Actions app={app} onChange={onChange} />}
      {tab === 'access' && <Access key={app.id + app.accessLevel + app.name + app.apiBaseUrl} app={app} onChange={onChange} />}
      {tab === 'test' && <TestChat app={app} />}
      {tab === 'conversations' && <Convs app={app} />}
      {tab === 'usage' && <UsageTab app={app} />}
      {tab === 'guide' && <Guide app={app} />}
    </div>
  );
}
