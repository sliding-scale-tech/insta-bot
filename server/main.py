import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.browser import registry
from server.routers import bot, log_ws, mirror_ws
import server.jobs as _jobs
import server.planner as _planner


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Clean up jobs left "processing" by a previous crashed/killed server
    try:
        await _jobs.recover_on_startup()
    except Exception as exc:
        print(f"[startup] job recovery skipped: {exc}")
    # Drive any running day plan (resumes across restarts — state is in Convex)
    _planner.start_poller()
    yield  # browser starts on first WS connection, not at server startup
    await _planner.stop_poller()
    await registry.stop_all()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # dashboard is served cross-origin (Vercel)
    allow_credentials=False,   # auth is a Bearer token, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mirror_ws.router)
app.include_router(log_ws.router)
app.include_router(bot.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Only serve built dashboard in production (not dev — Vite runs on 5173)
_dist = Path(__file__).resolve().parents[1] / "dashboard" / "dist"
_env = os.environ.get("ENV", "development")
if _dist.exists() and _env == "production":
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="spa")
