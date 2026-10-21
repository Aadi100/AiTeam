'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Send, Mic, MicOff, Loader2, Zap, Play } from 'lucide-react';
import VoiceOrb from './VoiceOrb';

export default function ChatInterface() {
  const {
    currentSessionId,
    chatSessions,
    sendChatMessage,
    isExecuting,
    isVoiceActive,
    voiceTranscript,
    toggleVoiceListening,
    isAgentSpeaking,
    executeParallelBuild,
    targetPath,
  } = useOffice();

  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const currentSession = chatSessions.find((s) => s.id === currentSessionId);
  const messages = currentSession?.messages ?? [];

  // Sync voice transcript to input
  useEffect(() => {
    if (voiceTranscript) setInput(voiceTranscript);
  }, [voiceTranscript]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = input.trim();
    if (!text || isSending || isExecuting) return;

    setInput('');
    setIsSending(true);
    try {
      await sendChatMessage(text);
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isLoading = isSending || isExecuting;
  const showOrb = isVoiceActive || isAgentSpeaking;

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-slate-950/60 border border-slate-800/80 rounded-2xl overflow-hidden backdrop-blur-xl shadow-2xl">

      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800/60 bg-slate-900/50 shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
          <span className="text-[11px] font-mono font-bold text-slate-300 uppercase tracking-widest">
            {currentSession?.title ?? 'DevSquad Chat'}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2 text-[10px] font-mono text-slate-500">
          <Zap className="w-3 h-3 text-cyan-500" />
          <span>Start with <span className="text-orange-400 font-bold">Hey Rex</span> for PC control</span>
        </div>
      </div>

      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-6 py-16">
            {/* Orb in idle state as welcome */}
            <VoiceOrb isActive={false} size={100} />
            <div>
              <h3 className="text-slate-200 font-bold text-lg mb-1">DevSquad AI</h3>
              <p className="text-slate-500 text-sm max-w-xs">
                Ask anything, build something, or say{' '}
                <span className="text-orange-400 font-mono font-bold">"Hey Rex, open Chrome"</span>{' '}
                to control your PC.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-sm">
              {[
                'Create a notes app with dark mode',
                'Hey Rex, take a screenshot',
                'Explain REST vs GraphQL',
                'Build a portfolio website',
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="text-xs bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-cyan-600/50 text-slate-400 hover:text-cyan-300 px-3 py-1.5 rounded-xl transition-all cursor-pointer"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.role === 'user';
          const isSystem = msg.role === 'system';

          if (isSystem) {
            return (
              <div key={msg.id} className="flex justify-center">
                <span className="text-[10px] font-mono text-slate-600 bg-slate-900/50 border border-slate-800/50 px-3 py-1 rounded-full">
                  {msg.content}
                </span>
              </div>
            );
          }

          return (
            <div key={msg.id} className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
              {/* Avatar */}
              {!isUser && (
                <div className="w-8 h-8 shrink-0 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-sm">
                  {msg.agentAvatar || '🤖'}
                </div>
              )}

              <div className={`flex flex-col gap-1 max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
                {!isUser && (
                  <span className="text-[10px] font-mono text-slate-500 px-1">
                    {msg.agentName || 'DevSquad AI'}
                    {msg.agentId === 'rex' && (
                      <span className="ml-1.5 text-orange-400 bg-orange-950/50 border border-orange-800/40 px-1.5 py-0.5 rounded font-bold">PC CTRL</span>
                    )}
                  </span>
                )}

                <div
                  className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    isUser
                      ? 'bg-gradient-to-br from-cyan-600 to-indigo-700 text-white rounded-tr-sm shadow-lg shadow-cyan-500/10'
                      : msg.type === 'error'
                      ? 'bg-rose-950/60 border border-rose-800/50 text-rose-200 rounded-tl-sm'
                      : msg.type === 'rex_plan'
                      ? 'bg-orange-950/60 border border-orange-700/50 text-orange-100 rounded-tl-sm'
                      : 'bg-slate-800/80 border border-slate-700/50 text-slate-100 rounded-tl-sm'
                  }`}
                >
                  {msg.type === 'thinking' ? (
                    <span className="italic text-slate-400 flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      {msg.content}
                    </span>
                  ) : (
                    msg.content
                  )}
                </div>

                <span className="text-[9px] font-mono text-slate-600 px-1">
                  {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          );
        })}

        {/* Loading dots */}
        {isLoading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 shrink-0 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-sm">🤖</div>
            <div className="bg-slate-800/80 border border-slate-700/50 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Voice orb overlay when listening/speaking */}
      {showOrb && (
        <div className="flex justify-center py-3 border-t border-slate-800/40 bg-slate-950/40">
          <div className="flex flex-col items-center gap-2">
            <VoiceOrb isActive={true} size={80} />
            <span className="text-[10px] font-mono text-cyan-400 animate-pulse">
              {isVoiceActive ? 'Listening...' : 'Agent speaking...'}
            </span>
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="shrink-0 border-t border-slate-800/60 bg-slate-900/60 px-4 py-3">
        <form onSubmit={handleSend} className="flex gap-2 items-center">
          {/* Mic button */}
          <button
            type="button"
            onClick={toggleVoiceListening}
            className={`p-2.5 rounded-xl border transition-all cursor-pointer shrink-0 ${
              isVoiceActive
                ? 'bg-rose-500/20 border-rose-500/60 text-rose-400 shadow-[0_0_12px_rgba(244,63,94,0.3)] animate-pulse'
                : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-cyan-400 hover:border-cyan-600/50'
            }`}
            title={isVoiceActive ? 'Stop listening' : 'Voice input'}
          >
            {isVoiceActive ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          {/* Text input */}
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isVoiceActive ? 'Listening...' : 'Message DevSquad... (Hey Rex, for PC control)'}
            disabled={isLoading}
            className="flex-1 bg-slate-950/80 border border-slate-700 focus:border-cyan-500/60 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none font-sans disabled:opacity-60"
          />

          {/* Deploy Squad button when text looks like a build prompt */}
          {input.trim() && !input.match(/^hey\s+rex\b/i) && !isLoading && (
            <button
              type="button"
              onClick={() => executeParallelBuild(input.trim(), targetPath)}
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shrink-0 transition-all cursor-pointer"
              title="Deploy Squad (build mode)"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              <span className="hidden sm:inline">Deploy</span>
            </button>
          )}

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="p-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-all cursor-pointer shrink-0"
            title="Send"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>

        <p className="text-[10px] font-mono text-slate-600 mt-1.5 px-1">
          Say <span className="text-orange-400">Hey Rex</span> to control your PC · Press <span className="text-slate-400">Enter</span> to send · <span className="text-cyan-500">Deploy</span> for full squad build
        </p>
      </div>
    </div>
  );
}
