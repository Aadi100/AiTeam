// Thin client for the Flask backend: bearer-token auth, JSON helpers, SSE URL builder.

const TOKEN_KEY = 'devsquad.token';

export function getToken(): string {
  try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; }
}
export function setToken(t: string) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY);
  } catch { /* private mode */ }
}

// Normal calls go through the Next.js proxy; the SSE stream talks to Flask directly
// (proxies can buffer event streams).
const PROXY = '/api/py';
const DIRECT = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:5000') + '/api';

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let body = init.body;
  if (init.json !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(init.json);
  }
  const res = await fetch(PROXY + path, { ...init, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError((data as { error?: string }).error || `HTTP ${res.status}`, res.status);
  return data as T;
}

export function streamUrl(runId: string): string {
  return `${DIRECT}/runs/${runId}/stream?token=${encodeURIComponent(getToken())}`;
}

// ───────── shared types ─────────
export type TaskStatus = 'queued' | 'running' | 'done' | 'failed' | 'skipped' | 'cancelled';
export type RunStatus = 'planning' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface AgentTask {
  id: string; runId: string; key: string; kind: 'module' | 'verify' | 'review'; parentId: string; title: string; description: string;
  folder: string; dependsOn: string[]; status: TaskStatus; model: string; attempts: number;
  tokens: number; tokensIn: number; tokensOut: number; summary: string; error: string;
  fileCount: number; order: number; startedAt: string | null; endedAt: string | null; lastLog: string;
  files?: { path: string; size: number; language: string }[];
  log?: { t: string; level: string; msg: string }[];
}

export interface Run {
  id: string; goal: string; projectName: string; summary: string; targetPath: string; status: RunStatus;
  plannerModel: string; workerModel: string; maxTokens: number; tokens: number; tokensIn: number;
  tokensOut: number; error: string; source: string; createdAt: string | null;
  startedAt: string | null; endedAt: string | null;
  owner: string; verify: boolean; suggested: { title: string; command: string; cwd: string }[];
}

export type Role = 'admin' | 'member' | 'viewer';
export interface User { username: string; role: Role; createdAt?: string }

export interface Snapshot { run: Run; tasks: AgentTask[] }

export interface Job {
  id: string; title: string; command: string; cwd: string; status: string; pid: number;
  exitCode: number | null; createdAt: string; endedAt: string | null; log?: string;
}
export interface MemoryItem { id: string; text: string; kind: string; createdAt: string }
export interface Schedule {
  id: string; name: string; goal: string; targetPath: string; everyMinutes: number; dailyAt: string;
  enabled: boolean; lastRunAt: string | null; lastRunId: string; maxTokens: number; hasKeys: boolean;
}

export function fmtTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
  return String(n);
}

export function fmtDuration(startIso: string | null, endIso: string | null, now: number): string {
  if (!startIso) return '–';
  const s = Math.max(0, Math.floor(((endIso ? Date.parse(endIso) : now) - Date.parse(startIso)) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}h ${m}m` : m ? `${m}m ${sec}s` : `${sec}s`;
}
