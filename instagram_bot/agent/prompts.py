"""System prompt for the Gemini Instagram agent.

The template lives in instagram_bot/agent/prompt_store.py (key: "system") and can
be overridden from the dashboard's Prompts tab — this module just fills it in.
"""

from instagram_bot.agent.prompt_store import render
from instagram_bot.config.settings import (
    AGENT_PERSONA,
    MAX_COMMENTS_PER_SESSION,
    MAX_DMS_PER_SESSION,
    MAX_FOLLOWS_PER_SESSION,
    MAX_LIKES_PER_SESSION,
    MAX_REPLIES_PER_SESSION,
)


def build_system_prompt() -> str:
    caps = (
        f"comments {MAX_COMMENTS_PER_SESSION} | DMs {MAX_DMS_PER_SESSION} | "
        f"likes {MAX_LIKES_PER_SESSION} | follows {MAX_FOLLOWS_PER_SESSION} | "
        f"replies {MAX_REPLIES_PER_SESSION}"
    )
    return render("system", persona=AGENT_PERSONA, caps=caps)
