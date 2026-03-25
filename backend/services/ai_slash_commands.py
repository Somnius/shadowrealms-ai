"""
Parse and execute /ai … slash commands from chat (diagnostics, tooling).

Extensible: add new verbs in execute_ai_slash_command().
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# First token after /ai is the subcommand; rest is payload (may be multiline)
_SLASH_RE = re.compile(r"^\s*/ai\s+(\S+)(?:\s+(.*))?$", re.IGNORECASE | re.DOTALL)

SUPPORTED_AI_SLASH_VERBS: List[str] = [
    "help",
    "respond",
    "health",
    "model",
    "ping",
    "context",
    "summarize",
    "roll",
]

# Shown in API hints / console (full detail: `/ai help`)
FUTURE_COMMAND_SUGGESTIONS = [
    "/ai help — list all admin commands (administrators only)",
    "/ai health — LM Studio / Ollama / Chroma snapshot (no generation)",
    "/ai model — configured + active provider snapshot",
    "/ai ping — tiny generation for baseline latency",
    "/ai context — truncated context for this room",
    "/ai summarize <text> — OOC wall-of-text helper",
    "/ai roll <expr> — Storyteller (oWoD) d10 pool, e.g. 5, 4+3@7",
]


def parse_ai_slash_line(line: str) -> Optional[Tuple[str, str]]:
    """
    If line is an /ai command, return (subcommand_lower, payload_stripped).
    Otherwise None.
    """
    if not line or not str(line).strip().lower().startswith("/ai"):
        return None
    m = _SLASH_RE.match(str(line).strip())
    if not m:
        return None
    verb = m.group(1).strip().lower()
    payload = (m.group(2) or "").strip()
    return verb, payload


def _format_respond_display(
    payload: str,
    received_iso: str,
    completed_iso: str,
    latency_ms: int,
    llm_text: str,
) -> str:
    """Markdown-ish block for chat UI."""
    safe_payload = payload if payload else "(empty)"
    return (
        "**AI diagnostics — `/ai respond`**\n\n"
        f"**Payload received:**\n{safe_payload}\n\n"
        f"**Server received (UTC):** {received_iso}\n"
        f"**Reasoning completed (UTC):** {completed_iso}\n"
        f"**Latency (request → LLM reply):** {latency_ms} ms\n\n"
        f"**Model acknowledgment:**\n{llm_text.strip()}"
    )


def _llm_snapshot_for_errors() -> str:
    from services.health_check import get_health_check_service

    r = get_health_check_service().check_all_services()
    lines = [
        f"- LM Studio: {'up' if r['lm_studio']['available'] else 'down'} — {r['lm_studio']['message']}",
        f"- Ollama: {'up' if r['ollama']['available'] else 'down'} — {r['ollama']['message']}",
    ]
    return "\n".join(lines)


def _truncate(s: str, max_chars: int) -> Tuple[str, bool]:
    if len(s) <= max_chars:
        return s, False
    return s[: max_chars - 20] + "\n… _(truncated)_\n", True


def execute_help_command(user_id: int) -> Dict[str, Any]:
    """List /ai subcommands and short explanations (admin-only at HTTP layer)."""
    display = """**`/ai help`** — administrator commands

These commands are **only for users with the site administrator role**. Other players should use the **Roll dice** control in the campaign sidebar for Old World of Darkness (Storyteller) d10 rolls.

- **`/ai help`** — This reference.
- **`/ai health`** — LM Studio, Ollama, and ChromaDB reachability — **no** text generation.
- **`/ai model`** — Env model names/URLs and router/provider snapshot.
- **`/ai ping`** — Smallest possible LLM round-trip to measure latency (needs a running LLM).
- **`/ai context`** — Truncated **location + recent messages + campaign** text the storyteller pipeline would see in the current room.
- **`/ai summarize …`** — OOC helper: compress a long pasted block into short bullets (needs LLM).
- **`/ai roll …`** — Server-side Storyteller d10 pool (e.g. `5`, `4+3@8`, `6 tn 7`).
- **`/ai respond …`** — Diagnostics: echo payload through the LLM with timing (needs LLM).

See **docs/dice-old-wod.md** in the repo for dice rules used by the app and the Roll dice UI.
"""
    return {
        "ok": True,
        "command": "help",
        "display_markdown": display.strip(),
        "supported_commands": SUPPORTED_AI_SLASH_VERBS,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_health_command(user_id: int) -> Dict[str, Any]:
    """LM Studio / Ollama / Chroma checks only — no generation."""
    from services.health_check import get_health_check_service

    r = get_health_check_service().check_all_services()
    display = (
        "**`/ai health`** — dependency snapshot (no LLM generation)\n\n"
        f"- **LM Studio** (`{r['lm_studio']['url']}`): "
        f"**{'OK' if r['lm_studio']['available'] else 'DOWN'}** — {r['lm_studio']['message']}\n"
        f"- **Ollama** (`{r['ollama']['url']}`): "
        f"**{'OK' if r['ollama']['available'] else 'DOWN'}** — {r['ollama']['message']}\n"
        f"- **ChromaDB** (`{r['chromadb']['host']}:{r['chromadb']['port']}`): "
        f"**{'OK' if r['chromadb']['available'] else 'DOWN'}** — {r['chromadb']['message']}\n\n"
        f"- **Any LLM up:** {'yes' if r['llm_available'] else 'no'}\n"
        f"- **LLM + Chroma (chat-ready):** {'yes' if r['all_services_ok'] else 'no'}\n"
    )
    return {
        "ok": True,
        "command": "health",
        "service_status": r,
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_model_command(user_id: int) -> Dict[str, Any]:
    """Active routing snapshot + env-configured model ids."""
    from services.llm_service import get_llm_service

    lm_model = os.environ.get("LM_STUDIO_MODEL", "")
    ollama_model = os.environ.get("OLLAMA_MODEL", "")
    lm_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

    llm = get_llm_service()
    status = llm.get_system_status()
    primary = status.get("primary_provider") or "(none reachable)"
    router = status.get("model_router_status") or {}

    lines = [
        "**`/ai model`** — configured models & provider snapshot\n",
        f"- **Env LM_STUDIO_MODEL:** `{lm_model or '—'}` @ `{lm_url}`",
        f"- **Env OLLAMA_MODEL:** `{ollama_model or '—'}` @ `{ollama_url}`",
        f"- **First available provider (legacy list):** `{primary}`",
        f"- **Router loaded models:** {', '.join(router.get('loaded_models', [])) or '—'}",
        f"- **Router available (count):** {router.get('available_models', '—')}",
    ]
    for pname, pinfo in (status.get("providers") or {}).items():
        st = pinfo.get("status", "?")
        lines.append(f"- **Provider `{pname}`:** {st}")

    display = "\n".join(lines)
    return {
        "ok": True,
        "command": "model",
        "system_status": status,
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_ping_command(user_id: int) -> Dict[str, Any]:
    """Minimal generation for latency baseline (requires an LLM)."""
    from services.health_check import get_health_check_service
    from services.llm_service import get_llm_service

    hc = get_health_check_service().check_all_services()
    if not hc["llm_available"]:
        display = (
            "**`/ai ping`** — skipped (no LLM)\n\n"
            + _llm_snapshot_for_errors()
        )
        return {
            "ok": False,
            "command": "ping",
            "error": "No LLM provider available",
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }

    received_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    llm = get_llm_service()
    llm_text = llm.generate_response(
        'Reply with exactly the single word "pong" and nothing else.',
        {
            "system_prompt": (
                "You are a latency probe. Output only the word pong, lowercase, no punctuation."
            ),
        },
        {"max_tokens": 8, "temperature": 0.0, "top_p": 0.5},
    )
    t1 = time.perf_counter()
    completed_at = datetime.now(timezone.utc)
    latency_ms = int(round((t1 - t0) * 1000))

    rec_iso = received_at.isoformat().replace("+00:00", "Z")
    done_iso = completed_at.isoformat().replace("+00:00", "Z")

    display = (
        "**`/ai ping`** — minimal generation latency\n\n"
        f"- **Server received (UTC):** {rec_iso}\n"
        f"- **Completed (UTC):** {done_iso}\n"
        f"- **Latency:** {latency_ms} ms\n"
        f"- **Raw reply:** `{llm_text.strip()[:200]}`\n"
    )
    return {
        "ok": True,
        "command": "ping",
        "latency_ms": latency_ms,
        "llm_reply": llm_text.strip(),
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_context_command(
    user_id: int, campaign_id: int, location_id: int
) -> Dict[str, Any]:
    """Truncated text the storyteller pipeline would lean on for this room."""
    # Late import avoids circular import with routes.ai
    from routes.ai import get_campaign_context, get_location_context, get_recent_messages

    loc = get_location_context(location_id, campaign_id)
    recent = get_recent_messages(location_id, campaign_id, limit=15)
    camp = get_campaign_context(campaign_id)

    parts = [
        "**`/ai context`** — truncated room context (no generation)\n",
        "### Location\n",
        loc.get("formatted") or "(none)",
        "\n\n### Recent messages (newest-last block may be trimmed)\n",
        (recent.get("formatted") or "(none)").strip(),
        "\n\n### Campaign (header)\n",
        (camp or "(none)")[:4000],
    ]
    blob = "\n".join(parts)
    blob, truncated = _truncate(blob, 12000)
    if truncated:
        blob += "\n\n_(Total preview truncated to ~12k characters.)_"

    return {
        "ok": True,
        "command": "context",
        "display_markdown": blob,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_summarize_command(payload: str, user_id: int) -> Dict[str, Any]:
    """OOC helper: compress long paste."""
    from services.health_check import get_health_check_service
    from services.llm_service import get_llm_service

    text = (payload or "").strip()
    if not text:
        raise ValueError(
            "Usage: `/ai summarize` followed by the text to compress (OOC helper)."
        )

    hc = get_health_check_service().check_all_services()
    if not hc["llm_available"]:
        display = "**`/ai summarize`** — needs an LLM\n\n" + _llm_snapshot_for_errors()
        return {
            "ok": False,
            "command": "summarize",
            "error": "No LLM provider available",
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }

    if len(text) > 14000:
        text = text[:13980] + "\n… _(input truncated)_"

    llm = get_llm_service()
    t0 = time.perf_counter()
    out = llm.generate_response(
        f"Summarize the following for a tabletop RPG table (OOC). "
        f"Use short bullet points; keep names and numbers; no in-character voice.\n\n---\n{text}\n---",
        {
            "system_prompt": (
                "You condense long player or ST pasted text for busy players. "
                "Bullet list, max ~12 bullets, neutral tone."
            ),
        },
        {"max_tokens": 512, "temperature": 0.35, "top_p": 0.9},
    )
    latency_ms = int(round((time.perf_counter() - t0) * 1000))

    display = (
        "**`/ai summarize`** — OOC compression\n\n"
        f"_Latency: {latency_ms} ms_\n\n"
        + out.strip()
    )
    return {
        "ok": True,
        "command": "summarize",
        "latency_ms": latency_ms,
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def _fetch_campaign_game_system(campaign_id: Optional[int]) -> str:
    if not campaign_id:
        return ""
    try:
        from database import get_db

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT game_system FROM campaigns WHERE id = %s AND is_active = TRUE",
            (campaign_id,),
        )
        row = cur.fetchone()
        cur.close()
        db.close()
        if row and row.get("game_system"):
            return str(row["game_system"])
    except Exception as e:
        logger.warning("Could not load game_system: %s", e)
    return ""


def execute_roll_command(
    payload: str, user_id: int, campaign_id: Optional[int] = None
) -> Dict[str, Any]:
    from services.wod_dice import (
        format_storyteller_roll_markdown,
        parse_roll_expression,
        roll_storyteller_pool,
    )

    game_system = _fetch_campaign_game_system(campaign_id)
    default_diff = 6
    pool, diff = parse_roll_expression(payload, default_difficulty=default_diff)
    result = roll_storyteller_pool(pool, diff)
    display = format_storyteller_roll_markdown(result, game_system=game_system)
    return {
        "ok": True,
        "command": "roll",
        "display_markdown": display,
        "roll": {
            "dice": result.dice,
            "pool": result.pool,
            "difficulty": result.difficulty,
            "net_successes": result.net_successes,
            "botch": result.botch,
        },
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_respond_command(payload: str, user_id: int) -> Dict[str, Any]:
    """
    Run a single short LLM call to acknowledge payload; record wall + monotonic timing.
    Does not use campaign_id in LLM context (no RAG) so timing reflects model round-trip.
    """
    from services.health_check import get_health_check_service
    from services.llm_service import get_llm_service

    hc = get_health_check_service().check_all_services()
    if not hc["llm_available"]:
        display = "**`/ai respond`** — needs an LLM\n\n" + _llm_snapshot_for_errors()
        return {
            "ok": False,
            "command": "respond",
            "error": "No LLM provider available",
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }

    received_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    user_prompt = (
        "Diagnostics echo.\n"
        f"Payload from operator (verbatim, may be empty):\n---\n{payload}\n---\n"
        "Reply with ONE short sentence confirming you received and understood this payload "
        "for a latency test. No RPG roleplay, no markdown headings."
    )
    context = {
        "system_prompt": (
            "You are a system diagnostics assistant. The user is measuring AI pipeline latency. "
            "Answer in one concise sentence. No storytelling."
        ),
    }
    config = {"max_tokens": 120, "temperature": 0.25, "top_p": 0.85}

    llm = get_llm_service()
    llm_text = llm.generate_response(user_prompt, context, config)

    t1 = time.perf_counter()
    completed_at = datetime.now(timezone.utc)
    latency_ms = int(round((t1 - t0) * 1000))

    rec_iso = received_at.isoformat().replace("+00:00", "Z")
    done_iso = completed_at.isoformat().replace("+00:00", "Z")

    display = _format_respond_display(payload, rec_iso, done_iso, latency_ms, llm_text)

    return {
        "ok": True,
        "command": "respond",
        "payload_received": payload,
        "server_received_at": rec_iso,
        "reasoning_completed_at": done_iso,
        "latency_ms": latency_ms,
        "llm_acknowledgment": llm_text.strip(),
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_ai_slash_command(
    verb: str,
    payload: str,
    user_id: int,
    *,
    campaign_id: Optional[int] = None,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Dispatch subcommand. Raises ValueError for unknown verb or bad args."""
    if verb == "help":
        return execute_help_command(user_id)
    if verb == "respond":
        return execute_respond_command(payload, user_id)
    if verb == "health":
        return execute_health_command(user_id)
    if verb == "model":
        return execute_model_command(user_id)
    if verb == "ping":
        return execute_ping_command(user_id)
    if verb == "context":
        if not campaign_id or location_id is None:
            raise ValueError(
                "Open a campaign location first — `/ai context` needs an active room."
            )
        return execute_context_command(user_id, campaign_id, location_id)
    if verb == "summarize":
        return execute_summarize_command(payload, user_id)
    if verb == "roll":
        return execute_roll_command(payload, user_id, campaign_id=campaign_id)
    raise ValueError(f"Unknown /ai subcommand: {verb}")
