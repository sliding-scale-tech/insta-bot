"""
Auth resolution: Clerk JWT when configured, simple token otherwise.

If CLERK_SECRET_KEY is set, every request must carry a valid Clerk JWT and the
resolved user_id is the Clerk `sub`. A missing/invalid token is rejected (401) —
there is no anonymous "default" fallback in Clerk mode.

Without CLERK_SECRET_KEY, falls back to simple-token mode: a request matching
AUTH_TOKEN (or any request if AUTH_TOKEN is unset) resolves to user_id="default".
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException

# Load .env so the server picks up CLERK_* / AUTH_TOKEN even when launched
# directly via uvicorn.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _clerk_enabled() -> bool:
    return bool(os.environ.get("CLERK_SECRET_KEY", "").strip())


def _jwks_url() -> str:
    url = os.environ.get("CLERK_JWKS_URL", "").strip()
    if url:
        return url
    # Derive from the publishable key domain, e.g.
    # pk_test_<base64("ruling-civet-84.clerk.accounts.dev$")>
    pk = os.environ.get("CLERK_PUBLISHABLE_KEY", "").strip()
    if not pk:
        return ""
    try:
        raw = pk.split("_", 2)[-1]
        domain = base64.b64decode(raw + "==").decode().rstrip("$")
        return f"https://{domain}/.well-known/jwks.json"
    except Exception:
        return ""


async def _verify_clerk(token: str) -> str | None:
    if not token:
        return None
    jwks_url = _jwks_url()
    if not jwks_url:
        print("[auth] Clerk enabled but no JWKS url (set CLERK_PUBLISHABLE_KEY or CLERK_JWKS_URL)")
        return None
    try:
        import httpx
        from jose import jwt as jose_jwt

        async with httpx.AsyncClient(timeout=5.0) as client:
            jwks = (await client.get(jwks_url)).json()
        payload = jose_jwt.decode(
            token, jwks, algorithms=["RS256"], options={"verify_aud": False}
        )
        return payload.get("sub")
    except Exception as exc:
        print(f"[auth] Clerk token verification failed: {exc}")
        return None


async def resolve_user_id(request, token: str = "") -> str:
    """Resolve the user_id for an HTTP request or WebSocket.

    HTTP: token via `Authorization: Bearer <jwt>` header or `?token=`.
    WebSocket: token via `?token=` query param.
    """
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        if not token:
            token = request.query_params.get("token", "")

    if _clerk_enabled():
        uid = await _verify_clerk(token)
        if uid:
            return uid
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Simple-token mode (no Clerk configured)
    auth_token = os.environ.get("AUTH_TOKEN", "").strip()
    if auth_token and token != auth_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return "default"
