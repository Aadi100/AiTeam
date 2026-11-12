'use client';

import React from 'react';
import { Settings } from 'lucide-react';
import { AppProvider, useApp } from '@/context/AppContext';
import LoginScreen from '@/components/LoginScreen';
import GoalConsole from '@/components/GoalConsole';
import AgentMap from '@/components/AgentMap';
import TaskDrawer from '@/components/TaskDrawer';
import SidePanel from '@/components/SidePanel';
import SettingsModal from '@/components/SettingsModal';
import GlobalVoiceBar from '@/components/GlobalVoiceBar';
import PcDock from '@/components/PcDock';
import VoiceOrb from '@/components/VoiceOrb';
import { VoiceProvider, useVoice } from '@/context/VoiceContext';

const ROLE_STYLE: Record<string, string> = {
  admin: 'text-amber-300 border-amber-500/30 bg-amber-500/10',
  member: 'text-cyan-300 border-cyan-500/30 bg-cyan-500/10',
  viewer: 'text-slate-300 border-slate-600 bg-slate-800/60',
};

function Shell() {
  const { authed, setSettingsOpen, user, snap } = useApp();
  const { isVoiceActive, isThinking, isSpeaking } = useVoice();
  if (authed === null) return <div className="min-h-screen bg-slate-950" />;
  if (!authed) return <LoginScreen />;
  const building = !!snap && ['planning', 'running'].includes(snap.run.status);
  return (
    <div className="min-h-screen text-slate-100 flex flex-col bg-slate-950 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(14,165,233,0.14),transparent)]">
      <header className="sticky top-0 z-30 border-b border-slate-800/70 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-[1500px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <VoiceOrb isActive={isVoiceActive || isThinking || isSpeaking || building} size={30} />
            <div className="leading-none">
              <span className="text-base font-semibold tracking-wide">Adion</span>
              <span className="block text-[10px] text-slate-500 mt-0.5 tracking-wider uppercase">your AI team</span>
            </div>
            {building && (
              <span className="hidden sm:flex items-center gap-1.5 ml-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-[11px] text-sky-300">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" /> building
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {user && (
              <span className={`hidden sm:inline rounded-full border px-2.5 py-0.5 text-[11px] ${ROLE_STYLE[user.role] || ROLE_STYLE.viewer}`}>
                {user.username} · {user.role}
              </span>
            )}
            <button onClick={() => setSettingsOpen(true)}
              className="flex items-center gap-1.5 rounded-lg border border-slate-800 hover:border-slate-600 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-300 hover:text-white transition">
              <Settings className="h-3.5 w-3.5" /> Models &amp; keys
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-[1500px] w-full mx-auto px-4 sm:px-6 pt-5 pb-28 flex flex-col lg:flex-row gap-5 min-h-0">
        <div className="flex-1 min-w-0 space-y-5">
          <GoalConsole />
          <AgentMap />
        </div>
        <SidePanel />
      </main>
      <TaskDrawer />
      <SettingsModal />
      <PcDock />
      <GlobalVoiceBar />
    </div>
  );
}

export default function Home() {
  return (
    <AppProvider>
      <VoiceProvider>
        <Shell />
      </VoiceProvider>
    </AppProvider>
  );
}
