'use client';

import React from 'react';
import { OfficeProvider } from '@/context/OfficeContext';
import CockpitHeader from '@/components/CockpitHeader';
import SatelliteRadar from '@/components/SatelliteRadar';
import TeamOfficePod from '@/components/TeamOfficePod';
import VoiceChatConsole from '@/components/VoiceChatConsole';
import ParallelExecutionDeck from '@/components/ParallelExecutionDeck';
import AISettingsModal from '@/components/AISettingsModal';
import AddPersonModal from '@/components/AddPersonModal';
import GlobalVoiceBar from '@/components/GlobalVoiceBar';
import ProjectHistoryModal from '@/components/ProjectHistoryModal';

function MissionControlApp() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* 1. Top Sci-Fi Cockpit Header */}
      <CockpitHeader />

      {/* 2. Main Mission Deck */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {/* Orbital Satellite Radar & Live Team Coordinates */}
        <SatelliteRadar />

        {/* The People in the Office (Michael, Dave, + Add Person) */}
        <TeamOfficePod />

        {/* Dual Voice & Chat Command Console + Target PC Path Selector */}
        <VoiceChatConsole />

        {/* Parallel Execution Streams (Michael Frontend || Dave Backend) + Disk File Writer */}
        <ParallelExecutionDeck />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 px-6 text-center text-xs font-mono text-slate-500 flex flex-wrap items-center justify-between gap-2 max-w-7xl mx-auto w-full">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>DevSquad Orbital Mission Control • Online</span>
        </div>
        <div>
          <span>Local MongoDB • Python Flask • Next.js • Parallel Worker Pods</span>
        </div>
      </footer>

      {/* Modals & Global Floating Voice */}
      <AISettingsModal />
      <AddPersonModal />
      <ProjectHistoryModal />
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
