"""Track Gemini API token usage and estimate cost per session."""

import json
import time
from pathlib import Path

from instagram_bot.config.settings import DATA_DIR, GEMINI_MODEL

# Gemini 2.5 Flash pricing (per 1M tokens, USD)
# Source: Google AI pricing as of 2025
_PRICING: dict[str, dict] = {
    "gemini-2.5-flash": {
        # prompts <= 200K context window
        "input_per_m": 0.075,
        "output_per_m": 0.30,
        "thinking_per_m": 3.50,
    },
    "gemini-2.5-pro": {
        "input_per_m": 1.25,
        "output_per_m": 10.00,
        "thinking_per_m": 3.50,
    },
    "gemini-2.0-flash": {
        "input_per_m": 0.10,
        "output_per_m": 0.40,
        "thinking_per_m": 0.0,
    },
}

USAGE_FILE = DATA_DIR / "token_usage.json"


def _get_price(model: str) -> dict:
    for key, price in _PRICING.items():
        if key in model.lower():
            return price
    return {"input_per_m": 0.075, "output_per_m": 0.30, "thinking_per_m": 3.50}


class TokenTracker:
    def __init__(self, model: str = ""):
        self.model = model or GEMINI_MODEL
        self._price = _get_price(self.model)
        self.session_input = 0
        self.session_output = 0
        self.session_thinking = 0
        self.session_calls = 0
        self.session_start = time.time()
        self._log: list[dict] = []

    def record(self, call_type: str, input_tokens: int, output_tokens: int, thinking_tokens: int = 0) -> dict:
        self.session_input += input_tokens
        self.session_output += output_tokens
        self.session_thinking += thinking_tokens
        self.session_calls += 1

        cost = self._calc_cost(input_tokens, output_tokens, thinking_tokens)

        entry = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "call": call_type,
            "input": input_tokens,
            "output": output_tokens,
            "thinking": thinking_tokens,
            "cost_usd": round(cost, 6),
        }
        self._log.append(entry)
        return entry

    def _calc_cost(self, input_t: int, output_t: int, thinking_t: int) -> float:
        p = self._price
        return (
            input_t / 1_000_000 * p["input_per_m"]
            + output_t / 1_000_000 * p["output_per_m"]
            + thinking_t / 1_000_000 * p["thinking_per_m"]
        )

    def session_cost(self) -> float:
        return self._calc_cost(self.session_input, self.session_output, self.session_thinking)

    def summary(self) -> dict:
        cost = self.session_cost()
        return {
            "model": self.model,
            "calls": self.session_calls,
            "input_tokens": self.session_input,
            "output_tokens": self.session_output,
            "thinking_tokens": self.session_thinking,
            "total_tokens": self.session_input + self.session_output + self.session_thinking,
            "estimated_cost_usd": round(cost, 6),
            "session_minutes": round((time.time() - self.session_start) / 60, 1),
        }

    def save(self) -> None:
        """Append this session's usage to the persistent log file."""
        existing: list[dict] = []
        if USAGE_FILE.exists():
            try:
                existing = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        session_record = {
            "date": time.strftime("%Y-%m-%d"),
            "time": time.strftime("%H:%M:%S"),
            **self.summary(),
            "calls_detail": self._log[-50:],  # keep last 50 call details
        }
        existing.append(session_record)

        USAGE_FILE.write_text(
            json.dumps(existing, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def cumulative(self) -> dict:
        """Sum all saved sessions from the usage file."""
        sessions: list[dict] = []
        if USAGE_FILE.exists():
            try:
                sessions = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
            except Exception:
                sessions = []
        total_input = sum(s.get("input_tokens", 0) for s in sessions)
        total_output = sum(s.get("output_tokens", 0) for s in sessions)
        total_thinking = sum(s.get("thinking_tokens", 0) for s in sessions)
        total_cost = sum(s.get("estimated_cost_usd", 0.0) for s in sessions)
        return {
            "sessions": len(sessions),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "thinking_tokens": total_thinking,
            "total_tokens": total_input + total_output + total_thinking,
            "total_cost_usd": round(total_cost, 6),
        }

    def print_summary(self) -> None:
        s = self.summary()
        print(f"\n{'='*50}")
        print(f"Gemini Token Usage — {s['model']}")
        print(f"  Calls:          {s['calls']}")
        print(f"  Input tokens:   {s['input_tokens']:,}")
        print(f"  Output tokens:  {s['output_tokens']:,}")
        if s['thinking_tokens']:
            print(f"  Thinking tokens:{s['thinking_tokens']:,}")
        print(f"  Total tokens:   {s['total_tokens']:,}")
        print(f"  Estimated cost: ${s['estimated_cost_usd']:.4f} USD")
        print(f"  Session time:   {s['session_minutes']} min")

        # Show all-time cumulative after saving (file already includes this session)
        try:
            c = self.cumulative()
            print(f"  --- All-time ({c['sessions']} sessions) ---")
            print(f"  Total tokens:   {c['total_tokens']:,}")
            print(f"  Total cost:     ${c['total_cost_usd']:.4f} USD")
        except Exception:
            pass

        print(f"{'='*50}")
