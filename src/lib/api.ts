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

/** The backend's origin (for iframe/preview URLs that cannot go through the Next.js proxy). */
export function backendOrigin(): string {
  return DIRECT.replace(/\/api$/, '');
}

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

export function screenshotUrl(runId: string, bust: string | number = ''): string {
  return `${DIRECT}/runs/${runId}/screenshot?token=${encodeURIComponent(getToken())}&t=${bust}`;
}

export function streamUrl(runId: string): string {
  return `${DIRECT}/runs/${runId}/stream?token=${encodeURIComponent(getToken())}`;
}

// ───────── shared types ─────────
export type TaskStatus = 'queued' | 'running' | 'waiting' | 'done' | 'failed' | 'skipped' | 'cancelled';
export type RunStatus = 'planning' | 'awaiting_input' | 'awaiting_approval' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface RunQuestion { id: string; q: string; options: string[]; answer: string; taskId: string; agent?: string }
export interface PlanModule { key: string; title: string; description: string; folder: string; depends_on: string[]; expects: string[] }
export interface PlanDraft { project_name?: string; summary?: string; contract?: string; assumptions?: string[]; modules?: PlanModule[] }
export interface BrowserCheck {
  ok?: boolean; url?: string; title?: string; skipped?: boolean; reason?: string; round?: number; screenshot?: boolean;
  buttons?: number; issues?: { level: 'error' | 'warn'; msg: string }[]; links?: { url: string; status: number }[];
}

export interface AgentTask {
  id: string; runId: string; key: string; kind: 'module' | 'verify' | 'review'; parentId: string; title: string; description: string;
  folder: string; dependsOn: string[]; status: TaskStatus; model: string; attempts: number; replaced: boolean; replans: number;
  tokens: number; tokensIn: number; tokensOut: number; summary: string; error: string;
  fileCount: number; order: number; startedAt: string | null; endedAt: string | null; lastLog: string;
  files?: { path: string; size: number; language: string }[];
  log?: { t: string; level: string; msg: string }[];
}

export interface Run {
  id: string; goal: string; projectName: string; summary: string; answer: string; sources: { title: string; url: string }[]; kind: string; mode: 'build' | 'edit'; parentRunId: string;
  reviewPlan: boolean; deepPlan: boolean; reusedPlan: string; pcTaskId: string; threadId: string; attachments: { id: string; name: string; kind: string }[]; questions: RunQuestion[]; plan: PlanDraft; assumptions: string[]; revisions: number; check: BrowserCheck; cost: number; cacheHit: number;
  estimateTokens: number; estimateCost: number; targetPath: string; status: RunStatus;
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

export function fmtCost(usd: number): string {
  if (!usd) return '$0.00';
  if (usd < 0.01) return '$' + usd.toFixed(4);
  return '$' + usd.toFixed(usd < 1 ? 3 : 2);
}

export interface Chat { threadId: string; title: string; count: number; preview: string; updatedAt: string | null }

export interface Upload {
  id: string; name: string; kind: 'text' | 'pdf' | 'docx' | 'image'; size: number; note: string; chars: number;
  info: { width?: number; height?: number; format?: string; pages?: number; colors?: { hex: string; share: number }[] };
}
export const ATTACH_ACCEPT = '.txt,.md,.csv,.tsv,.json,.log,.html,.css,.js,.ts,.tsx,.jsx,.py,.xml,.yml,.yaml,.sql,.pdf,.docx,.png,.jpg,.jpeg,.gif,.bmp,.webp';
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const MAX_ATTACHMENTS = 5;

export interface PcStep {
  id: string; tool: string; args: Record<string, unknown>; risk: 'read' | 'low' | 'change' | 'danger';
  status: 'pending' | 'ok' | 'error' | 'denied' | 'skipped'; preview: string; result: string; error: string; needs: string[]; untrusted: boolean;
}
export interface PcTask {
  id: string; runId: string; request: string; status: 'planning' | 'awaiting_approval' | 'running' | 'done' | 'failed' | 'denied' | 'cancelled';
  say: string; steps: PcStep[]; pendingFolders: string[]; pendingPhase: string; untrusted: boolean; error: string; undoable: number;
  createdAt: string | null; undoReport?: { undone: number; failed: string[] };
}
export interface PcSettings { paused: boolean; trust: boolean; desktop: string; folders: string[]; known: Record<string, string> }
export interface PcAction { id: string; taskId: string; tool: string; summary: string; risk: string; ok: boolean; result: string; undone: boolean; canUndo: boolean; auto: boolean; createdAt: string | null }
export interface PcActivity { actions: PcAction[]; tasks: PcTask[] }

export interface Forecast {
  kind: 'chat' | 'small' | 'large' | 'auto' | 'pc'; modules: number; tokens: number; low: number; high: number;
  cost: number; costLow: number; costHigh: number; parts: { name: string; tokens: number; cost: number }[];
}

export interface UsageStats {
  days: number; calls: number; tokensIn: number; tokensOut: number; tokens: number; cacheHit: number; cacheRate: number;
  cost: number; saved: number;
  byDay: { day: string; tokens: number; cost: number; calls: number }[];
  byPurpose: { purpose: string; tokens: number; cost: number; calls: number }[];
  runs: { id: string; goal: string; status: string; tokens: number; cost: number; estimate: number }[];
  prices: { hit: number; miss: number; out: number };
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
