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
- **PC control** (admin): say or type "open Spotify", "find my invoices on the desktop", "move these into a folder", "how much disk space is left". Only the Desktop is open by default, any other folder asks first, changes and deletes need your approval, and everything can be undone and is logged. See the **PC** tab for the pause switch, trust mode and allowed folders.
- **Voice**: click the mic or press `Alt+V`. Say "Adion" to wake it. Needs Chrome or Edge.

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
