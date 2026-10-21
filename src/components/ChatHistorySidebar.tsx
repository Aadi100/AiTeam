'use client';

import React, { useState, useEffect } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { SquarePen, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import { ChatSession } from '@/types/office';

function groupByDate(sessions: ChatSession[], now: Date): { label: string; items: ChatSession[] }[] {
  const startOfToday     = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday); startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const startOf7Days     = new Date(startOfToday);  startOf7Days.setDate(startOf7Days.getDate() - 7);
  const startOf30Days    = new Date(startOfToday);  startOf30Days.setDate(startOf30Days.getDate() - 30);

  const groups: Record<string, ChatSession[]> = {
    Today: [], Yesterday: [], 'Previous 7 Days': [], 'Previous 30 Days': [], Older: [],
  };

  for (const s of sessions) {
    const d = new Date(s.createdAt);
    if      (d >= startOfToday)     groups.Today.push(s);
    else if (d >= startOfYesterday) groups.Yesterday.push(s);
    else if (d >= startOf7Days)     groups['Previous 7 Days'].push(s);
    else if (d >= startOf30Days)    groups['Previous 30 Days'].push(s);
    else                            groups.Older.push(s);
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

export default function ChatHistorySidebar() {
  const { chatSessions, currentSessionId, startNewChat, switchSession, deleteChatSession } = useOffice();
  const [collapsed, setCollapsed]   = useState(false);
  const [hoverId, setHoverId]       = useState<string | null>(null);

  // Defer new Date() to client only — avoids Next.js 16 prerender "unstable value" error
  const [grouped, setGrouped] = useState<{ label: string; items: ChatSession[] }[]>([]);
  useEffect(() => {
    setGrouped(groupByDate(chatSessions, new Date()));
  }, [chatSessions]);

  if (collapsed) {
    return (
      <aside className="w-10 shrink-0 flex flex-col items-center pt-3 gap-3">
        <button
          onClick={() => setCollapsed(false)}
          className="p-2 rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-all cursor-pointer"
          title="Expand sidebar"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <button
          onClick={startNewChat}
          className="p-2 rounded-lg text-slate-500 hover:text-cyan-400 hover:bg-slate-800 transition-all cursor-pointer"
          title="New chat"
        >
          <SquarePen className="w-4 h-4" />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-60 shrink-0 flex flex-col bg-slate-900/40 border border-slate-800/60 rounded-2xl overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 shrink-0">
        <span className="text-[11px] font-semibold text-slate-300 tracking-wide">DevSquad</span>
        <div className="flex items-center gap-1">
          <button
            onClick={startNewChat}
            className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition-all cursor-pointer"
            title="New chat"
          >
            <SquarePen className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCollapsed(true)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all cursor-pointer"
            title="Collapse"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* New chat button */}
      <div className="px-2 pb-2 shrink-0">
        <button
          onClick={startNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 text-slate-300 hover:text-white transition-all cursor-pointer"
        >
          <SquarePen className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-[13px]">New chat</span>
        </button>
      </div>

      <div className="w-full h-px bg-slate-800/60 shrink-0" />

      {/* Session list */}
      <div className="flex-1 overflow-y-auto py-2 px-1.5 space-y-4 min-h-0">
        {chatSessions.length === 0 && (
          <p className="text-xs text-slate-600 text-center px-3 py-6">No conversations yet</p>
        )}

        {grouped.map(({ label, items }) => (
          <div key={label}>
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest px-2 mb-1">{label}</p>
            <div className="space-y-0.5">
              {items.map((session) => {
                const isActive  = session.id === currentSessionId;
                const isHovered = hoverId === session.id;
                return (
                  <div
                    key={session.id}
                    className={`group relative flex items-center gap-2 px-2.5 py-2 rounded-xl cursor-pointer transition-all ${
                      isActive
                        ? 'bg-slate-700/60 text-white'
                        : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-100'
                    }`}
                    onClick={() => switchSession(session.id)}
                    onMouseEnter={() => setHoverId(session.id)}
                    onMouseLeave={() => setHoverId(null)}
                  >
                    <span className="flex-1 text-[13px] truncate leading-snug">{session.title}</span>

                    {(isActive || isHovered) && (
                      <div className="absolute right-0 top-0 h-full flex items-center pr-1.5">
                        <div className={`absolute right-8 top-0 h-full w-8 bg-gradient-to-r ${isActive ? 'from-transparent to-slate-700/60' : 'from-transparent to-slate-800/60'}`} />
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteChatSession(session.id); }}
                          className="relative z-10 p-1 rounded-md text-slate-500 hover:text-rose-400 hover:bg-slate-700 transition-all cursor-pointer"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
