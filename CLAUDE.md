# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Playwright-driven Instagram automation bot with two run modes:

1. **Gemini agent mode** (`agent.py`) — the active, developed system. A Gemini 2.5 Flash model decides which tool to call each step (function calling loop), browsing hashtags, evaluating posts, and commenting/liking/DMing real-estate content autonomously for a timed session.
2. **Legacy scripted bot** (`main.py`) — tries `instagrapi` (official API) first, falls back to the Playwright browser bot (`instagram_bot/bots/`). Simpler, fixed-goal (comment/DM a hashtag N times). Not under active development — most new work targets the agent path.

## Commands

```powershell
# Run the Gemini agent (interactive goal prompt, or pass --goal)
python agent.py
python agent.py --goal "comment on 2 posts and send 2 DMs"

# Show cumulative token usage / cost across all sessions
python agent.py --stats

# First-time / re-login (browser login, saves session to data/browser_state.json)
python authenticate.py

# Legacy scripted bot (instagrapi, falls back to browser)
python main.py

# Manual tool-by-tool verification (no Gemini API key needed)
python scripts/test_tools.py
```

Env setup before running: `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUNBUFFERED="1"` (keeps piped output flushing correctly).

There is no lint/test-framework config (no pytest, no linter configured) — `scripts/test_tools.py` and the other `scripts/debug_*.py` files are manual, screenshot-driven verification scripts, not an automated test suite.

### Debugging a single tool/flow

`scripts/debug_flow.py`, `scripts/debug_comment.py`, `scripts/debug_password.py`, `scripts/debug_submit.py` each exercise one narrow flow and dump HTML/screenshots to `debug_output/`. `scripts/parse_debug.py` reads a saved debug HTML dump offline (no browser) to test `page_parser.py` selectors in isolation.

## CRITICAL safety rule

**Never run more than one Playwright/Chrome browser instance at once** — Instagram flags concurrent sessions from the same account and can block it. Before starting a new run, kill any lingering python process:

```powershell
Get-Process python | Stop-Process -Force
```

`runner.py` also self-enforces this via a PID file at `data/bot.pid` — `_kill_previous_session()` taskkills any leftover bot process at session start.

## Architecture (Gemini agent path)

```
agent.py                          # entry point: asks for a goal, calls run_agent_session()
  → instagram_bot/agent/runner.py       # timed session loop (SESSION_MINUTES), drives everything below
      → instagram_bot/agent/gemini_client.py   # GeminiAgent.decide() picks tool(s) via function calling;
                                                # also generates comment/DM/reply text; tracks tokens
      → instagram_bot/agent/prompts.py         # system prompt: tool usage rules, workflow, mission/persona
      → instagram_bot/agent/memory.py          # SessionMemory: in-session dedup (commented/liked/DM'd this run)
      → instagram_bot/agent/persistent_memory.py  # cross-session dedup: data/commented_posts.json,
                                                    # normalize_url() so query params/trailing slash don't
                                                    # defeat duplicate detection
      → instagram_bot/tools/registry.py        # TOOLS dict: name → {fn, description, JSON-schema params}.
                                                # This is the single source of truth for what Gemini can call —
                                                # add a tool here (+ its schema) to expose new capability.
          → instagram_bot/tools/navigation.py  # scroll_down, open_hashtag, open_post, go_home/back, open_profile,
                                                #   open_inbox, open_thread
          → instagram_bot/tools/perception.py  # observe_page_state/feed/current_post/comments,
                                                #   evaluate_current_post (asks Gemini should_comment/confidence/reason,
                                                #   checks persistent memory first to skip the API call if already commented)
          → instagram_bot/tools/actions.py     # like_post/comment, ai_comment_on_post, ai_reply_to_comment,
                                                #   follow/unfollow, send_dm, read_inbox, ai_reply_to_dm, skip_post, wait
          → instagram_bot/tools/context.py     # ToolContext — carries the Playwright `page` + session memory dict
                                                #   through every tool call
      → instagram_bot/perception/page_parser.py   # DOM → JSON: parse_feed_posts, _extract_post_via_js
                                                    #   (caption extraction, JS-first with og:description fallback),
                                                    #   parse_comments
      → instagram_bot/utils/verify.py          # ToolVerifier: screenshots + JSON after each tool call, written to
                                                #   debug_output/tool_checks/<timestamp>/report.html
  → instagram_bot/auth/browser.py       # Playwright session load/login (data/browser_state.json), handles
                                          #   Meta "Continue" screen, password popup, cookie/notification dismissal
  → instagram_bot/config/settings.py    # all env vars + paths in one place (PROJECT_ROOT-relative), including
                                          #   MAX_*_PER_SESSION caps, GEMINI_MODEL, AGENT_MISSION/PERSONA,
                                          #   SEARCH_HASHTAGS rotation
```

**Tool-call flow per step:** `runner.py` builds a prompt (goal + memory state + last tool result) → `gemini_client.decide()` returns one or more tool calls → `registry.execute_tool()` dispatches to the matching function in `navigation.py`/`perception.py`/`actions.py` → result screenshotted/logged by `verify.py` → fed back into the next `decide()` call. Session ends on `end_session` tool call, `MAX_*_PER_SESSION` caps reached, or the `SESSION_MINUTES` timer.

**Duplicate-engagement protection (layered):**
1. `data/commented_posts.json` (via `persistent_memory.py`) — survives across runs/days.
2. `SessionMemory` (`memory.py`) — pre-populated from the file above, tracks the current run.
3. DOM-level check for the bot's own username already present in a post's comments.

`evaluate_current_post` must be called before any commenting tool — it's the gate that consults memory (no API call if already commented) and, if not a duplicate, asks Gemini whether the post is worth engaging with.

## Configuration (`.env`, not committed — see `.env.example`)

Key variables read in `instagram_bot/config/settings.py`:
- `username`/`IG_USERNAME`, `password`/`IG_PASSWORD`, `email`, `LOGIN_METHOD` — credentials, read directly from the `.env` file (not just `os.environ`, to dodge Windows env var collisions)
- `GEMINI_API_KEY`, `GEMINI_MODEL` — agent brain. No key → agent runs in dry-run mode (no live actions).
- `HASHTAG_TO_SEARCH`, `SEARCH_HASHTAGS` — comma-separated rotation list for browsing
- `AGENT_MISSION`, `AGENT_PERSONA` — free-text goal/voice fed into every Gemini prompt
- `SESSION_MINUTES` — session length
- `MAX_COMMENTS_PER_SESSION`, `MAX_REPLIES_PER_SESSION`, `MAX_LIKES_PER_SESSION`, `MAX_FOLLOWS_PER_SESSION`, `MAX_DMS_PER_SESSION` — hard caps enforced in `runner.py`, independent of what Gemini decides
- `SESSION_FILE`, `BROWSER_STATE_FILE`, `BROWSER_COOKIES_FILE` — override storage paths (default under `data/`)
- `USE_BROWSER` — forces `main.py` to skip `instagrapi` and go straight to the Playwright bot

Legacy data files at the project root (`browser_state.json`, `browser_cookies.json`, `session.json`) are auto-migrated into `data/` on startup by `_migrate_legacy_data_files()`.

## Working with the DOM parser

Instagram's DOM/selectors change frequently and silently break scraping. When a tool misbehaves, check `debug_output/` first — `verify.py` and the `scripts/debug_*.py` helpers save the actual HTML + screenshot at the point of failure, which is far faster than re-running the live agent to reproduce. `parse_debug.py` lets you replay a saved HTML dump through `page_parser.py` without touching the browser at all.
