'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiError, getToken, setToken, streamUrl, MAX_ATTACHMENTS, MAX_UPLOAD_BYTES, type Chat, type Run, type Snapshot, type Upload, type User } from '@/lib/api';

export interface Settings {
  targetPath: string; plannerModel: string; workerModel: string; maxTokens: number; autoRun: boolean; verify: boolean; webSearch: boolean; reviewPlan: boolean; deepPlan: boolean; v: number;
}

const DEFAULTS: Settings = {
  targetPath: '~/Desktop/adion-output', plannerModel: 'deepseek-chat', workerModel: 'deepseek-chat',
  maxTokens: 150000, autoRun: false, verify: true, webSearch: false, reviewPlan: true, deepPlan: true, v: 2,
};
const SETTINGS_KEY = 'devsquad.settings.v2';

export type Panel = 'runs' | 'jobs' | 'schedules' | 'memory' | 'usage' | 'pc' | 'users';

interface Ctx {
  authed: boolean | null;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  settings: Settings;
  threadId: string; newChat: () => void; chats: Chat[]; threadRuns: Run[];
  openChat: (threadId: string) => Promise<void>; deleteChat: (threadId: string) => Promise<void>;
  attachments: Upload[]; uploading: boolean; addFiles: (files: File[]) => Promise<void>; removeAttachment: (id: string) => void;
  pcTaskId: string; setPcTaskId: (id: string) => void; pcVersion: number; refreshPc: () => void;
  continueFrom: string; setContinueFrom: (id: string) => void;
  answerQuestions: (answers: Record<string, string>) => Promise<void>;
  approvePlan: (edits: { modules: { key: string; title: string; description: string; removed: boolean }[]; contract?: string }) => Promise<void>;
  revisePlan: (feedback: string) => Promise<void>;
  rejectPlan: () => Promise<void>;
  updateSettings: (p: Partial<Settings>) => void;
  settingsOpen: boolean; setSettingsOpen: (v: boolean) => void;
  panel: Panel; setPanel: (p: Panel) => void;
  snap: Snapshot | null;
  runs: Run[];
  refreshRuns: () => Promise<void>;
  goal: string; setGoal: (g: string) => void;
  startRun: (goal: string, source?: string) => Promise<void>;
  openRun: (id: string) => void;
  cancelRun: () => Promise<void>;
  retryTask: (taskId: string) => Promise<void>;
  starting: boolean;
  error: string;
  clearError: () => void;
  selectedTaskId: string | null; selectTask: (id: string | null) => void;
}

const AppCtx = createContext<Ctx | null>(null);
export const useApp = () => {
  const c = useContext(AppCtx);
  if (!c) throw new Error('useApp must be used inside <AppProvider>');
  return c;
};

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<Settings>(DEFAULTS);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [continueFrom, setContinueFrom] = useState('');
  const [pcTaskId, setPcTaskId] = useState('');
  // the conversation id is created on first use (in an event handler), never during render: it uses the clock
  const [threadId, setThreadId] = useState('');
  const threadRef = useRef('');
  const [chats, setChats] = useState<Chat[]>([]);
  const [threadRuns, setThreadRuns] = useState<Run[]>([]);
  const [attachments, setAttachments] = useState<Upload[]>([]);
  const [uploading, setUploading] = useState(false);
  const [pcVersion, setPcVersion] = useState(0);
  const refreshPc = useCallback(() => setPcVersion(v => v + 1), []);
  const [panel, setPanel] = useState<Panel>('runs');
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [starting, setStarting] = useState(false);
  const [goal, setGoal] = useState('');
  const [error, setError] = useState('');
  const [selectedTaskId, selectTask] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // load persisted settings once
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        const ds = (m: unknown) => (typeof m === 'string' && m.startsWith('deepseek') ? m : 'deepseek-chat');
        const clean = { ...DEFAULTS, ...saved, plannerModel: ds(saved.plannerModel), workerModel: ds(saved.workerModel) };
        if (!saved.v || saved.v < 2) { clean.verify = true; clean.reviewPlan = true; clean.v = 2; }   // the agentic upgrade turns these on once
        // drop any API keys older versions left in this browser
        for (const k of ['gemini', 'claude', 'openai', 'ollamaUrl', 'deepseek']) delete (clean as Record<string, unknown>)[k];
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(clean));
        // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from persisted storage
        setSettings(clean);
      }
    } catch { /* ignore */ }
  }, []);

  const updateSettings = useCallback((p: Partial<Settings>) => {
    setSettings(prev => {
      const next = { ...prev, ...p };
      try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const handleErr = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) { setToken(''); setAuthed(false); return; }
    setError(e instanceof Error ? e.message : String(e));
  }, []);

  // verify stored token on mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    if (!getToken()) { setAuthed(false); return; }
    api<{ user: User }>('/auth/check').then(r => { setUser(r.user); setAuthed(true); }).catch(() => { setToken(''); setAuthed(false); });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const r = await api<{ token: string; user: User }>('/auth/login', { method: 'POST', json: { username, password } });
    setToken(r.token);
    setUser(r.user);
    setAuthed(true);
  }, []);
  const logout = useCallback(() => { setToken(''); setAuthed(false); setUser(null); setSnap(null); }, []);

  const refreshRuns = useCallback(async () => {
    try { setRuns(await api<Run[]>('/runs')); setChats(await api<Chat[]>('/chats')); } catch (e) { handleErr(e); }
  }, [handleErr]);

  const stopWatching = useCallback(() => {
    esRef.current?.close(); esRef.current = null;
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const watch = useCallback((id: string) => {
    stopWatching();
    selectTask(null);
    const startPolling = () => {
      pollRef.current = setInterval(async () => {
        try {
          const s = await api<Snapshot>(`/runs/${id}`);
          setSnap(s);
          if (['completed', 'failed', 'cancelled'].includes(s.run.status) &&
              !s.tasks.some(t => t.status === 'queued' || t.status === 'running')) { stopWatching(); refreshRuns(); }
        } catch (e) { handleErr(e); stopWatching(); }
      }, 1500);
    };
    api<Snapshot>(`/runs/${id}`).then(setSnap).catch(handleErr);
    const es = new EventSource(streamUrl(id));
    esRef.current = es;
    es.onmessage = ev => { try { setSnap(JSON.parse(ev.data)); } catch { /* partial frame */ } };
    es.addEventListener('done', () => { es.close(); esRef.current = null; refreshRuns(); });
    es.onerror = () => { es.close(); esRef.current = null; if (!pollRef.current) startPolling(); };
  }, [handleErr, refreshRuns, stopWatching]);

  useEffect(() => stopWatching, [stopWatching]);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
    if (authed) refreshRuns();
  }, [authed, refreshRuns]);

  const startRun = useCallback(async (goal: string, source = 'manual') => {
    setStarting(true); setError('');
    if (!threadRef.current) { threadRef.current = 'th_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); setThreadId(threadRef.current); }
    const thread = threadRef.current;
    try {
      const run = await api<Run>('/runs', {
        method: 'POST',
        json: {
          goal, targetPath: settings.targetPath, source, verify: settings.verify, webSearch: settings.webSearch,
          reviewPlan: settings.reviewPlan, deepPlan: settings.deepPlan, continueRunId: continueFrom || undefined,
          attachments: attachments.map(a => a.id), threadId: thread,
          plannerModel: settings.plannerModel, workerModel: settings.workerModel, maxTokens: settings.maxTokens,
        },
      });
      setPanel('runs');
      setContinueFrom('');
      setAttachments([]);
      setGoal('');   // like a chat: the box empties once you send
      watch(run.id);
      refreshRuns();
    } catch (e) { handleErr(e); } finally { setStarting(false); }
  }, [settings, continueFrom, attachments, watch, refreshRuns, handleErr]);

  const cancelRun = useCallback(async () => {
    if (!snap) return;
    try { await api(`/runs/${snap.run.id}/cancel`, { method: 'POST' }); } catch (e) { handleErr(e); }
  }, [snap, handleErr]);

  const retryTask = useCallback(async (taskId: string) => {
    if (!snap) return;
    try {
      await api(`/runs/${snap.run.id}/tasks/${taskId}/retry`, {
        method: 'POST',
      });
      watch(snap.run.id);
    } catch (e) { handleErr(e); }
  }, [snap, watch, handleErr]);

  const newChat = useCallback(() => {
    stopWatching(); setSnap(null); setGoal(''); setAttachments([]); setContinueFrom('');
    threadRef.current = ''; setThreadId(''); setThreadRuns([]);
  }, [stopWatching]);

  // the turns of the open conversation (kept fresh while it changes)
  useEffect(() => {
    if (!threadId) return;
    let alive = true;
    api<Run[]>(`/chats/${threadId}`).then(r => { if (alive) setThreadRuns(r); }).catch(() => { if (alive) setThreadRuns([]); });
    return () => { alive = false; };
  }, [threadId, snap?.run.id, snap?.run.status]);

  const openChat = useCallback(async (tid: string) => {
    try {
      const turns = await api<Run[]>(`/chats/${tid}`);
      if (!turns.length) return;
      threadRef.current = tid; setThreadId(tid); setThreadRuns(turns); setGoal(''); setContinueFrom(''); setAttachments([]);
      watch(turns[turns.length - 1].id);
    } catch (e) { handleErr(e); }
  }, [watch, handleErr]);

  const deleteChat = useCallback(async (tid: string) => {
    try {
      await api(`/chats/${tid}`, { method: 'DELETE' });
      if (tid === threadRef.current || snap?.run.threadId === tid || snap?.run.id === tid) newChat();
      await refreshRuns();
    } catch (e) { handleErr(e); }
  }, [snap, newChat, refreshRuns, handleErr]);

  const addFiles = useCallback(async (files: File[]) => {
    setUploading(true);
    let count = attachments.length;
    for (const f of files) {
      if (count >= MAX_ATTACHMENTS) { setError(`At most ${MAX_ATTACHMENTS} files per request.`); break; }
      if (f.size > MAX_UPLOAD_BYTES) { setError(`${f.name} is larger than 10 MB.`); continue; }
      try {
        const fd = new FormData();
        fd.append('file', f);
        const up = await api<Upload>('/files', { method: 'POST', body: fd });
        setAttachments(a => [...a, up]);
        count++;
      } catch (e) { setError(`${f.name}: ${e instanceof Error ? e.message : 'upload failed'}`); }
    }
    setUploading(false);
  }, [attachments.length]);
  const removeAttachment = useCallback((id: string) => {
    setAttachments(a => a.filter(x => x.id !== id));
    api(`/files/${id}`, { method: 'DELETE' }).catch(() => { /* already gone */ });
  }, []);

  // resume a paused run: the server returns the fresh snapshot; keep watching it
  const resume = useCallback(async (path: string, json: unknown) => {
    if (!snap) return;
    try {
      const s = await api<Snapshot>(`/runs/${snap.run.id}/${path}`, { method: 'POST', json });
      setSnap(s);
      watch(snap.run.id);
      refreshRuns();
    } catch (e) { handleErr(e); }
  }, [snap, watch, refreshRuns, handleErr]);
  const answerQuestions = useCallback((answers: Record<string, string>) => resume('answers', { answers }), [resume]);
  const approvePlan = useCallback((edits: { modules: { key: string; title: string; description: string; removed: boolean }[]; contract?: string }) => resume('approve', { edits }), [resume]);
  const revisePlan = useCallback((feedback: string) => resume('replan', { feedback }), [resume]);
  const rejectPlan = useCallback(() => resume('reject', {}), [resume]);

  return (
    <AppCtx.Provider value={{
      threadId, newChat, chats, threadRuns, openChat, deleteChat, attachments, uploading, addFiles, removeAttachment, pcTaskId, setPcTaskId, pcVersion, refreshPc, continueFrom, setContinueFrom, answerQuestions, approvePlan, revisePlan, rejectPlan,
      authed, user, login, retryTask, goal, setGoal, logout, settings, updateSettings, settingsOpen, setSettingsOpen, panel, setPanel,
      snap, runs, refreshRuns, startRun, openRun: watch, cancelRun, starting, error,
      clearError: () => setError(''), selectedTaskId, selectTask,
    }}>
      {children}
    </AppCtx.Provider>
  );
}
