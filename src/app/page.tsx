'use client';

import React from 'react';
import { OfficeProvider } from '@/context/OfficeContext';
import CockpitHeader from '@/components/CockpitHeader';
import AISettingsModal from '@/components/AISettingsModal';
import AddPersonModal from '@/components/AddPersonModal';
import GlobalVoiceBar from '@/components/GlobalVoiceBar';
import AgentSidebar from '@/components/AgentSidebar';
import ChatHistorySidebar from '@/components/ChatHistorySidebar';
import ChatInterface from '@/components/ChatInterface';
function MissionControlApp() {
  return (
    <div className="h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200 overflow-hidden">
      <CockpitHeader />

      {/* 3-column layout — fills remaining height */}
      <div className="flex-1 flex gap-3 max-w-[1700px] w-full mx-auto px-3 sm:px-4 lg:px-6 py-4 min-h-0">

        {/* Left: chat history */}
        <ChatHistorySidebar />

        {/* Centre: chat */}
        <ChatInterface />

        {/* Right: agent roster (radar lives inside) */}
        <AgentSidebar />
      </div>

      <AISettingsModal />
      <AddPersonModal />
      <GlobalVoiceBar />
    </div>
  );
}

export default function Home() {
  return (
    <OfficeProvider>
      <MissionControlApp />
    </OfficeProvider>
  );
}
