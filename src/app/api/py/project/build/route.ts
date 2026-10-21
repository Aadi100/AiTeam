import { NextRequest, NextResponse } from 'next/server';

// Allow up to 5 minutes — build takes 2-3 min with AI generation
export const maxDuration = 300;

export async function POST(req: NextRequest) {
  const body = await req.json();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 290_000); // 4m50s hard abort

  try {
    const res = await fetch('http://127.0.0.1:5000/api/project/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timer);
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: unknown) {
    clearTimeout(timer);
    const msg = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json({ success: false, error: msg }, { status: 500 });
  }
}
