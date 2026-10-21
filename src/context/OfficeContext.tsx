'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { Person, AIKeys, GeneratedFile, ProjectState, ParallelStreams, ProjectHistoryItem, ChatMessage, ChatSession } from '@/types/office';
import confetti from 'canvas-confetti';

// Use the Next.js proxy by default (/api/py â†’ http://127.0.0.1:5000/api).
// Set NEXT_PUBLIC_BACKEND_URL to a full origin (e.g. http://localhost:5000) to bypass the proxy.
const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL.replace(/\/$/, '')}/api`
  : '/api/py';

const DEFAULT_PEOPLE: Person[] = [
  {
    id: 'michael',
    name: 'Michael',
    role: 'Frontend Specialist',
    department: 'Frontend',
    avatar: 'ðŸ’»',
    color: 'from-cyan-500 to-blue-600',
    status: 'idle',
    statusText: 'Orbital Frontend Station online. Standing by for directives.',
    model: 'gemini-3.8-flash',
    systemPrompt: 'You are Michael, Senior Frontend Developer. You build responsive, modern, beautiful user interfaces using HTML5, CSS3, Tailwind CSS, JavaScript, and React.',
    skills: ['HTML5 & Modern CSS', 'Tailwind CSS', 'JavaScript (ESNext)', 'React Components', 'UI/UX & Responsive Design'],
    stats: { tasksDone: 12, filesCreated: 18, reviewsDone: 10 },
    desk: { room: 'Orbital Station Alpha', col: 1, row: 1 }
  },
  {
    id: 'dave',
    name: 'Dave',
    role: 'Backend Specialist',
    department: 'Backend',
    avatar: 'âš™ï¸',
    color: 'from-emerald-500 to-teal-700',
    status: 'idle',
    statusText: 'Orbital Backend Station online. Database handlers synced.',
    model: 'gemini-3.8-flash',
    systemPrompt: 'You are Dave, Senior Backend Developer. You build robust REST APIs, Flask/Node.js servers, database schemas, and server-side logic.',
    skills: ['Python Flask', 'Node.js & Express', 'MongoDB & SQLite', 'REST API Architecture', 'Authentication & Endpoints'],
    stats: { tasksDone: 14, filesCreated: 16, reviewsDone: 12 },
    desk: { room: 'Orbital Station Beta', col: 2, row: 1 }
  },
  {
    id: 'sarah',
    name: 'Sarah',
    role: 'QA & UI/UX Specialist',
    department: 'Design & QA',
    avatar: 'ðŸŽ¨',
    color: 'from-purple-500 to-pink-600',
    status: 'idle',
    statusText: 'Quality control matrix primed.',
    model: 'gemini-3.8-flash',
    systemPrompt: 'You are Sarah, QA & Design Specialist. You verify UI styling, responsiveness, cross-browser compatibility, and API integrity.',
    skills: ['UI/UX Testing', 'Responsiveness QA', 'API Validation', 'Accessibility'],
    stats: { tasksDone: 8, filesCreated: 6, reviewsDone: 15 },
    desk: { room: 'Orbital Station Gamma', col: 3, row: 1 }
  }
];

interface OfficeContextType {
  people: Person[];
  aiKeys: AIKeys;
  updateAIKeys: (keys: Partial<AIKeys>) => void;
  targetPath: string;
  setTargetPath: (path: string) => void;
  project: ProjectState;
  streams: ParallelStreams;
  writtenFiles: GeneratedFile[];
  selectedFile: GeneratedFile | null;
  setSelectedFile: (file: GeneratedFile | null) => void;
  isExecuting: boolean;
  isVoiceActive: boolean;
  voiceTranscript: string;
  startVoiceListening: () => void;
  stopVoiceListening: () => void;
  toggleVoiceListening: () => void;
  isAudioReplyEnabled: boolean;
  toggleAudioReply: () => void;
  isAutoProcessVoice: boolean;
  toggleAutoProcessVoice: () => void;
  speakText: (text: string) => void;
  executeParallelBuild: (prompt: string, pathOverride?: string) => Promise<boolean>;
  openFolderInExplorer: (path?: string) => Promise<boolean>;
  addPerson: (person: Omit<Person, 'stats' | 'status' | 'statusText'>) => Promise<void>;
  updatePersonModel: (personId: string, model: string) => Promise<void>;
  isAISettingsOpen: boolean;
  setIsAISettingsOpen: (open: boolean) => void;
  isAddPersonOpen: boolean;
  setIsAddPersonOpen: (open: boolean) => void;
  isHistoryOpen: boolean;
  setIsHistoryOpen: (open: boolean) => void;
  history: ProjectHistoryItem[];
  refreshHistory: () => Promise<void>;
  loadProjectFromHistory: (item: ProjectHistoryItem) => void;
  deleteHistoryItem: (id: string) => Promise<void>;
  clearAllHistory: () => Promise<void>;
  refreshFromBackend: () => Promise<void>;
  // Chat
  chatSessions: ChatSession[];
  currentSessionId: string;
  startNewChat: () => void;
  switchSession: (id: string) => void;
  deleteChatSession: (id: string) => void;
  sendChatMessage: (text: string) => Promise<void>;
  isAgentSpeaking: boolean;
}

const OfficeContext = createContext<OfficeContextType | undefined>(undefined);

function makeSession(): ChatSession {
  // Use crypto.randomUUID when available (no Date.now during render)
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : `chat-${Math.random().toString(36).slice(2, 10)}`;
  return {
    id,
    title: 'New Chat',
    createdAt: new Date().toISOString(),
    messages: [],
  };
}

export function OfficeProvider({ children }: { children: ReactNode }) {
  const [people, setPeople] = useState<Person[]>(DEFAULT_PEOPLE);
  const [targetPath, setTargetPath] = useState<string>('~/Desktop/devsquad-app');
  const [aiKeys, setAiKeys] = useState<AIKeys>({
    gemini: '',
    claude: '',
    openai: '',
    ollamaUrl: 'http://localhost:11434'
  });
  const [project, setProject] = useState<ProjectState>({
    projectName: 'Mission Control Office',
    projectGoal: 'Ready for user directive via voice or chat...',
    status: 'idle',
    progress: 0,
    targetPath: '~/Desktop/devsquad-app',
    totalFiles: 0
  });
  const [streams, setStreams] = useState<ParallelStreams>({
    michael: '',
    dave: ''
  });
  const [writtenFiles, setWrittenFiles] = useState<GeneratedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [isVoiceActive, setIsVoiceActive] = useState<boolean>(false);
  const [voiceTranscript, setVoiceTranscript] = useState<string>('');
  const [isAudioReplyEnabled, setIsAudioReplyEnabled] = useState<boolean>(true);
  const [isAutoProcessVoice, setIsAutoProcessVoice] = useState<boolean>(true);
  const [isAISettingsOpen, setIsAISettingsOpen] = useState<boolean>(false);
  const [isAddPersonOpen, setIsAddPersonOpen] = useState<boolean>(false);
  const [history, setHistory] = useState<ProjectHistoryItem[]>([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);

  // Chat state — start empty to avoid Date.now() during prerender, hydrate in useEffect
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>('');
  const [isAgentSpeaking, setIsAgentSpeaking] = useState<boolean>(false);

  const isExecutingRef = useRef<boolean>(false);
  const voiceTranscriptRef = useRef<string>('');
  const executeParallelBuildRef = useRef<((prompt: string, pathOverride?: string) => Promise<boolean>) | null>(null);

  isExecutingRef.current = isExecuting;
  voiceTranscriptRef.current = voiceTranscript;

  // Audio Speech Synthesis Reply Function
  const speakText = useCallback(
    (text: string) => {
      if (!isAudioReplyEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
        return;
      }

      try {
        window.speechSynthesis.cancel(); // cancel any active speech

        const cleanText = text.replace(/[*#`_]/g, '');
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;

        // Try to pick a clear English voice
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice =
          voices.find((v) => v.name.includes('Google US English') || v.name.includes('Natural')) ||
          voices.find((v) => v.lang.startsWith('en')) ||
          voices[0];

        if (preferredVoice) {
          utterance.voice = preferredVoice;
        }

        window.speechSynthesis.speak(utterance);
      } catch {
        // ignore speech synthesis errors
      }
    },
    [isAudioReplyEnabled]
  );

  const toggleAudioReply = useCallback(() => {
    setIsAudioReplyEnabled((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('devsquad_audio_reply', String(next));
      } catch {
        // ignore
      }
      if (next) {
        speakText('Audio reply enabled.');
      } else {
        if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
          window.speechSynthesis.cancel();
        }
      }
      return next;
    });
  }, [speakText]);

  const toggleAutoProcessVoice = useCallback(() => {
    setIsAutoProcessVoice((prev) => {
      const next = !prev;
      speakText(next ? 'Automatic voice processing enabled.' : 'Manual voice processing enabled.');
      return next;
    });
  }, [speakText]);

  const refreshHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/project/history`);
      if (res.ok) {
        const data = await res.json();
        if (data.history) {
          setHistory(data.history);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  const loadProjectFromHistory = useCallback((item: ProjectHistoryItem) => {
    setProject({
      projectName: item.prompt.slice(0, 32),
      projectGoal: item.prompt,
      status: 'completed',
      progress: 100,
      targetPath: item.targetPath,
      totalFiles: item.totalFiles,
      startedAt: item.timestamp
    });
    setTargetPath(item.targetPath);
    setWrittenFiles(item.files || []);
    if (item.files && item.files.length > 0) {
      setSelectedFile(item.files[0]);
    }
    setStreams(item.streams || {
      michael: `[Restored from History] Loaded frontend files from: ${item.targetPath}`,
      dave: `[Restored from History] Loaded backend routes from: ${item.targetPath}`
    });
    setIsHistoryOpen(false);
    speakText(`Restored ${item.prompt} from mission history.`);
  }, [setTargetPath, speakText]);

  const deleteHistoryItem = useCallback(async (id: string) => {
    setHistory((prev) => prev.filter((h) => h.id !== id));
    try {
      await fetch(`${API_URL}/project/history/${id}`, { method: 'DELETE' });
    } catch {
      // ignore
    }
  }, []);

  const clearAllHistory = useCallback(async () => {
    setHistory([]);
    try {
      await fetch(`${API_URL}/project/history`, { method: 'DELETE' });
    } catch {
      // ignore
    }
  }, []);

  // Load persisted AI keys, target folder, audio settings from localStorage
  useEffect(() => {
    try {
      const savedKeys = localStorage.getItem('devsquad_ai_keys');
      if (savedKeys) {
        setAiKeys(JSON.parse(savedKeys));
      }
      const savedPath = localStorage.getItem('devsquad_target_path');
      if (savedPath) {
        setTargetPath(savedPath);
      }
      const savedAudio = localStorage.getItem('devsquad_audio_reply');
      if (savedAudio !== null) {
        setIsAudioReplyEnabled(savedAudio === 'true');
      }
    } catch {
      // ignore local storage errors
    }
  }, []);

  // Update & persist AI keys
  const updateAIKeys = useCallback((newKeys: Partial<AIKeys>) => {
    setAiKeys((prev) => {
      const updated = { ...prev, ...newKeys };
      try {
        localStorage.setItem('devsquad_ai_keys', JSON.stringify(updated));
      } catch {
        // ignore
      }
      return updated;
    });
  }, []);

  const updateTargetPath = useCallback((newPath: string) => {
    setTargetPath(newPath);
    try {
      localStorage.setItem('devsquad_target_path', newPath);
    } catch {
      // ignore
    }
  }, []);

  // Fetch agents from Flask backend
  const refreshFromBackend = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/agents`);
      if (res.ok) {
        const data = await res.json();
        if (data.agents && data.agents.length > 0) {
          setPeople(data.agents);
        }
      }
    } catch {
      // Backend might still be starting, fallback smoothly
    }
  }, []);

  useEffect(() => {
    refreshFromBackend();
  }, [refreshFromBackend]);

  // Web Speech API Voice Recognition with Automatic Processing
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    let capturedText = '';
    let silenceTimer: ReturnType<typeof setTimeout> | null = null;
    let hasTriggered = false;

    const triggerAutoProcess = (rawText: string) => {
      const clean = rawText.trim();
      if (hasTriggered || !clean || clean.length < 3 || isExecutingRef.current) return;
      hasTriggered = true;
      setIsVoiceActive(false);
      try {
        recognition.stop();
      } catch {
        // ignore
      }

      if (executeParallelBuildRef.current) {
        executeParallelBuildRef.current(clean);
      }
    };

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      let interim = '';
      let isFinalResult = false;
      for (let i = 0; i < event.results.length; i++) {
        interim += event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          isFinalResult = true;
        }
      }
      capturedText = interim;
      voiceTranscriptRef.current = interim;
      setVoiceTranscript(interim);

      if (silenceTimer) clearTimeout(silenceTimer);

      if (isAutoProcessVoice && interim.trim().length > 3) {
        if (isFinalResult) {
          // Final sentence detected from speech engine -> auto-trigger parallel build!
          triggerAutoProcess(interim);
        } else {
          // User paused speaking for 1.2s -> auto-trigger without needing any click!
          silenceTimer = setTimeout(() => {
            triggerAutoProcess(capturedText);
          }, 1200);
        }
      }
    };

    recognition.onerror = () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      setIsVoiceActive(false);
    };

    recognition.onend = () => {
      setIsVoiceActive(false);
      if (silenceTimer) clearTimeout(silenceTimer);
      const spokenText = (capturedText || voiceTranscriptRef.current).trim();

      // Automatically trigger parallel execution without needing to click any button!
      if (isAutoProcessVoice && spokenText.length > 2 && !hasTriggered && !isExecutingRef.current) {
        triggerAutoProcess(spokenText);
      }
    };

    if (isVoiceActive) {
      try {
        recognition.start();
      } catch {
        // already started
      }
    } else {
      try {
        recognition.stop();
      } catch {
        // already stopped
      }
    }

    return () => {
      if (silenceTimer) clearTimeout(silenceTimer);
      try {
        recognition.stop();
      } catch {
        // clean up
      }
    };
  }, [isVoiceActive, isAutoProcessVoice]);

  const startVoiceListening = useCallback(() => {
    setVoiceTranscript('');
    voiceTranscriptRef.current = '';
    setIsVoiceActive(true);
  }, []);

  const stopVoiceListening = useCallback(() => {
    setIsVoiceActive(false);
    const spoken = voiceTranscriptRef.current.trim();
    // Auto-process on stop if transcript exists
    if (isAutoProcessVoice && spoken.length > 2 && !isExecutingRef.current) {
      if (executeParallelBuildRef.current) {
        executeParallelBuildRef.current(spoken);
      }
    }
  }, [isAutoProcessVoice]);

  const toggleVoiceListening = useCallback(() => {
    if (isVoiceActive) {
      stopVoiceListening();
    } else {
      startVoiceListening();
    }
  }, [isVoiceActive, startVoiceListening, stopVoiceListening]);

  // Global hotkey: Alt+V or Ctrl+Space to toggle voice
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.altKey && e.code === 'KeyV') || (e.ctrlKey && e.code === 'Space')) {
        e.preventDefault();
        toggleVoiceListening();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleVoiceListening]);

  // Execute Parallel Generation on Python Backend & Write to PC Disk
  const executeParallelBuild = useCallback(
    async (prompt: string, pathOverride?: string): Promise<boolean> => {
      if (!prompt.trim()) return false;
      const effectivePath = pathOverride || targetPath;

      setIsExecuting(true);

      // Voice Audio confirmation
      speakText(`Directive received. Michael and Dave are initializing parallel build for ${prompt} on your PC.`);

      setProject({
        projectName: prompt.slice(0, 32),
        projectGoal: prompt,
        status: 'generating',
        progress: 25,
        targetPath: effectivePath,
        totalFiles: 0,
        startedAt: new Date().toLocaleTimeString()
      });

      // Optimistically update people status to coding
      setPeople((prev) =>
        prev.map((p) => {
          if (p.id === 'michael') {
            return {
              ...p,
              status: 'coding',
              statusText: `Michael: Synthesizing UI components & styles for '${prompt.slice(0, 24)}...'`
            };
          }
          if (p.id === 'dave') {
            return {
              ...p,
              status: 'coding',
              statusText: `Dave: Architecting Python Flask REST routes & schema for '${prompt.slice(0, 24)}...'`
            };
          }
          return p;
        })
      );

      setStreams({
        michael: `[Michael - Frontend // Free Open-Source Engine] Parsing UX requirements for "${prompt}"...\n> Designing modern responsive layout with Tailwind CSS.\n> Building interactive state engine & local storage fallback.\n> Synthesizing index.html, styles.css, app.js...`,
        dave: `[Dave - Backend // Free Open-Source Engine] Analyzing backend specifications for "${prompt}"...\n> Configuring Python Flask REST API with CORS headers.\n> Writing CRUD endpoints (GET /api/items, POST /api/items, DELETE /api/items/<id>).\n> Preparing requirements.txt and README.md...`
      });

      try {
        // Call Python Flask Backend directly
        const res = await fetch(`${API_URL}/project/build`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            prompt,
            targetPath: effectivePath,
            apiKeys: aiKeys
          })
        });

        if (!res.ok) {
          throw new Error(`Backend response status ${res.status}`);
        }

        const data = await res.json();

        if (data.success) {
          setWrittenFiles(data.files || []);
          if (data.files && data.files.length > 0) {
            setSelectedFile(data.files[0]);
          }

          setProject({
            projectName: prompt.slice(0, 32),
            projectGoal: prompt,
            status: 'completed',
            progress: 100,
            targetPath: data.targetPath || effectivePath,
            totalFiles: data.totalFiles || data.files.length,
            startedAt: new Date().toLocaleTimeString()
          });

          setStreams({
            michael: `[Michael - Frontend] Complete!\nâœ” Created index.html (Responsive Tailwind UI)\nâœ” Created styles.css (Animations & Glassmorphism)\nâœ” Created app.js (Dynamic search, filter, local storage)\nâœ” All files saved to: ${data.targetPath}`,
            dave: `[Dave - Backend] Complete!\nâœ” Created backend/app.py (Flask REST API)\nâœ” Created backend/requirements.txt\nâœ” Created README.md (Quick start guide)\nâœ” Server ready on port 5001.`
          });

          // Refresh people stats & project history
          refreshFromBackend();
          refreshHistory();

          // Audio Speech reply on completion!
          speakText(`Build complete! ${data.totalFiles || 6} files successfully created and saved directly to your desktop. You can now preview the UI or open the folder.`);

          // Celebrate with confetti
          try {
            confetti({
              particleCount: 80,
              spread: 70,
              origin: { y: 0.6 }
            });
          } catch {
            // ignore confetti error
          }

          setIsExecuting(false);
          return true;
        } else {
          throw new Error(data.error || 'Parallel generation failed');
        }
      } catch (err: unknown) {
        console.error('Parallel build error:', err);
        speakText('An error occurred during parallel generation. Please check the logs.');
        setProject((prev) => ({
          ...prev,
          status: 'error',
          progress: 0
        }));
        setIsExecuting(false);
        return false;
      }
    },
    [targetPath, aiKeys, refreshFromBackend, refreshHistory, speakText]
  );

  // Keep executeParallelBuildRef continuously synced
  executeParallelBuildRef.current = executeParallelBuild;
  useEffect(() => {
    executeParallelBuildRef.current = executeParallelBuild;
  }, [executeParallelBuild]);

  // Open folder on Windows PC via Python Backend
  const openFolderInExplorer = useCallback(
    async (path?: string): Promise<boolean> => {
      const folderToOpen = path || targetPath;
      try {
        const res = await fetch(`${API_URL}/project/open-folder`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ targetPath: folderToOpen })
        });
        const data = await res.json();
        if (data.success) {
          speakText('Opening project folder in Windows Explorer.');
        }
        return !!data.success;
      } catch {
        return false;
      }
    },
    [targetPath, speakText]
  );

  // Add person to MongoDB and state
  const addPerson = useCallback(
    async (newPersonData: Omit<Person, 'stats' | 'status' | 'statusText'>) => {
      const newPerson: Person = {
        ...newPersonData,
        status: 'idle',
        statusText: `Orbital Station online. Standing by for ${newPersonData.role} tasks.`,
        stats: { tasksDone: 0, filesCreated: 0, reviewsDone: 0 }
      };

      setPeople((prev) => [...prev, newPerson]);
      speakText(`${newPerson.name} has joined the office as ${newPerson.role}.`);

      try {
        await fetch(`${API_URL}/agents`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newPerson)
        });
      } catch {
        // local state fallback
      }
    },
    [speakText]
  );

  // Update Person's assigned AI model
  const updatePersonModel = useCallback(async (personId: string, model: string) => {
    setPeople((prev) =>
      prev.map((p) => (p.id === personId ? { ...p, model } : p))
    );

    try {
      await fetch(`${API_URL}/agents/${personId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model })
      });
    } catch {
      // local state fallback
    }
  }, []);

  // Hydrate chat sessions from localStorage (client-only, deferred from prerender)
  useEffect(() => {
    try {
      const saved = localStorage.getItem('devsquad_chat_sessions');
      if (saved) {
        const sessions: ChatSession[] = JSON.parse(saved);
        if (sessions.length > 0) {
          setChatSessions(sessions);
          setCurrentSessionId(sessions[0].id);
          return;
        }
      }
    } catch {/* */}
    // No saved sessions — create a fresh one
    const fresh = makeSession();
    setChatSessions([fresh]);
    setCurrentSessionId(fresh.id);
  }, []);

  // Persist chat sessions to localStorage (skip initial empty state)
  useEffect(() => {
    if (chatSessions.length === 0) return;
    try {
      localStorage.setItem('devsquad_chat_sessions', JSON.stringify(chatSessions));
    } catch {/* */}
  }, [chatSessions]);

  const startNewChat = useCallback(() => {
    const s = makeSession();
    setChatSessions((prev) => [s, ...prev]);
    setCurrentSessionId(s.id);
  }, []);

  const switchSession = useCallback((id: string) => {
    setCurrentSessionId(id);
  }, []);

  const deleteChatSession = useCallback((id: string) => {
    setChatSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      if (next.length === 0) {
        const fresh = makeSession();
        setCurrentSessionId(fresh.id);
        return [fresh];
      }
      setCurrentSessionId((cur) => (cur === id ? next[0].id : cur));
      return next;
    });
  }, []);

  const addChatMessage = useCallback((sessionId: string, msg: ChatMessage) => {
    setChatSessions((prev) =>
      prev.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              title: s.messages.length === 0 && msg.role === 'user'
                ? msg.content.slice(0, 38) + (msg.content.length > 38 ? '…' : '')
                : s.title,
              messages: [...s.messages, msg],
            }
          : s
      )
    );
  }, []);

  const sendChatMessage = useCallback(
    async (text: string) => {
      const sessionId = currentSessionId;
      const isRexCommand = /^hey\s+rex\b/i.test(text.trim());

      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: new Date().toISOString(),
        type: 'text',
      };
      addChatMessage(sessionId, userMsg);

      if (isRexCommand) {
        const rexPrompt = text.replace(/^hey\s+rex[,\s]*/i, '').trim();
        const thinkingMsg: ChatMessage = {
          id: `msg-${Date.now()}-t`,
          role: 'agent',
          agentId: 'rex',
          agentName: 'Rex',
          agentAvatar: '🖥️',
          content: 'Planning PC action...',
          timestamp: new Date().toISOString(),
          type: 'thinking',
        };
        addChatMessage(sessionId, thinkingMsg);

        try {
          const res = await fetch('/api/py/rex/plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task: rexPrompt, prompt: rexPrompt, apiKeys: aiKeys }),
          });
          const data = await res.json();
          const rexReply: ChatMessage = {
            id: `msg-${Date.now()}-r`,
            role: 'agent',
            agentId: 'rex',
            agentName: 'Rex',
            agentAvatar: '🖥️',
            content: data.success
              ? (data.explanation || data.reply || JSON.stringify(data.plan, null, 2))
              : `Error: ${data.error || 'Rex could not process that'}`,
            timestamp: new Date().toISOString(),
            type: data.success ? 'rex_plan' : 'error',
            rexPlan: data.plan,
          };
          setChatSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId
                ? { ...s, messages: s.messages.filter((m) => m.id !== thinkingMsg.id).concat(rexReply) }
                : s
            )
          );
          if (data.success && data.explanation) {
            setIsAgentSpeaking(true);
            speakText(data.explanation);
            setTimeout(() => setIsAgentSpeaking(false), 3000);
          }
        } catch (err) {
          const errMsg: ChatMessage = {
            id: `msg-${Date.now()}-e`,
            role: 'agent',
            agentId: 'rex',
            agentName: 'Rex',
            agentAvatar: '🖥️',
            content: `Rex offline: ${err instanceof Error ? err.message : 'Unknown error'}`,
            timestamp: new Date().toISOString(),
            type: 'error',
          };
          setChatSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId
                ? { ...s, messages: s.messages.filter((m) => m.id !== thinkingMsg.id).concat(errMsg) }
                : s
            )
          );
        }
      } else {
        // General chat
        const thinkingMsg: ChatMessage = {
          id: `msg-${Date.now()}-t`,
          role: 'agent',
          agentId: 'squad',
          agentName: 'DevSquad AI',
          agentAvatar: '🤖',
          content: 'Thinking...',
          timestamp: new Date().toISOString(),
          type: 'thinking',
        };
        addChatMessage(sessionId, thinkingMsg);

        try {
          const res = await fetch('/api/py/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, sessionId, apiKeys: aiKeys }),
          });
          const data = await res.json();
          const reply: ChatMessage = {
            id: `msg-${Date.now()}-r`,
            role: 'agent',
            agentId: data.agentId || 'squad',
            agentName: data.agentName || 'DevSquad AI',
            agentAvatar: '🤖',
            content: data.success ? data.reply : `Error: ${data.error || 'No response'}`,
            timestamp: new Date().toISOString(),
            type: data.success ? 'text' : 'error',
          };
          setChatSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId
                ? { ...s, messages: s.messages.filter((m) => m.id !== thinkingMsg.id).concat(reply) }
                : s
            )
          );
          if (data.success && data.reply) {
            setIsAgentSpeaking(true);
            speakText(data.reply.slice(0, 200));
            setTimeout(() => setIsAgentSpeaking(false), 4000);
          }
        } catch (err) {
          const errMsg: ChatMessage = {
            id: `msg-${Date.now()}-e`,
            role: 'agent',
            agentId: 'squad',
            agentName: 'DevSquad AI',
            agentAvatar: '🤖',
            content: `Error: ${err instanceof Error ? err.message : 'Unknown error'}`,
            timestamp: new Date().toISOString(),
            type: 'error',
          };
          setChatSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId
                ? { ...s, messages: s.messages.filter((m) => m.id !== thinkingMsg.id).concat(errMsg) }
                : s
            )
          );
        }
      }
    },
    [currentSessionId, aiKeys, addChatMessage, speakText]
  );

  return (
    <OfficeContext.Provider
      value={{
        people,
        aiKeys,
        updateAIKeys,
        targetPath,
        setTargetPath: updateTargetPath,
        project,
        streams,
        writtenFiles,
        selectedFile,
        setSelectedFile,
        isExecuting,
        isVoiceActive,
        voiceTranscript,
        startVoiceListening,
        stopVoiceListening,
        toggleVoiceListening,
        isAudioReplyEnabled,
        toggleAudioReply,
        isAutoProcessVoice,
        toggleAutoProcessVoice,
        speakText,
        executeParallelBuild,
        openFolderInExplorer,
        addPerson,
        updatePersonModel,
        isAISettingsOpen,
        setIsAISettingsOpen,
        isAddPersonOpen,
        setIsAddPersonOpen,
        isHistoryOpen,
        setIsHistoryOpen,
        history,
        refreshHistory,
        loadProjectFromHistory,
        deleteHistoryItem,
        clearAllHistory,
        refreshFromBackend,
        chatSessions,
        currentSessionId,
        startNewChat,
        switchSession,
        deleteChatSession,
        sendChatMessage,
        isAgentSpeaking,
      }}
    >
      {children}
    </OfficeContext.Provider>
  );
}

export function useOffice() {
  const context = useContext(OfficeContext);
  if (!context) {
    throw new Error('useOffice must be used within an OfficeProvider');
  }
  return context;
}
