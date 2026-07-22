"""Gemini 2.5 Flash client with function calling, comment generation, and post evaluation."""

import json
import time
from typing import Any

from instagram_bot.agent.token_tracker import TokenTracker
from instagram_bot.config.settings import AGENT_MISSION, AGENT_PERSONA, GEMINI_API_KEY, GEMINI_MODEL
from instagram_bot.tools.registry import get_tool_schemas


def _require_genai():
    try:
        from google import genai
        from google.genai import types

        return genai, types
    except ImportError as error:
        raise SystemExit(
            "Install google-genai:\n  pip install google-genai"
        ) from error


def _build_gemini_tools(types) -> list:
    declarations = []
    for schema in get_tool_schemas():
        declarations.append(
            types.FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=schema["parameters"],
            )
        )
    return [types.Tool(function_declarations=declarations)]


class GeminiAgent:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise SystemExit(
                "GEMINI_API_KEY missing from .env\n"
                "Get a key: https://aistudio.google.com/apikey"
            )
        genai, types = _require_genai()
        self._types = types
        self._client = genai.Client(api_key=GEMINI_API_KEY)
        self._model = GEMINI_MODEL
        self._tools = _build_gemini_tools(types)
        self._history: list[Any] = []
        self.tokens = TokenTracker(model=GEMINI_MODEL)

    def complete_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        label: str = "complete_text",
    ) -> str:
        """Single-shot text completion (used by the day planner)."""
        types = self._types
        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                label,
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        return (response.text or "").strip()

    def generate_post_caption(self, image_bytes: bytes, mime_type: str, hint: str = "") -> str:
        """Vision-based Instagram caption writer for the Posts tab's "Write with AI"."""
        from instagram_bot.agent.prompt_store import render

        types = self._types
        prompt = render(
            "generate_caption",
            persona=AGENT_PERSONA,
            hint_line=f"- Context from the user: {hint}" if hint else "",
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.85,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "generate_caption",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        return (response.text or "").strip()

    def evaluate_post_for_comment(
        self,
        caption: str,
        author: str,
        comments: list,
        commented_urls: list[str],
        mission: str = "",
    ) -> dict:
        """Decide whether to comment on this post. Returns {should_comment, confidence, reason, skip_reason}."""
        types = self._types
        mission = mission or AGENT_MISSION

        existing = ""
        if comments:
            existing = "\n".join(
                f"- @{c.get('username', '?')}: {c.get('text', '')[:100]}"
                for c in comments[:5]
            )

        from instagram_bot.agent.prompt_store import render

        prompt = render(
            "evaluate_post",
            persona=AGENT_PERSONA,
            mission=mission,
            commented_count=len(commented_urls),
            author=author or "unknown",
            caption=caption[:900] or "(no caption visible)",
            existing_comments=f"Top comments:{chr(10)}{existing}" if existing else "",
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "evaluate_post",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )

        raw = (response.text or "").strip()
        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()

        try:
            parsed = json.loads(raw)
            return {
                "should_comment": bool(parsed.get("should_comment", False)),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": str(parsed.get("reason", "")),
                "skip_reason": parsed.get("skip_reason"),
            }
        except Exception:
            return {
                "should_comment": False,
                "confidence": 0.0,
                "reason": "JSON parse failed",
                "skip_reason": f"Raw response: {raw[:100]}",
            }

    def generate_helpful_comment(
        self,
        caption: str,
        author: str = "",
        comments: list | None = None,
        goal: str = "",
    ) -> str:
        """Write a genuine, specific comment based on post content."""
        types = self._types
        existing = ""
        if comments:
            existing = "\n".join(
                f"- @{c.get('username', '?')}: {c.get('text', '')[:100]}"
                for c in comments[:5]
            )

        from instagram_bot.agent.prompt_store import render

        prompt = render(
            "generate_comment",
            persona=AGENT_PERSONA,
            goal=goal or "(no specific focus)",
            author=author or "unknown",
            caption=caption or "(no caption visible)",
            existing_comments=f"Existing comments:{chr(10)}{existing}" if existing else "",
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.85,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "generate_comment",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        text = (response.text or "").strip().strip('"')
        if not text:
            raise RuntimeError("Gemini returned empty comment")
        return text[:500]

    def generate_reply_to_comment(
        self,
        comment_text: str,
        comment_author: str,
        post_caption: str,
        post_author: str,
    ) -> str:
        """Write a natural, human reply to someone else's comment on a real estate post."""
        types = self._types
        prompt = f"""{AGENT_PERSONA}

You are replying to a comment on an Instagram real estate post. Write like a real person — conversational, warm, specific.

Post by @{post_author or "unknown"}:
Caption snippet: {post_caption[:300] or "(no caption)"}

Comment by @{comment_author or "someone"}:
"{comment_text[:200]}"

Write ONE short reply (1-2 sentences max). Rules:
- Respond directly to what they said
- Sound like a knowledgeable real estate person, not a bot
- Can agree, add info, ask a follow-up question, or share a relevant tip
- NO hashtags. NO excessive emojis. Natural tone.
- Do NOT just say "great comment!" or empty praise

Reply with ONLY the reply text, nothing else."""

        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.85,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "generate_reply",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        return (response.text or "").strip().strip('"')[:300]

    def generate_dm_message(self, username: str, context: str = "") -> str:
        """Write a genuine first DM — no pitch, no mention of services, just human curiosity."""
        types = self._types
        prompt = f"""{AGENT_PERSONA}

Write a first DM to @{username} on Instagram.
{f"Context about them: {context}" if context else ""}

This is a COLD first message. Rules:
- 1 sentence, under 15 words — short and natural
- End with a QUESTION about something specific they do or posted
- Sound like a real person who genuinely noticed something about them
- Reference something SPECIFIC from the context (their market, niche, location, years of experience)
- NEVER say "Congratulations", "Great post!", "I love your content", or any generic compliment as the whole message
- NEVER mention automation, technology, tools, services, or that you want to sell anything
- NEVER ask for a "quick chat", "call", or pitch anything
- Do NOT compliment them — ask about them
- Good: "How long have you been working the [area] market?"
- Bad: "Congratulations on joining the team! That's fantastic news."

Reply with ONLY the message text, nothing else."""

        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.9,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "generate_dm",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        return (response.text or "").strip()[:300]

    def generate_dm_reply(self, thread_context: str = "") -> str:
        """Read the DM thread context and write a short warm-lead reply in English."""
        types = self._types
        prompt = f"""{AGENT_PERSONA}

You are having a natural DM conversation on Instagram with a real estate professional. Your goal is to move from a cold intro to a warm conversation by genuinely understanding their challenges — NOT to pitch or sell anything yet.

Conversation so far:
{thread_context or "(no messages visible)"}

Write ONE short reply IN ENGLISH. Rules:
- 1-2 sentences MAX — keep it conversational, like texting a new contact
- Reply in English only, no matter what language they write in
- Sound like a real person — warm, curious, genuine
- If they replied positively: ask ONE open question about their current challenges
  (e.g. lead gen, follow-up, time management, marketing — pick the most relevant from context)
- If they asked about you/what you do: give a brief, honest 1-sentence answer then redirect to them
- If they seem cold or uninterested: be gracious and leave the door open
- NEVER pitch automation, tools, or services directly — just build rapport and understand their world
- No hashtags, no emojis unless they used them, no links

Reply with ONLY the reply text, nothing else."""

        response = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.85,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "generate_dm_reply",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )
        return (response.text or "").strip()[:300]

    def decide(self, user_message: str) -> list[dict[str, Any]]:
        types = self._types

        self._history.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

        # Keep history bounded: first message (system+kickoff) + up to ~8 recent exchanges.
        # This prevents unbounded context growth that causes 429s and high costs.
        # The cut point must land on a plain user text turn (never mid function_call/
        # function_response pair), otherwise Gemini rejects the next request with a 400.
        _MAX_HISTORY = 17  # 1 kickoff + 8 exchanges × 2 messages each
        if len(self._history) > _MAX_HISTORY:
            cutoff = len(self._history) - (_MAX_HISTORY - 1)
            while cutoff < len(self._history):
                content = self._history[cutoff]
                parts = content.parts or []
                is_safe_cut = content.role == "user" and all(
                    getattr(p, "function_response", None) is None for p in parts
                )
                if is_safe_cut:
                    break
                cutoff += 1
            self._history = [self._history[0]] + self._history[cutoff:]

        response = None
        for _attempt in range(5):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=self._history,
                    config=types.GenerateContentConfig(
                        tools=self._tools,
                        temperature=0.7,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                break
            except Exception as exc:
                err = str(exc)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    wait = 60 * (_attempt + 1)
                    print(f"  [rate limit] 429 received — waiting {wait}s before retry ({_attempt + 1}/5) ...")
                    time.sleep(wait)
                else:
                    raise
        if response is None:
            raise RuntimeError("Gemini API: 5 rate-limit retries exhausted")

        if response.usage_metadata:
            u = response.usage_metadata
            self.tokens.record(
                "decide",
                input_tokens=getattr(u, "prompt_token_count", 0) or 0,
                output_tokens=getattr(u, "candidates_token_count", 0) or 0,
                thinking_tokens=getattr(u, "thoughts_token_count", 0) or 0,
            )

        self._history.append(response.candidates[0].content)

        tool_calls: list[dict[str, Any]] = []
        for part in response.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                tool_calls.append({"name": fc.name, "arguments": args})

        return tool_calls

    def report_tool_result(self, name: str, result: dict) -> None:
        types = self._types
        self._history.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=name,
                            response={"result": result},
                        )
                    )
                ],
            )
        )
