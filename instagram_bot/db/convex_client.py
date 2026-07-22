"""Convex database client — thin wrapper around the convex Python SDK."""

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv(_PROJECT_ROOT / ".env.local", override=True)  # Convex dev writes URL here


@lru_cache(maxsize=1)
def _client():
    from convex import ConvexClient
    url = os.getenv("CONVEX_URL")
    if not url:
        raise RuntimeError("CONVEX_URL not set in .env — run `npx convex dev` to get it")
    return ConvexClient(url)


def has_commented(url: str) -> bool:
    try:
        return _client().query("bot:hasCommented", {"url": url})
    except Exception:
        return False


def add_commented_post(url: str, shortcode: str, comment_snippet: str, username: str) -> None:
    try:
        _client().mutation("bot:addCommentedPost", {
            "url": url,
            "shortcode": shortcode,
            "comment_snippet": comment_snippet[:100],
            "username": username,
        })
    except Exception as e:
        print(f"  [convex] addCommentedPost failed: {e}")


def get_all_commented_urls() -> list[str]:
    try:
        return _client().query("bot:getAllCommentedUrls", {})
    except Exception:
        return []


def get_all_dm_usernames() -> list[str]:
    try:
        return _client().query("bot:getAllDmUsernames", {})
    except Exception:
        return []


def get_all_followed_usernames() -> list[str]:
    try:
        return _client().query("bot:getAllFollowedUsernames", {})
    except Exception:
        return []


def has_dm_sent(to_username: str, from_username: str) -> bool:
    try:
        return _client().query("bot:hasDmSent", {
            "to_username": to_username,
            "from_username": from_username,
        })
    except Exception:
        return False


def add_dm_sent(to_username: str, from_username: str, message_preview: str) -> None:
    try:
        _client().mutation("bot:addDmSent", {
            "to_username": to_username,
            "from_username": from_username,
            "message_preview": message_preview[:200],
        })
    except Exception as e:
        print(f"  [convex] addDmSent failed: {e}")


def has_followed(username: str) -> bool:
    try:
        return _client().query("bot:hasFollowed", {"username": username})
    except Exception:
        return False


def add_followed_user(username: str) -> None:
    try:
        _client().mutation("bot:addFollowedUser", {"username": username})
    except Exception as e:
        print(f"  [convex] addFollowedUser failed: {e}")


def start_session(goal: str) -> str | None:
    try:
        return _client().mutation("bot:startSession", {"goal": goal})
    except Exception as e:
        print(f"  [convex] startSession failed: {e}")
        return None


def end_session(session_id: str, comments: int, likes: int, follows: int,
                dms: int, replies: int, steps: int, status: str = "done",
                usage: dict | None = None) -> None:
    """`usage` is TokenTracker.summary() — token counts + estimated cost."""
    if not session_id:
        return
    try:
        args: dict[str, Any] = {
            "session_id": session_id,
            "comments": comments,
            "likes": likes,
            "follows": follows,
            "dms": dms,
            "replies": replies,
            "steps": steps,
            "status": status,
        }
        if usage:
            args.update({
                "model": str(usage.get("model", "")),
                "api_calls": int(usage.get("calls", 0)),
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
                "thinking_tokens": int(usage.get("thinking_tokens", 0)),
                "total_tokens": int(usage.get("total_tokens", 0)),
                "cost_usd": float(usage.get("estimated_cost_usd", 0.0)),
            })
        _client().mutation("bot:endSession", args)
    except Exception as e:
        print(f"  [convex] endSession failed: {e}")


def create_job(user_id: str, goal: str) -> str | None:
    try:
        return _client().mutation("jobs:createJob", {"user_id": user_id, "goal": goal})
    except Exception as e:
        print(f"  [convex] createJob failed: {e}")
        return None


def start_job(job_id: str) -> None:
    try:
        _client().mutation("jobs:startJob", {"job_id": job_id})
    except Exception as e:
        print(f"  [convex] startJob failed: {e}")


def finish_job(job_id: str, status: str, exit_code: int | None = None,
               error: str | None = None) -> None:
    try:
        args: dict[str, Any] = {"job_id": job_id, "status": status}
        if exit_code is not None:
            args["exit_code"] = exit_code
        if error is not None:
            args["error"] = error
        _client().mutation("jobs:finishJob", args)
    except Exception as e:
        print(f"  [convex] finishJob failed: {e}")


def next_pending_job(user_id: str) -> dict | None:
    try:
        return _client().query("jobs:nextPending", {"user_id": user_id})
    except Exception:
        return None


def fail_stale_processing(user_id: str) -> None:
    try:
        _client().mutation("jobs:failStaleProcessing", {"user_id": user_id})
    except Exception as e:
        print(f"  [convex] failStaleProcessing failed: {e}")


def fail_all_stale_processing() -> None:
    """Same as fail_stale_processing but across every user — call at server
    startup since a restart can orphan any user's job, not just 'default'."""
    try:
        _client().mutation("jobs:failAllStaleProcessing", {})
    except Exception as e:
        print(f"  [convex] failAllStaleProcessing failed: {e}")


# ── Media posts (dashboard uploads for post_photo) ──────────────────────────

def pending_media_posts(user_id: str) -> list[dict]:
    try:
        return _client().query("media:pendingMediaPosts", {"user_id": user_id}) or []
    except Exception:
        return []


def get_media_url(storage_id: str) -> str | None:
    try:
        return _client().query("media:getMediaUrl", {"storage_id": storage_id})
    except Exception:
        return None


def download_media_to_temp(storage_id: str, suffix: str = "") -> str | None:
    """Download a Convex-stored file to a temp path for one-time use (e.g.
    Playwright's file chooser). Caller is responsible for deleting it after —
    files are never kept on disk, to avoid growing VPS storage over time."""
    import tempfile
    import httpx

    url = get_media_url(storage_id)
    if not url:
        return None
    try:
        resp = httpx.get(url, timeout=30.0)
        resp.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=suffix)
        with open(fd, "wb") as f:
            f.write(resp.content)
        return path
    except Exception as e:
        print(f"  [convex] download_media_to_temp failed: {e}")
        return None


def mark_media_posted(media_id: str, post_url: str | None = None) -> None:
    try:
        args: dict[str, Any] = {"media_id": media_id}
        if post_url:
            args["post_url"] = post_url
        _client().mutation("media:markMediaPosted", args)
    except Exception as e:
        print(f"  [convex] markMediaPosted failed: {e}")


def upload_error_screenshot(png_bytes: bytes) -> str | None:
    """Upload a failure screenshot to Convex storage, returning its storage_id.

    Reuses the same generateUploadUrl mutation the dashboard's file upload uses —
    one-time signed URL, POST bytes directly to Convex storage."""
    import httpx

    try:
        upload_url = _client().mutation("media:generateUploadUrl", {})
        resp = httpx.post(upload_url, content=png_bytes, headers={"Content-Type": "image/png"}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()["storageId"]
    except Exception as e:
        print(f"  [convex] upload_error_screenshot failed: {e}")
        return None


def mark_media_error(media_id: str, error: str, error_screenshot_id: str | None = None) -> None:
    try:
        args: dict[str, Any] = {"media_id": media_id, "error": error[:300]}
        if error_screenshot_id:
            args["error_screenshot_id"] = error_screenshot_id
        _client().mutation("media:markMediaError", args)
    except Exception as e:
        print(f"  [convex] markMediaError failed: {e}")


# ── Day plans ────────────────────────────────────────────────────────────────

def create_day_plan(user_id: str, raw_goal: str, sessions: list[dict],
                    daily_caps: dict | None = None) -> str | None:
    try:
        args: dict[str, Any] = {
            "user_id": user_id,
            "raw_goal": raw_goal,
            "sessions": sessions,
        }
        if daily_caps:
            args["daily_caps"] = daily_caps
        return _client().mutation("dayplans:createPlan", args)
    except Exception as e:
        print(f"  [convex] createPlan failed: {e}")
        return None


def running_day_plans() -> list[dict]:
    try:
        return _client().query("dayplans:runningPlans", {}) or []
    except Exception:
        return []


def mark_plan_session_running(plan_id: str, index: int, job_id: str | None) -> None:
    try:
        args: dict[str, Any] = {"plan_id": plan_id, "index": index}
        if job_id:
            args["job_id"] = job_id
        _client().mutation("dayplans:markSessionRunning", args)
    except Exception as e:
        print(f"  [convex] markSessionRunning failed: {e}")


def finish_plan_session(plan_id: str, index: int, outcome: str,
                        retry: bool = False, retry_delay_seconds: int = 60) -> None:
    try:
        _client().mutation("dayplans:finishSession", {
            "plan_id": plan_id,
            "index": index,
            "outcome": outcome,
            "retry": retry,
            "retry_delay_seconds": retry_delay_seconds,
        })
    except Exception as e:
        print(f"  [convex] finishSession failed: {e}")


def end_day_plan(plan_id: str, status: str, note: str | None = None) -> None:
    try:
        args: dict[str, Any] = {"plan_id": plan_id, "status": status}
        if note:
            args["note"] = note
        _client().mutation("dayplans:endPlan", args)
    except Exception as e:
        print(f"  [convex] endPlan failed: {e}")


def cancel_day_plan(plan_id: str, note: str | None = None) -> None:
    try:
        args: dict[str, Any] = {"plan_id": plan_id}
        if note:
            args["note"] = note
        _client().mutation("dayplans:cancelPlan", args)
    except Exception as e:
        print(f"  [convex] cancelPlan failed: {e}")


def start_day_plan(plan_id: str) -> None:
    try:
        _client().mutation("dayplans:startPlan", {"plan_id": plan_id})
    except Exception as e:
        print(f"  [convex] startPlan failed: {e}")


def today_totals() -> dict:
    try:
        return _client().query("dayplans:todayTotals", {}) or {}
    except Exception:
        return {}


def job_status(job_id: str) -> str | None:
    try:
        return _client().query("dayplans:jobStatus", {"job_id": job_id})
    except Exception:
        return None


def save_browser_session(user_id: str, storage_state_json: str) -> None:
    try:
        _client().mutation("bot:saveBrowserSession", {
            "user_id": user_id,
            "storage_state": storage_state_json,
        })
    except Exception as e:
        print(f"  [convex] saveBrowserSession failed: {e}")


def get_browser_session(user_id: str) -> str | None:
    try:
        return _client().query("bot:getBrowserSession", {"user_id": user_id})
    except Exception:
        return None


def delete_browser_session(user_id: str) -> None:
    try:
        _client().mutation("bot:deleteBrowserSession", {"user_id": user_id})
    except Exception as e:
        print(f"  [convex] deleteBrowserSession failed: {e}")


def log_engagement(post_url: str, action: str, detail: str,
                   session_id: str | None = None) -> None:
    try:
        args: dict[str, Any] = {
            "post_url": post_url,
            "action": action,
            "detail": detail[:300],
        }
        if session_id:
            args["session_id"] = session_id
        _client().mutation("bot:logEngagement", args)
    except Exception as e:
        print(f"  [convex] logEngagement failed: {e}")
