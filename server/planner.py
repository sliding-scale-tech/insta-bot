"""Day-plan runner.

State lives in Convex (`day_plans`); this poller drives it. Convex can't launch a
browser, so the backend asks every POLL_SECONDS: "is a session due?" — which means
a container restart resumes the day exactly where it left off.

Per tick, for each running plan:
  bot already running for this user   -> wait
  current session marked 'running'    -> it finished; read job outcome
                                          error & attempts < MAX_ATTEMPTS -> retry after RETRY_DELAY
                                          else -> mark done/error, advance, break
  session 'pending' and now >= due    -> check daily caps, then dispatch as a job
"""

import asyncio
import os
import time

import server.jobs as _jobs
import server.routers.log_ws as _log
from instagram_bot.db import convex_client as _cx

POLL_SECONDS = int(os.getenv("PLAN_POLL_SECONDS", "30"))
MAX_ATTEMPTS = 2          # initial run + one retry (user chose "retry once")
RETRY_DELAY_SECONDS = 60

_task: asyncio.Task | None = None


def _int(value, default: int = 0) -> int:
    """Convex returns every number as a float (0.0), which blows up when used as
    a list index. Coerce defensively."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _caps_exceeded(caps: dict, totals: dict) -> str | None:
    """Return the name of the first daily cap that's been hit, if any."""
    for key in ("comments", "likes", "dms", "follows"):
        cap = caps.get(key)
        if cap is None:
            continue
        if totals.get(key, 0) >= cap:
            return key
    return None


async def _tick_plan(plan: dict) -> None:
    plan_id = plan["_id"]
    user_id = plan["user_id"]
    sessions = plan.get("sessions") or []
    index = _int(plan.get("current_index", 0))

    if index >= len(sessions):
        await asyncio.to_thread(_cx.end_day_plan, plan_id, "done", "All sessions finished")
        return

    # A session is in flight — nothing to do until the bot exits.
    if _log.bot_is_running(user_id):
        return

    session = sessions[index]
    status = session.get("status", "pending")

    # ── A dispatched session has finished ────────────────────────────────────
    if status == "running":
        job_id = session.get("job_id")
        outcome = "done"
        if job_id:
            job_state = await asyncio.to_thread(_cx.job_status, job_id)
            if job_state == "error":
                outcome = "error"

        attempts = _int(session.get("attempts", 1), 1)
        if outcome == "error" and attempts < MAX_ATTEMPTS:
            print(f"  [plan] Session {index} failed — retrying once in {RETRY_DELAY_SECONDS}s")
            _log.emit_log(user_id, f"[plan] Session {index + 1} failed — retrying once")
            await asyncio.to_thread(
                _cx.finish_plan_session, plan_id, index, "error", True, RETRY_DELAY_SECONDS
            )
            return

        brk = _int(session.get("break_minutes", 0))
        label = "completed" if outcome == "done" else "failed"
        _log.emit_log(
            user_id,
            f"[plan] Session {index + 1}/{len(sessions)} {label}"
            + (f" — next in {brk} min" if index + 1 < len(sessions) else " — day complete"),
        )
        await asyncio.to_thread(_cx.finish_plan_session, plan_id, index, outcome, False, 0)
        return

    # ── Session is pending — is it due? ──────────────────────────────────────
    due_at = plan.get("next_run_at")
    if due_at is not None and time.time() * 1000 < due_at:
        return  # still on break

    # Daily caps (user chose caps-only, no active-hours window)
    caps = plan.get("daily_caps") or {}
    totals = await asyncio.to_thread(_cx.today_totals)
    hit = _caps_exceeded(caps, totals)
    if hit:
        msg = f"Daily cap reached ({hit}: {totals.get(hit)}/{caps.get(hit)})"
        print(f"  [plan] {msg} — ending plan")
        _log.emit_log(user_id, f"[plan] {msg} — stopping for today")
        await asyncio.to_thread(_cx.end_day_plan, plan_id, "done", msg)
        return

    goal = session.get("goal", "").strip()
    if not goal:
        await asyncio.to_thread(_cx.finish_plan_session, plan_id, index, "error", False, 0)
        return

    _log.emit_log(user_id, f"[plan] Starting session {index + 1}/{len(sessions)}: {goal}")
    result = await _jobs.submit(user_id, goal)
    await asyncio.to_thread(
        _cx.mark_plan_session_running, plan_id, index, result.get("job_id")
    )


async def _loop() -> None:
    print(f"[planner] Day-plan poller started (every {POLL_SECONDS}s)")
    while True:
        try:
            plans = await asyncio.to_thread(_cx.running_day_plans)
            for plan in plans:
                try:
                    await _tick_plan(plan)
                except Exception as exc:
                    print(f"[planner] tick error for plan {plan.get('_id')}: {exc}")
        except Exception as exc:
            print(f"[planner] poll error: {exc}")
        await asyncio.sleep(POLL_SECONDS)


def start_poller() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.ensure_future(_loop())


async def stop_poller() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
    _task = None
