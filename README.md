# Adion

Your personal AI software team. Tell Adion what to build (typing or by voice) and it **plans** the work, splits it
into modules, and runs **parallel agents** you can watch live. It asks you questions when it must, shows you the plan
before spending anything big, tests the result in a real browser, fixes what breaks, and lets you keep changing the
project afterwards. It also answers questions (with optional web search) and tracks every token it spends.

Powered by [DeepSeek](https://platform.deepseek.com). Web search by [Tavily](https://tavily.com) (optional).

## What you need

| | |
|---|---|
| **Node.js** 20 or newer | for the web app |
| **Python** 3.11 or newer | for the backend |
| **MongoDB** (local, default port) | stores runs, users, usage and memory. [Download](https://www.mongodb.com/try/download/community) |
| **Microsoft Edge or Google Chrome** | used by the browser check and the voice features |
| **A DeepSeek API key** | [platform.deepseek.com](https://platform.deepseek.com): top up a few dollars, then *API keys* |

## Set up (about 5 minutes)

```bash
# 1. get the code
git clone <your repo url> adion
cd adion

# 2. backend
cd backend
python -m venv venv
venv\Scripts\activate            # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env   (then edit it, see below)
cd ..

# 3. frontend
npm install
```

Open `backend/.env` and set at least `DEEPSEEK_API_KEY` (or skip it and paste the key into the app later).
Everything else in that file is optional and explained inside it.

## Run it

Start MongoDB, then use two terminals:

```bash
# terminal 1: backend  (http://127.0.0.1:5000)
cd backend
venv\Scripts\activate
python app.py

# terminal 2: web app  (http://localhost:3000)
npm run dev
```

Open the web app and sign in as **admin**. The password is `APP_PASSWORD` from `backend/.env`; if you left it empty,
the backend printed a generated one when it first started and saved it in `backend/.auth.json`.

Then open **Models & keys** (top right):
1. paste your **DeepSeek key** and Save. It is stored encrypted in the database, never in the browser;
2. optionally paste a **Tavily key** to let Adion search the web for recent facts.

Try: *"who is elon musk"* (a quick answer), *"make a simple landing page for a coffee shop"* (one agent), or a bigger
goal such as *"a CRM with a dashboard, pipeline board and contacts"* (planner, plan review, parallel agents).

## How it behaves

- **Questions** get one short answer that streams in word by word. Recent-facts questions are searched on the web.
- **Small builds** (a page, a calculator, a script) use a single agent, with no planner.
- **Big builds** are planned (big, multi-part goals by DeepSeek's reasoning model), shown to you for approval, then built
  by parallel agents. If an agent fails twice the planner re-plans it. Agents can ask you a question if something is
  truly ambiguous.
- **Browser check** opens the finished site in a headless browser, finds errors, 404s and broken buttons, and has an
  agent fix them. You can also **Preview the site** inside Adion and **Change this project** afterwards.
- **Usage tab** shows cost, tokens, cache savings and forecasts before you run anything.
- **Attachments**: click **Attach** or drag files into the box (documents, PDFs, spreadsheets as CSV, pictures). Adion reads the text (scanned pages and pictures by free local OCR) and can use pictures and data files in a build. It cannot *see* pictures, only the text in them.
- **PC control** (admin): say or type "open Spotify", "find my invoices on the desktop", "move these into a folder", "how much disk space is left". Only the Desktop is open by default, any other folder asks first, changes and deletes need your approval, and everything can be undone and is logged. See the **PC** tab for the pause switch, trust mode and allowed folders.
- **Voice**: click the mic or press `Alt+V`. Say "Adion" to wake it (Chrome or Edge). Speak in **any language** and Adion answers in it. Open **Voice** in the header to pick a male or female voice from 300+ natural voices in 75 languages, a style (robot, deep, radio...), and the language you listen in. The first any-language recognition downloads a ~140 MB speech model.

## Where things live

```
src/              web app (Next.js + React)
backend/          Flask API
  orchestrator/   router, planner, agents, browser check, search, plan memory, usage ledger
  routes/         HTTP endpoints
  tests/          offline tests (no tokens, no credits):  python tests/run_all.py
PROJECT_NOTES.md  design notes, roles, every setting
```

Generated projects are written to the **output folder** you set in Options (default `~/Desktop/adion-output`), one
folder per project.

## Run the tests

```bash
cd backend
venv\Scripts\activate
python tests/run_all.py
```

They use a fake model, a fake search service and a separate `devsquad_test` database, so they cost nothing and never
touch your real data. The browser check test opens a real headless Edge/Chrome.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Could not connect to MongoDB" | Start MongoDB, or set `MONGO_URI` in `backend/.env`. |
| "No DeepSeek API key" | Add it in **Models & keys**, or `DEEPSEEK_API_KEY` in `backend/.env`. |
| "insufficient balance (402)" | Top up at platform.deepseek.com. |
| Browser check says "skipped" | Install Edge or Chrome, or set `ADION_BROWSER`. Run `pip install -r requirements.txt` again. |
| Web page looks unstyled after an update | Stop `npm run dev`, delete the `.next` folder, start it again. |
| Port 3000 or 5000 is busy | Use `npm run dev -- -p 3001` (the app finds the backend at 127.0.0.1:5000; set `NEXT_PUBLIC_BACKEND_URL` if you change the backend port). |
| Forgot the admin password | Delete `backend/.auth.json` and the `users` collection, or set `APP_PASSWORD` and re-create the user. |

## Security notes

- The backend only listens on `127.0.0.1` by default. Keep it that way unless you add HTTPS and a firewall.
- Agents write only inside the output folder (and `ALLOWED_ROOTS`). They never choose shell commands.
- The browser check and **Run the result** execute generated code on this computer. Both are opt-in and run with your
  secrets removed from the environment, but they are not a container.
- API keys are encrypted in the database with a secret kept in `backend/.auth.json`. Back that file up with the database.

## Adion Connect (connect other people's apps)

Clients sign up at `/portal`, create a project → app, and get a public key (`pk_…`, safe in the app) and a secret key (`sk_…`, shown once, for their server).
Each app's assistant knows only that app (description, rules, uploaded knowledge) and acts only for that app's signed-in users. PC control, builds and personal memory are off.

- **Modes:** knowledge only · API connection (import OpenAPI/Swagger/Postman, or add by hand; Adion calls the client's server with the user's own token or a saved header key) · in-app actions (the app's own code runs them via the SDK).
- **Access levels:** limited (read only) · standard (changes, always confirmed) · complete (risky too, always confirmed). Per action: never-by-AI, hidden fields; secrets are auto-redacted.
- **Billing:** every model call is tagged client/app/user; price = DeepSeek cost × owner markup; caps per app/client; owner console in the portal (shown to the Adion admin login).
- **Embedding:** `<script src=".../api/connect/widget.js">` + `Adion.init({...})`, or the REST API (`/api/connect/v1/...`). The portal's Guide tab generates the exact code for web, React/Next, React Native and plain REST.
- **Env:** `PUBLIC_URL` (the server's public address, used in guides), `CONNECT_ALLOW_PRIVATE=1` (dev/tests only: lets API connections reach localhost).
- **Hosting:** use an always-on server (Render/Railway/VPS) + MongoDB Atlas for the backend; Vercel is fine for the frontend only.
- **Tests:** `venv\Scripts\python.exe tests\run_all.py` (147 checks for Connect).

## Connected apps (Gmail, Calendar, GitHub, Slack, Notion, ...)

Every user (and the owner) can connect their own accounts in the **Apps** tab with one Connect button, then just ask Adion in chat or by voice
("any unread mail from Sara?", "put lunch with Omar on Friday at 1 and email him", "open an issue on my repo").

- **Services:** Google (Gmail, Calendar, Drive, Docs, Sheets, Tasks), Microsoft (Outlook, Calendar, OneDrive, To Do), GitHub, Slack, Notion, Todoist, Asana, Linear, Dropbox, Spotify, Zoom, LinkedIn, X, Facebook/Instagram. Add one by adding an entry in `backend/integrations/providers.py`.
- **Set-up (owner, once per service):** Owner tab > Connected apps. Create the OAuth app on the service's developer page, register the Redirect URI shown there, paste the client ID and secret. Users never see or need these.
- **Safety:** reading runs by itself; sending, creating, posting, changing or deleting always shows the exact action first and waits for Approve. Mail/events/messages are treated as data, never as instructions. Tokens are encrypted per user; a user can only use their own accounts. Max 20 changes per hour.
- **Env:** `PUBLIC_URL` = the backend's address as the browser reaches it (default: the request address, e.g. http://localhost:5000); `FRONTEND_URL` = where to send the browser back after connecting (default http://localhost:3001).
- **Tests:** `backend/tests/test_integrations.py` (65 checks, offline).

## The Adion agent (chat that can do things)

Typed and spoken messages that are not clearly "build me an app" go to one general agent (`backend/orchestrator/agent.py`) instead of fixed lanes. It has a toolbox and loops until the job is done:
web search, reading web pages, memory (remember/recall), `connect_account` (shows a Connect button in the chat, or tells the owner exactly what to set up), `accounts_task` (mail, calendar, GitHub, Slack... with approval cards),
`pc_task` (your PC, with approvals) and `start_build` (hands over to the build team). It gets the whole conversation (last 16 turns), streams its answer, and answers are shown as Markdown with copyable code blocks.
Web pages and tool results are treated as data, never instructions. `ADION_AGENT=0` switches back to the classic one-call answer path. Tests: `backend/tests/test_agent.py`.

## Claude as a second brain (optional)

DeepSeek is the default and the cheapest. The owner can add a Claude API key on the **Owner** tab (get one at console.anthropic.com, add credit under Billing) and pick:

- **DeepSeek only** - everything on DeepSeek.
- **Mixed** - Claude plans, chats and works in your accounts; DeepSeek writes the code files (best value).
- **Claude only** - everything on Claude.

The choice applies to everyone; members never see the keys. Removing the Claude key puts everything back on DeepSeek. Claude uses the official `anthropic` SDK (`backend/orchestrator/claude_llm.py`); models: `claude-sonnet-5-5` (default), `claude-haiku-5-5`, `claude-opus-5-5`. Env: `ANTHROPIC_API_KEY`, `ADION_BRAIN`, `ANTHROPIC_FALLBACK=0` (turn off the safety fallback), `ANTHROPIC_PRICES` (override prices). Tavily is for DeepSeek only: when Claude answers it uses its own built-in web search (about $0.01 per search), so no Tavily key is needed.

## Tool servers (MCP, e.g. Zapier)

In **Assistant -> Apps -> Tool servers** each person can add their own MCP link (for example from mcp.zapier.com). Adion can then use those tools in that person's apps only. Links are stored encrypted, only public https servers are called, lookups run at once and anything that sends or changes something waits for Approve. Tests: `tests/test_mcp.py`.

## Learning and long conversations

- **Adion learns from chats.** After an answer it can write down lasting things you said (who you are, how you like answers, corrections) into **your own** memory, marked "learned". Only you see them; secrets (keys, passwords, card numbers) are never saved; you can delete any note or switch learning off in Assistant -> Memory. `ADION_LEARN=0` switches it off for everyone.
- **Memory is private per person** (it used to be shared; older notes stay with the owner).
- **Longer context.** Recent turns are sent in full up to a token budget (28k tokens for DeepSeek, 150k for Claude; `ADION_HISTORY_TOKENS` overrides), and older turns become a rolling summary refreshed in the background. Code: `backend/orchestrator/learn.py`, tests: `tests/test_learn.py`.
