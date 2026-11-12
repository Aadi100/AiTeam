'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { api, fmtCost, fmtTokens, type Forecast, type UsageStats } from '@/lib/api';

const PURPOSE_LABEL: Record<string, string> = {
  answer: 'Answers', plan: 'Planner', critic: 'Plan critic', replan: 'Re-planning', pc: 'PC control', agent: 'Agents', fix: 'Fixes', review: 'Review', assistant: 'Voice chat', search: 'Web searches', other: 'Other',
};
const KIND_LABEL: Record<Forecast['kind'], string> = {
  chat: 'Quick answer', pc: 'PC task', small: 'Small build (1 agent)', large: 'Full build', auto: 'Full build',
};

function Calculator() {
  const [goal, setGoal] = useState('');
  const [fc, setFc] = useState<Forecast | null>(null);
  useEffect(() => {
    const g = goal.trim();
    if (!g) return;
    const t = setTimeout(() => { api<Forecast>('/usage/estimate', { method: 'POST', json: { goal: g } }).then(setFc).catch(() => setFc(null)); }, 450);
    return () => clearTimeout(t);
  }, [goal]);
  const shown = goal.trim() ? fc : null;
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3 space-y-2">
      <p className="text-[11px] uppercase tracking-wider text-slate-500">Calculator</p>
      <textarea value={goal} onChange={e => setGoal(e.target.value)} rows={2} placeholder="Type a goal to see what it would cost…"
        className="w-full resize-none rounded-md bg-slate-950 border border-slate-800 px-2 py-1.5 text-xs outline-none focus:border-cyan-500" />
      {shown && (
        <div className="text-xs space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-slate-300">{KIND_LABEL[shown.kind]}</span>
            <span className="font-mono text-cyan-300">{fmtCost(shown.cost)}</span>
          </div>
          <p className="text-[11px] text-slate-500">
            about {fmtTokens(shown.tokens)} tokens (likely {fmtTokens(shown.low)} to {fmtTokens(shown.high)}, {fmtCost(shown.costLow)} to {fmtCost(shown.costHigh)})
          </p>
          <div className="space-y-0.5">
            {shown.parts.map(p => (
              <div key={p.name} className="flex justify-between text-[11px] text-slate-400">
                <span>{p.name}</span><span className="font-mono">{fmtTokens(p.tokens)} · {fmtCost(p.cost)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function UsagePanel() {
  const [days, setDays] = useState(30);
  const [u, setU] = useState<UsageStats | null>(null);
  const [err, setErr] = useState('');
  const load = useCallback(() => {
    api<UsageStats>(`/usage?days=${days}`).then(d => { setU(d); setErr(''); }).catch(e => setErr(e instanceof Error ? e.message : 'Failed'));
  }, [days]);
  useEffect(() => { load(); const id = setInterval(load, 8000); return () => clearInterval(id); }, [load]);

  const maxDay = Math.max(1, ...(u?.byDay.map(d => d.tokens) || [1]));
  const maxPurpose = Math.max(1e-9, ...(u?.byPurpose.map(d => d.cost) || [1e-9]));
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Token usage</p>
        <div className="flex rounded-md border border-slate-800 overflow-hidden text-[11px]">
          {[7, 30, 90].map(d => (
            <button key={d} onClick={() => setDays(d)} className={`px-2 py-0.5 ${days === d ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}>{d}d</button>
          ))}
        </div>
      </div>
      {err && <p className="text-xs text-rose-400">{err}</p>}
      {u && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Cost</p>
              <p className="text-lg font-semibold text-cyan-300 font-mono">{fmtCost(u.cost)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Tokens</p>
              <p className="text-lg font-semibold font-mono">{fmtTokens(u.tokens)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Requests</p>
              <p className="text-lg font-semibold font-mono">{u.calls}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3" title="Input tokens DeepSeek served from its cache at a much lower price">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Cache saved</p>
              <p className="text-lg font-semibold text-emerald-400 font-mono">{fmtCost(u.saved)}</p>
              <p className="text-[10px] text-slate-500">{Math.round(u.cacheRate * 100)}% of input cached</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500">
            {fmtTokens(u.tokensIn)} in ({fmtTokens(u.cacheHit)} cached) · {fmtTokens(u.tokensOut)} out
          </p>

          {u.byDay.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Per day</p>
              <div className="flex items-end gap-1 h-16">
                {u.byDay.slice(-30).map(d => (
                  <div key={d.day} title={`${d.day}: ${fmtTokens(d.tokens)} tokens, ${fmtCost(d.cost)}`} className="flex-1 min-w-[3px] rounded-t bg-cyan-500/70 hover:bg-cyan-400"
                    style={{ height: `${Math.max(6, (d.tokens / maxDay) * 100)}%` }} />
                ))}
              </div>
            </div>
          )}

          {u.byPurpose.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Where it goes</p>
              <div className="space-y-1.5">
                {u.byPurpose.map(p => (
                  <div key={p.purpose} className="text-[11px]">
                    <div className="flex justify-between text-slate-300"><span>{PURPOSE_LABEL[p.purpose] || p.purpose}</span><span className="font-mono text-slate-400">{fmtTokens(p.tokens)} · {fmtCost(p.cost)}</span></div>
                    <div className="h-1 rounded bg-slate-800 mt-0.5"><div className="h-full rounded bg-violet-500/80" style={{ width: `${Math.max(3, (p.cost / maxPurpose) * 100)}%` }} /></div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {u.runs.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Recent runs (actual vs forecast)</p>
              <ul className="space-y-1.5">
                {u.runs.map(r => (
                  <li key={r.id} className="rounded-lg border border-slate-800 bg-slate-950/40 px-2.5 py-1.5 text-[11px]">
                    <p className="truncate text-slate-200">{r.goal || r.id}</p>
                    <p className="font-mono text-slate-400">{fmtTokens(r.tokens)} · {fmtCost(r.cost)}{r.estimate > 0 && <span className="text-slate-600"> · forecast {fmtTokens(r.estimate)}</span>}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {u.calls === 0 && <p className="text-xs text-slate-500">No usage in this period yet.</p>}
        </>
      )}
      <Calculator />
      {u && (
        <p className="text-[10px] text-slate-600 leading-relaxed">
          Prices per 1M tokens: cached input ${u.prices.hit}, input ${u.prices.miss}, output ${u.prices.out}. Costs are computed from the usage DeepSeek reports for each call; forecasts are estimates.
        </p>
      )}
    </div>
  );
}
