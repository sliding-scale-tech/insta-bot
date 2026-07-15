"""Instagram bot entry point."""

import os

from dotenv import load_dotenv

from instagram_bot.bots.browser import run_browser_bot
from instagram_bot.bots.instagrapi import run_instagrapi_bot
from instagram_bot.config.settings import ENV_PATH

load_dotenv(ENV_PATH, override=True)


def main() -> None:
    force_browser = os.getenv("USE_BROWSER", "").lower() in {"1", "true", "yes"}

    if force_browser:
        run_browser_bot()
        return

    try:
        run_instagrapi_bot()
    except SystemExit as error:
        message = str(error)
        if "browser" in message.lower() or "facebook" in message.lower():
            print("\nFalling back to browser mode...")
            run_browser_bot()
        else:
            raise
    except Exception as error:
        print(f"\ninstagrapi error: {error}")
        print("Falling back to browser mode...")
        run_browser_bot()


if __name__ == "__main__":
    main()
