'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { GeneratedFile } from '@/types/office';
import {
  Code2,
  Terminal,
  FolderCheck,
  ExternalLink,
  Copy,
  Check,
  CheckCircle2,
  FileCode,
  Layers,
  Sparkles,
  Eye,
  Loader2,
  X
} from 'lucide-react';

export default function ParallelExecutionDeck() {
  const {
    streams,
    writtenFiles,
    project,
    targetPath,
    openFolderInExplorer,
    isExecuting,
    selectedFile,
    setSelectedFile
  } = useOffice();

  const [copied, setCopied] = useState(false);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  const frontendFiles = writtenFiles.filter(
    (f) => f.author.includes('Michael') || f.path.endsWith('.html') || f.path.endsWith('.css') || f.path.endsWith('.js')
  );

  const backendFiles = writtenFiles.filter(
    (f) => f.author.includes('Dave') || f.path.includes('backend') || f.path.endsWith('.py') || f.path.endsWith('.md') || f.path.endsWith('.txt')
  );

  const handleCopyCode = () => {
    if (selectedFile?.content) {
      navigator.clipboard.writeText(selectedFile.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const htmlFile = writtenFiles.find((f) => f.name.endsWith('.html'));

  return (
    <div className="space-y-4">
      {/* Top Banner: Local Disk Write Status */}
      {project.status === 'completed' && writtenFiles.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-950/90 via-slate-900 to-cyan-950/90 border border-emerald-500/40 rounded-2xl p-4 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3 animate-fade-in">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400 flex items-center justify-center text-emerald-400 shrink-0">
              <FolderCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  <span>DISK WRITE COMPLETE</span>
                  <span className="text-[10px] bg-emerald-900/80 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-600/50 font-mono">
                    {writtenFiles.length} FILES WRITTEN TO PC
                  </span>
                </h3>
              </div>
              <p className="text-xs font-mono text-emerald-200/80 truncate max-w-xl mt-0.5" title={targetPath}>
                Saved directly to: {targetPath}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 w-full md:w-auto justify-end">
            {htmlFile && (
              <button
                onClick={() => setIsPreviewOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all cursor-pointer"
              >
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Preview UI</span>
              </button>
            )}

            <button
              onClick={() => openFolderInExplorer(targetPath)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/20 transition-all cursor-pointer"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Open Folder on PC</span>
            </button>
          </div>
        </div>
      )}

      {/* Side-by-Side Parallel Workstream Decks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Left Column: Michael's Frontend Deck */}
        <div className="bg-slate-900/80 border border-cyan-500/30 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col justify-between">
          <div>
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center text-cyan-400 font-bold text-sm">
                  💻
                </div>
                <div>
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-cyan-300">
                    MICHAEL // FRONTEND POD
                  </h3>
                  <p className="text-[11px] text-slate-400">UI, Tailwind Layouts, Dynamic Client Logic</p>
                </div>
              </div>

              {isExecuting ? (
                <span className="flex items-center gap-1 text-[10px] font-mono text-cyan-400 bg-cyan-950 px-2 py-0.5 rounded border border-cyan-800 animate-pulse">
                  <Loader2 className="w-3 h-3 animate-spin" /> GENERATING
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                  {frontendFiles.length} deliverables
                </span>
              )}
            </div>

            {/* Michael's Live Output Stream */}
            <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-3 mb-3 font-mono text-xs text-slate-300 min-h-[90px] whitespace-pre-wrap leading-relaxed overflow-x-auto">
              {streams.michael}
            </div>

            {/* Frontend Files List */}
            {frontendFiles.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                  Files Created by Michael:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {frontendFiles.map((file, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedFile(file)}
                      className={`text-left p-2 rounded-lg border text-xs font-mono transition-all flex items-center justify-between cursor-pointer ${
                        selectedFile?.path === file.path
                          ? 'bg-cyan-950/80 border-cyan-500 text-cyan-300 shadow-md'
                          : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <FileCode className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        <span className="truncate">{file.name}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 ml-1 shrink-0">
                        {Math.round(file.size / 1024 * 10) / 10}k
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Dave's Backend Deck */}
        <div className="bg-slate-900/80 border border-emerald-500/30 rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col justify-between">
          <div>
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-950 border border-emerald-800 flex items-center justify-center text-emerald-400 font-bold text-sm">
                  ⚙️
                </div>
                <div>
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-emerald-300">
                    DAVE // BACKEND POD
                  </h3>
                  <p className="text-[11px] text-slate-400">Flask REST API, JSON Routes, Server Specs</p>
                </div>
              </div>

              {isExecuting ? (
                <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800 animate-pulse">
                  <Loader2 className="w-3 h-3 animate-spin" /> GENERATING
                </span>
              ) : (
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                  {backendFiles.length} deliverables
                </span>
              )}
            </div>

            {/* Dave's Live Output Stream */}
            <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-3 mb-3 font-mono text-xs text-slate-300 min-h-[90px] whitespace-pre-wrap leading-relaxed overflow-x-auto">
              {streams.dave}
            </div>

            {/* Backend Files List */}
            {backendFiles.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                  Files Created by Dave:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  {backendFiles.map((file, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedFile(file)}
                      className={`text-left p-2 rounded-lg border text-xs font-mono transition-all flex items-center justify-between cursor-pointer ${
                        selectedFile?.path === file.path
                          ? 'bg-emerald-950/80 border-emerald-500 text-emerald-300 shadow-md'
                          : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 truncate">
                        <Terminal className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="truncate">{file.name}</span>
                      </div>
                      <span className="text-[10px] text-slate-500 ml-1 shrink-0">
                        {Math.round(file.size / 1024 * 10) / 10}k
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Code Inspector (when a file is clicked) */}
      {selectedFile && (
        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-4 shadow-2xl relative overflow-hidden">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
            <div className="flex items-center gap-2.5">
              <Code2 className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white font-mono">{selectedFile.path}</span>
              <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
                {selectedFile.author}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyCode}
                className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-xs text-slate-300 hover:text-white transition-all cursor-pointer font-mono"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                onClick={() => setSelectedFile(null)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <pre className="p-4 bg-slate-900/90 rounded-xl overflow-x-auto text-xs font-mono text-slate-200 max-h-96 leading-relaxed selection:bg-cyan-500/30 selection:text-cyan-200">
            <code>{selectedFile.content}</code>
          </pre>
        </div>
      )}

      {/* Live In-App Web Preview Modal */}
      {isPreviewOpen && htmlFile && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-950">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                <Eye className="w-4 h-4 text-cyan-400" />
                <span>Live Browser Preview: {htmlFile.name}</span>
              </div>
              <button
                onClick={() => setIsPreviewOpen(false)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 bg-white">
              <iframe
                title="Application Preview"
                srcDoc={htmlFile.content}
                className="w-full h-full border-none"
                sandbox="allow-scripts allow-modals"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
