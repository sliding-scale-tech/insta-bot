"""Shared Playwright page context for agent tools."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolContext:
    page: Any
    gemini: Any = None
    # The user's goal for this session. Drives which hashtags to browse and what
    # counts as a relevant post — overrides the default AGENT_MISSION niche.
    goal: str = ""
    memory: dict = field(default_factory=lambda: {
        "commented_posts": [],
        "replied_comments": [],
        "liked_items": [],
    })
