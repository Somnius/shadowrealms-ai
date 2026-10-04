"""
Storyteller prompt helpers (pure): token estimates, the context budget, room history
formatting, prompt shrinking after a context overflow, and the Greek reply script check.

Token estimate: measured on LM Studio gemma-4-e2b (2026-10-04) English ~5.3 characters per
token, Greek ~2.4. We count ASCII at 3.5 and everything else at 2.0 per token, so the
estimate errs high for both (and for Llama-based models such as Krikri).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

ASCII_CHARS_PER_TOKEN = 3.5
OTHER_CHARS_PER_TOKEN = 2.0
# Template text we don't see when budgeting: master system prompt, language line, chat
# template tokens, the RAG section headers.
PROMPT_RESERVE_TOKENS = 400
DEFAULT_CONTEXT_TOKENS = 8192
# Longest Storyteller reply quoted in the room history (characters); the scene so far
# matters, not every word of it.
HISTORY_REPLY_CHARS = 700
HISTORY_USER_CHARS = 500


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    ascii_n = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_n
    return int(ascii_n / ASCII_CHARS_PER_TOKEN + other / OTHER_CHARS_PER_TOKEN) + 1


def messages_tokens(messages: Iterable[Dict[str, str]]) -> int:
    return sum(estimate_tokens(m.get("content") or "") + 4 for m in messages)


def prompt_budget(context_tokens: int, max_reply_tokens: int) -> int:
    """Tokens the prompt may use: the model's context minus the reply and a reserve."""
    return max(512, int(context_tokens) - int(max_reply_tokens) - PROMPT_RESERVE_TOKENS)


def truncate_to_tokens(text: str, tokens: int, marker: str = " […]") -> str:
    """Cut text (at a word boundary when possible) so it fits in about `tokens` tokens."""
    if estimate_tokens(text) <= tokens:
        return text
    lo, hi = 0, len(text)
    while lo < hi:  # longest prefix that fits
        mid = (lo + hi + 1) // 2
        if estimate_tokens(text[:mid]) + 2 <= tokens:
            lo = mid
        else:
            hi = mid - 1
    cut = text[:lo]
    sp = cut.rfind(" ")
    if sp > lo * 0.7:
        cut = cut[:sp]
    return cut.rstrip() + marker


def _clip(text: str, chars: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= chars:
        return text
    cut = text[:chars]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > chars * 0.7 else cut).rstrip() + " […]"


def format_history(rows: List[Dict[str, Any]], current_message: Optional[str], budget_tokens: int,
                   time_label=lambda r: "") -> Tuple[str, int]:
    """
    Room history for the Storyteller, oldest first, newest kept when over budget.

    rows: oldest first, each {'role', 'content', 'username', ...}. The player's current
    message is already saved, so the newest user row equal to it is left out (the message is
    sent once, as the user turn). AI rows are labelled "Storyteller", long lines are clipped.
    Returns (formatted text or '', number of rows used).
    """
    rows = list(rows)
    cur = " ".join(str(current_message or "").split())
    if cur:
        for i in range(len(rows) - 1, -1, -1):
            if rows[i].get("role") == "user":
                if " ".join(str(rows[i].get("content") or "").split()) == cur:
                    rows.pop(i)
                break
    lines: List[str] = []
    used = estimate_tokens("Recent Conversation History (this location):\n")
    for r in reversed(rows):
        if r.get("role") == "assistant":
            who, text = "Storyteller", _clip(r.get("content"), HISTORY_REPLY_CHARS)
        else:
            who, text = f"Player {r.get('username') or '?'}", _clip(r.get("content"), HISTORY_USER_CHARS)
        label = time_label(r)
        line = f"[{label}] {who}: {text}" if label else f"{who}: {text}"
        cost = estimate_tokens(line) + 1
        if used + cost > budget_tokens:
            break
        used += cost
        lines.append(line)
    if not lines:
        return "", 0
    lines.reverse()
    return "Recent Conversation History (this location):\n" + "\n".join(lines), len(lines)


# --- context overflow ---------------------------------------------------------------------------

_OVERFLOW_RE = re.compile(
    r"context (length|size|window)|n_ctx|exceed(s|ed)? the (context|available)|"
    r"too many tokens|prompt is too long|maximum context|context_length_exceeded|"
    r"tokens? (to keep|exceeds?)|greater than the context",
    re.IGNORECASE,
)


def is_context_overflow(error: Any) -> bool:
    return bool(_OVERFLOW_RE.search(str(error or "")))


def shrink_messages(messages: List[Dict[str, str]], factor: float = 0.6) -> List[Dict[str, str]]:
    """
    Make a prompt smaller after a context overflow: the longest message keeps its head (35%)
    and tail (65% of what remains), losing the middle (older history, extra sheet detail).
    The last user turn (the player's message) is never cut unless it is the only message.
    """
    out = [dict(m) for m in messages]
    candidates = [i for i in range(len(out)) if not (i == len(out) - 1 and out[i].get("role") == "user")]
    if not candidates:
        candidates = list(range(len(out)))
    i = max(candidates, key=lambda k: len(out[k].get("content") or ""))
    text = out[i].get("content") or ""
    keep = int(len(text) * factor)
    if keep >= len(text) or keep <= 0:
        return out
    head = int(keep * 0.35)
    tail = keep - head
    out[i]["content"] = text[:head].rstrip() + "\n[…older context trimmed…]\n" + text[len(text) - tail:].lstrip()
    return out


# --- Greek reply script check ---------------------------------------------------------------------


def _allowed_char(ch: str) -> bool:
    o = ord(ch)
    if o < 0x250:  # ASCII + Latin-1 + Latin Extended-A/B
        return True
    if 0x0370 <= o <= 0x03FF or 0x1F00 <= o <= 0x1FFF:  # Greek, Greek Extended
        return True
    if 0x2000 <= o <= 0x2BFF:  # punctuation, symbols, arrows, dingbats, box drawing
        return True
    if 0x1F000 <= o <= 0x1FAFF:  # emoji
        return True
    if 0x0300 <= o <= 0x036F or o in (0xFE0F, 0x200D):  # combining accents, emoji joiners
        return True
    return unicodedata.category(ch)[0] in "ZPS"  # other spaces, punctuation, symbols


def foreign_script_chars(text: str) -> List[str]:
    """Characters outside Greek/Latin/punctuation/digits/common symbols (e.g. CJK, Thai)."""
    return [c for c in (text or "") if not _allowed_char(c)]


def strip_foreign_script(text: str) -> str:
    """Drop foreign-script characters; tidy the spaces they leave."""
    out = "".join(c for c in text if _allowed_char(c))
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r" +([,.;:!?·])", r"\1", out)
