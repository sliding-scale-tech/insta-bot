import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.auth import resolve_user_id
from server.browser import registry
import server.routers.log_ws as _log_ws_mod

router = APIRouter()


@router.websocket("/ws/mirror")
async def mirror_ws(websocket: WebSocket, token: str = ""):
    try:
        user_id = await resolve_user_id(websocket, token=token)
    except Exception as exc:
        print(f"[mirror_ws] auth failed: {exc}")
        await websocket.close(code=4001)
        return

    await websocket.accept()

    mgr = registry.get(user_id)
    frame_counter = 0

    def _status() -> str:
        # Reported to the client whenever the mirror browser is NOT live.
        if _log_ws_mod.bot_is_running(user_id):
            return "bot_running"        # bot drives its own browser
        if mgr._starting:
            return "starting"           # user asked to open the mirror
        if mgr.has_saved_session():
            return "session_ready"      # logged in already — show "Connected"
        return "idle"                    # first-time: needs login

    async def send_frames():
        nonlocal frame_counter
        browser_up = mgr.page and not mgr.page.is_closed()
        if not browser_up:
            try:
                await websocket.send_json({"type": "status", "msg": _status()})
            except Exception:
                return

        while True:
            if not mgr.page or mgr.page.is_closed():
                try:
                    await websocket.send_json({"type": "status", "msg": _status()})
                except Exception:
                    return
                await asyncio.sleep(0.5)
                continue
            try:
                frame = await mgr.screenshot()
                await websocket.send_bytes(frame)
                frame_counter += 1
                if frame_counter % 10 == 0:
                    try:
                        await websocket.send_json({"type": "url", "url": mgr.get_url()})
                    except Exception:
                        return
            except Exception:
                await asyncio.sleep(0.2)
                continue
            await asyncio.sleep(1 / 20)  # 20 fps

    async def recv_input():
        while True:
            try:
                raw = await websocket.receive_text()
            except (WebSocketDisconnect, Exception):
                return
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            if t == "start_browser":
                # Explicit user request to open the mirror (first login or re-login)
                if _log_ws_mod.bot_is_running(user_id):
                    try:
                        await websocket.send_json({"type": "status", "msg": "bot_running"})
                    except Exception:
                        pass
                else:
                    asyncio.ensure_future(mgr.ensure_started())
            elif t == "click":
                if mgr.page: await mgr.click(msg["x"], msg["y"])
            elif t == "key":
                if mgr.page: await mgr.key(msg["key"])
            elif t == "type":
                if mgr.page: await mgr.type_text(msg["text"])
            elif t == "scroll":
                if mgr.page: await mgr.scroll(msg["x"], msg["y"], msg["deltaY"])
            elif t == "save_session":
                if mgr.page:
                    try:
                        await mgr.save_session()
                        await websocket.send_json({"type": "session_saved"})
                        # Login done — close the mirror browser so reopening the
                        # dashboard shows "Connected", not the login mirror again.
                        await mgr.stop()
                    except Exception as exc:
                        print(f"[mirror_ws] save_session error: {exc}")
                        try:
                            await websocket.send_json({"type": "error", "msg": f"Save failed: {exc}"})
                        except Exception:
                            pass
            elif t == "navigate" and mgr.page:
                await mgr.page.goto(msg["url"], wait_until="commit")

    send_task = asyncio.ensure_future(send_frames())
    recv_task = asyncio.ensure_future(recv_input())

    try:
        await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        send_task.cancel()
        recv_task.cancel()
        await asyncio.gather(send_task, recv_task, return_exceptions=True)
