'use client';

import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

function Code({ code, lang }: { code: string; lang: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="relative my-3 group">
      <button onClick={() => { navigator.clipboard?.writeText(code).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }).catch(() => { /* clipboard blocked */ }); }}
        className="absolute right-2 top-2 flex items-center gap-1 rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 opacity-70 hover:opacity-100">
        {done ? <><Check className="h-3 w-3" /> copied</> : <><Copy className="h-3 w-3" /> copy</>}
      </button>
      {lang && <span className="absolute left-3 top-1.5 text-[10px] uppercase tracking-wider text-slate-500">{lang}</span>}
      <pre className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-3 pt-6 text-xs leading-relaxed text-slate-200"><code>{code}</code></pre>
    </div>
  );
}

function inline(text: string): React.ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)\s]+\)|(?<![*\w])\*[^*\s][^*]*\*(?![*\w]))/g).map((p, i) => {
    if (p.startsWith('`') && p.endsWith('`') && p.length > 2) return <code key={i} className="rounded bg-slate-800 px-1 py-0.5 text-[12px] text-cyan-200">{p.slice(1, -1)}</code>;
    if (p.startsWith('**') && p.endsWith('**') && p.length > 4) return <b key={i} className="text-slate-100">{p.slice(2, -2)}</b>;
    const link = p.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
    if (link) return <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer" className="text-cyan-300 hover:underline">{link[1]}</a>;
    if (p.length > 2 && p.startsWith('*') && p.endsWith('*') && !p.startsWith('**')) return <i key={i}>{p.slice(1, -1)}</i>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
}

/** Small markdown renderer for the integration guides: headings, paragraphs, lists, tables, and copyable code blocks. */
export default function Markdown({ text }: { text: string }) {
  const out: React.ReactNode[] = [];
  const lines = text.split('\n');
  let i = 0, k = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith('```')) {
      const lang = l.slice(3).trim(); const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) buf.push(lines[i++]);
      i++;
      out.push(<Code key={k++} code={buf.join('\n')} lang={lang} />);
    } else if (/^#{1,3} /.test(l)) {
      const n = l.match(/^#+/)![0].length;
      out.push(React.createElement(`h${n + 1}`, { key: k++, className: n === 1 ? 'text-lg font-semibold mt-1 mb-2' : 'text-sm font-semibold mt-5 mb-1.5 text-cyan-200' }, inline(l.replace(/^#+ /, ''))));
      i++;
    } else if (l.startsWith('|')) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith('|')) { if (!/^\|[\s:-]+\|/.test(lines[i])) rows.push(lines[i].split('|').slice(1, -1).map(c => c.trim())); i++; }
      out.push(
        <div key={k++} className="my-3 overflow-x-auto"><table className="text-xs border-collapse"><tbody>{rows.map((r, ri) => (
          <tr key={ri} className={ri === 0 ? 'text-slate-300 font-medium' : 'text-slate-400'}>{r.map((c, ci) => <td key={ci} className="border border-slate-800 px-2 py-1 align-top">{inline(c)}</td>)}</tr>))}</tbody></table></div>);
    } else if (/^\d+[.)] /.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)] /.test(lines[i])) items.push(lines[i++].replace(/^\d+[.)] /, ''));
      out.push(<ol key={k++} className="my-2 list-decimal pl-5 text-sm text-slate-300 space-y-1">{items.map((it, ii) => <li key={ii}>{inline(it)}</li>)}</ol>);
    } else if (l.startsWith('> ')) {
      const buf: string[] = [];
      while (i < lines.length && lines[i].startsWith('> ')) buf.push(lines[i++].slice(2));
      out.push(<blockquote key={k++} className="my-2 border-l-2 border-slate-600 pl-3 text-sm text-slate-400">{inline(buf.join(' '))}</blockquote>);
    } else if (/^[-*] /.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*] /.test(lines[i])) items.push(lines[i++].replace(/^[-*] /, ''));
      out.push(<ul key={k++} className="my-2 list-disc pl-5 text-sm text-slate-300 space-y-1">{items.map((it, ii) => <li key={ii}>{inline(it)}</li>)}</ul>);
    } else if (l.trim() === '') { i++; } else {
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim() !== '' && !lines[i].startsWith('```') && !/^#{1,3} /.test(lines[i]) && !lines[i].startsWith('|') && !/^[-*] /.test(lines[i]) && !/^\d+[.)] /.test(lines[i]) && !lines[i].startsWith('> ')) buf.push(lines[i++]);
      out.push(<p key={k++} className="my-2 text-sm leading-relaxed text-slate-300">{inline(buf.join(' '))}</p>);
    }
  }
  return <div>{out}</div>;
}
