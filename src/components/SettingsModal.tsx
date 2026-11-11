'use client';

import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';

const FIELDS: { key: 'claude' | 'gemini' | 'openai' | 'ollamaUrl'; label: string; secret: boolean; hint: string }[] = [
  { key: 'claude', label: 'Anthropic (Claude) API key', secret: true, hint: 'Used for claude-* models' },
  { key: 'gemini', label: 'Google Gemini API key', secret: true, hint: 'Used for gemini-* models' },
  { key: 'openai', label: 'OpenAI API key', secret: true, hint: 'Used for gpt-* models and Whisper voice fallback' },
  { key: 'ollamaUrl', label: 'Ollama URL', secret: false, hint: 'Local models, e.g. ollama:llama3.2 (no key, fully offline)' },
];

export default function SettingsModal() {
  const { settingsOpen, setSettingsOpen, settings, updateSettings, logout, user } = useApp();
  const [pw, setPw] = useState({ current: '', next: '' });
  const [pwMsg, setPwMsg] = useState('');
  if (!settingsOpen) return null;
  const changePw = async () => {
    try { await api('/auth/password', { method: 'POST', json: { current: pw.current, new: pw.next } }); setPwMsg('Password changed'); setPw({ current: '', next: '' }); }
    catch (e) { setPwMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setSettingsOpen(false)}>
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950 p-5 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Models &amp; keys</h2>
          <button onClick={() => setSettingsOpen(false)} className="text-slate-400 hover:text-white"><X className="h-4 w-4" /></button>
        </div>
        {FIELDS.map(f => (
          <label key={f.key} className="block text-xs space-y-1">
            <span className="text-slate-300">{f.label}</span>
            <input type={f.secret ? 'password' : 'text'} autoComplete="off" value={settings[f.key]}
              onChange={e => updateSettings({ [f.key]: e.target.value })}
              className="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-2 outline-none focus:border-cyan-500 font-mono" />
            <span className="text-slate-500">{f.hint}</span>
          </label>
        ))}
        <p className="text-[11px] text-slate-500 leading-relaxed">
          Keys stay in this browser and are sent only with a run request. They are held in server memory for that run and never written to the database. You can also set GEMINI_API_KEY, CLAUDE_API_KEY or OPENAI_API_KEY in backend/.env.
        </p>
        <div className="border-t border-slate-800 pt-3 space-y-1.5">
          <p className="text-xs text-slate-300">Signed in as <b>{user?.username}</b> ({user?.role}) · change password</p>
          <input type="password" placeholder="Current password" value={pw.current} onChange={e => setPw({ ...pw, current: e.target.value })}
            className="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500" />
          <input type="password" placeholder="New password (8+ characters)" value={pw.next} onChange={e => setPw({ ...pw, next: e.target.value })}
            className="w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500" />
          <div className="flex items-center gap-3">
            <button onClick={changePw} disabled={!pw.current || pw.next.length < 8} className="rounded-md bg-slate-700 hover:bg-slate-600 disabled:opacity-40 px-3 py-1 text-xs">Change</button>
            {pwMsg && <span className="text-[11px] text-slate-400">{pwMsg}</span>}
          </div>
        </div>
        <div className="flex justify-between pt-1">
          <button onClick={logout} className="text-xs text-rose-300 hover:text-rose-200">Sign out</button>
          <button onClick={() => setSettingsOpen(false)} className="rounded-lg bg-cyan-600 hover:bg-cyan-500 px-4 py-1.5 text-xs font-medium">Done</button>
        </div>
      </div>
    </div>
  );
}
