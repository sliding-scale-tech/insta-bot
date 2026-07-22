# Instagram AI Outreach Bot

Playwright-driven Instagram automation powered by Gemini 2.5 Flash. Browses hashtags, reads posts, and comments/likes/DMs real-estate accounts autonomously. Includes a React dashboard with a live browser mirror for hands-on session control.

---

## Prerequisites

- Python 3.11+
- Node.js 18+ and pnpm (`npm install -g pnpm`)
- Docker Desktop (optional — for VPS-identical deploys)
- A Gemini API key — [get one free](https://aistudio.google.com/)

---

## 1. First-time setup

### Clone and install Python deps
```powershell
git clone <your-repo-url>
cd instagram
pip install -r requirements.txt -r requirements-server.txt
playwright install chromium
```

### Copy and fill in `.env`
```powershell
copy .env.example .env
```

Open `.env` and set at minimum:
```
username=your_instagram_username
password=your_instagram_password
GEMINI_API_KEY=your_gemini_api_key
```

### Install dashboard deps
```powershell
cd dashboard
pnpm install
cd ..
```

### Configure dashboard env
`dashboard/.env.local` (create if it doesn't exist):
```
VITE_API_URL=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000
VITE_SECRET_TOKEN=changeme
```

> **Windows note:** Chrome resolves `localhost` to IPv6 (`::1`) which breaks WebSocket. Always use `127.0.0.1` here.

---

## 2. Starting the dashboard (3 terminals)

**Terminal 1 — FastAPI server**
```powershell
$env:PYTHONIOENCODING="utf-8"
$env:AUTH_TOKEN="changeme"
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 — React dashboard**
```powershell
cd dashboard
pnpm dev
```

Open **http://localhost:5173** and enter the token `changeme` when prompted.

**Terminal 3 — Convex database** (for history / dedup across sessions)
```powershell
npx convex dev
```

---

## 3. First-time Instagram login

The bot needs a saved browser session to run without manual login each time.

1. Open the dashboard → **Integration** tab
2. Click **Start Browser** — Chrome launches inside the server
3. Log in to Instagram in the mirror (click, type, scroll as normal)
4. Complete any 2FA prompts
5. Click **Save Session** in the toolbar — session is saved to `data/users/default/browser_state.json`

Next time the server starts, the browser will resume from the saved session automatically.

**Alternative: authenticate from terminal**
```powershell
python authenticate.py
```

---

## 4. Running the bot

**From the dashboard** — go to the **Bot** tab, enter a goal, and click Start.

**From terminal:**
```powershell
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUNBUFFERED="1"
python agent.py --goal "comment on 3 real estate posts and send 2 DMs"
```

### Example goals
```
comment on 3 posts about construction
like 10 real estate posts
send DMs to 3 realtors I haven't contacted before
follow 5 agents from the realestate hashtag
reply to any DMs I received
browse explore page and engage with 3 posts
```

---

## 5. Check token usage and costs

```powershell
python agent.py --stats
```

---

## 6. Running in Docker

```powershell
# Build image (after code changes)
docker build -t instagram-bot .

# Run (Xvfb + FastAPI inside container, dashboard served from built bundle)
docker-compose up
```

> Build the React bundle first:
> ```powershell
> cd dashboard && pnpm build && cd ..
> ```

Then open **http://localhost:8000** — the dashboard is served from the built bundle.

---

## 7. Project structure

```
agent.py              Entry point — run the bot
authenticate.py       First-time login (terminal)
dashboard/            React dashboard (Vite + Tailwind)
  src/components/
    MirrorView.tsx    Live browser mirror (Start Browser button + session save)
  src/pages/
    Integration.tsx   Mirror + session management tab
    Bot.tsx           Run bot + live logs tab
    History.tsx       Session history from Convex
server/               FastAPI backend
  browser.py          Per-user Playwright browser manager (BrowserRegistry)
  auth.py             Token auth (simple token or Clerk JWT)
  routers/
    mirror_ws.py      20fps WebSocket screenshot stream
    log_ws.py         Bot stdout stream
    bot.py            Start/stop/status REST endpoints
instagram_bot/
  agent/              Gemini loop (runner, prompts, memory)
  tools/              All bot tools (navigation, actions, perception)
convex/               Database schema + functions (cross-session dedup)
data/                 Runtime files (session, pid, per-user state) — gitignored
debug_output/         Screenshots after each tool call — gitignored
media/                Put images here for post_photo tool
```

---

## 8. Safety

- **Never run two bot instances at once** — Instagram flags concurrent sessions from the same account
- Kill any lingering process before starting: `Get-Process python | Stop-Process -Force`
- Session caps (set in `.env`): `MAX_COMMENTS_PER_SESSION`, `MAX_DMS_PER_SESSION`, `MAX_LIKES_PER_SESSION`, etc.
- All commented posts and DMs are stored — the bot won't re-engage the same account twice

---

## 9. Debugging

Screenshots and HTML reports are saved after every tool call:
```
debug_output/tool_checks/<timestamp>/report.html
```

Run a single tool manually (no Gemini key needed):
```powershell
python scripts/test_tools.py
```

Debug a specific flow:
```powershell
python scripts/debug_flow.py      # navigation + page state
python scripts/debug_comment.py   # comment submission
```
