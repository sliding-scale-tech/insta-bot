import asyncio
import json
from pathlib import Path

from playwright.async_api import Browser, Page, Playwright, async_playwright

from instagram_bot.config.settings import DATA_DIR


def _state_path_for(user_id: str) -> Path:
    """Session file path.  'default' maps to data/browser_state.json so the bot
    subprocess (which reads BROWSER_STATE_FILE = data/browser_state.json) picks
    up the same session saved by the mirror."""
    if user_id == "default":
        p = DATA_DIR / "browser_state.json"
    else:
        p = DATA_DIR / "users" / user_id / "browser_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _save_to_convex(user_id: str, state_json: str) -> None:
    try:
        from instagram_bot.db.convex_client import save_browser_session
        save_browser_session(user_id, state_json)
        print(f"  [browser] session saved to Convex for user={user_id}")
    except Exception as exc:
        print(f"  [browser] Convex save skipped: {exc}")


def _load_from_convex(user_id: str) -> str | None:
    try:
        from instagram_bot.db.convex_client import get_browser_session
        return get_browser_session(user_id)
    except Exception:
        return None


class BrowserManager:
    def __init__(self, user_id: str = "default") -> None:
        self.user_id = user_id
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None
        self._starting = False
        self._ready = asyncio.Event()

    def has_saved_session(self) -> bool:
        return _state_path_for(self.user_id).exists()

    async def ensure_started(self) -> None:
        if self.page and not self.page.is_closed():
            return
        if self._starting:
            await self._ready.wait()
            return

        self._starting = True
        self._ready.clear()
        try:
            self._playwright = await async_playwright().start()
            # Headed (not headless) so Instagram sees a real browser. On Linux
            # this needs a display — Xvfb provides it in Docker (DISPLAY=:99);
            # on Windows it opens a normal window. Screenshots stream to the
            # dashboard mirror either way.
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--window-size=1280,800",
                ],
            )

            ctx_kwargs: dict = {
                "viewport": {"width": 1280, "height": 800},
            }

            # Try local session file first
            state_file = _state_path_for(self.user_id)
            if state_file.exists():
                ctx_kwargs["storage_state"] = str(state_file)
                print(f"  [browser] loaded session from file for user={self.user_id}")
            else:
                # Fall back to Convex
                state_json = _load_from_convex(self.user_id)
                if state_json:
                    # Write to local file so Playwright can read it
                    state_file.write_text(state_json, encoding="utf-8")
                    ctx_kwargs["storage_state"] = str(state_file)
                    print(f"  [browser] loaded session from Convex for user={self.user_id}")

            context = await self._browser.new_context(**ctx_kwargs)
            # Prevent tab pileup: when a link opens a new tab (target=_blank,
            # Threads/profile promos, etc.), adopt the newest page as the mirror
            # target and close the old one so tabs can never accumulate.
            context.on("page", self._on_new_page)
            self.page = await context.new_page()
            await self.page.goto("https://www.instagram.com/", wait_until="commit")
        finally:
            self._starting = False
            self._ready.set()

    def _on_new_page(self, new_page: Page) -> None:
        old = self.page
        self.page = new_page
        if old is not None and old is not new_page:
            asyncio.ensure_future(self._safe_close(old))

    @staticmethod
    async def _safe_close(page: Page) -> None:
        try:
            if not page.is_closed():
                await page.close()
        except Exception:
            pass

    async def screenshot(self) -> bytes:
        assert self.page
        return await self.page.screenshot(type="jpeg", quality=70)

    async def click(self, x: float, y: float) -> None:
        assert self.page
        await self.page.mouse.click(x, y)

    async def key(self, key: str) -> None:
        assert self.page
        await self.page.keyboard.press(key)

    async def type_text(self, text: str) -> None:
        assert self.page
        await self.page.keyboard.type(text)

    async def scroll(self, x: float, y: float, delta_y: float) -> None:
        assert self.page
        await self.page.mouse.wheel(delta_x=0, delta_y=delta_y)

    def get_url(self) -> str:
        if self.page and not self.page.is_closed():
            return self.page.url
        return ""

    async def save_session(self) -> None:
        assert self.page
        dest = _state_path_for(self.user_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        await self.page.context.storage_state(path=str(dest))
        print(f"  [browser] session saved to {dest} for user={self.user_id}")
        # Push to Convex in background — don't block or fail the save
        state_json = dest.read_text(encoding="utf-8")
        asyncio.ensure_future(asyncio.to_thread(_save_to_convex, self.user_id, state_json))

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self.page = None
        self._playwright = None

    async def logout(self) -> None:
        """Instagram logout: close the browser and delete the saved session
        (local file + Convex) so the next Start Browser requires a fresh login."""
        await self.stop()
        state_file = _state_path_for(self.user_id)
        try:
            if state_file.exists():
                state_file.unlink()
        except Exception as exc:
            print(f"  [browser] could not delete session file: {exc}")
        try:
            from instagram_bot.db.convex_client import delete_browser_session
            delete_browser_session(self.user_id)
        except Exception as exc:
            print(f"  [browser] Convex session delete skipped: {exc}")


class BrowserRegistry:
    """Maps user_id → BrowserManager, one instance per user."""

    def __init__(self) -> None:
        self._managers: dict[str, BrowserManager] = {}

    def get(self, user_id: str) -> BrowserManager:
        if user_id not in self._managers:
            self._managers[user_id] = BrowserManager(user_id)
        return self._managers[user_id]

    async def stop_all(self) -> None:
        for mgr in self._managers.values():
            await mgr.stop()
        self._managers.clear()


registry = BrowserRegistry()
