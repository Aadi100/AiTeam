'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { MessageSquare, Terminal, CalendarClock, Brain, Trash2, RotateCw, Square, Plus, Users, Coins, Laptop } from 'lucide-react';
import UsagePanel from '@/components/UsagePanel';
import PcPanel from '@/components/PcPanel';
import { useApp, type Panel } from '@/context/AppContext';
import { api, fmtTokens, type Job, type MemoryItem, type Role, type Run, type Schedule, type User } from '@/lib/api';

const TABS: { id: Panel; label: string; icon: React.ReactNode; admin?: boolean }[] = [
  { id: 'runs', label: 'Chats', icon: <MessageSquare className="h-3.5 w-3.5" /> },
  { id: 'jobs', label: 'Background', icon: <Terminal className="h-3.5 w-3.5" />, admin: true },
  { id: 'schedules', label: 'Schedules', icon: <CalendarClock className="h-3.5 w-3.5" /> },
  { id: 'memory', label: 'Memory', icon: <Brain className="h-3.5 w-3.5" /> },
  { id: 'pc', label: 'PC', icon: <Laptop className="h-3.5 w-3.5" />, admin: true },
  { id: 'usage', label: 'Usage', icon: <Coins className="h-3.5 w-3.5" /> },
  { id: 'users', label: 'Users', icon: <Users className="h-3.5 w-3.5" />, admin: true },
];

const inputCls = 'w-full rounded-md bg-slate-950 border border-slate-700 px-2 py-1.5 text-xs outline-none focus:border-cyan-500';
const btnCls = 'rounded-md bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 px-2.5 py-1.5 text-xs font-medium flex items-center gap-1';
const STATUS_COLOR: Record<string, string> = {
  completed: 'text-emerald-400', running: 'text-sky-400', planning: 'text-violet-400', awaiting_input: 'text-amber-400', awaiting_approval: 'text-amber-400', exited: 'text-emerald-400',
  failed: 'text-rose-400', cancelled: 'text-slate-400', stopped: 'text-amber-400', lost: 'text-slate-500',
};

function ago(iso: string | null): string {
  if (!iso) return '';
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return m < 1 ? 'just now' : m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`;
}

/** Conversations (one entry per chat) and, separately, the projects Adion built. */
function RunsList() {
  const { runs, chats, openRun, openChat, deleteChat, newChat, snap, refreshRuns } = useApp();
  const [confirm, setConfirm] = useState('');
  useEffect(() => { refreshRuns(); }, [refreshRuns]);
  const activeChat = snap && (snap.run.answer || snap.run.pcTaskId) ? (snap.run.threadId || snap.run.id) : '';
  const projects = runs.filter((r: Run) => !r.answer && !r.pcTaskId);
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <p className="text-[11px] uppercase tracking-wider text-slate-500">Chats</p>
          <button onClick={newChat} className="flex items-center gap-1 rounded-md border border-slate-700 px-2 py-0.5 text-[11px] text-slate-300 hover:border-cyan-500 hover:text-cyan-200"><Plus className="h-3 w-3" /> New chat</button>
        </div>
        {chats.length === 0 ? <p className="text-xs text-slate-500">No chats yet. Ask Adion anything.</p> : (
          <ul className="space-y-1.5">
            {chats.map(g => (
              <li key={g.threadId} className="group relative">
                <button onClick={() => { setConfirm(''); openChat(g.threadId); }}
                  className={`w-full text-left rounded-lg border px-2.5 py-2 pr-8 ${activeChat === g.threadId ? 'border-cyan-500 bg-slate-800' : 'border-slate-800 hover:bg-slate-800/60'}`}>
                  <div className="text-xs truncate">{g.title}</div>
                  <div className="text-[11px] text-slate-500 truncate">{g.count} message{g.count === 1 ? '' : 's'} · {ago(g.updatedAt)}</div>
                </button>
                {confirm === g.threadId ? (
                  <button onClick={() => { setConfirm(''); deleteChat(g.threadId); }} title="Click again to delete this chat"
                    className="absolute right-1.5 top-1.5 rounded bg-rose-600 px-1.5 py-0.5 text-[10px] text-white">Delete?</button>
                ) : (
                  <button onClick={() => setConfirm(g.threadId)} title="Delete this chat"
                    className="absolute right-1.5 top-2 rounded p-1 text-slate-600 opacity-0 group-hover:opacity-100 hover:text-rose-300 focus:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1.5">Projects</p>
        {projects.length === 0 ? <p className="text-xs text-slate-500">Nothing built yet.</p> : (
          <ul className="space-y-1.5">
            {projects.map((r: Run) => (
              <li key={r.id}>
                <button onClick={() => openRun(r.id)}
                  className={`w-full text-left rounded-lg border px-2.5 py-2 ${snap?.run.id === r.id ? 'border-cyan-500 bg-slate-800' : 'border-slate-800 hover:bg-slate-800/60'}`}>
                  <div className="text-xs truncate">{r.projectName || r.goal}</div>
                  <div className="text-[11px] font-mono text-slate-500">
                    <span className={STATUS_COLOR[r.status]}>{r.status.replace('_', ' ')}</span> · {fmtTokens(r.tokens)} tokens
                    {r.source !== 'manual' && ` · ${r.source}`}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function JobsPanel() {
  const { settings } = useApp();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [form, setForm] = useState({ title: '', command: '', cwd: settings.targetPath });
  const [open, setOpen] = useState<Job | null>(null);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    try { setJobs(await api<Job[]>('/jobs')); } catch { /* auth handled elsewhere */ }
    if (open) { try { setOpen(await api<Job>(`/jobs/${open.id}`)); } catch { /* ignore */ } }
  }, [open?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    load();
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [load]);

  const act = async (fn: () => Promise<unknown>) => { setErr(''); try { await fn(); await load(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } };

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <input className={inputCls} placeholder="Title (e.g. Start dev server)" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
        <input className={`${inputCls} font-mono`} placeholder="Command (e.g. npm run dev)" value={form.command} onChange={e => setForm({ ...form, command: e.target.value })} />
        <input className={`${inputCls} font-mono`} placeholder="Folder" value={form.cwd} onChange={e => setForm({ ...form, cwd: e.target.value })} />
        <button className={btnCls} disabled={!form.command.trim()}
          onClick={() => act(() => api('/jobs', { method: 'POST', json: form }))}><Plus className="h-3 w-3" /> Start</button>
        {err && <p className="text-[11px] text-rose-400">{err}</p>}
      </div>
      <ul className="space-y-1.5">
        {jobs.map(j => (
          <li key={j.id} className="rounded-lg border border-slate-800 px-2.5 py-2">
            <div className="flex items-center justify-between gap-2">
              <button className="text-xs truncate text-left" onClick={() => setOpen(open?.id === j.id ? null : j)}>{j.title}</button>
              <span className={`text-[11px] font-mono ${STATUS_COLOR[j.status]}`}>{j.status}</span>
            </div>
            <div className="text-[11px] text-slate-500 font-mono truncate">{j.command}</div>
            <div className="mt-1 flex gap-2">
              {j.status === 'running' && (
                <button className="text-[11px] text-rose-300 flex items-center gap-1" onClick={() => act(() => api(`/jobs/${j.id}/stop`, { method: 'POST' }))}>
                  <Square className="h-3 w-3" />Stop</button>)}
              <button className="text-[11px] text-sky-300 flex items-center gap-1" onClick={() => act(() => api(`/jobs/${j.id}/restart`, { method: 'POST' }))}>
                <RotateCw className="h-3 w-3" />Restart</button>
            </div>
            {open?.id === j.id && (
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-950 p-2 text-[11px] font-mono text-slate-300 whitespace-pre-wrap">{open.log || '(no output yet)'}</pre>
            )}
          </li>
        ))}
        {!jobs.length && <p className="text-xs text-slate-500">No background tasks.</p>}
      </ul>
    </div>
  );
}

function SchedulesPanel() {
  const { settings } = useApp();
  const [items, setItems] = useState<Schedule[]>([]);
  const [f, setF] = useState({ name: '', goal: '', everyMinutes: 0, dailyAt: '' });
  const [err, setErr] = useState('');
  const load = useCallback(async () => { try { setItems(await api<Schedule[]>('/schedules')); } catch { /* ignore */ } }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    load();
  }, [load]);
  const act = async (fn: () => Promise<unknown>) => { setErr(''); try { await fn(); await load(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } };

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <input className={inputCls} placeholder="Name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />
        <textarea className={inputCls} rows={2} placeholder="Goal to run" value={f.goal} onChange={e => setF({ ...f, goal: e.target.value })} />
        <div className="flex gap-2">
          <input className={inputCls} type="number" min={0} placeholder="every N min" value={f.everyMinutes || ''} onChange={e => setF({ ...f, everyMinutes: Number(e.target.value) || 0, dailyAt: '' })} />
          <input className={inputCls} type="time" value={f.dailyAt} onChange={e => setF({ ...f, dailyAt: e.target.value, everyMinutes: 0 })} />
        </div>
        <button className={btnCls} disabled={!f.goal.trim() || (!f.everyMinutes && !f.dailyAt)}
          onClick={() => act(() => api('/schedules', { method: 'POST', json: { ...f, targetPath: settings.targetPath, plannerModel: settings.plannerModel, workerModel: settings.workerModel, maxTokens: settings.maxTokens } }))}>
          <Plus className="h-3 w-3" /> Add schedule</button>
        {err && <p className="text-[11px] text-rose-400">{err}</p>}
      </div>
      <ul className="space-y-1.5">
        {items.map(s => (
          <li key={s.id} className="rounded-lg border border-slate-800 px-2.5 py-2">
            <div className="flex justify-between gap-2 text-xs"><span className="truncate">{s.name}</span>
              <span className="font-mono text-slate-500">{s.everyMinutes ? `every ${s.everyMinutes}m` : `daily ${s.dailyAt}`}{s.hasKeys ? ' · keys' : ''}</span></div>
            <div className="text-[11px] text-slate-500 truncate">{s.goal}</div>
            <div className="mt-1 flex gap-3 text-[11px]">
              <button className="text-sky-300" onClick={() => act(() => api(`/schedules/${s.id}`, { method: 'PUT', json: { enabled: !s.enabled } }))}>{s.enabled ? 'Pause' : 'Resume'}</button>
              <button className="text-rose-300" onClick={() => act(() => api(`/schedules/${s.id}`, { method: 'DELETE' }))}>Delete</button>
            </div>
          </li>
        ))}
        {!items.length && <p className="text-xs text-slate-500">No schedules.</p>}
      </ul>
    </div>
  );
}

function MemoryPanel() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [text, setText] = useState('');
  const [kind, setKind] = useState<'note' | 'preference'>('preference');
  const load = useCallback(async () => { try { setItems(await api<MemoryItem[]>('/memory')); } catch { /* ignore */ } }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    load();
  }, [load]);
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-slate-500 leading-relaxed">Preferences are always given to the planner; other notes are recalled when they match your goal. Finished builds are remembered automatically.</p>
      <textarea className={inputCls} rows={2} placeholder="e.g. Always use dark theme and vanilla JS" value={text} onChange={e => setText(e.target.value)} />
      <div className="flex gap-2">
        <select className={inputCls} value={kind} onChange={e => setKind(e.target.value as 'note' | 'preference')}>
          <option value="preference">Preference</option><option value="note">Note</option>
        </select>
        <button className={btnCls} disabled={!text.trim()} onClick={async () => { await api('/memory', { method: 'POST', json: { text, kind } }); setText(''); load(); }}>
          <Plus className="h-3 w-3" /> Save</button>
      </div>
      <ul className="space-y-1.5">
        {items.map(m => (
          <li key={m.id} className="rounded-lg border border-slate-800 px-2.5 py-2 flex justify-between gap-2">
            <div className="min-w-0"><span className="text-[10px] uppercase text-slate-500">{m.kind}</span>
              <p className="text-xs break-words">{m.text}</p></div>
            <button className="text-slate-500 hover:text-rose-400 shrink-0" onClick={async () => { await api(`/memory/${m.id}`, { method: 'DELETE' }); load(); }}><Trash2 className="h-3.5 w-3.5" /></button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UsersPanel() {
  const { user } = useApp();
  const [users, setUsers] = useState<User[]>([]);
  const [f, setF] = useState<{ username: string; password: string; role: Role }>({ username: '', password: '', role: 'member' });
  const [err, setErr] = useState('');
  const load = useCallback(async () => { try { setUsers(await api<User[]>('/users')); } catch { /* ignore */ } }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    load();
  }, [load]);
  const act = async (fn: () => Promise<unknown>) => { setErr(''); try { await fn(); await load(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } };
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-slate-500 leading-relaxed">
        <b>admin</b>: everything. <b>member</b>: own runs, memory, schedules. <b>viewer</b>: read-only, sees all runs.
      </p>
      <div className="space-y-1.5">
        <input className={inputCls} placeholder="Username" value={f.username} onChange={e => setF({ ...f, username: e.target.value })} />
        <input className={inputCls} type="password" placeholder="Password (8+ characters)" value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
        <div className="flex gap-2">
          <select className={inputCls} value={f.role} onChange={e => setF({ ...f, role: e.target.value as Role })}>
            <option value="member">member</option><option value="viewer">viewer</option><option value="admin">admin</option>
          </select>
          <button className={btnCls} disabled={!f.username || f.password.length < 8}
            onClick={() => act(async () => { await api('/users', { method: 'POST', json: f }); setF({ username: '', password: '', role: 'member' }); })}>
            <Plus className="h-3 w-3" /> Add</button>
        </div>
        {err && <p className="text-[11px] text-rose-400">{err}</p>}
      </div>
      <ul className="space-y-1.5">
        {users.map(u => (
          <li key={u.username} className="rounded-lg border border-slate-800 px-2.5 py-2 flex items-center justify-between gap-2">
            <span className="text-xs truncate">{u.username}{u.username === user?.username && <span className="text-slate-500"> (you)</span>}</span>
            <span className="flex items-center gap-2">
              <select className="rounded bg-slate-950 border border-slate-700 text-[11px] px-1 py-0.5" value={u.role}
                onChange={e => act(() => api(`/users/${u.username}/role`, { method: 'PUT', json: { role: e.target.value } }))}>
                <option>admin</option><option>member</option><option>viewer</option>
              </select>
              {u.username !== user?.username && (
                <button className="text-slate-500 hover:text-rose-400" onClick={() => act(() => api(`/users/${u.username}`, { method: 'DELETE' }))}><Trash2 className="h-3.5 w-3.5" /></button>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function SidePanel() {
  const { panel, setPanel, user } = useApp();
  const tabs = TABS.filter(t => !t.admin || user?.role === 'admin');
  return (
    <aside className="lg:w-80 shrink-0 rounded-3xl border border-slate-800/80 bg-slate-900/40 flex flex-col min-h-[24rem] lg:sticky lg:top-[4.5rem] lg:h-[calc(100vh-6rem)] overflow-hidden">
      <div className="grid border-b border-slate-800/80 bg-slate-950/30" style={{ gridTemplateColumns: `repeat(${tabs.length > 6 ? 4 : tabs.length > 4 ? 3 : tabs.length}, minmax(0, 1fr))` }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setPanel(t.id)} title={t.label}
            className={`py-2.5 flex flex-col items-center justify-center gap-1 text-[10px] transition ${panel === t.id ? 'text-cyan-300 bg-slate-900/70 shadow-[inset_0_-2px_0_0_rgb(6,182,212)]' : 'text-slate-500 hover:text-slate-200 hover:bg-slate-900/40'}`}>
            {t.icon}<span>{t.label}</span>
          </button>
        ))}
      </div>
      <div className="p-4 overflow-y-auto flex-1 min-h-0">
        {panel === 'runs' && <RunsList />}
        {panel === 'jobs' && <JobsPanel />}
        {panel === 'schedules' && <SchedulesPanel />}
        {panel === 'memory' && <MemoryPanel />}
        {panel === 'usage' && <UsagePanel />}
        {panel === 'pc' && <PcPanel />}
        {panel === 'users' && <UsersPanel />}
      </div>
    </aside>
  );
}
