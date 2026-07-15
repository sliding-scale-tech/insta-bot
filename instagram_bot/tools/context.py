"""Shared Playwright page context for agent tools."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolContext:
    page: Any
    gemini: Any = None
    memory: dict = field(default_factory=lambda: {
        "commented_posts": [],
        "replied_comments": [],
        "liked_items": [],
    })
