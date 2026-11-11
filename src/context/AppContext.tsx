'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api, ApiError, getToken, setToken, streamUrl, type Run, type Snapshot, type User } from '@/lib/api';

export interface Settings {
  gemini: string; claude: string; openai: string; ollamaUrl: string;
  targetPath: string; plannerModel: string; workerModel: string; maxTokens: number; autoRun: boolean; verify: boolean;
}

const DEFAULTS: Settings = {
  gemini: '', claude: '', openai: '', ollamaUrl: 'http://localhost:11434',
  targetPath: '~/Desktop/devsquad-output', plannerModel: 'claude-sonnet-5-5', workerModel: 'gemini-2.5-flash',
  maxTokens: 0, autoRun: false, verify: false,
};
const SETTINGS_KEY = 'devsquad.settings.v2';

export type Panel = 'runs' | 'jobs' | 'schedules' | 'memory' | 'users';

interface Ctx {
  authed: boolean | null;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  settings: Settings;
  updateSettings: (p: Partial<Settings>) => void;
  settingsOpen: boolean; setSettingsOpen: (v: boolean) => void;
  panel: Panel; setPanel: (p: Panel) => void;
  snap: Snapshot | null;
  runs: Run[];
  refreshRuns: () => Promise<void>;
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
  const [panel, setPanel] = useState<Panel>('runs');
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [selectedTaskId, selectTask] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // load persisted settings once
  useEffect(() => {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- data loading: state is set from async results
      if (raw) setSettings({ ...DEFAULTS, ...JSON.parse(raw) });
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
    try { setRuns(await api<Run[]>('/runs')); } catch (e) { handleErr(e); }
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
    try {
      const run = await api<Run>('/runs', {
        method: 'POST',
        json: {
          goal, targetPath: settings.targetPath, source, verify: settings.verify,
          plannerModel: settings.plannerModel, workerModel: settings.workerModel, maxTokens: settings.maxTokens,
          apiKeys: { gemini: settings.gemini, claude: settings.claude, openai: settings.openai, ollamaUrl: settings.ollamaUrl },
        },
      });
      setPanel('runs');
      watch(run.id);
      refreshRuns();
    } catch (e) { handleErr(e); } finally { setStarting(false); }
  }, [settings, watch, refreshRuns, handleErr]);

  const cancelRun = useCallback(async () => {
    if (!snap) return;
    try { await api(`/runs/${snap.run.id}/cancel`, { method: 'POST' }); } catch (e) { handleErr(e); }
  }, [snap, handleErr]);

  const retryTask = useCallback(async (taskId: string) => {
    if (!snap) return;
    try {
      await api(`/runs/${snap.run.id}/tasks/${taskId}/retry`, {
        method: 'POST',
        json: { apiKeys: { gemini: settings.gemini, claude: settings.claude, openai: settings.openai, ollamaUrl: settings.ollamaUrl } },
      });
      watch(snap.run.id);
    } catch (e) { handleErr(e); }
  }, [snap, settings, watch, handleErr]);

  return (
    <AppCtx.Provider value={{
      authed, user, login, retryTask, logout, settings, updateSettings, settingsOpen, setSettingsOpen, panel, setPanel,
      snap, runs, refreshRuns, startRun, openRun: watch, cancelRun, starting, error,
      clearError: () => setError(''), selectedTaskId, selectTask,
    }}>
      {children}
    </AppCtx.Provider>
  );
}
