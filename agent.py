"""Run the Gemini-powered Instagram agent."""

import io
import os
import sys

# Force unbuffered stdout so logs appear immediately when piped
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

from dotenv import load_dotenv

from instagram_bot.agent.runner import run_agent_session
from instagram_bot.config.settings import ENV_PATH, GEMINI_API_KEY, SESSION_MINUTES

load_dotenv(ENV_PATH, override=True)


def _ask_goal() -> str:
    # If goal passed as --goal "..." argument, use that
    args = sys.argv[1:]
    if "--goal" in args:
        idx = args.index("--goal")
        if idx + 1 < len(args):
            return args[idx + 1].strip()

    print("\n" + "=" * 55)
    print("  Instagram AI Agent")
    print("=" * 55)
    print("\nWhat do you want to do this session?")
    print("Examples:")
    print("  - comment on 3 real estate posts and like them")
    print("  - send 2 DMs to agents who might need automation")
    print("  - find 2 posts, comment, reply to a comment, follow 1")
    print("  - just browse and like 5 posts naturally")
    print()
    try:
        goal = input("Your goal > ").strip()
    except (EOFError, OSError):
        goal = ""
    if not goal:
        goal = "Browse real estate posts, engage naturally with comments and likes."
    return goal


def _print_token_stats() -> None:
    """Print cumulative token usage across all sessions."""
    import json
    from instagram_bot.config.settings import DATA_DIR
    usage_file = DATA_DIR / "token_usage.json"
    if not usage_file.exists():
        print("No token usage data yet. Run a session first.")
        return

    try:
        sessions = json.loads(usage_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not read token_usage.json: {e}")
        return

    total_input = sum(s.get("input_tokens", 0) for s in sessions)
    total_output = sum(s.get("output_tokens", 0) for s in sessions)
    total_thinking = sum(s.get("thinking_tokens", 0) for s in sessions)
    total_tokens = total_input + total_output + total_thinking
    total_cost = sum(s.get("estimated_cost_usd", 0.0) for s in sessions)

    print(f"\n{'='*52}")
    print(f"  Token Usage — All Sessions ({len(sessions)} total)")
    print(f"{'='*52}")
    print(f"  {'Session':<22} {'Tokens':>10}  {'Cost':>10}")
    print(f"  {'-'*44}")
    for s in sessions:
        date_time = f"{s.get('date','')} {s.get('time','')}"
        tokens = s.get("total_tokens", 0)
        cost = s.get("estimated_cost_usd", 0.0)
        calls = s.get("calls", 0)
        print(f"  {date_time:<22} {tokens:>10,}  ${cost:>9.4f}  ({calls} calls)")
    print(f"  {'-'*44}")
    print(f"  {'TOTAL':<22} {total_tokens:>10,}  ${total_cost:>9.4f}")
    print(f"  {'Input':>28} {total_input:>10,}")
    print(f"  {'Output':>28} {total_output:>10,}")
    print(f"  {'Thinking':>28} {total_thinking:>10,}")
    print(f"{'='*52}\n")


def main() -> None:
    # python agent.py --stats  →  show all-time token usage and exit
    if "--stats" in sys.argv:
        _print_token_stats()
        return

    dry_run = os.getenv("AGENT_DRY_RUN", "").lower() in {"1", "true", "yes"}

    if GEMINI_API_KEY:
        dry_run = False
    elif not dry_run:
        print("No GEMINI_API_KEY in .env — running in dry-run mode.")
        print("Add your key from https://aistudio.google.com/apikey")
        dry_run = True

    goal = _ask_goal()

    print(f"\nStarting session ({SESSION_MINUTES} min) with goal:")
    print(f'  "{goal}"\n')
    sys.stdout.flush()

    run_agent_session(dry_run=dry_run, verify=True, goal=goal)


if __name__ == "__main__":
    main()
