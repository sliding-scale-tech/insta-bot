from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from server.auth import resolve_user_id
from server.browser import registry
import server.routers.log_ws as _log_ws_mod
import server.jobs as _jobs

router = APIRouter(prefix="/api")


class StartBody(BaseModel):
    goal: str
    token: str = ""


class TokenBody(BaseModel):
    token: str = ""


@router.post("/bot/start")
async def start_bot(body: StartBody, request: Request):
    user_id = await resolve_user_id(request, token=body.token)
    if not body.goal.strip():
        return {"queued": False, "error": "Goal is empty"}
    result = await _jobs.submit(user_id, body.goal.strip())
    return {"user_id": user_id, **result}


@router.post("/bot/stop")
async def stop_bot(body: TokenBody, request: Request):
    user_id = await resolve_user_id(request, token=body.token)
    await _jobs.stop_current(user_id)
    return {"stopped": True}


@router.get("/bot/status")
async def bot_status(request: Request, token: str = ""):
    user_id = await resolve_user_id(request, token=token)
    return {"running": _log_ws_mod.bot_is_running(user_id), "pid": _log_ws_mod.bot_pid(user_id)}


@router.get("/session/url")
async def session_url(request: Request, token: str = ""):
    user_id = await resolve_user_id(request, token=token)
    return {"url": registry.get(user_id).get_url()}


@router.post("/session/logout")
async def session_logout(body: TokenBody, request: Request):
    user_id = await resolve_user_id(request, token=body.token)
    await registry.get(user_id).logout()
    return {"logged_out": True}


class PlanBody(BaseModel):
    day_goal: str
    token: str = ""
    caps: dict | None = None


class PlanIdBody(BaseModel):
    plan_id: str
    token: str = ""


@router.post("/plan/generate")
async def plan_generate(body: PlanBody, request: Request):
    """Split a day-long instruction into session goals + breaks, save as a draft
    for the user to review/edit before starting."""
    user_id = await resolve_user_id(request, token=body.token)
    if not body.day_goal.strip():
        return {"created": False, "error": "Day goal is empty"}

    import asyncio
    from instagram_bot.agent.day_planner import default_daily_caps, plan_day
    from instagram_bot.db import convex_client as cx

    caps = body.caps or await asyncio.to_thread(default_daily_caps)
    sessions = await asyncio.to_thread(plan_day, body.day_goal.strip(), caps)
    plan_id = await asyncio.to_thread(
        cx.create_day_plan, user_id, body.day_goal.strip(), sessions, caps
    )
    return {"created": True, "plan_id": plan_id, "sessions": sessions}


@router.post("/plan/start")
async def plan_start(body: PlanIdBody, request: Request):
    await resolve_user_id(request, token=body.token)
    import asyncio
    from instagram_bot.db import convex_client as cx
    await asyncio.to_thread(cx.start_day_plan, body.plan_id)
    return {"started": True}


@router.post("/plan/cancel")
async def plan_cancel(body: PlanIdBody, request: Request):
    await resolve_user_id(request, token=body.token)
    import asyncio
    from instagram_bot.db import convex_client as cx
    await asyncio.to_thread(cx.cancel_day_plan, body.plan_id, "Cancelled by user")
    return {"cancelled": True}


_CAPTION_MIME_MAP = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
_CAPTION_MAX_BYTES = 20 * 1024 * 1024  # 20MB — plenty for a photo, keeps the request light


@router.post("/caption/generate")
async def caption_generate(
    request: Request,
    file: UploadFile = File(...),
    hint: str = Form(""),
    token: str = Form(""),
):
    """Vision-based caption for the Posts tab's "Write with AI" button.
    Takes the raw image the user just picked — no upload to Convex needed first."""
    await resolve_user_id(request, token=token)

    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    mime_type = _CAPTION_MIME_MAP.get(ext)
    if not mime_type:
        raise HTTPException(400, "Only JPG/PNG photos are supported for AI captions")

    body = await file.read()
    if len(body) > _CAPTION_MAX_BYTES:
        raise HTTPException(400, "Image too large for caption generation (max 20MB)")

    try:
        from instagram_bot.agent.gemini_client import GeminiAgent
        agent = GeminiAgent()
        caption = agent.generate_post_caption(body, mime_type, hint=hint)
    except SystemExit as exc:
        raise HTTPException(500, f"Gemini not configured: {exc}")
    except Exception as exc:
        raise HTTPException(500, f"Caption generation failed: {exc}")

    return {"caption": caption}


@router.get("/prompts/defaults")
async def prompts_defaults(request: Request, token: str = ""):
    """Built-in prompt templates + their placeholders, so the dashboard can show
    what's editable and offer a reset-to-default."""
    await resolve_user_id(request, token=token)
    from instagram_bot.agent.prompt_store import defaults_payload
    return {"prompts": defaults_payload()}


class SettingBody(BaseModel):
    key: str
    value: str
    token: str = ""


class SettingKeyBody(BaseModel):
    key: str
    token: str = ""


@router.get("/settings")
async def settings_list(request: Request, token: str = ""):
    """Effective settings (override or built-in default) + metadata for the UI."""
    await resolve_user_id(request, token=token)
    from instagram_bot.config import settings_store
    settings_store.refresh()
    return {"settings": settings_store.defaults_payload()}


@router.post("/settings/update")
async def settings_update(body: SettingBody, request: Request):
    await resolve_user_id(request, token=body.token)
    from instagram_bot.config import settings_store
    if body.key not in settings_store.DEFAULTS:
        raise HTTPException(400, f"Unknown setting: {body.key}")
    from instagram_bot.db import convex_client as cx
    cx._client().mutation("settings:upsertSetting", {"key": body.key, "value": body.value})
    return {"saved": True}


@router.post("/settings/reset")
async def settings_reset(body: SettingKeyBody, request: Request):
    await resolve_user_id(request, token=body.token)
    from instagram_bot.db import convex_client as cx
    cx._client().mutation("settings:resetSetting", {"key": body.key})
    return {"reset": True}
