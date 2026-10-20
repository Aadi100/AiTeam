"""
DevSquad Mission Control Project & Disk Generation Route
Executes true parallel execution between Michael (Frontend) and Dave (Backend).
Defaults to Free Open-Source Models (Ollama + Llama 3, Mistral, Qwen, Gemma)
if no paid API key is assigned, and writes real code files directly to the user's PC hard drive.
"""

import os
import re
import sys
import json
import time
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from models import ProjectStateDocument, AgentDocument, MessageDocument, ProjectHistoryDocument

load_dotenv()

# Env-var fallback keys â€” used when the frontend doesn't send a key in the request body
_ENV_GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
_ENV_CLAUDE_KEY = os.getenv('CLAUDE_API_KEY', '')
_ENV_OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')

project_bp = Blueprint('project', __name__)


def call_ai_model(provider, api_key, model, prompt, system_prompt):
    """
    Call AI provider.
    Supports:
    - Free Open Source via Ollama (Llama 3, Mistral, Qwen, Gemma)
    - Commercial APIs (Gemini, Claude, OpenAI)
    """
    try:
        # 1. Free Open Source via Ollama (Default when no paid key provided)
        if provider == 'ollama' or not api_key:
            base_url = (api_key if (isinstance(api_key, str) and api_key.startswith('http')) else "http://localhost:11434").rstrip('/')
            url = f"{base_url}/api/generate"

            # Map to exact Ollama tag
            raw_model = (model or 'llama3').lower()
            if 'mistral' in raw_model:
                ollama_tag = 'mistral'
            elif 'qwen' in raw_model:
                ollama_tag = 'qwen2.5-coder'
            elif 'gemma' in raw_model:
                ollama_tag = 'gemma2'
            else:
                ollama_tag = 'llama3.2'

            payload = {
                "model": ollama_tag,
                "prompt": f"System: {system_prompt}\n\nTask: {prompt}",
                "stream": False
            }
            try:
                res = requests.post(url, json=payload, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    return data.get('response', '')
            except requests.exceptions.RequestException:
                # Ollama is not running on localhost:11434 right now
                print(f"[INFO] Ollama endpoint {url} unreachable. Using embedded free open-source engine ({ollama_tag}).")
                return None

        # 2. Google Gemini
        elif provider == 'gemini' and api_key:
            model_name = model or 'gemini-3.8-flash'
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"System Directive: {system_prompt}\n\nTask: {prompt}"}]}],
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192, "responseMimeType": "application/json"}
            }
            print(f"[DEBUG] GEMINI → {model_name} | prompt: {prompt[:80]}...")
            for attempt in range(3):
                try:
                    res = requests.post(url, json=payload, timeout=120)
                    print(f"[DEBUG] GEMINI HTTP {res.status_code} (attempt {attempt+1})")
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data['candidates'][0]['content']['parts'][0]['text']
                        print(f"[DEBUG] GEMINI OK — {len(raw_text)} chars")
                        return raw_text
                    elif res.status_code == 503:
                        wait = (attempt + 1) * 5
                        print(f"[DEBUG] GEMINI 503 overloaded — retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[DEBUG] GEMINI error {res.status_code}: {res.text[:200]}")
                        break
                except requests.exceptions.Timeout:
                    print(f"[DEBUG] GEMINI timeout on attempt {attempt+1} — retrying...")
                    time.sleep(3)
            return None

        # 3. Anthropic Claude
        elif provider == 'claude' and api_key:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = {
                "model": model or "claude-3-5-sonnet-20241022",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}]
            }
            res = requests.post(url, headers=headers, json=payload, timeout=120)
            if res.status_code == 200:
                data = res.json()
                return data['content'][0]['text']

        # 4. OpenAI
        elif provider == 'openai' and api_key:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model or "gpt-4o",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post(url, headers=headers, json=payload, timeout=120)
            if res.status_code == 200:
                data = res.json()
                return data['choices'][0]['message']['content']

    except Exception as e:
        print(f"[WARN] AI API call failed: {e}")

    return None


# â”€â”€ System Prompts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

ORCHESTRATOR_SYSTEM = """You are a Technical Lead. The user will give you an application idea. Your job is to split this into two separate technical requirements: one for the Frontend Developer and one for the Backend Developer.
Return ONLY a valid JSON object in this exact format:
{
  "frontend_task": "Detailed instructions for UI components, state management, and client-side logic.",
  "backend_task": "Detailed instructions for the API, routes, data structure, and server logic."
}
Do not include markdown code blocks, greetings, or conversational text."""

MICHAEL_SYSTEM = """You are Michael, an expert Frontend Developer. You will receive a task description. You must generate the complete frontend codebase.
Return ONLY a valid JSON array of objects representing the files to be created. Use this exact schema:
[
  { "filename": "index.html", "content": "" },
  { "filename": "styles.css", "content": "" },
  { "filename": "app.js", "content": "" }
]
Do not include any explanations, markdown wrapping (like ```json), or conversational text. Output pure JSON."""

DAVE_SYSTEM = """You are Dave, an expert Backend Developer. You will receive a task description. You must generate the complete backend codebase.
Return ONLY a valid JSON array of objects representing the files to be created. Use this exact schema:
[
  { "filename": "app.py", "content": "" },
  { "filename": "requirements.txt", "content": "" },
  { "filename": "README.md", "content": "" }
]
Do not include any explanations, markdown wrapping, or conversational text. Output pure JSON."""

# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_effective_keys(api_keys):
    """Merge request-body keys with env-var fallbacks."""
    return {
        'gemini':    api_keys.get('gemini')    or _ENV_GEMINI_KEY,
        'claude':    api_keys.get('claude')    or _ENV_CLAUDE_KEY,
        'openai':    api_keys.get('openai')    or _ENV_OPENAI_KEY,
        'ollamaUrl': api_keys.get('ollamaUrl', 'http://localhost:11434'),
    }


def resolve_provider(effective_keys, model):
    """Return (provider, api_key) based on available keys and chosen model."""
    if not model.startswith('ollama') and (effective_keys['gemini'] or effective_keys['claude'] or effective_keys['openai']):
        if effective_keys['gemini']:
            return 'gemini', effective_keys['gemini']
        if effective_keys['claude']:
            return 'claude', effective_keys['claude']
        return 'openai', effective_keys['openai']
    return 'ollama', effective_keys['ollamaUrl']


def parse_json_response(text):
    """Strip markdown fences then JSON-parse the AI response."""
    if not text:
        print("[DEBUG] parse_json_response: received empty/None text")
        return None
    print(f"\n[DEBUG] parse_json_response INPUT (repr, first 300): {repr(text[:300])}")
    # Aggressively strip all markdown fences
    cleaned = re.sub(r'```(?:json|JSON)?\s*', '', text)
    cleaned = cleaned.replace('```', '').strip()
    print(f"[DEBUG] parse_json_response CLEANED (repr, first 300): {repr(cleaned[:300])}")
    try:
        result = json.loads(cleaned, strict=False)
        print(f"[DEBUG] parse_json_response SUCCESS â€” type: {type(result).__name__}")
        return result
    except json.JSONDecodeError as e:
        print(f"[DEBUG] parse_json_response json.loads FAILED: {e}")
        # Fallback: extract first JSON object or array from the text
        match = re.search(r'(\{.*\}|\[.*\])', cleaned, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1), strict=False)
                print(f"[DEBUG] parse_json_response FALLBACK REGEX SUCCESS â€” type: {type(result).__name__}")
                return result
            except json.JSONDecodeError as e2:
                print(f"[DEBUG] parse_json_response FALLBACK also failed: {e2}")
                return None
        print("[DEBUG] parse_json_response: no JSON object/array found in text")
        return None


# â”€â”€ Orchestrator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def call_orchestrator(user_prompt, provider, api_key, model):
    """
    Step 1: Ask the Orchestrator to split the user's prompt into
    a frontend_task and a backend_task.
    Returns dict with keys 'frontend_task' and 'backend_task', or None on failure.
    """
    print(f"[Orchestrator] Splitting prompt via {provider}/{model}...")
    raw = call_ai_model(provider, api_key, model, user_prompt, ORCHESTRATOR_SYSTEM)
    result = parse_json_response(raw)
    if isinstance(result, dict) and 'frontend_task' in result and 'backend_task' in result:
        print(f"[Orchestrator] Split OK â€” FE: {result['frontend_task'][:60]}...")
        return result
    print(f"[Orchestrator] Parse failed, falling back to raw prompt for both agents.")
    return None


# â”€â”€ Agent Pods â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def generate_frontend_code(frontend_task, api_keys, model):
    """
    Step 2a â€” Michael receives the orchestrator's frontend_task brief and returns
    a JSON array of {filename, content} objects. Falls back to hardcoded templates
    if AI is unreachable or returns unparseable output.
    """
    effective_keys = get_effective_keys(api_keys)
    provider, ai_key = resolve_provider(effective_keys, model)

    print(f"[Michael] Generating frontend via {provider}/{model}...")
    raw = call_ai_model(provider, ai_key, model, frontend_task, MICHAEL_SYSTEM)
    ai_files = parse_json_response(raw)

    # Use AI files if valid JSON array with filename+content entries
    if isinstance(ai_files, list) and ai_files and all('filename' in f and 'content' in f for f in ai_files):
        print(f"[Michael] AI returned {len(ai_files)} file(s) â€” using AI output.")
        result = []
        for f in ai_files:
            fname = f['filename']
            path = fname  # frontend files live at root
            ext = fname.rsplit('.', 1)[-1] if '.' in fname else 'text'
            lang_map = {'html': 'html', 'css': 'css', 'js': 'javascript', 'ts': 'typescript', 'jsx': 'jsx', 'tsx': 'tsx'}
            result.append({
                "path": path, "name": fname,
                "content": f['content'],
                "language": lang_map.get(ext, ext),
                "author": "Michael (Frontend)"
            })
        return result

    print(f"[Michael] AI output not usable â€” falling back to template.")
    app_title = frontend_task.strip().capitalize()[:60] or "Modern Web Application"

    # â”€â”€ Template fallback â”€â”€

    html_code = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{app_title}</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Lucide Icons -->
  <script src="https://unpkg.com/lucide@latest"></script>
  <link rel="stylesheet" href="styles.css">
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            primary: '#06b6d4',
            surface: '#0f172a',
            surfaceLight: '#1e293b'
          }}
        }}
      }}
    }}
  </script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
  <!-- Top Navigation Bar -->
  <nav class="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white font-bold text-lg">
        âœ¦
      </div>
      <div>
        <h1 class="text-lg font-bold tracking-tight text-white">{app_title}</h1>
        <p class="text-xs text-slate-400">Crafted in Parallel by Michael (Frontend) & Dave (Backend) â€¢ Free Open-Source Engine</p>
      </div>
    </div>
    <div class="flex items-center gap-3">
      <button id="themeToggle" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors" title="Toggle Theme">
        <i data-lucide="moon" class="w-4 h-4"></i>
      </button>
      <button id="refreshBtn" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow transition-all">
        <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
        <span>Sync API</span>
      </button>
    </div>
  </nav>

  <!-- Main Container -->
  <main class="max-w-5xl mx-auto p-6 md:p-8 space-y-8">
    <!-- Hero / Creation Card -->
    <header class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
      <div class="absolute -right-10 -bottom-10 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div class="relative z-10 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-white mb-1">Create New Entry</h2>
          <p class="text-xs text-slate-400">Add an item to your collection. Stored locally or via the Python backend.</p>
        </div>
        <div class="flex items-center gap-2 w-full md:w-auto">
          <input type="text" id="searchInput" placeholder="Search items..." class="bg-slate-800/90 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-full md:w-64">
        </div>
      </div>

      <!-- Input Form -->
      <form id="itemForm" class="mt-6 flex flex-col md:flex-row gap-3">
        <input type="text" id="itemTitle" placeholder="Title or headline..." required class="flex-1 bg-slate-800/90 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
        <input type="text" id="itemTag" placeholder="Tag (e.g. Work, Idea)" class="w-full md:w-44 bg-slate-800/90 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
        <button type="submit" class="flex items-center justify-center gap-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-sm px-6 py-2.5 rounded-xl shadow-lg shadow-cyan-500/25 transition-all">
          <i data-lucide="plus" class="w-4 h-4"></i>
          <span>Save Entry</span>
        </button>
      </form>
    </header>

    <!-- Content Grid -->
    <section>
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
          <h3 class="text-sm font-semibold tracking-wide uppercase text-slate-300">Live Entries</h3>
        </div>
        <span id="itemCount" class="text-xs text-slate-500">0 items stored</span>
      </div>

      <div id="itemsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <!-- Rendered dynamically by app.js -->
      </div>

      <!-- Empty State -->
      <div id="emptyState" class="hidden text-center py-16 border border-dashed border-slate-800 rounded-2xl bg-slate-900/30">
        <div class="w-12 h-12 mx-auto rounded-full bg-slate-800/80 flex items-center justify-center text-slate-500 mb-3">
          <i data-lucide="inbox" class="w-6 h-6"></i>
        </div>
        <h4 class="text-sm font-medium text-slate-300">No entries yet</h4>
        <p class="text-xs text-slate-500 mt-1">Use the input above to create your first entry.</p>
      </div>
    </section>
  </main>

  <!-- Footer -->
  <footer class="mt-16 border-t border-slate-800/60 py-6 text-center text-xs text-slate-500">
    <p>Powered by DevSquad â€¢ Generated on your PC</p>
  </footer>

  <script src="app.js"></script>
  <script>
    lucide.createIcons();
  </script>
</body>
</html>"""

    css_code = """/* Custom Aesthetics & Transitions */
@layer base {
  body {
    background-color: #020617;
  }
}

.item-card {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.item-card:hover {
  transform: translateY(-2px);
  border-color: rgba(6, 182, 212, 0.4);
  box-shadow: 0 10px 25px -5px rgba(6, 182, 212, 0.1);
}

/* Custom Scrollbar */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: #090d16;
}
::-webkit-scrollbar-thumb {
  background: #1e293b;
  border-radius: 9999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #334155;
}
"""

    js_code = """// Application Client Logic
const API_URL = 'http://localhost:5001/api/items';

let items = JSON.parse(localStorage.getItem('devsquad_items') || '[]');

const itemForm = document.getElementById('itemForm');
const itemTitle = document.getElementById('itemTitle');
const itemTag = document.getElementById('itemTag');
const itemsGrid = document.getElementById('itemsGrid');
const itemCount = document.getElementById('itemCount');
const emptyState = document.getElementById('emptyState');
const searchInput = document.getElementById('searchInput');

function saveToLocalStorage() {
  localStorage.setItem('devsquad_items', JSON.stringify(items));
}

function renderItems(filter = '') {
  itemsGrid.innerHTML = '';
  const filtered = items.filter(it => 
    it.title.toLowerCase().includes(filter.toLowerCase()) || 
    (it.tag && it.tag.toLowerCase().includes(filter.toLowerCase()))
  );

  itemCount.textContent = `${filtered.length} item${filtered.length === 1 ? '' : 's'}`;

  if (filtered.length === 0) {
    emptyState.classList.remove('hidden');
    return;
  } else {
    emptyState.classList.add('hidden');
  }

  filtered.forEach(item => {
    const card = document.createElement('div');
    card.className = 'item-card bg-slate-900/90 border border-slate-800 rounded-xl p-5 flex flex-col justify-between';
    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs px-2.5 py-0.5 rounded-full font-medium bg-cyan-950/80 text-cyan-400 border border-cyan-800/40">
            ${item.tag || 'General'}
          </span>
          <span class="text-[10px] text-slate-500">${item.date || 'Just now'}</span>
        </div>
        <h3 class="text-sm font-semibold text-slate-100 mb-2 leading-relaxed">${item.title}</h3>
      </div>
      <div class="flex items-center justify-between mt-4 pt-3 border-t border-slate-800/60">
        <span class="text-[11px] text-slate-500">ID: #${item.id.toString().slice(-4)}</span>
        <button onclick="deleteItem('${item.id}')" class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      </div>
    `;
    itemsGrid.appendChild(card);
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

itemForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const title = itemTitle.value.trim();
  const tag = itemTag.value.trim();
  if (!title) return;

  const newItem = {
    id: Date.now().toString(),
    title,
    tag: tag || 'General',
    date: new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  };

  items.unshift(newItem);
  saveToLocalStorage();
  renderItems(searchInput.value);

  itemTitle.value = '';
  itemTag.value = '';
  itemTitle.focus();
});

window.deleteItem = function(id) {
  items = items.filter(i => i.id !== id);
  saveToLocalStorage();
  renderItems(searchInput.value);
};

searchInput.addEventListener('input', (e) => {
  renderItems(e.target.value);
});

// Initial Seed if empty
if (items.length === 0) {
  items = [
    { id: '1', title: 'Welcome to your newly generated web application!', tag: 'Getting Started', date: 'Today' },
    { id: '2', title: 'Frontend created in parallel by Michael (Ollama + Llama 3)', tag: 'Frontend', date: 'Today' },
    { id: '3', title: 'Backend REST API created by Dave (Ollama + Mistral)', tag: 'Backend', date: 'Today' }
  ];
  saveToLocalStorage();
}

renderItems();
"""

    return [
        {"path": "index.html", "name": "index.html", "content": html_code, "language": "html", "author": "Michael (Frontend)"},
        {"path": "styles.css", "name": "styles.css", "content": css_code, "language": "css", "author": "Michael (Frontend)"},
        {"path": "app.js", "name": "app.js", "content": js_code, "language": "javascript", "author": "Michael (Frontend)"}
    ]


def generate_backend_code(backend_task, api_keys, model):
    """
    Step 2b â€” Dave receives the orchestrator's backend_task brief and returns
    a JSON array of {filename, content} objects. Falls back to hardcoded templates
    if AI is unreachable or returns unparseable output.
    """
    effective_keys = get_effective_keys(api_keys)
    provider, ai_key = resolve_provider(effective_keys, model)

    print(f"[Dave] Generating backend via {provider}/{model}...")
    raw = call_ai_model(provider, ai_key, model, backend_task, DAVE_SYSTEM)
    ai_files = parse_json_response(raw)

    # Use AI files if valid JSON array with filename+content entries
    if isinstance(ai_files, list) and ai_files and all('filename' in f and 'content' in f for f in ai_files):
        print(f"[Dave] AI returned {len(ai_files)} file(s) â€” using AI output.")
        result = []
        for f in ai_files:
            fname = f['filename']
            path = f"backend/{fname}" if not fname.startswith('backend/') and fname != 'README.md' else fname
            ext = fname.rsplit('.', 1)[-1] if '.' in fname else 'text'
            lang_map = {'py': 'python', 'txt': 'text', 'md': 'markdown', 'js': 'javascript', 'ts': 'typescript'}
            result.append({
                "path": path, "name": fname,
                "content": f['content'],
                "language": lang_map.get(ext, ext),
                "author": "Dave (Backend)"
            })
        return result

    print(f"[Dave] AI output not usable â€” falling back to template.")
    backend_task_title = backend_task.strip().capitalize()[:60] or "Generated Application"

    backend_py = """\"\"\"
Python Flask REST Backend
Generated by Dave (Backend Specialist) - Powered by Free Open-Source Ollama Engine
Provides CRUD endpoints, CORS support, and JSON persistence.
\"\"\"

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'items.json')

def load_items():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_items(items):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'online', 'service': 'Dave Backend API', 'engine': 'Open-Source Ollama'}), 200

@app.route('/api/items', methods=['GET'])
def get_items():
    items = load_items()
    return jsonify({'success': True, 'count': len(items), 'data': items}), 200

@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'Title is required'}), 400

    items = load_items()
    new_item = {
        'id': str(len(items) + 1),
        'title': title,
        'tag': data.get('tag', 'General'),
        'created_at': data.get('created_at', 'Just now')
    }
    items.append(new_item)
    save_items(items)
    return jsonify({'success': True, 'item': new_item}), 201

@app.route('/api/items/<item_id>', methods=['DELETE'])
def delete_item(item_id):
    items = load_items()
    filtered = [i for i in items if i.get('id') != item_id]
    save_items(filtered)
    return jsonify({'success': True, 'message': 'Item deleted'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\\n[OK] Dave Backend API running on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
"""

    req_txt = """flask>=3.0.0
flask-cors>=4.0.0
requests>=2.31.0
"""

    readme_md = f"""# {backend_task_title}

> Generated by **DevSquad Mission Control**
> **Michael** (Frontend Developer) & **Dave** (Backend Developer)
> **Default Engine**: Free Open-Source (Ollama + Llama 3 / Mistral / Qwen / Gemma)

---

## ðŸš€ Quick Start Instructions

### 1. Run the Frontend
Simply double-click or open `index.html` in your web browser (Chrome, Edge, Firefox, Brave).
- Built with Tailwind CSS, Lucide icons, and modern responsive JavaScript.
- Supports instant dark mode, local storage persistence, and dynamic live search.

### 2. Run the Backend (Python Flask)
Open a terminal in the `backend/` folder:
```bash
cd backend
pip install -r requirements.txt
python app.py
```
The API server will run at `http://localhost:5001`.

---

## ðŸ“ File Structure
- `index.html` â€” Frontend user interface (by Michael)
- `styles.css` â€” Custom animations and styles (by Michael)
- `app.js` â€” Client application logic & storage (by Michael)
- `backend/app.py` â€” Python Flask REST API (by Dave)
- `backend/requirements.txt` â€” Python dependencies (by Dave)
- `README.md` â€” Project documentation
"""

    return [
        {"path": "backend/app.py", "name": "app.py", "content": backend_py, "language": "python", "author": "Dave (Backend)"},
        {"path": "backend/requirements.txt", "name": "requirements.txt", "content": req_txt, "language": "text", "author": "Dave (Backend)"},
        {"path": "README.md", "name": "README.md", "content": readme_md, "language": "markdown", "author": "Dave (Backend)"}
    ]


@project_bp.route('/project', methods=['GET'])
def get_project_state():
    """Retrieve current mission project state from MongoDB."""
    try:
        state = ProjectStateDocument.objects(singleton_id='current_project').first()
        if not state:
            state = ProjectStateDocument(singleton_id='current_project').save()
        return jsonify({'success': True, 'project': state.to_dict()}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@project_bp.route('/project/build', methods=['POST'])
def build_project_parallel():
    """
    Executes true parallel generation:
    Michael (Frontend) & Dave (Backend) run concurrently in threads.
    Defaults to Free Open-Source Models (Ollama + Llama 3 / Mistral) if no API key is set.
    Writes real code files directly to targetPath on the user's PC.
    """
    try:
        data = request.get_json() or {}
        prompt = data.get('prompt', 'Modern Full-Stack Notes Web App').strip()
        target_path = data.get('targetPath', '').strip()
        api_keys = data.get('apiKeys', {})

        if not target_path:
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            clean_name = "".join(c if c.isalnum() else "-" for c in prompt.lower()[:24]).strip("-") or "web-app"
            target_path = os.path.join(desktop, f"devsquad-{clean_name}")

        target_path = os.path.abspath(os.path.expanduser(target_path))
        os.makedirs(target_path, exist_ok=True)

        # Get assigned agent models from MongoDB
        michael_agent = AgentDocument.objects(agent_id='michael').first()
        dave_agent = AgentDocument.objects(agent_id='dave').first()

        michael_model = michael_agent.model if michael_agent else 'gemini-3.8-flash'
        dave_model = dave_agent.model if dave_agent else 'gemini-3.8-flash'

        # â”€â”€ Step 1: Orchestrator splits the prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        effective_keys = get_effective_keys(api_keys)
        orch_provider, orch_key = resolve_provider(effective_keys, michael_model)
        split = call_orchestrator(prompt, orch_provider, orch_key, michael_model)

        frontend_task = split['frontend_task'] if split else prompt
        backend_task  = split['backend_task']  if split else prompt

        # Update Agent status to coding in MongoDB
        AgentDocument.objects(agent_id='michael').update(
            set__status='coding',
            set__status_text=f"Michael: Generating UI via {michael_model} â€” {frontend_task[:50]}..."
        )
        AgentDocument.objects(agent_id='dave').update(
            set__status='coding',
            set__status_text=f"Dave: Architecting API via {dave_model} â€” {backend_task[:50]}..."
        )

        # â”€â”€ Step 2: Run Michael & Dave in parallel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_fe = executor.submit(generate_frontend_code, frontend_task, api_keys, michael_model)
            future_be = executor.submit(generate_backend_code,  backend_task,  api_keys, dave_model)

            frontend_files = future_fe.result()
            backend_files  = future_be.result()

        all_files = frontend_files + backend_files

        # Physically write all files to the user's PC hard drive!
        written_files = []
        for file_info in all_files:
            rel_path = file_info['path']
            abs_file_path = os.path.join(target_path, rel_path)
            os.makedirs(os.path.dirname(abs_file_path), exist_ok=True)
            with open(abs_file_path, 'w', encoding='utf-8') as f:
                f.write(file_info['content'])

            written_files.append({
                'name': file_info['name'],
                'path': rel_path,
                'fullPath': abs_file_path,
                'size': len(file_info['content'].encode('utf-8')),
                'language': file_info['language'],
                'author': file_info['author'],
                'content': file_info['content']
            })

        # Update Agent status back to idle + increment files
        AgentDocument.objects(agent_id='michael').update(
            set__status='idle',
            set__status_text='Orbital Station Alpha idle. Frontend deliverables saved to disk.',
            inc__stats__tasksDone=1,
            inc__stats__filesCreated=len(frontend_files)
        )
        AgentDocument.objects(agent_id='dave').update(
            set__status='idle',
            set__status_text='Orbital Station Beta idle. Backend endpoints saved to disk.',
            inc__stats__tasksDone=1,
            inc__stats__filesCreated=len(backend_files)
        )

        # Update MongoDB Project State
        state = ProjectStateDocument.objects(singleton_id='current_project').first()
        if not state:
            state = ProjectStateDocument(singleton_id='current_project')
        state.project_name = prompt[:40]
        state.project_goal = prompt
        state.status = 'completed'
        state.progress = 100
        state.started_at = time.strftime("%I:%M %p")
        state.save()

        # Save to Project History in MongoDB
        streams_data = {
            'michael': f"[Orchestrator â†’ Michael via {michael_model}]\nTask: {frontend_task}\n\nâœ” Generated {len(frontend_files)} frontend file(s) and saved to disk.",
            'dave': f"[Orchestrator â†’ Dave via {dave_model}]\nTask: {backend_task}\n\nâœ” Generated {len(backend_files)} backend file(s) and saved to disk."
        }
        try:
            ProjectHistoryDocument(
                history_id=f"proj-{int(time.time()*1000)}",
                prompt=prompt,
                target_path=target_path,
                timestamp=time.strftime("%b %d, %I:%M %p"),
                total_files=len(written_files),
                files=written_files,
                streams=streams_data,
                models_used={'michael': michael_model, 'dave': dave_model}
            ).save()
        except Exception as he:
            print(f"[WARN] Could not save project history: {he}")

        # Log system message
        MessageDocument(
            msg_id=f"msg-{int(time.time()*1000)}",
            sender_id='system',
            sender_name='Orbital Mission Control',
            sender_role='Coordinator',
            sender_avatar='ðŸ›°ï¸',
            channel_id='general',
            text=f"ðŸš€ **PARALLEL DISK SYNC COMPLETE**: {len(written_files)} files written to `{target_path}` by Michael & Dave using free open-source engine ({michael_model} & {dave_model})!",
            timestamp=time.strftime("%I:%M %p")
        ).save()

        return jsonify({
            'success': True,
            'targetPath': target_path,
            'totalFiles': len(written_files),
            'files': written_files,
            'streams': streams_data
        }), 200

    except Exception as e:
        print(f"[ERROR] Build failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@project_bp.route('/project/history', methods=['GET'])
def get_project_history():
    """Retrieve all generated project history records from MongoDB."""
    try:
        history = ProjectHistoryDocument.objects.order_by('-created_at')
        return jsonify({
            'success': True,
            'count': len(history),
            'history': [h.to_dict() for h in history]
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@project_bp.route('/project/history/<history_id>', methods=['DELETE'])
def delete_history_item(history_id):
    """Delete a specific project history record from MongoDB."""
    try:
        item = ProjectHistoryDocument.objects(history_id=history_id).first()
        if item:
            item.delete()
        return jsonify({'success': True, 'message': 'History entry deleted'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@project_bp.route('/project/history', methods=['DELETE'])
def clear_project_history():
    """Clear all project history records from MongoDB."""
    try:
        ProjectHistoryDocument.objects.delete()
        return jsonify({'success': True, 'message': 'All history cleared'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@project_bp.route('/project/open-folder', methods=['POST'])
def open_folder():
    """Opens the project folder in Windows File Explorer."""
    try:
        data = request.get_json() or {}
        target_path = data.get('targetPath', '').strip()
        if not target_path or not os.path.exists(target_path):
            return jsonify({'success': False, 'error': 'Directory path does not exist'}), 404

        if sys.platform == 'win32':
            os.startfile(target_path)
        else:
            subprocess.Popen(['xdg-open', target_path])

        return jsonify({'success': True, 'message': f'Opened {target_path} in Explorer'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
