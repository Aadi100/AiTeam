'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { Cpu, Key, X, Check, Eye, EyeOff, Save, Sparkles, Server, HardDrive } from 'lucide-react';

export default function AISettingsModal() {
  const {
    isAISettingsOpen,
    setIsAISettingsOpen,
    aiKeys,
    updateAIKeys,
    people,
    updatePersonModel
  } = useOffice();

  const [keys, setKeys] = useState(aiKeys);
  const [showKeys, setShowKeys] = useState<{ [key: string]: boolean }>({});
  const [saved, setSaved] = useState(false);

  if (!isAISettingsOpen) return null;

  const toggleShowKey = (k: string) => {
    setShowKeys((prev) => ({ ...prev, [k]: !prev[k] }));
  };

  const handleSave = () => {
    updateAIKeys(keys);
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      setIsAISettingsOpen(false);
    }, 900);
  };

  const availableModels = [
    { id: 'gemini-3.8-flash', label: '⚡ Google Gemini 3.8 Flash (Recommended)' },
    { id: 'gemini-2.5-pro', label: '🌟 Google Gemini 2.5 Pro (API Key Required)' },
    { id: 'claude-sonnet-4-5', label: '🟠 Anthropic Claude Sonnet 4.5 (API Key Required)' },
    { id: 'claude-opus-4', label: '🟠 Anthropic Claude Opus 4 (API Key Required)' },
    { id: 'gpt-4o', label: '🟢 OpenAI GPT-4o (API Key Required)' },
    { id: 'gpt-4o-mini', label: '🟢 OpenAI GPT-4o Mini (API Key Required)' },
    { id: 'ollama:llama3', label: '🦙 Ollama + Llama 3 (Free, Local)' },
    { id: 'ollama:mistral', label: '🌪️ Ollama + Mistral (Free, Local)' },
    { id: 'ollama:qwen', label: '⚡ Ollama + Qwen (Free, Local)' },
    { id: 'ollama:gemma', label: '💎 Ollama + Gemma (Free, Local)' },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-cyan-500/40 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl relative">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/60 sticky top-0 z-10 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20">
              <Cpu className="w-5 h-5 text-cyan-200" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                AI SATELLITE UPLINK & MODEL SETUP
              </h2>
              <p className="text-xs text-slate-400">
                Configure your API keys and assign intelligence models to each specialist.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsAISettingsOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Section 1: Team Model Assignments */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
              <h3 className="text-xs font-bold font-mono uppercase text-slate-200">
                1. ASSIGN AI MODELS TO YOUR PEOPLE
              </h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {people.map((person) => (
                <div
                  key={person.id}
                  className="bg-slate-950/80 border border-slate-800 rounded-xl p-3 flex flex-col justify-between"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{person.avatar}</span>
                    <div>
                      <h4 className="text-xs font-bold text-white">{person.name}</h4>
                      <p className="text-[10px] text-slate-400">{person.role}</p>
                    </div>
                  </div>

                  <select
                    value={person.model}
                    onChange={(e) => updatePersonModel(person.id, e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-cyan-300 font-mono focus:outline-none focus:border-cyan-500 cursor-pointer"
                  >
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {/* Section 2: API Keys Configuration */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-400"></span>
              <h3 className="text-xs font-bold font-mono uppercase text-slate-200">
                2. SATELLITE API KEYS & PROVIDERS
              </h3>
            </div>

            {/* Google Gemini */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-cyan-400" />
                  Google Gemini API Key
                </span>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-cyan-400 hover:underline"
                >
                  Get Free Key ↗
                </a>
              </div>
              <div className="relative">
                <input
                  type={showKeys['gemini'] ? 'text' : 'password'}
                  value={keys.gemini}
                  onChange={(e) => setKeys({ ...keys, gemini: e.target.value })}
                  placeholder="AIzaSy..."
                  className="w-full bg-slate-900 border border-slate-700 focus:border-cyan-500 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => toggleShowKey('gemini')}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showKeys['gemini'] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Anthropic Claude */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-amber-400" />
                  Anthropic Claude API Key
                </span>
                <a
                  href="https://console.anthropic.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-amber-400 hover:underline"
                >
                  Console ↗
                </a>
              </div>
              <div className="relative">
                <input
                  type={showKeys['claude'] ? 'text' : 'password'}
                  value={keys.claude}
                  onChange={(e) => setKeys({ ...keys, claude: e.target.value })}
                  placeholder="sk-ant-api03-..."
                  className="w-full bg-slate-900 border border-slate-700 focus:border-amber-500 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => toggleShowKey('claude')}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showKeys['claude'] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* OpenAI */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Key className="w-3.5 h-3.5 text-emerald-400" />
                  OpenAI API Key
                </span>
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-emerald-400 hover:underline"
                >
                  Platform ↗
                </a>
              </div>
              <div className="relative">
                <input
                  type={showKeys['openai'] ? 'text' : 'password'}
                  value={keys.openai}
                  onChange={(e) => setKeys({ ...keys, openai: e.target.value })}
                  placeholder="sk-..."
                  className="w-full bg-slate-900 border border-slate-700 focus:border-emerald-500 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => toggleShowKey('openai')}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-200"
                >
                  {showKeys['openai'] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Ollama Local URL & Open-Source Models */}
            <div className="bg-slate-950/80 border border-indigo-500/30 rounded-xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Server className="w-3.5 h-3.5 text-indigo-400" />
                  Free Open-Source Engine (Ollama Local Node)
                </span>
                <span className="text-[10px] text-emerald-400 bg-emerald-950 border border-emerald-800/60 px-2 py-0.5 rounded font-mono">
                  Default Fallback
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Whenever no paid API key is assigned, agents automatically default to free open-source models:
              </p>
              <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
                <span className="bg-slate-900 border border-slate-700 px-2 py-1 rounded text-cyan-300">
                  🦙 Ollama + Llama 3
                </span>
                <span className="bg-slate-900 border border-slate-700 px-2 py-1 rounded text-emerald-300">
                  🌪️ Ollama + Mistral
                </span>
                <span className="bg-slate-900 border border-slate-700 px-2 py-1 rounded text-amber-300">
                  ⚡ Ollama + Qwen
                </span>
                <span className="bg-slate-900 border border-slate-700 px-2 py-1 rounded text-purple-300">
                  💎 Ollama + Gemma
                </span>
              </div>
              <div className="pt-1">
                <label className="block text-[10px] font-mono text-slate-400 uppercase mb-1">
                  Ollama Base URL (Default: http://localhost:11434):
                </label>
                <input
                  type="text"
                  value={keys.ollamaUrl}
                  onChange={(e) => setKeys({ ...keys, ollamaUrl: e.target.value })}
                  placeholder="http://localhost:11434"
                  className="w-full bg-slate-900 border border-slate-700 focus:border-indigo-500 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 font-mono focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between sticky bottom-0 z-10 backdrop-blur-md">
          <span className="text-[11px] text-slate-500 font-mono">
            Keys are stored locally in your browser.
          </span>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white text-xs font-bold shadow-lg shadow-cyan-500/20 transition-all cursor-pointer"
          >
            {saved ? (
              <>
                <Check className="w-4 h-4 text-emerald-300" />
                <span>Saved & Synchronized!</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Save Uplink Configuration</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
