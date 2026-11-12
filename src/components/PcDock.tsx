'use client';

import React from 'react';
import { useApp } from '@/context/AppContext';
import PcTaskCard from '@/components/PcTaskCard';

/** Floating card for PC requests started by voice or chat, so the approval is always in front of you. */
export default function PcDock() {
  const { pcTaskId, setPcTaskId } = useApp();
  if (!pcTaskId) return null;
  return (
    <div className="fixed bottom-24 right-4 z-40 w-[26rem] max-w-[calc(100vw-2rem)] max-h-[70vh] overflow-y-auto rounded-2xl shadow-2xl shadow-black/50">
      <PcTaskCard key={pcTaskId} taskId={pcTaskId} onClose={() => setPcTaskId('')} />
    </div>
  );
}
