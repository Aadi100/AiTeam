'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useApp } from '@/context/AppContext';
import { api } from '@/lib/api';
import KeyField from '@/components/KeyField';

type Brain = 'deepseek' | 'claude' | 'mixed';
const BRAINS: { id: Brain; name: string; line: string }[] = [
  { id: 'deepseek', name: 'DeepSeek only', line: 'Cheapest. Everything runs on DeepSeek.' },
  { id: 'mixed', name: 'Mixed (best value)', line: 'Claude plans, chats and runs your accounts. DeepSeek writes the code files.' },
  { id: 'claude', name: 'Claude only', line: 'Strongest. Everything runs on Claude. Costs the most.' },
];

/** The owner's switch between DeepSeek and Claude. Claude options unlock once a Claude key is saved. */
function ModelSwitch({ hasClaude }: { hasClaude: boolean }) {
  const [brain, setBrain] = useState<Brain>('deepseek');
  const [msg, setMsg] = useState('');
  const load = useCallback(() => { api<{ brain: Brain }>('/auth/brain').then(r => setBrain(r.brain)).catch(() => {}); }, []);
  useEffect(() => { load(); }, [load, hasClaude]);
  const pick = async (b: Brain) => {
    try { await api('/auth/brain', { method: 'PUT', json: { brain: b } }); setBrain(b); setMsg(''); }
    catch (e) { setMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-300">Which AI does the work? <span className="text-slate-500">(you can switch any time; it applies to everyone)</span></p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {BRAINS.map(b => {
          const locked = b.id !== 'deepseek' && !hasClaude;
          return (
            <button key={b.id} onClick={() => pick(b.id)} disabled={locked} title={locked ? 'Add the Claude API key first' : ''}
              className={`text-left rounded-lg border p-2.5 transition disabled:opacity-40 ${brain === b.id ? 'border-cyan-500 bg-cyan-500/10' : 'border-slate-700 hover:border-slate-500'}`}>
              <span className="block text-xs font-medium text-slate-100">{brain === b.id ? '● ' : '○ '}{b.name}</span>
              <span className="block mt-0.5 text-[11px] text-slate-400 leading-snug">{b.line}</span>
            </button>
          );
        })}
      </div>
      {!hasClaude && <p className="text-[11px] text-amber-300">Add a Claude API key above to unlock Mixed and Claude only.</p>}
      {msg && <p className="text-[11px] text-rose-300">{msg}</p>}
    </div>
  );
}


/** Models & keys, password and sign-out: owner-only settings, shown on the Owner tab. */
export default function OwnerKeys() {
  const { logout, user } = useApp();
  const [hasClaude, setHasClaude] = useState(false);
  const checkClaude = useCallback(() => { api<{ set: boolean }>('/auth/claudekey').then(r => setHasClaude(r.set)).catch(() => {}); }, []);
  useEffect(() => { checkClaude(); }, [checkClaude]);
  const [pw, setPw] = useState({ current: '', next: '' });
  const [pwMsg, setPwMsg] = useState('');
  const changePw = async () => {
    try { await api('/auth/password', { method: 'POST', json: { current: pw.current, new: pw.next } }); setPwMsg('Password changed'); setPw({ current: '', next: '' }); }
    catch (e) { setPwMsg(e instanceof Error ? e.message : 'Failed'); }
  };
  const box = 'w-full rounded-lg bg-slate-900 border border-slate-700 px-2.5 py-1.5 text-xs outline-none focus:border-cyan-500';
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-4">
      <p className="text-sm text-slate-200">Models &amp; keys</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <KeyField title="DeepSeek API key" endpoint="/auth/apikey" placeholder="sk-..." minLen={16} active
          missing="No key yet. Adion cannot build or chat until you add one."
          help={<>Get one at platform.deepseek.com, then API keys. This one key powers Adion and every connected app.</>} />
        <KeyField title="Claude API key (optional, stronger)" endpoint="/auth/claudekey" placeholder="sk-ant-..." minLen={20} active onChange={checkClaude}
          missing="No key yet. Adion runs on DeepSeek only."
          help={<>Get one at console.anthropic.com, then API keys. Add some credit under Billing. Then pick how to use it below.</>} />
        <KeyField title="Tavily API key (web search for DeepSeek)" endpoint="/auth/searchkey" placeholder="tvly-..." minLen={12} active
          missing="No key yet. Adion will answer from its built-in knowledge only."
          help={<>Get a free one at tavily.com. Used for DeepSeek only: when Claude is answering it searches the web by itself and needs no Tavily key.</>} />
      </div>
      <ModelSwitch hasClaude={hasClaude} />
      <p className="text-[11px] text-slate-500 leading-relaxed">Keys are encrypted and stored in the database on the server. They are never kept in this browser or shown again after saving.</p>
      <div className="border-t border-slate-800 pt-3 space-y-1.5 max-w-sm">
        <p className="text-xs text-slate-300">Signed in as <b>{user?.username}</b> ({user?.role}) · change password</p>
        <input type="password" placeholder="Current password" value={pw.current} onChange={e => setPw({ ...pw, current: e.target.value })} className={box} />
        <input type="password" placeholder="New password (8+ characters)" value={pw.next} onChange={e => setPw({ ...pw, next: e.target.value })} className={box} />
        <div className="flex items-center gap-3">
          <button onClick={changePw} disabled={!pw.current || pw.next.length < 8} className="rounded-md bg-slate-700 hover:bg-slate-600 disabled:opacity-40 px-3 py-1 text-xs">Change</button>
          {pwMsg && <span className="text-[11px] text-slate-400">{pwMsg}</span>}
          <span className="flex-1" />
          <button onClick={logout} className="text-xs text-rose-300 hover:text-rose-200">Sign out</button>
        </div>
      </div>
    </div>
  );
}
