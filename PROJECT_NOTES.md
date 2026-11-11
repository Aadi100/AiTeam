# DevSquad Mission Control: Project Notes

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
| Model routing (planner vs worker; Claude/Gemini/OpenAI/Ollama) | `orchestrator/llm.py` |
| File safety (no `..`, no absolute paths, extension block, size caps, `ALLOWED_ROOTS`) | `sandbox.py`, `auth.py` |
| Accounts + roles (admin / member / viewer), signed tokens, rate-limited login | `auth.py` |
| Background tasks panel (admin only: it runs shell commands) | `routes/jobs.py` |
| Memory: embedding recall (Ollama `nomic-embed-text` or OpenAI), keyword fallback | `routes/memory.py` |
| Schedules; optional API keys stored encrypted (Fernet) | `routes/schedules.py`, `auth.encrypt_json` |
| Voice: browser SpeechRecognition, Whisper fallback for any browser | `src/lib/hooks.ts`, `routes/voice.py` |

## Roles
- **admin**: everything, including users, shell background jobs, all runs.
- **member**: start/cancel/retry own runs, memory, own schedules.
- **viewer**: read-only, can see all runs.

## Env vars (`backend/.env`)
`MONGO_URI`, `PORT`, `HOST` (default 127.0.0.1), `APP_PASSWORD` (initial `admin` password), `ALLOWED_ROOTS`
(default: your home folder), `MAX_WORKERS`, `PLANNER_MODEL`, `WORKER_MODEL`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`,
`OPENAI_API_KEY`, `OLLAMA_URL`, `EMBED_MODEL` (default `nomic-embed-text`).

## Known limits
- Local 7B models work but are slow, and Ollama may serialise requests, which reduces real parallelism. They also leave
  integration bugs the fixer can't repair (for example a Flask app with no `/` route); use a stronger model for planner and workers.
- Run-and-fix executes generated Python on your machine. It is opt-in per run, and the child process gets no API keys or
  database URI, but it is not a container. Only Python/Flask entry points are smoke-tested.
- Embedding recall needs an embedding model (`ollama pull nomic-embed-text`). Without one, memory uses word overlap.
- Stored schedule keys are encrypted with a secret kept in `backend/.auth.json` on the same machine. That protects a database
  leak, not someone with access to the whole folder.
- Helper agents go one level deep only.
- `backend/routes/rex.py` and the other legacy routes (tasks, training, messages, research) are untouched and no longer used by the UI.
  The old fixed-agent routes (`agents`, `project`) are unregistered.
