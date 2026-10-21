import { NextRequest, NextResponse } from 'next/server';

export const maxDuration = 120;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 115_000);
  try {
    const res = await fetch('http://127.0.0.1:5000/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);
    const text = await res.text();
    let data: unknown;
    try { data = JSON.parse(text); } catch { data = { success: false, error: `Server error (${res.status})` }; }
    return NextResponse.json(data, { status: res.ok ? res.status : (res.status || 500) });
  } catch (err: unknown) {
    clearTimeout(timer);
    const msg = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}
