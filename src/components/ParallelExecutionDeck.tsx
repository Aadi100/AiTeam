'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Person, GeneratedFile } from '@/types/office';
import {
  Code2,
  Terminal,
  FolderCheck,
  ExternalLink,
  Copy,
  Check,
  FileCode,
  Eye,
  EyeOff,
  Loader2,
  X,
  Monitor,
} from 'lucide-react';

const AGENT_THEME: Record<string, { border: string; headerText: string; iconBg: string; fileBorder: string; fileActiveBg: string; fileActiveText: string; genBadge: string }> = {
  michael: {
    border: 'border-cyan-500/30',
    headerText: 'text-cyan-300',
    iconBg: 'bg-cyan-950 border-cyan-800',
    fileBorder: 'border-cyan-500',
    fileActiveBg: 'bg-cyan-950/80',
    fileActiveText: 'text-cyan-300',
    genBadge: 'text-cyan-400 bg-cyan-950 border-cyan-800',
  },
  dave: {
    border: 'border-emerald-500/30',
    headerText: 'text-emerald-300',
    iconBg: 'bg-emerald-950 border-emerald-800',
    fileBorder: 'border-emerald-500',
    fileActiveBg: 'bg-emerald-950/80',
    fileActiveText: 'text-emerald-300',
    genBadge: 'text-emerald-400 bg-emerald-950 border-emerald-800',
  },
  rex: {
    border: 'border-orange-500/30',
    headerText: 'text-orange-300',
    iconBg: 'bg-orange-950 border-orange-800',
    fileBorder: 'border-orange-500',
    fileActiveBg: 'bg-orange-950/80',
    fileActiveText: 'text-orange-300',
    genBadge: 'text-orange-400 bg-orange-950 border-orange-800',
  },
  sarah: {
    border: 'border-purple-500/30',
    headerText: 'text-purple-300',
    iconBg: 'bg-purple-950 border-purple-800',
    fileBorder: 'border-purple-500',
    fileActiveBg: 'bg-purple-950/80',
    fileActiveText: 'text-purple-300',
    genBadge: 'text-purple-400 bg-purple-950 border-purple-800',
  },
};

const DEFAULT_THEME = {
  border: 'border-indigo-500/30',
  headerText: 'text-indigo-300',
  iconBg: 'bg-indigo-950 border-indigo-800',
  fileBorder: 'border-indigo-500',
  fileActiveBg: 'bg-indigo-950/80',
  fileActiveText: 'text-indigo-300',
  genBadge: 'text-indigo-400 bg-indigo-950 border-indigo-800',
};

function getTheme(id: string) {
  return AGENT_THEME[id] || DEFAULT_THEME;
}

function filesBelongTo(files: GeneratedFile[], person: Person): GeneratedFile[] {
  return files.filter((f) => {
    if (f.author && f.author.toLowerCase().includes(person.name.toLowerCase())) return true;
    if (person.id === 'michael' && (f.path.endsWith('.html') || f.path.endsWith('.css') || (f.path.endsWith('.js') && !f.path.includes('backend')))) return true;
    if (person.id === 'dave' && (f.path.includes('backend') || f.path.endsWith('.py') || f.path.endsWith('.md') || f.path.endsWith('.txt') || f.path.endsWith('.json'))) return true;
    return false;
  });
}

export default function ParallelExecutionDeck() {
  const { streams, writtenFiles, project, targetPath, openFolderInExplorer, isExecuting, selectedFile, setSelectedFile, people } = useOffice();

  const [copied, setCopied] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [inlinePreview, setInlinePreview] = useState(false);

  const htmlFile = writtenFiles.find((f) => f.name.endsWith('.html'));

  const handleCopyCode = () => {
    if (selectedFile?.content) {
      navigator.clipboard.writeText(selectedFile.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Which agents to show pods for: anyone with a stream, or anyone that's coding
  const activePeople = people.filter(
    (p) => p.id !== 'rex' && ((streams[p.id] && streams[p.id].trim()) || p.status === 'coding' || isExecuting)
  );

  // If nobody active, show Michael + Dave by default as "standing by"
  const codeAgents = activePeople.length > 0
    ? activePeople
    : people.filter((p) => p.id === 'michael' || p.id === 'dave');

  const cols = codeAgents.length === 1 ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-2';

  return (
    <div className="space-y-4">
      {/* Completion Banner */}
      {project.status === 'completed' && writtenFiles.length > 0 && (
        <div className="bg-gradient-to-r from-emerald-950/90 via-slate-900 to-cyan-950/90 border border-emerald-500/40 rounded-2xl p-4 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-400/60 flex items-center justify-center text-emerald-400 shrink-0">
              <FolderCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                MISSION COMPLETE
                <span className="text-[10px] bg-emerald-900/80 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-600/50 font-mono">
                  {writtenFiles.length} FILES
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">{project.projectGoal?.slice(0, 60)}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto justify-end flex-wrap">
            {htmlFile && (
              <button
                onClick={() => setInlinePreview((v) => !v)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all cursor-pointer"
              >
                {inlinePreview ? <EyeOff className="w-3.5 h-3.5 text-cyan-400" /> : <Eye className="w-3.5 h-3.5 text-cyan-400" />}
                <span>{inlinePreview ? 'Hide Preview' : 'Live Preview'}</span>
              </button>
            )}
            {htmlFile && (
              <button
                onClick={() => setPreviewOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all cursor-pointer"
              >
                <Monitor className="w-3.5 h-3.5 text-indigo-400" />
                <span>Full Screen</span>
              </button>
            )}
            <button
              onClick={() => openFolderInExplorer(targetPath)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/20 transition-all cursor-pointer"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Open Folder</span>
            </button>
          </div>
        </div>
      )}

      {/* Inline Browser Preview */}
      {inlinePreview && htmlFile && (
        <div className="bg-slate-900 border border-indigo-500/30 rounded-2xl overflow-hidden shadow-2xl">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-800 bg-slate-950">
            <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
              <Eye className="w-3.5 h-3.5 text-indigo-400" />
              <span>Live Preview — {htmlFile.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPreviewOpen(true)}
                className="text-[10px] font-mono text-slate-400 hover:text-white hover:underline cursor-pointer"
              >
                Full Screen ↗
              </button>
              <button onClick={() => setInlinePreview(false)} className="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300 cursor-pointer">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
          <div className="bg-white" style={{ height: '420px' }}>
            <iframe
              title="Inline Preview"
              srcDoc={htmlFile.content}
              className="w-full h-full border-none"
              sandbox="allow-scripts allow-modals"
            />
          </div>
        </div>
      )}

      {/* Dynamic Agent Pods */}
      <div className={`grid ${cols} gap-5`}>
        {codeAgents.map((person) => {
          const theme = getTheme(person.id);
          const agentFiles = filesBelongTo(writtenFiles, person);
          const stream = streams[person.id] || '';
          const isActive = person.status === 'coding';

          return (
            <div
              key={person.id}
              className={`bg-slate-900/80 border ${theme.border} rounded-2xl p-4 shadow-xl backdrop-blur-md flex flex-col`}
            >
              {/* Pod Header */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                <div className="flex items-center gap-2.5">
                  <div className={`w-8 h-8 rounded-lg border flex items-center justify-center text-sm ${theme.iconBg}`}>
                    {person.avatar || '🤖'}
                  </div>
                  <div>
                    <h3 className={`text-xs font-bold font-mono uppercase tracking-wider ${theme.headerText}`}>
                      {person.name} // {person.department || person.role.split(' ')[0].toUpperCase()} POD
                    </h3>
                    <p className="text-[11px] text-slate-400">{person.role}</p>
                  </div>
                </div>

                {isActive || (isExecuting && !stream) ? (
                  <span className={`flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border animate-pulse ${theme.genBadge}`}>
                    <Loader2 className="w-3 h-3 animate-spin" /> WORKING
                  </span>
                ) : (
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                    {agentFiles.length} deliverables
                  </span>
                )}
              </div>

              {/* Live Stream Output */}
              <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-3 mb-3 font-mono text-xs text-slate-300 min-h-[90px] whitespace-pre-wrap leading-relaxed overflow-x-auto flex-1">
                {stream || (
                  <span className="text-slate-600 italic">
                    {person.name} standing by... waiting for directive.
                  </span>
                )}
              </div>

              {/* Files List */}
              {agentFiles.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
                    Files by {person.name}:
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-1.5">
                    {agentFiles.map((file, idx) => (
                      <button
                        key={idx}
                        onClick={() => setSelectedFile(file)}
                        className={`text-left p-2 rounded-lg border text-xs font-mono transition-all flex items-center justify-between cursor-pointer ${
                          selectedFile?.path === file.path
                            ? `${theme.fileActiveBg} ${theme.fileBorder} ${theme.fileActiveText} shadow-md`
                            : 'bg-slate-950/60 border-slate-800 hover:border-slate-700 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-1.5 truncate">
                          {person.id === 'dave' ? (
                            <Terminal className={`w-3.5 h-3.5 shrink-0 ${theme.headerText}`} />
                          ) : (
                            <FileCode className={`w-3.5 h-3.5 shrink-0 ${theme.headerText}`} />
                          )}
                          <span className="truncate">{file.name}</span>
                        </div>
                        <span className="text-[10px] text-slate-500 ml-1 shrink-0">
                          {Math.round((file.size / 1024) * 10) / 10}k
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Code Inspector */}
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
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
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

      {/* Full-Screen Preview Modal */}
      {previewOpen && htmlFile && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-5xl h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800 bg-slate-950">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                <Eye className="w-4 h-4 text-cyan-400" />
                <span>Browser Preview — {htmlFile.name}</span>
              </div>
              <button
                onClick={() => setPreviewOpen(false)}
                className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 bg-white">
              <iframe
                title="Full Preview"
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
