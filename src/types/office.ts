export type AgentStatus = 'idle' | 'coding' | 'reviewing' | 'syncing' | 'completed' | 'error';

export interface Person {
  id: string;
  name: string;
  role: string;
  department: string;
  avatar: string;
  color: string;
  status: AgentStatus;
  statusText: string;
  model: string;
  systemPrompt: string;
  skills: string[];
  stats: {
    tasksDone: number;
    filesCreated: number;
    reviewsDone: number;
  };
  desk?: {
    room: string;
    col: number;
    row: number;
  };
}

export interface AIKeys {
  gemini: string;
  claude: string;
  openai: string;
  ollamaUrl: string;
}

export interface GeneratedFile {
  name: string;
  path: string;
  fullPath?: string;
  size: number;
  language: string;
  author: string;
  content: string;
}

export interface ProjectState {
  projectName: string;
  projectGoal: string;
  status: 'idle' | 'delegating' | 'generating' | 'writing_disk' | 'completed' | 'error';
  progress: number;
  targetPath: string;
  totalFiles: number;
  startedAt?: string;
}

export type ParallelStreams = Record<string, string>;

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent' | 'system';
  agentId?: string;
  agentName?: string;
  agentAvatar?: string;
  content: string;
  timestamp: string;
  type: 'text' | 'build_result' | 'rex_plan' | 'error' | 'thinking';
  files?: GeneratedFile[];
  rexPlan?: {
    tasks: Array<{ tool: string; args: Record<string, unknown>; risk: string; description: string }>;
    requires_confirmation: boolean;
    pending_permissions: string[];
  };
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
}

export interface ProjectHistoryItem {
  id: string;
  prompt: string;
  targetPath: string;
  timestamp: string;
  totalFiles: number;
  files: GeneratedFile[];
  streams: {
    michael: string;
    dave: string;
  };
  modelsUsed?: {
    michael?: string;
    dave?: string;
  };
  createdAt?: string;
}
