import asyncio
import os
import signal
import sys
from collections import deque
from pathlib import Path
from typing import Awaitable, Callable

_POSIX = os.name != "nt"

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.auth import resolve_user_id

router = APIRouter()

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_BUFFER_SIZE = 500

# Per-user state
_bot_processes: dict[str, asyncio.subprocess.Process] = {}
_log_clients: dict[str, set[WebSocket]] = {}
_log_queues: dict[str, asyncio.Queue[str]] = {}
# Rolling history so a client that connects late (tab switch / refresh) can
# replay recent lines instead of seeing an empty log.
_log_buffers: dict[str, deque[str]] = {}


def _queue_for(user_id: str) -> asyncio.Queue[str]:
    if user_id not in _log_queues:
        _log_queues[user_id] = asyncio.Queue()
    return _log_queues[user_id]


def _buffer_for(user_id: str) -> deque[str]:
    if user_id not in _log_buffers:
        _log_buffers[user_id] = deque(maxlen=_LOG_BUFFER_SIZE)
    return _log_buffers[user_id]


def emit_log(user_id: str, line: str) -> None:
    """Push a synthetic log line (e.g. job boundaries, completion) into the
    same stream the bot subprocess uses, so the UI shows it inline."""
    _buffer_for(user_id).append(line)
    _queue_for(user_id).put_nowait(line)


@router.websocket("/ws/log")
async def log_ws(websocket: WebSocket, token: str = ""):
    try:
        user_id = await resolve_user_id(websocket, token=token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    _log_clients.setdefault(user_id, set()).add(websocket)

    # Replay recent history so switching tabs / refreshing doesn't wipe logs.
    for line in list(_buffer_for(user_id)):
        try:
            await websocket.send_text(line)
        except Exception:
            _log_clients.get(user_id, set()).discard(websocket)
            return

    q = _queue_for(user_id)
    try:
        while True:
            line = await q.get()
            for client in list(_log_clients.get(user_id, [])):
                try:
                    await client.send_text(line)
                except Exception:
                    _log_clients[user_id].discard(client)
    except WebSocketDisconnect:
        pass
    finally:
        _log_clients.get(user_id, set()).discard(websocket)


async def _stream_stdout(process: asyncio.subprocess.Process, user_id: str) -> None:
    assert process.stdout
    q = _queue_for(user_id)
    buf = _buffer_for(user_id)
    async for line_bytes in process.stdout:
        line = line_bytes.decode("utf-8", errors="replace").rstrip()
        buf.append(line)
        await q.put(line)


async def start_bot_subprocess(
    goal: str,
    env: dict,
    user_id: str = "default",
    on_exit: Callable[[int], Awaitable[None]] | None = None,
) -> None:
    proc = _bot_processes.get(user_id)
    if proc and proc.returncode is None:
        return

    agent_path = _PROJECT_ROOT / "agent.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",                 # unbuffered stdout so the live log streams in real time
        str(agent_path),
        "--goal",
        goal,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
        cwd=str(_PROJECT_ROOT),
        # Own process group so we can kill the agent AND its Chromium children
        # together (prevents orphaned browsers = concurrent-session ban risk).
        start_new_session=_POSIX,
    )
    _bot_processes[user_id] = process

    async def _run_and_wait() -> None:
        await _stream_stdout(process, user_id)
        rc = await process.wait()
        if on_exit is not None:
            try:
                await on_exit(rc)
            except Exception as exc:
                print(f"[log_ws] on_exit error: {exc}")

    asyncio.ensure_future(_run_and_wait())


def _signal_tree(proc: asyncio.subprocess.Process, sig: int) -> None:
    """Signal the whole process group (agent + Chromium children) on POSIX,
    or just the process on Windows."""
    try:
        if _POSIX:
            os.killpg(os.getpgid(proc.pid), sig)
        else:
            proc.terminate() if sig == signal.SIGTERM else proc.kill()
    except (ProcessLookupError, PermissionError):
        pass
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def stop_bot_subprocess(user_id: str = "default") -> None:
    proc = _bot_processes.get(user_id)
    if proc and proc.returncode is None:
        _signal_tree(proc, signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            _signal_tree(proc, signal.SIGKILL)
    _bot_processes.pop(user_id, None)


def bot_is_running(user_id: str = "default") -> bool:
    proc = _bot_processes.get(user_id)
    return proc is not None and proc.returncode is None


def bot_pid(user_id: str = "default") -> int | None:
    proc = _bot_processes.get(user_id)
    return proc.pid if proc and proc.returncode is None else None
