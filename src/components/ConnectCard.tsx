'use client';

import React, { useState } from 'react';
import { Plug, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

export interface RunCard { type: string; provider?: string; name?: string }

/** A button the agent puts in the chat, e.g. "Connect Google". Pressing it opens the service's allow-access page. */
export default function ConnectCard({ card }: { card: RunCard }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  if (card.type !== 'connect' || !card.provider) return null;
  const go = async () => {
    setBusy(true); setErr('');
    try { const r = await api<{ url: string }>(`/integrations/connect/${card.provider}`, { method: 'POST', json: {} }); window.location.assign(r.url); }
    catch (e) { setErr(e instanceof Error ? e.message : 'Failed'); setBusy(false); }
  };
  return (
    <div className="mt-3 inline-flex flex-col gap-1">
      <button onClick={go} disabled={busy} className="flex items-center gap-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 px-4 py-2 text-sm font-medium transition">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />} Connect {card.name?.split(' (')[0] || card.provider}
      </button>
      {err && <span className="text-[11px] text-rose-300">{err}</span>}
    </div>
  );
}
