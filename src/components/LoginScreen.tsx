'use client';

import React, { useState } from 'react';
import { Lock, Loader2 } from 'lucide-react';
import { useApp } from '@/context/AppContext';

export default function LoginScreen() {
  const { login } = useApp();
  const [name, setName] = useState('admin');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr('');
    try { await login(name, pw); } catch (x) { setErr(x instanceof Error ? x.message : 'Login failed'); }
    finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/70 p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center">
            <Lock className="h-5 w-5 text-cyan-300" />
          </div>
          <div>
            <h1 className="text-base font-semibold">Adion</h1>
            <p className="text-xs text-slate-400">Sign in to meet your AI team</p>
          </div>
        </div>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Username" autoComplete="username"
          className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500" />
        <input
          type="password" autoFocus value={pw} onChange={e => setPw(e.target.value)} placeholder="Password"
          className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-cyan-500"
        />
        {err && <p className="text-xs text-rose-400">{err}</p>}
        <button disabled={busy || !pw}
          className="w-full rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 py-2 text-sm font-medium flex items-center justify-center gap-2">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Sign in
        </button>
        <p className="text-[11px] text-slate-500 leading-relaxed">
          First login: user <code className="text-slate-300">admin</code> with <code className="text-slate-300">APP_PASSWORD</code> from <code className="text-slate-300">backend/.env</code>, or the generated one in <code className="text-slate-300">backend/.auth.json</code>. Admins can add users.
        </p>
      </form>
    </div>
  );
}
