# Adion: Project Notes

A planner splits one goal into modules and spawns one agent per module. The agents run in parallel, and you
watch them live on an **agent map**. There are no fixed agents.

## Run it
```bash
# MongoDB must be running on localhost:27017
cd backend && python -m venv venv && venv\Scripts\pip install -r requirements.txt && venv\Scripts\python app.py   # :5000
npm install && npm run dev -- -p 3001                                                                          # UI
```
Login password: `APP_PASSWORD` in `backend/.env`, otherwise a random one is generated in `backend/.auth.json` (git-ignored).

## Flow
1. `POST /api/runs {goal, targetPath, plannerModel, workerModel, maxTokens, apiKeys}` creates a Run.
2. **Planner** (strong model) returns modules, each with its own folder, `depends_on`, and a shared **contract**.
3. **Engine** (`backend/orchestrator/engine.py`) creates one `AgentTask` per module and schedules them on a worker pool
   (`MAX_WORKERS`, default 6). Independent modules run simultaneously. Dependent ones wait. Failed tasks retry once, and their dependents are skipped.
4. **Worker** (`worker.py`) writes files only inside its own folder (`sandbox.py`), runs fixed syntax checks
   (python compile, `node --check`, JSON parse) and feeds errors back to the model for up to 3 passes.
5. A final **review** agent writes root-level README and glue files and audits syntax.
6. `GET /api/runs/<id>/stream` (SSE) pushes live snapshots to the agent map.

## Features
| Area | Where |
|---|---|
| Task/run model with status, time, tokens, retries, dependencies | `models.py` (`RunDocument`, `AgentTaskDocument`) |
| Token tracking, budget auto-stop, cancel | `worker.charge`, `engine.cancel_run` |
| Retry one failed/skipped agent (and what it blocked) | `engine.retry_task`, `POST /runs/<id>/tasks/<tid>/retry` |
| Helper sub-agents (one level) spawned by a module agent | `worker._spawn_children` |
| Optional run-and-fix: start the generated app, GET /, model repairs failures | `orchestrator/verify.py`, `worker.run_integration` |
| "Run the result" suggestions (python / npm / static) | `verify.detect_commands`, shown on the map |
| Model routing (planner vs worker; DeepSeek) | `orchestrator/llm.py` |
| File safety (no `..`, no absolute paths, extension block, size caps, `ALLOWED_ROOTS`) | `sandbox.py`, `auth.py` |
| Accounts + roles (admin / member / viewer), signed tokens, rate-limited login | `auth.py` |
| Background tasks panel (admin only: it runs shell commands) | `routes/jobs.py` |
| Memory: keyword recall | `routes/memory.py` |
| Schedules; optional API keys stored encrypted (Fernet) | `routes/schedules.py`, `auth.encrypt_json` |
| **Adion**, the voice assistant: talks back, reads files aloud, runs commands (build / cancel / read / remember), wake word "Adion", hands-free loop, Alt+V / Ctrl+Space, spoken build progress, particle orb | `routes/assistant.py`, `src/context/VoiceContext.tsx`, `GlobalVoiceBar.tsx`, `VoiceOrb.tsx` |
| Voice fallback: server-side Whisper for browsers without Web Speech | `routes/voice.py` |

## Roles
- **admin**: everything, including users, shell background jobs, all runs.
- **member**: start/cancel/retry own runs, memory, own schedules.
- **viewer**: read-only, can see all runs.

## Env vars (`backend/.env`)
`MONGO_URI`, `PORT`, `HOST` (default 127.0.0.1), `APP_PASSWORD` (initial `admin` password), `ALLOWED_ROOTS`
(default: your home folder), `MAX_WORKERS`, `PLANNER_MODEL`, `WORKER_MODEL`, `DEEPSEEK_API_KEY`, `TAVILY_API_KEY` (web search), `SEARCH_PROVIDER` (default tavily), `TAVILY_PRICE_PER_SEARCH` (0 on the free plan), `DEEPSEEK_PRICE_HIT/MISS/OUT`.

## Web search and token calculator
- Questions about recent or changing facts are searched via Tavily (key in Models & keys, encrypted in the DB); results are trimmed and cited. Options has an "Always search the web" switch. `orchestrator/search.py` is provider-independent.
- A router (`orchestrator/router.py`) sends questions to one cheap call, small builds to one agent, and big builds to the planner. Every model call is written to a usage ledger; the Usage tab shows cost, cache savings and forecasts.

## Agentic behaviour
- **Clarifying questions:** if a goal is too vague the planner asks up to 3 questions (with quick-answer chips). The run pauses (`awaiting_input`), your answers go straight back to the planner, and it plans without asking again.
- **Plan review:** plans with 4+ modules pause (`awaiting_approval`) before any agent runs, so nothing is spent on agents until you press Start building. You can edit module titles/descriptions, untick modules, edit the shared contract, ask the planner to revise (with feedback), or reject. Toggle in Options.
- **Mid-build questions:** an agent may ask ONE question when a decision is truly ambiguous (max 3 per run, never in scheduled runs). The run pauses once the other agents finish and resumes with your answer.
- **Re-planning on failure:** when an agent fails twice the planner chooses: rewrite its brief and retry, split it into smaller agents (dependents are rewired), or drop it. Max 2 re-plans per run, one per agent. It ends honestly as failed if nothing works; there are no canned templates.
- **Browser check:** with "Test in a real browser & auto-fix" on, the finished project is served (Flask entry or static `index.html`), opened in headless Edge/Chrome via Playwright, and checked for load errors, JS errors, 404s, broken images/links, blank pages, buttons that throw, and sideways scroll on a phone width. Problems go to the fixer (2 rounds). A screenshot is saved in `backend/.shots/`. It cannot judge visual taste (DeepSeek has no vision). It executes generated code on this machine, so it is opt-in. Needs `pip install playwright` and Edge or Chrome (`ADION_BROWSER` overrides).
- **Follow-up changes:** "Change this project" continues a finished run in the same folder. The planner sees the existing files and plans only what changes; agents get the current file contents and return only changed files. Each new build gets its own project folder inside the output folder.

## Speed, cost and quality extras
- **Streaming answers:** questions stream into the run word by word (`llm.chat_stream`); if streaming fails it falls back to one normal call.
- **Deep planning:** big, multi-part goals (25+ words or 4+ "big" keywords) are planned by `deepseek-reasoner`; the plan critic and all agents stay on the fast model. If the reasoner returns junk it falls back to the fast model; a rejected key or empty balance is never hidden. Switch off in Options.
- **Plan memory:** a build that finished cleanly (2+ modules, no errors, at most one re-plan) is stored in `plan_memory`; the closest earlier plan (keyword overlap, per user) is shown to the planner as an example. No model call is used for matching.
- **Live preview:** "Preview the site" serves the finished static site in a sandboxed iframe. It uses a 15-minute, run-scoped, read-only token placed in the URL (it cannot call the API), serves only whitelisted static file types (never `.py`), and responds with a `sandbox` CSP. Python-backed apps are not previewed; use "Run the result".
- **Tests:** `python backend/tests/run_all.py` runs every offline suite (about 165 checks) against the `devsquad_test` database.

## PC control (admin only)
Adion can look at and operate your PC through a fixed set of tools (`backend/orchestrator/pc/`). It never gets a raw shell.
- **Folders:** only the Desktop is open. Any other folder shows a permission card: Allow once, Always allow (saved in the PC tab) or Not this folder. Secrets (`.ssh`, `.env`, key files, browser profiles, Windows folders) are refused no matter what.
- **Risk levels:** `read` and `low` (open an app/site/document, volume, media keys, lock) run without asking. `change` (create, copy, move, rename) needs approval. `danger` (delete, run an allowlisted command, open a program or script) always needs approval.
- **Trust mode** (PC tab) lets plain `change` steps in allowed folders run without a click. It never covers `danger`, folders outside the allowed list, or anything planned after Adion read file contents (prompt-injection guard).
- **Undo:** moves, renames, creates and copies are reversible. Delete moves to `~/.adion/trash` (kept 30 days), never permanent. Every action is in the Activity log.
- **Controls:** a Pause switch stops everything; at most 60 actions per minute; max 25 steps and 5 model rounds per request.
- **How requests arrive:** typing "open Spotify", "find my invoices on the desktop" in the composer (router kind `pc`), or by voice/chat (assistant action `pc`).
- **Allowed commands:** `git_status`, `git_log`, `git_diff`, `git_pull`, `npm_install`, `npm_run <script>`, `pip_install_requirements` in an allowed folder, with secrets removed from the environment.
- **Not built:** typing/mouse control, reading the screen, reading pictures or scanned PDFs, email and calendar.
- Tests: `backend/tests/test_pc.py` runs in a throwaway fake home with the OS hooks (open, volume, lock) replaced, so nothing real is touched.

## Attachments (files and pictures)
- **Attach** in the composer (or drag and drop): text/code, CSV/JSON, PDF, Word (.docx) and pictures (png, jpg, gif, bmp, webp). Up to 5 files of 10 MB per request. Programs and unknown types are refused.
- **What Adion gets:** the extracted text. Scanned PDFs and pictures are read with free, local OCR (RapidOCR, no key, nothing leaves the PC). Pictures also give size, format and main colours.
- **Honest limit:** DeepSeek cannot see pictures. Adion only knows the text OCR found plus basic facts, and tells the model so. Understanding a mockup or photo needs a vision model (not added).
- **Questions:** "summarize this" with a file attached is answered from the file. **Builds:** the planner sees the files; pictures are copied to `assets/` and CSV/JSON to `data/` inside the project, and every agent is told the exact paths, sizes and colours.
- **Safety:** extracted text is labelled as data and never followed as instructions. Uploads are private to their owner and stored under `~/.adion/uploads` (override with `ADION_UPLOADS`).
- **PC control** can also read pictures and scanned PDFs on your PC by OCR.
- Tests: `backend/tests/test_files.py` (uses the real OCR engine).

## Chat and automatic search
- **Conversations:** questions in the same chat share a thread. Follow-ups see the last 6 turns (within 90 minutes, same user) so "how old is he" works. A vague follow-up in a chat is treated as chat, not as a build. **New chat** starts a fresh thread. **Enter** sends, **Shift+Enter** adds a line, and the box empties after sending.
- **Automatic search:** with a Tavily key saved, factual questions (who/what/when/where/how is..., news, "look up", "go read the real information") are searched on the web without any special words. Greetings and writing tasks (explain, write, translate, summarize) are not. One question = one search credit.
- **Follow-up searches:** a vague message like "go read its real information" is rewritten into a real search query using the conversation, so the search is about the right person or topic.
- **No key:** Adion answers from what it knows and says plainly that adding a free Tavily key lets it look the answer up.

## Known limits
- Adion uses DeepSeek only (`deepseek-chat`, or slower `deepseek-reasoner`). No local models. It is a paid cloud API, so keep a token budget set.
- Run-and-fix executes generated Python on your machine. It is opt-in per run, and the child process gets no API keys or
  database URI, but it is not a container. Only Python/Flask entry points are smoke-tested.
- Memory recall is keyword-based (DeepSeek has no embeddings API).
- Not built: image understanding (needs a vision model), generating images, Excel (.xlsx) files.
- Stored schedule keys are encrypted with a secret kept in `backend/.auth.json` on the same machine. That protects a database
  leak, not someone with access to the whole folder.
- Adion's wake word and speech recognition need Chrome or Edge (Web Speech). Other browsers get push-to-talk via Whisper (needs an OpenAI key). The wake word listens only while the tab is open, and speech engines can mishear the made-up name, so several spellings are accepted.
- Adion's answers are only as good as DeepSeek's; it can still miss integration bugs in generated apps.
- Helper agents go one level deep only.
- `backend/routes/rex.py` and the other legacy routes (tasks, training, messages, research) are untouched and no longer used by the UI.
  The old fixed-agent routes (`agents`, `project`) are unregistered.
