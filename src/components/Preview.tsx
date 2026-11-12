'use client';

import React, { useState } from 'react';
import { Eye, Smartphone, Monitor, RefreshCw, ExternalLink, X, Loader2 } from 'lucide-react';
import { api, backendOrigin } from '@/lib/api';

/** Live preview of a finished static site, inside Adion. The page runs in a sandboxed iframe (no access to Adion)
 *  and is served with a 15-minute read-only token that cannot call the API. */
export default function Preview({ runId }: { runId: string }) {
  const [url, setUrl] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [phone, setPhone] = useState(false);
  const [nonce, setNonce] = useState(0);

  const open = async () => {
    setBusy(true); setErr('');
    try {
      const r = await api<{ url: string }>(`/runs/${runId}/preview-token`, { method: 'POST' });
      setUrl(backendOrigin() + r.url); setNonce(n => n + 1);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Preview failed'); setUrl(''); }
    setBusy(false);
  };

  if (!url) {
    return (
      <div className="mt-4">
        <button onClick={open} disabled={busy}
          className="flex items-center gap-1.5 text-xs rounded-md border border-cyan-500/40 text-cyan-200 px-3 py-1.5 hover:bg-cyan-500/10 disabled:opacity-50">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />} Preview the site
        </button>
        {err && <p className="mt-2 text-xs text-slate-400">{err}</p>}
      </div>
    );
  }
  return (
    <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950 overflow-hidden">
      <div className="flex items-center gap-1 border-b border-slate-800 bg-slate-900/80 px-2 py-1.5 text-xs">
        <span className="px-1.5 text-slate-400">Preview</span>
        <button onClick={() => setPhone(false)} title="Desktop" className={`rounded p-1 ${!phone ? 'bg-cyan-600/30 text-cyan-200' : 'text-slate-400 hover:text-slate-200'}`}><Monitor className="h-3.5 w-3.5" /></button>
        <button onClick={() => setPhone(true)} title="Phone" className={`rounded p-1 ${phone ? 'bg-cyan-600/30 text-cyan-200' : 'text-slate-400 hover:text-slate-200'}`}><Smartphone className="h-3.5 w-3.5" /></button>
        <button onClick={open} title="Reload (gets a fresh link)" className="rounded p-1 text-slate-400 hover:text-slate-200">{busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}</button>
        <a href={url} target="_blank" rel="noopener noreferrer" title="Open in a new tab" className="rounded p-1 text-slate-400 hover:text-slate-200"><ExternalLink className="h-3.5 w-3.5" /></a>
        <span className="flex-1" />
        <button onClick={() => setUrl('')} title="Close" className="rounded p-1 text-slate-400 hover:text-slate-200"><X className="h-3.5 w-3.5" /></button>
      </div>
      <div className="flex justify-center bg-slate-900/40 p-2">
        <iframe key={nonce} src={url} title="Preview of the finished site" sandbox="allow-scripts allow-forms allow-modals"
          className="bg-white rounded border border-slate-800 transition-all" style={{ width: phone ? 390 : '100%', height: 520 }} />
      </div>
    </div>
  );
}
