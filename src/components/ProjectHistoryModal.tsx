'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { ProjectHistoryItem } from '@/types/office';
import {
  History,
  X,
  ExternalLink,
  RotateCcw,
  Trash2,
  FileCode,
  HardDrive,
  Eye,
  Sparkles,
  Search,
  CheckCircle2,
  FolderOpen
} from 'lucide-react';

export default function ProjectHistoryModal() {
  const {
    isHistoryOpen,
    setIsHistoryOpen,
    history,
    loadProjectFromHistory,
    deleteHistoryItem,
    clearAllHistory,
    openFolderInExplorer
  } = useOffice();

  const [search, setSearch] = useState('');
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  if (!isHistoryOpen) return null;

  const filtered = history.filter(
    (h) =>
      h.prompt.toLowerCase().includes(search.toLowerCase()) ||
      h.targetPath.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-5">
      <div className="bg-slate-900 border border-cyan-500/40 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-slate-800 bg-slate-950/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-950 border border-cyan-800/80 flex items-center justify-center text-cyan-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                  MISSION ARCHIVE // PROJECT HISTORY
                </h2>
                <span className="text-xs bg-cyan-950 text-cyan-400 px-2 py-0.5 rounded-full border border-cyan-800/60 font-mono">
                  {history.length} Saved Projects
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Browse and reuse all previous builds created on your PC.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {history.length > 0 && (
              <button
                onClick={() => {
                  if (confirm('Clear all project history records? (Files on your disk will remain untouched)')) {
                    clearAllHistory();
                  }
                }}
                className="text-xs text-rose-400 hover:text-rose-300 px-2.5 py-1.5 rounded-lg border border-rose-900/40 hover:bg-rose-950/40 transition-colors font-mono cursor-pointer"
              >
                Clear All
              </button>
            )}
            <button
              onClick={() => setIsHistoryOpen(false)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-slate-800/80 bg-slate-950/40">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search history by prompt or folder name..."
              className="w-full bg-slate-950 border border-slate-700/80 focus:border-cyan-500 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none"
            />
          </div>
        </div>

        {/* History Items List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {filtered.length === 0 ? (
            <div className="text-center py-16 border border-dashed border-slate-800 rounded-2xl bg-slate-950/30">
              <History className="w-10 h-10 mx-auto text-slate-600 mb-2" />
              <h3 className="text-sm font-semibold text-slate-300">No projects found</h3>
              <p className="text-xs text-slate-500 mt-1">
                Give a command via voice or chat to build your first project.
              </p>
            </div>
          ) : (
            filtered.map((item) => {
              const htmlFile = item.files.find((f) => f.name.endsWith('.html'));

              return (
                <div
                  key={item.id}
                  className="bg-slate-950/80 border border-slate-800 hover:border-slate-700 rounded-2xl p-4 transition-all shadow-md space-y-3"
                >
                  {/* Card Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-bold text-white tracking-tight flex items-center gap-2">
                        <span>{item.prompt}</span>
                      </h3>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400 font-mono mt-1">
                        <span className="text-slate-500">{item.timestamp}</span>
                        <span>•</span>
                        <span className="text-emerald-400 bg-emerald-950/80 px-2 py-0.2 rounded border border-emerald-800/40">
                          {item.totalFiles} files generated
                        </span>
                        {item.modelsUsed && (
                          <>
                            <span>•</span>
                            <span className="text-cyan-400">
                              {item.modelsUsed.michael || 'Llama 3'} &amp; {item.modelsUsed.dave || 'Mistral'}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 pt-2 sm:pt-0">
                      {htmlFile && (
                        <button
                          onClick={() => setPreviewHtml(htmlFile.content)}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono border border-slate-700 transition-all cursor-pointer"
                          title="Preview HTML in browser"
                        >
                          <Eye className="w-3.5 h-3.5 text-cyan-400" />
                          <span>Preview</span>
                        </button>
                      )}

                      <button
                        onClick={() => openFolderInExplorer(item.targetPath)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono border border-slate-700 transition-all cursor-pointer"
                        title="Open in Windows Explorer"
                      >
                        <FolderOpen className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Open Folder</span>
                      </button>

                      <button
                        onClick={() => loadProjectFromHistory(item)}
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-bold shadow-md shadow-cyan-600/20 transition-all cursor-pointer"
                        title="Load this project into active cockpit"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>Use / Restore</span>
                      </button>

                      <button
                        onClick={() => deleteHistoryItem(item.id)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        title="Delete from history"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Target PC Folder Path */}
                  <div className="bg-slate-900 border border-slate-800/80 rounded-xl px-3 py-1.5 text-xs font-mono text-slate-300 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 truncate">
                      <HardDrive className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="text-slate-500 shrink-0">Path on PC:</span>
                      <span className="truncate text-slate-200">{item.targetPath}</span>
                    </div>
                  </div>

                  {/* Files List Chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {item.files.map((file, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] font-mono bg-slate-900 border border-slate-800 text-slate-300 px-2 py-0.5 rounded flex items-center gap-1"
                      >
                        <FileCode className="w-3 h-3 text-cyan-400" />
                        <span>{file.name}</span>
                      </span>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Live Browser Preview Modal (within history) */}
        {previewHtml && (
          <div className="fixed inset-0 z-[60] bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-950">
                <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                  <Eye className="w-4 h-4 text-cyan-400" />
                  <span>History Project Web Preview</span>
                </div>
                <button
                  onClick={() => setPreviewHtml(null)}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 bg-white">
                <iframe
                  title="History Preview"
                  srcDoc={previewHtml}
                  className="w-full h-full border-none"
                  sandbox="allow-scripts allow-modals"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
