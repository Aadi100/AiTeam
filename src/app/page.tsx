'use client';

import React from 'react';
import { Settings, Network } from 'lucide-react';
import { AppProvider, useApp } from '@/context/AppContext';
import LoginScreen from '@/components/LoginScreen';
import GoalConsole from '@/components/GoalConsole';
import AgentMap from '@/components/AgentMap';
import TaskDrawer from '@/components/TaskDrawer';
import SidePanel from '@/components/SidePanel';
import SettingsModal from '@/components/SettingsModal';

function Shell() {
  const { authed, setSettingsOpen } = useApp();
  if (authed === null) return <div className="min-h-screen bg-slate-950" />;
  if (!authed) return <LoginScreen />;
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="max-w-[1500px] mx-auto px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-cyan-400" />
            <span className="text-sm font-semibold">DevSquad Mission Control</span>
            <span className="text-[11px] text-slate-500 hidden sm:inline">· planner + parallel agent map</span>
          </div>
          <button onClick={() => setSettingsOpen(true)} className="text-slate-400 hover:text-white flex items-center gap-1.5 text-xs">
            <Settings className="h-4 w-4" /> Models &amp; keys
          </button>
        </div>
      </header>
      <main className="flex-1 max-w-[1500px] w-full mx-auto px-4 py-4 flex flex-col lg:flex-row gap-4 min-h-0">
        <div className="flex-1 min-w-0 space-y-4">
          <GoalConsole />
          <AgentMap />
        </div>
        <SidePanel />
      </main>
      <TaskDrawer />
      <SettingsModal />
    </div>
  );
}

export default function Home() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
