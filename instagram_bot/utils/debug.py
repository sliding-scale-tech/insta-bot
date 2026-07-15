"""Save screenshots/HTML when automation gets stuck."""

from instagram_bot.config.settings import DEBUG_DIR


def save_debug(page, label: str) -> None:
    DEBUG_DIR.mkdir(exist_ok=True)
    safe = label.replace(" ", "_").replace("/", "-")
    page.screenshot(path=str(DEBUG_DIR / f"{safe}.png"), full_page=True)
    (DEBUG_DIR / f"{safe}.html").write_text(page.content(), encoding="utf-8")
    print(f"  [debug] saved debug_output/{safe}.png")
