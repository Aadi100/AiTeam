'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { UserPlus, X, Sparkles, Check, Cpu } from 'lucide-react';

export default function AddPersonModal() {
  const { isAddPersonOpen, setIsAddPersonOpen, addPerson } = useOffice();

  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [avatar, setAvatar] = useState('🧑‍💻');
  const [model, setModel] = useState('gemini-2.0-flash');
  const [skills, setSkills] = useState('Architecture, Code Optimization');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isAddPersonOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !role.trim()) return;

    setIsSubmitting(true);
    const personId = name.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Date.now().toString().slice(-4);
    const skillsList = skills.split(',').map((s) => s.trim()).filter(Boolean);

    await addPerson({
      id: personId,
      name: name.trim(),
      role: role.trim(),
      department,
      avatar,
      color: 'from-blue-600 to-indigo-700',
      model,
      systemPrompt: `You are ${name}, ${role}. You specialize in high-quality software craftsmanship.`,
      skills: skillsList.length > 0 ? skillsList : ['Development', 'Optimization']
    });

    setIsSubmitting(false);
    setIsAddPersonOpen(false);
    setName('');
    setRole('');
  };

  const emojiOptions = ['💻', '⚙️', '🎨', '🚀', '📐', '🔬', '🛡️', '⚡', '🧑‍💻', '🤖'];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl w-full max-w-lg shadow-2xl relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                ADD PERSON TO THE OFFICE
              </h2>
              <p className="text-xs text-slate-400">
                Create a specialist with a specific role and assigned AI model.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsAddPersonOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Avatar selector */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1.5">
              Choose Avatar:
            </label>
            <div className="flex flex-wrap gap-2">
              {emojiOptions.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setAvatar(e)}
                  className={`w-9 h-9 rounded-xl text-lg flex items-center justify-center transition-all ${
                    avatar === e
                      ? 'bg-emerald-500/20 border-2 border-emerald-400 scale-110 shadow-lg'
                      : 'bg-slate-800 border border-slate-700 hover:border-slate-600'
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {/* Name & Role */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                Person Name:
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Alex or Elena"
                className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                Specific Job / Role:
              </label>
              <input
                type="text"
                required
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. DevOps Engineer"
                className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Assigned AI Model */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              Assigned AI Model:
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none cursor-pointer"
            >
              <option value="gemini-2.0-flash">Google Gemini 2.0 Flash</option>
              <option value="claude-3-5-sonnet">Anthropic Claude 3.5 Sonnet</option>
              <option value="gpt-4o">OpenAI GPT-4o</option>
              <option value="ollama:llama3.2">Local Ollama (Llama 3.2)</option>
            </select>
          </div>

          {/* Skills / Specialties */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
              Skills (comma-separated):
            </label>
            <input
              type="text"
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder="Docker, CI/CD, Kubernetes"
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none"
            />
          </div>

          {/* Submit Button */}
          <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsAddPersonOpen(false)}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all cursor-pointer"
            >
              <Check className="w-4 h-4" />
              <span>{isSubmitting ? 'Deploying...' : 'Add to Office'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
