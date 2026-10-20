# DevSquad Mission Control — Project Notes

> A full-stack "autonomous AI office" app: a Next.js 16 frontend with a Python Flask backend.
> Three AI agents (Michael, Dave, Sarah) receive voice or text directives, generate code in parallel, and write real files to the user's PC hard drive.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.4.1 (App Router), React 19, Tailwind CSS v4, Turbopack |
| UI Icons | lucide-react ^1.57.0 |
| Confetti | canvas-confetti |
| Backend | Python Flask 3, Flask-CORS |
| Database | MongoDB (local) via MongoEngine |
| AI (default) | Ollama — Llama 3 (Michael), Mistral (Dave), Gemma (Sarah) |
| AI (paid) | Google Gemini, Anthropic Claude, OpenAI GPT-4o |
| Voice | Web Speech API (webkitSpeechRecognition) — browser only |
| Speech output | SpeechSynthesis API — browser only |

---

## Architecture

```
Browser (Next.js)
  └─ /api/py/* proxy (next.config.ts)
        └─ Flask backend  :5000
              └─ MongoDB  :27017/devsquad
```

The Next.js dev server proxies `/api/py/:path*` → `http://127.0.0.1:5000/api/:path*`.  
The frontend uses `/api/py` as the base URL by default (no `NEXT_PUBLIC_BACKEND_URL` env var needed for local dev).

---

## Directory Layout

```
dev-squad/
├── src/
│   ├── app/
│   │   ├── layout.tsx          Root layout — Geist font, dark theme
│   │   ├── page.tsx            Root page — wraps everything in <OfficeProvider>
│   │   └── globals.css         Tailwind import, CSS vars, scrollbar, fadeIn animation
│   ├── components/
│   │   ├── CockpitHeader.tsx         Sticky nav: logo, MongoDB badge, mic, history, add-person
│   │   ├── SatelliteRadar.tsx        Animated radar with agent blips
│   │   ├── TeamOfficePod.tsx         Agent cards grid with model selector dropdowns
│   │   ├── VoiceChatConsole.tsx      Target path editor + voice/text prompt + Run button
│   │   ├── ParallelExecutionDeck.tsx Michael & Dave live stream columns + file inspector
│   │   ├── AISettingsModal.tsx       API key inputs (Gemini / Claude / OpenAI / Ollama URL)
│   │   ├── AddPersonModal.tsx        Add a custom agent (saved to MongoDB)
│   │   ├── ProjectHistoryModal.tsx   Full-screen history browser + HTML preview iframe
│   │   └── GlobalVoiceBar.tsx        Fixed floating mic dock (bottom-right)
│   ├── context/
│   │   └── OfficeContext.tsx         All global state + all backend fetch calls
│   └── types/
│       └── office.ts                 TypeScript interfaces for Person, AIKeys, ProjectState, etc.
├── backend/
│   ├── app.py                Flask factory — registers 7 blueprints, enables CORS
│   ├── database.py           MongoEngine connect + seed (Michael, Dave, Sarah + ProjectState)
│   ├── models.py             MongoEngine document schemas (8 collections)
│   ├── requirements.txt      Flask, Flask-CORS, pymongo, mongoengine, python-dotenv, requests
│   ├── reset_db.py           Standalone script to wipe and re-seed MongoDB
│   ├── .env                  MONGO_URI, PORT, FLASK_ENV
│   └── routes/
│       ├── project.py        Core build engine — parallel generation + disk write + history
│       ├── agents.py         Agent CRUD (deploy, update model, pause/resume)
│       ├── health.py         GET /api/health — MongoDB connectivity + collection counts
│       ├── tasks.py          Task CRUD + parallel dispatch
│       ├── messages.py       Message log (channel-scoped)
│       ├── training.py       Training pairs, custom model export (JSONL / Modelfile)
│       └── research.py       Research brief stubs
├── next.config.ts            cacheComponents, partialPrefetching, Turbopack, /api/py proxy
├── tsconfig.json             target ES2017, moduleResolution bundler, @/* alias → ./src/*
├── .env.local                Documents NEXT_PUBLIC_BACKEND_URL (commented out by default)
└── PROJECT_NOTES.md          This file
```

---

## MongoDB Collections

| Collection | Document class | Purpose |
|---|---|---|
| `agents` | `AgentDocument` | People / AI agent nodes |
| `tasks` | `TaskDocument` | Assigned work items |
| `training_pairs` | `TrainingPairDocument` | Prompt-response pairs for fine-tuning |
| `custom_models` | `CustomModelDocument` | Fine-tuned model configs |
| `messages` | `MessageDocument` | Channel message log |
| `project_state` | `ProjectStateDocument` | Singleton current mission state |
| `research_briefs` | `ResearchBriefDocument` | Research summaries |
| `project_history` | `ProjectHistoryDocument` | Every completed parallel build |

---

## How the Parallel Build Works

1. User types or speaks a prompt → hits **Run Parallel Build**
2. Frontend POSTs to `/api/py/project/build` with `{ prompt, targetPath, apiKeys }`
3. Backend looks up Michael's model and Dave's model from MongoDB
4. `ThreadPoolExecutor(max_workers=2)` runs both generators concurrently:
   - `generate_frontend_code()` → calls AI → returns `index.html`, `styles.css`, `app.js`
   - `generate_backend_code()` → calls AI → returns `backend/app.py`, `backend/requirements.txt`, `README.md`
5. All 6 files are written to `targetPath` on disk (`os.makedirs` + `open(..., 'w')`)
6. Agent stats updated in MongoDB, history record saved, system message logged
7. Response JSON includes file paths + content → frontend displays them in the stream columns

### AI Model Resolution

```
User assigns model in UI
        │
        ▼
  starts with "ollama:" ?
     YES → Ollama endpoint (http://localhost:11434 or custom URL)
              │
              ├─ Ollama reachable? → use AI response for index.html / app.py
              └─ Ollama unreachable? → fall back to hardcoded template
     NO  → paid key present?
              │
              ├─ gemini key   → Google Gemini API
              ├─ claude key   → Anthropic Claude API
              └─ openai key   → OpenAI API
                     │
                     └─ AI response used if it contains <!DOCTYPE / from flask
                        otherwise fall back to hardcoded template
```

---

## Key State — OfficeContext

Everything lives in `src/context/OfficeContext.tsx`. The main pieces:

| State | Type | What it holds |
|---|---|---|
| `people` | `Person[]` | All agents (synced from MongoDB on mount) |
| `targetPath` | `string` | Where to write files; persisted to `localStorage` |
| `aiKeys` | `AIKeys` | Gemini / Claude / OpenAI keys + Ollama URL; persisted to `localStorage` |
| `project` | `ProjectState` | Current mission name, status, progress |
| `streams` | `ParallelStreams` | Live text shown in Michael and Dave columns |
| `writtenFiles` | `GeneratedFile[]` | Files from the last build (content + path + author) |
| `isExecuting` | `boolean` | Locks the UI during a build |
| `isVoiceActive` | `boolean` | Drives Web Speech recognition lifecycle |
| `history` | `ProjectHistoryItem[]` | Past builds fetched from MongoDB |

---

## Voice System

- Uses `webkitSpeechRecognition` (Chrome / Edge)
- **Auto-process mode** (default on): fires the parallel build automatically after 1.2 s of silence or when a final speech result arrives — no button click needed
- Global hotkey: `Alt+V` or `Ctrl+Space` toggles listening
- Speech synthesis reads build status back to the user

---

## Env Vars

| Variable | Where | Default | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `.env.local` | *(unset — uses proxy)* | Override backend origin for production |
| `MONGO_URI` | `backend/.env` | `mongodb://localhost:27017/devsquad` | MongoDB connection string |
| `PORT` | `backend/.env` | `5000` | Flask listen port |
| `FLASK_ENV` | `backend/.env` | `development` | Flask mode |

---

## Running Locally

```bash
# 1. Start MongoDB (must be running on localhost:27017)

# 2. Backend
cd backend
pip install -r requirements.txt
python app.py
# Flask starts on http://localhost:5000

# 3. Frontend (separate terminal)
npm install
npm run dev
# Next.js starts on http://localhost:3000
```

To reset the database back to the three default agents:
```bash
cd backend
python reset_db.py
```

---

## Bugs Fixed

| Bug | Root cause | Fix |
|---|---|---|
| Backend crashes on start | `mongoengine` not in `requirements.txt` | Added `mongoengine>=0.27.0` |
| AI never used — always same template | `call_ai_model()` return value was discarded | Capture response, extract code block, use when valid |
| `~/Desktop/...` paths silently broken | `os.path.abspath()` does not expand `~` | Added `os.path.expanduser()` before `abspath` |
| Frontend bypassed Next.js proxy | `BACKEND_URL` defaulted to `http://localhost:5000`; proxy at `/api/py` was dead code | Default changed to `/api/py` (through proxy); env var still overrides for production |
| Hardcoded `C:\Users\Abdul Hadi\...` paths | Machine-specific username baked into source | Replaced with `~/Desktop/...` (expanded server-side) |
| `z-60` Tailwind class missing | Tailwind v4 default scale stops at `z-50` | Changed to `z-[60]` (arbitrary value syntax) |
| Dead npm packages | `three`, `file-saver`, `jszip` listed but never imported | Removed all three + their `@types` packages |

---

## Known Limitations

- **AI generation quality**: When Ollama is running, the AI response is used as `index.html` (and `app.py`), but `styles.css` and `app.js` are always the hardcoded templates. Extending to full AI generation for all files requires either one structured JSON response or separate AI calls per file.
- **Voice recognition**: Only works in Chromium-based browsers (Chrome, Edge). Firefox does not support `webkitSpeechRecognition`.
- **Windows-only folder open**: `os.startfile()` is Windows-specific. Linux/macOS falls back to `xdg-open`.
- **MongoDB must be local**: No hosted Atlas support out of the box — change `MONGO_URI` in `backend/.env` to use Atlas.
- **No auth**: The app has no authentication layer. Anyone who can reach port 3000 can trigger file writes to the server's disk.
