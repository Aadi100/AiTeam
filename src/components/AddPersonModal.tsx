'use client';

import React, { useState } from 'react';
import { useOffice } from '@/context/OfficeContext';
import { UserPlus, X, Check } from 'lucide-react';

const ROLE_CATALOG = [
  {
    value: 'Frontend Developer',
    dept: 'Frontend',
    avatar: '💻',
    skills: ['HTML/CSS', 'JavaScript', 'React', 'TypeScript', 'Tailwind CSS', 'Next.js', 'Vue.js', 'Animation', 'Responsive Design'],
  },
  {
    value: 'Backend Developer',
    dept: 'Backend',
    avatar: '⚙️',
    skills: ['Python', 'Node.js', 'Flask', 'FastAPI', 'REST APIs', 'GraphQL', 'Authentication', 'MongoDB', 'PostgreSQL'],
  },
  {
    value: 'Full Stack Developer',
    dept: 'Engineering',
    avatar: '🚀',
    skills: ['React', 'Node.js', 'Python', 'REST APIs', 'MongoDB', 'TypeScript', 'Tailwind CSS', 'Docker'],
  },
  {
    value: 'DevOps Engineer',
    dept: 'Infrastructure',
    avatar: '🔬',
    skills: ['Docker', 'Kubernetes', 'CI/CD', 'AWS', 'Azure', 'GCP', 'Linux', 'Bash', 'Terraform', 'Monitoring'],
  },
  {
    value: 'Mobile Developer',
    dept: 'Mobile',
    avatar: '📱',
    skills: ['React Native', 'Flutter', 'Swift', 'Kotlin', 'iOS', 'Android', 'Cross-Platform', 'Expo'],
  },
  {
    value: 'Database Engineer',
    dept: 'Data',
    avatar: '🗄️',
    skills: ['PostgreSQL', 'MongoDB', 'MySQL', 'Redis', 'SQLite', 'Query Optimization', 'Data Modeling', 'Migrations'],
  },
  {
    value: 'QA Specialist',
    dept: 'Quality',
    avatar: '🛡️',
    skills: ['Testing', 'Selenium', 'Jest', 'Cypress', 'Playwright', 'API Testing', 'Performance Testing', 'Bug Tracking', 'Automation'],
  },
  {
    value: 'UI/UX Designer',
    dept: 'Design',
    avatar: '🎨',
    skills: ['Figma', 'Prototyping', 'User Research', 'Accessibility', 'Design Systems', 'CSS Animations', 'Wireframing'],
  },
  {
    value: 'Security Engineer',
    dept: 'Security',
    avatar: '🔒',
    skills: ['Penetration Testing', 'OWASP', 'Authentication', 'Encryption', 'Vulnerability Assessment', 'Security Audits', 'Zero Trust'],
  },
  {
    value: 'Data Scientist',
    dept: 'Data Science',
    avatar: '📐',
    skills: ['Python', 'Pandas', 'NumPy', 'Data Visualization', 'SQL', 'Machine Learning', 'Statistics', 'Jupyter'],
  },
  {
    value: 'Machine Learning Engineer',
    dept: 'AI/ML',
    avatar: '🤖',
    skills: ['PyTorch', 'TensorFlow', 'Scikit-learn', 'NLP', 'Computer Vision', 'Model Training', 'MLOps', 'Python'],
  },
  {
    value: 'API Developer',
    dept: 'Backend',
    avatar: '⚡',
    skills: ['REST APIs', 'GraphQL', 'OpenAPI', 'FastAPI', 'Express', 'Authentication', 'Rate Limiting', 'Webhooks'],
  },
];

const EXTRA_AVATARS = ['🧑‍💻', '👩‍💻', '👨‍💻', '🦾', '🧠', '📡', '🌐', '🧬'];

export default function AddPersonModal() {
  const { isAddPersonOpen, setIsAddPersonOpen, addPerson } = useOffice();

  const [name, setName] = useState('');
  const [selectedRole, setSelectedRole] = useState(ROLE_CATALOG[0]);
  const [selectedSkills, setSelectedSkills] = useState<string[]>(ROLE_CATALOG[0].skills.slice(0, 4));
  const [avatar, setAvatar] = useState(ROLE_CATALOG[0].avatar);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isAddPersonOpen) return null;

  const handleRoleChange = (value: string) => {
    const role = ROLE_CATALOG.find((r) => r.value === value) || ROLE_CATALOG[0];
    setSelectedRole(role);
    setSelectedSkills(role.skills.slice(0, 4));
    setAvatar(role.avatar);
  };

  const toggleSkill = (skill: string) => {
    setSelectedSkills((prev) =>
      prev.includes(skill) ? prev.filter((s) => s !== skill) : [...prev, skill]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || selectedSkills.length === 0) return;

    setIsSubmitting(true);
    const personId = name.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Date.now().toString().slice(-4);

    await addPerson({
      id: personId,
      name: name.trim(),
      role: selectedRole.value,
      department: selectedRole.dept,
      avatar,
      color: 'from-blue-600 to-indigo-700',
      model: 'gemini-3.8-flash',
      systemPrompt: `You are ${name.trim()}, a ${selectedRole.value}. You specialize in ${selectedSkills.slice(0, 3).join(', ')} and high-quality software craftsmanship.`,
      skills: selectedSkills,
    });

    setIsSubmitting(false);
    setIsAddPersonOpen(false);
    setName('');
    setSelectedRole(ROLE_CATALOG[0]);
    setSelectedSkills(ROLE_CATALOG[0].skills.slice(0, 4));
    setAvatar(ROLE_CATALOG[0].avatar);
  };

  const allAvatars = [selectedRole.avatar, ...EXTRA_AVATARS.filter((a) => a !== selectedRole.avatar)];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <UserPlus className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">Hire a Specialist</h2>
              <p className="text-xs text-slate-400">Choose a role — skills are predefined for quality output.</p>
            </div>
          </div>
          <button onClick={() => setIsAddPersonOpen(false)} className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Name */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1.5">Agent Name:</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Alex, Elena, Marcus..."
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none"
            />
          </div>

          {/* Role select */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1.5">Role / Specialty:</label>
            <select
              value={selectedRole.value}
              onChange={(e) => handleRoleChange(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 rounded-xl px-3 py-2.5 text-sm text-white focus:outline-none cursor-pointer"
            >
              {ROLE_CATALOG.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.avatar}  {r.value}
                </option>
              ))}
            </select>
          </div>

          {/* Avatar picker */}
          <div>
            <label className="block text-xs font-mono text-slate-300 uppercase mb-1.5">Avatar:</label>
            <div className="flex flex-wrap gap-2">
              {allAvatars.map((e) => (
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

          {/* Skills — toggle chips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-mono text-slate-300 uppercase">Skills (select all that apply):</label>
              <span className="text-[10px] font-mono text-slate-500">{selectedSkills.length} selected</span>
            </div>
            <div className="flex flex-wrap gap-1.5 bg-slate-950/60 border border-slate-800 rounded-xl p-3">
              {selectedRole.skills.map((skill) => {
                const active = selectedSkills.includes(skill);
                return (
                  <button
                    key={skill}
                    type="button"
                    onClick={() => toggleSkill(skill)}
                    className={`text-xs font-mono px-2.5 py-1 rounded-lg border transition-all cursor-pointer ${
                      active
                        ? 'bg-emerald-600/30 border-emerald-500/60 text-emerald-300'
                        : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-300'
                    }`}
                  >
                    {active && <span className="mr-1">✓</span>}
                    {skill}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model note */}
          <p className="text-[11px] text-slate-500 font-mono bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">
            🧠 Model: <span className="text-cyan-400">gemini-3.8-flash</span> (default) — change in <span className="text-cyan-400 underline cursor-pointer">AI Settings</span>
          </p>

          {/* Actions */}
          <div className="pt-2 border-t border-slate-800 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsAddPersonOpen(false)}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !name.trim() || selectedSkills.length === 0}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <Check className="w-4 h-4" />
              <span>{isSubmitting ? 'Deploying...' : 'Hire to Squad'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
