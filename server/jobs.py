"""Goal job queue — one goal runs at a time per user; the rest wait as
'pending' and are drained in order as each subprocess finishes.

Job status lives in Convex (survives refresh/restart); this module owns the
in-process queue + subprocess lifecycle and keeps Convex in sync.
"""

import asyncio
import os

import server.routers.log_ws as _log

from instagram_bot.db import convex_client as _cx

# user_id → Convex job_id currently processing
_current_job: dict[str, str] = {}
# Serialize dequeue decisions per user so two events can't both start a job
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(user_id: str) -> asyncio.Lock:
    if user_id not in _locks:
        _locks[user_id] = asyncio.Lock()
    return _locks[user_id]


def _bot_env(user_id: str) -> dict:
    from server.browser import _state_path_for
    env = dict(os.environ)
    env["DISPLAY"] = ":99"  # harmless on Windows, used by Xvfb in Docker
    # Point the agent at THIS user's saved session (same file the mirror wrote),
    # and tell it which user to load from Convex if the local file is missing.
    env["BROWSER_STATE_FILE"] = str(_state_path_for(user_id))
    env["BOT_USER_ID"] = user_id
    return env


async def submit(user_id: str, goal: str) -> dict:
    """Queue a goal. Starts it immediately if nothing is running, else pending."""
    job_id = await asyncio.to_thread(_cx.create_job, user_id, goal)
    _log.emit_log(user_id, f"[queued] Goal added to queue: {goal}")
    await _maybe_start_next(user_id)
    running = _log.bot_is_running(user_id)
    return {"job_id": job_id, "queued": True, "started": running}


async def _maybe_start_next(user_id: str) -> None:
    async with _lock_for(user_id):
        if _log.bot_is_running(user_id):
            return  # one at a time

        job = await asyncio.to_thread(_cx.next_pending_job, user_id)
        if not job:
            return

        job_id = job["_id"]
        goal = job["goal"]
        _current_job[user_id] = job_id
        await asyncio.to_thread(_cx.start_job, job_id)
        _log.emit_log(user_id, f"[processing] Starting goal: {goal}")

        async def _on_exit(rc: int) -> None:
            status = "done" if rc == 0 else "error"
            err = None if rc == 0 else f"Bot exited with code {rc}"
            finished = _current_job.pop(user_id, None)
            if finished:
                await asyncio.to_thread(
                    _cx.finish_job, finished, status, rc, err
                )
            label = "completed" if rc == 0 else "failed"
            _log.emit_log(user_id, f"[{label}] Goal '{goal}' {label} (exit {rc})")
            # Drain the rest of the queue
            await _maybe_start_next(user_id)

        await _log.start_bot_subprocess(
            goal, _bot_env(user_id), user_id=user_id, on_exit=_on_exit
        )


async def stop_current(user_id: str) -> None:
    """Stop the running job and mark it errored; leaves pending jobs queued."""
    await _log.stop_bot_subprocess(user_id=user_id)
    job_id = _current_job.pop(user_id, None)
    if job_id:
        await asyncio.to_thread(
            _cx.finish_job, job_id, "error", None, "Stopped by user"
        )
        _log.emit_log(user_id, "[stopped] Bot stopped by user")


async def recover_on_startup() -> None:
    """Mark any orphaned 'processing' jobs (from a crashed run) as errored,
    across all users — a restart can orphan any user's job, not just one."""
    await asyncio.to_thread(_cx.fail_all_stale_processing)
