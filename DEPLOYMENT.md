# Deployment Guide

How this system is deployed. Two independently-hosted pieces plus two managed
services.

```
┌──────────────────┐        HTTPS + WSS         ┌───────────────────────────┐
│   Vercel          │  ───────────────────────▶ │   VPS (Docker)             │
│   dashboard/ SPA  │                            │   FastAPI + Playwright     │
│   (static, HTTPS) │ ◀───────────────────────  │   headed Chrome on Xvfb    │
└────────┬─────────┘        JSON / frames        └────────────┬──────────────┘
         │                                                     │
         │  Convex JS client                    Convex Python client
         ▼                                                     ▼
              ┌───────────────────────────────────────────┐
              │   Convex Cloud  (jobs, sessions, users)    │
              └───────────────────────────────────────────┘
         ▲
         │  auth (JWT) + user webhook
         ▼
              ┌───────────────────────────────────────────┐
              │   Clerk  (auth + user management)          │
              └───────────────────────────────────────────┘
```

- **Docker (VPS)** — backend only: API, WebSockets, and the Instagram browser
  automation. Headed Chrome runs on Xvfb (no monitor needed, dodges headless
  bot-detection).
- **Vercel** — the React dashboard (`dashboard/`), a static SPA.
- **Convex Cloud** — database (jobs queue, session history, synced users).
- **Clerk** — authentication + the user webhook that syncs users into Convex.

---

## 0. Deployment target: DEV Convex + Clerk (current)

We deploy against the **dev** Convex deployment and the existing Clerk instance —
NOT prod. When you later want a separate prod stack, create a Convex prod
deployment + a Clerk production instance and swap the URLs/keys below; the steps
are otherwise identical.

- **Convex (dev):** `https://rugged-crow-939.convex.cloud`
  (HTTP actions / webhooks: `https://rugged-crow-939.convex.site`)
- **Clerk:** current instance — `pk_test_…` / `sk_test_…`,
  Frontend API domain `ruling-civet-84.clerk.accounts.dev`.

---

## 1. Backend on the VPS (Docker)

### Prerequisites on the VPS
- Docker + Docker Compose installed
- The repo cloned to the VPS
- A `.env` file present in the repo root (NOT committed — see reference below)

### Bring it up
```bash
cd /path/to/instagram
docker compose up --build -d
docker compose logs -f          # watch startup
```

This builds the backend image (Playwright 1.48 + Chromium + Xvfb), starts Xvfb
`:99`, and runs uvicorn on port **8000**. `ENV=production` makes the mirror
browser auto-start on WebSocket connect.

### Volumes (already configured in docker-compose.yml)
- `./data:/app/data` — Instagram sessions persist here across restarts
- `./.env:/app/.env:ro` — all secrets/config
- `./media:/app/media` — images for the post_photo tool

### Health check
```bash
curl http://localhost:8000/health      # -> {"status":"ok"}
```

---

## 2. HTTPS in front of the backend  ⚠️ REQUIRED for Vercel

Vercel serves the dashboard over **HTTPS**. Browsers block an HTTPS page from
calling a plain `http://`/`ws://` backend (mixed content). So the VPS backend
must be reachable at `https://` + `wss://`.

> **TODO on VPS deploy day.** Not needed for local dev (localhost→localhost is
> HTTP and allowed). Pick ONE:

### Option A — Caddy reverse proxy (needs a domain pointed at the VPS)
Point e.g. `api.yourdomain.com` → VPS IP, then add a Caddy service. Caddy
auto-provisions a Let's Encrypt cert and proxies `:443 → backend:8000`
(WebSockets pass through automatically).

`Caddyfile`:
```
api.yourdomain.com {
    reverse_proxy backend:8000
}
```
Add to `docker-compose.yml`:
```yaml
  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on:
      - backend
volumes:
  caddy_data:
```
Then the backend URL is `https://api.yourdomain.com` (`wss://…`).

### Option B — Cloudflare Tunnel (no domain/open ports on VPS)
Run `cloudflared` pointed at `http://backend:8000`; Cloudflare gives you an
`https://…` hostname that tunnels in. Good when you can't open ports / manage DNS.

---

## 3. Frontend on Vercel

1. Import the repo in Vercel.
2. **Root Directory = `dashboard`** (it uses `dashboard/vercel.json`).
3. Set **Environment Variables** (point at the HTTPS backend from step 2):
   ```
   VITE_API_URL=https://api.yourdomain.com
   VITE_WS_URL=wss://api.yourdomain.com
   VITE_CONVEX_URL=https://rugged-crow-939.convex.cloud
   VITE_CLERK_PUBLISHABLE_KEY=pk_test_cnVsaW5nLWNpdmV0LTg0LmNsZXJrLmFjY291bnRzLmRldiQ
   ```
4. Deploy. Vercel runs `pnpm build` and serves `dist/`.

> Vite bakes these at **build time** — after changing any `VITE_*` var you must
> redeploy.

---

## 4. Convex (dev deployment)

Push schema + functions to the dev deployment:
```bash
npx convex dev --once        # deploys functions to rugged-crow-939
```
Set these in the Convex dashboard (rugged-crow-939) → Settings → Environment Variables:
```
JWT_ISSUER_DOMAIN=https://<your-clerk-frontend-api-domain>
CLERK_WEBHOOK_SECRET=whsec_...        # from the prod Clerk webhook (step 5)
```

---

## 5. Clerk (current instance)

1. **JWT template** named `convex` (Convex preset) — required for Convex auth.
2. **Webhook** → Add Endpoint:
   - URL: `https://rugged-crow-939.convex.site/clerk-users-webhook`
   - Events: `user.created`, `user.updated`, `user.deleted`
   - Copy the signing secret → set `CLERK_WEBHOOK_SECRET` in Convex (step 4).
3. **Allowed origins / domains** — add your Vercel URL (e.g.
   `https://your-app.vercel.app`) to the Clerk instance so sign-in works there.
4. Put the matching keys where they belong:
   - `VITE_CLERK_PUBLISHABLE_KEY` → Vercel (step 3)
   - `CLERK_SECRET_KEY` + `CLERK_PUBLISHABLE_KEY` → VPS `.env` (backend verifies JWTs)

---

## 6. First-run on the deployed dashboard

1. Open the Vercel URL → sign in with Clerk.
2. **Integration tab** → **Start Browser** → log into Instagram in the mirror →
   **Save Session**. Session is written to `data/` on the VPS **and** Convex, so
   it survives container restarts.
3. **Bot tab** → enter a goal → **Run**. Goals queue (pending → processing →
   done/error) with live logs.

---

## Environment variable reference

### VPS `.env` (backend — never commit; gitignored)
```
# Instagram
username=...
password=...
email=...
LOGIN_METHOD=facebook

# Clerk (backend verifies JWTs; user_id = Clerk sub)
CLERK_SECRET_KEY=sk_...
CLERK_PUBLISHABLE_KEY=pk_...

# Convex (backend writes jobs/sessions/users)
CONVEX_URL=https://rugged-crow-939.convex.cloud

# Gemini agent
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash

# Session caps
SESSION_MINUTES=20
MAX_COMMENTS_PER_SESSION=2
MAX_DMS_PER_SESSION=2
```

### Vercel env (frontend — build-time)
```
VITE_API_URL=https://api.yourdomain.com
VITE_WS_URL=wss://api.yourdomain.com
VITE_CONVEX_URL=https://rugged-crow-939.convex.cloud
VITE_CLERK_PUBLISHABLE_KEY=pk_...
```

### Convex prod env
```
JWT_ISSUER_DOMAIN=https://<clerk-frontend-api-domain>
CLERK_WEBHOOK_SECRET=whsec_...
```

---

## Safety

- **Never run two browsers for one Instagram account at once** — concurrent
  sessions get flagged. One VPS container = one browser. Don't also run the bot
  locally against the same account.
- Sessions and engagement history live in Convex, so the bot won't re-comment or
  re-DM the same target across runs.

---

## Local development (for reference)

Backend in Docker (or native), dashboard via Vite — both HTTP on localhost, so
no TLS needed:
```powershell
# backend
docker compose up --build            # or: python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
# frontend (separate terminal)
cd dashboard; pnpm dev               # http://localhost:5173
```
`dashboard/.env.local` already points at `http://127.0.0.1:8000` / `ws://127.0.0.1:8000`.
