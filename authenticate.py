"""
Authenticate for instagrapi + browser fallback.

Run: python authenticate.py
"""

from instagram_bot.auth.browser import browser_login
from instagram_bot.auth.instagrapi import (
    create_client,
    get_credentials,
    try_browser_session_import,
    try_password_login,
)
from instagram_bot.config.settings import ENV_PATH, SESSION_FILE
from dotenv import load_dotenv

load_dotenv(ENV_PATH, override=True)


def main() -> None:
    print("Instagram Bot — Login\n")
    print("Step 1: Trying instagrapi (official API)...")

    username, password = get_credentials()
    client = None

    if username and password:
        client = try_password_login(username, password)

    if client:
        print(f"\nSuccess with instagrapi as @{client.username}")
        print(f"Session saved to {SESSION_FILE}")
        print("Run the bot: python main.py")
        return

    print("\ninstagrapi password login blocked (Facebook-linked account).")
    print("Step 2: Chrome login (Facebook / email supported)\n")

    print("Choose login method:")
    print("  1. Facebook")
    print("  2. Email")
    print("  3. Username + password")
    choice = input("\nEnter 1, 2, or 3 [default: 1]: ").strip() or "1"
    methods = {"1": "facebook", "2": "email", "3": "username"}
    method = methods.get(choice, "facebook")

    browser_login(method=method)

    print("\nStep 3: Importing browser session into instagrapi...")
    client = try_browser_session_import(create_client())

    if client:
        print(f"\ninstagrapi ready as @{client.username}")
        print("Run the bot: python main.py")
    else:
        print("\nBrowser login saved, but instagrapi API session is limited.")
        print("Run the bot in browser mode: USE_BROWSER=true python main.py")


if __name__ == "__main__":
    main()
