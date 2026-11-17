// Client portal API helpers (clients have their own login, separate from Adion's personal one).
import { ApiError } from '@/lib/api';

const KEY = 'adion.portal.token';
export function getPortalToken(): string { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } }
export function setPortalToken(t: string) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch { /* private mode */ } }

export async function papi<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = getPortalToken();
  if (t) headers.set('Authorization', `Bearer ${t}`);
  let body = init.body;
  if (init.json !== undefined) { headers.set('Content-Type', 'application/json'); body = JSON.stringify(init.json); }
  const res = await fetch('/api/py/platform' + path, { ...init, headers, body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError((data as { error?: string }).error || `HTTP ${res.status}`, res.status);
  return data as T;
}

export interface PClient { id: string; email: string; name: string; status: string; capUsd: number; freeCredit?: number; defaultCap?: number }
export interface PApp {
  id: string; projectId: string; name: string; platform: string; publicKey: string; secretPrefix: string; allowedOrigins: string[]; allowNative: boolean;
  description: string; rules: string; persona: string; greeting: string; strictScope: boolean; language: string; accessLevel: 'limited' | 'standard' | 'complete';
  apiBaseUrl: string; apiAuth: 'forward' | 'header' | 'none'; hasApiHeaders: boolean; monthlyCapUsd: number; enabled: boolean;
}
export interface PProject { id: string; name: string; apps: PApp[] }
export interface PDoc { id: string; title: string; kind: string; chars: number; chunks: number; preview: string }
export interface PParam { name: string; in: 'path' | 'query' | 'body'; type: string; required: boolean; description: string }
export interface PAction {
  id: string; name: string; description: string; mode: 'api' | 'client'; method: string; path: string; params: PParam[]; risk: 'read' | 'write' | 'danger';
  enabled: boolean; confirm: boolean; neverAi: boolean; requiresUser: boolean; hideFields: string[];
}
export interface PPending { callId: string; name: string; kind: 'confirm' | 'client'; needsConfirm: boolean; summary: string; args: Record<string, unknown> }
export interface PReply { reply: string; lang: string; conversationId: string; pending: PPending[] }
export interface PConv { id: string; endUser: string; title: string; count: number; updatedAt: string; messages?: { role: string; text: string }[] }
export interface PUsage {
  days: number; cost: number; tokens: number; calls: number; monthSpend: number; freeCredit: number; defaultCap: number;
  byDay: { day: string; cost: number; tokens: number; calls: number }[]; byApp: { appId: string; name: string; cost: number; calls: number }[];
  caps?: { app: number; client: number };
}

export function fmtUsd(n: number): string { return n < 0.01 && n > 0 ? '$' + n.toFixed(4) : '$' + n.toFixed(n < 1 ? 3 : 2); }
