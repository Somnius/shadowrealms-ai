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
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# English labels to align with chat UI (“Wednesday, March 25, 2026 · 9:39 PM”).
_WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

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
    "roll-hidden",
    "clean",
    "dice-diff",
]

# Shown in API hints / console (full detail: `/ai help`)
FUTURE_COMMAND_SUGGESTIONS = [
    "/ai help — list all /ai commands",
    "/ai health — LM Studio / Ollama / Chroma snapshot (no generation)",
    "/ai model — configured + active provider snapshot",
    "/ai ping — tiny generation for baseline latency",
    "/ai context — truncated context for this room",
    "/ai summarize <text> — OOC wall-of-text helper",
    "/ai roll <expr> — Storyteller (oWoD) d10 pool, e.g. 5, 4+3@7",
    "/ai roll-hidden <expr> — same as `/ai roll`, but hidden from normal players",
    "/ai clean … — remove clutter (see `/ai clean`)",
    "/ai dice-diff <2-10|restore> — room leniency for sidebar dice (owner/admin)",
]


def parse_ai_slash_line(line: str) -> Optional[Tuple[str, str]]:
    """
    If line is an /ai command, return (subcommand_lower, payload_stripped).
    Otherwise None.
    """
    if not line or not str(line).strip().lower().startswith("/ai"):
        return None
    stripped = str(line).strip()
    # Bare "/ai" or "/ai " → same as help (common user expectation)
    if re.match(r"^/ai\s*$", stripped, re.IGNORECASE):
        return "help", ""
    m = _SLASH_RE.match(stripped)
    if not m:
        return None
    verb = m.group(1).strip().lower()
    payload = (m.group(2) or "").strip()
    return verb, payload


def _format_athens_like_chat(ath: datetime) -> str:
    """Wall clock in Europe/Athens, similar to message timestamps (12h + weekday)."""
    wd = _WEEKDAYS_EN[ath.weekday()]
    mon = _MONTHS_EN[ath.month - 1]
    h12 = ath.hour % 12 or 12
    am_pm = "AM" if ath.hour < 12 else "PM"
    tzabbr = (ath.tzname() or "").strip()
    tz_part = f" {tzabbr}" if tzabbr else ""
    return (
        f"{wd}, {mon} {ath.day}, {ath.year} · {h12}:{ath.minute:02d}:{ath.second:02d} "
        f"{am_pm}{tz_part}"
    )


def _format_time_utc_and_athens(label: str, dt_utc: datetime) -> str:
    """Europe/Athens first (matches chat-style 9:39 PM), then UTC ISO-Z."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    else:
        dt_utc = dt_utc.astimezone(timezone.utc)
    utc_s = dt_utc.isoformat().replace("+00:00", "Z")
    try:
        ath = dt_utc.astimezone(ZoneInfo("Europe/Athens"))
        ath_chat = _format_athens_like_chat(ath)
    except Exception:
        ath_chat = "— (Europe/Athens unavailable; ensure tzdata on server)"
    return (
        f"**{label} (Europe/Athens):** {ath_chat}\n"
        f"**{label} (UTC):** {utc_s}\n"
    )


def _format_respond_display(
    payload: str,
    received_at: datetime,
    completed_at: datetime,
    latency_ms: int,
    llm_text: str,
) -> str:
    """Markdown-ish block for chat UI."""
    safe_payload = payload if payload else "(empty)"
    times = (
        _format_time_utc_and_athens("Server received", received_at)
        + _format_time_utc_and_athens("Reasoning completed", completed_at)
    )
    return (
        "**AI diagnostics — `/ai respond`**\n\n"
        f"**Payload received:**\n{safe_payload}\n\n"
        f"{times}"
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
    """List /ai subcommands. Most verbs are site-admin-only; see notes for exceptions."""
    display = """**`/ai help`** — slash commands

**Who can use what**
- **Site administrators** can use every `/ai` verb below.
- **Campaign owner** (creator of the campaign) can also use **`/ai clean …`** and **`/ai dice-diff …`** from inside a campaign room.
- Everyone else: use **Roll dice** in the right sidebar for Storyteller (Old World of Darkness) d10 pools in chat.

**Commands**
- **`/ai help`** — This reference.
- **`/ai health`** — LM Studio, Ollama, and ChromaDB reachability — **no** text generation.
- **`/ai model`** — Env model names/URLs and router/provider snapshot.
- **`/ai ping`** — Smallest possible LLM round-trip to measure latency (needs a running LLM).
- **`/ai context`** — Truncated **location + recent messages + campaign** text the storyteller pipeline would see in the current room.
- **`/ai summarize …`** — OOC helper: compress a long pasted block into short bullets (needs LLM).
- **`/ai roll …`** — Server-side Storyteller d10 pool (e.g. `5`, `4+3@8`, `6 tn 7`). Uses this room’s leniency if **`/ai dice-diff`** is active.
- **`/ai roll-hidden …`** — Same roll math as **`/ai roll`**, but the result is hidden from normal players (shown to admin/storyteller only).
- **`/ai respond …`** — Diagnostics: echo payload through the LLM with timing (needs LLM).
- **`/ai clean`** — Lists what you can remove from the **current room** (more targets later).
- **`/ai clean ai`** — Deletes **admin `/ai` command lines** and the **assistant slash replies** tied to them in this room (does not remove normal storyteller chat).
- **`/ai dice-diff <2–10>`** — **Lenient dice** for this **room** only: no **1**s; with **2+** dice, **at least one** die is **≥** your floor (e.g. `7` → one die in 7–10, others 2–10). **Botches from 1s** cannot occur. Affects **Roll dice** in the sidebar for everyone in this channel.
- **`/ai dice-diff restore`** — Clear leniency; rolls return to normal random d10s (1–10) and standard Revised Storyteller rules.

Site admins can also set the same option per room via **Admin Dice Rules** in the sidebar.

See **docs/dice-old-wod.md** for base dice rules used by the app and the Roll dice UI.
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

    times_block = (
        _format_time_utc_and_athens("Server received", received_at)
        + _format_time_utc_and_athens("Completed", completed_at)
    )
    raw = llm_text.strip()[:200]
    raw_display = raw if raw else "(empty)"
    display = (
        "**`/ai ping`** — minimal generation latency\n\n"
        + times_block
        + "\n**Note:** The UTC line is *24-hour* and ends with *Z* (UTC). "
        "So `19:39Z` is the *same moment* as *9:39 PM* in Athens during EET (UTC+2), "
        "not 7:39 PM.\n\n"
        + f"- **Latency:** {latency_ms} ms\n"
        f"- **Raw reply:** `{raw_display}`\n"
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


def _fetch_location_dice_leniency_floor(
    campaign_id: Optional[int], location_id: Optional[int]
) -> Optional[int]:
    if not campaign_id or location_id is None:
        return None
    try:
        from database import get_db

        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            SELECT dice_leniency_floor FROM locations
            WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """,
            (location_id, campaign_id),
        )
        row = cur.fetchone()
        cur.close()
        db.close()
        if not row:
            return None
        v = row.get("dice_leniency_floor")
        if v is None:
            return None
        iv = int(v)
        if 2 <= iv <= 10:
            return iv
    except Exception as e:
        logger.warning("dice_leniency_floor lookup: %s", e)
    return None


def execute_clean_command(
    payload: str,
    user_id: int,
    campaign_id: int,
    location_id: int,
) -> Dict[str, Any]:
    """Room cleanup helpers (campaign owner or site admin at HTTP layer)."""
    target = (payload or "").strip().lower()
    if not target:
        display = (
            "**`/ai clean`** — remove clutter in **this room**\n\n"
            "Pick a target after `clean`:\n\n"
            "- **`/ai clean ai`** — Delete lines that are **admin `/ai …` commands** and the "
            "**assistant slash replies** (the markdown blocks right under them). "
            "Normal IC/OOC storyteller replies are **not** removed.\n\n"
            "_More `/ai clean …` targets may be added later._"
        )
        return {
            "ok": True,
            "command": "clean",
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }
    if target == "ai":
        from database import get_db
        from services.chat_cleanup import delete_slash_ai_messages

        conn = get_db()
        try:
            n = delete_slash_ai_messages(conn, campaign_id, location_id)
        finally:
            conn.close()
        display = (
            "**`/ai clean ai`**\n\n"
            f"Removed **{n}** message(s) (`/ai` slash lines and matching assistant outputs) "
            f"from this room."
        )
        return {
            "ok": True,
            "command": "clean",
            "clean_target": "ai",
            "deleted_count": n,
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }
    raise ValueError(
        f"Unknown clean target `{payload.strip()!r}`. Use **`/ai clean`** to list options."
    )


def execute_dice_diff_command(
    payload: str,
    user_id: int,
    campaign_id: int,
    location_id: int,
) -> Dict[str, Any]:
    """Set or clear Storyteller leniency floor for this location (owner or site admin)."""
    from database import get_db

    raw = (payload or "").strip().lower()
    if not raw:
        display = (
            "**`/ai dice-diff`** — lenient **d10** rolls in **this room only**\n\n"
            "- **`/ai dice-diff 7`** — Floor **7**: no **1**s; with **2+** dice, **one** die is always "
            "in **7–10**; other dice are **2–10**. Sidebar **Roll dice** uses this until restored.\n"
            "- **`/ai dice-diff restore`** — Back to normal **1–10** random dice and standard botch rules.\n\n"
            "_Floor must be an integer **2–10**._"
        )
        return {
            "ok": True,
            "command": "dice-diff",
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }

    conn = get_db()
    cur = conn.cursor()
    try:
        if raw in ("restore", "off", "none", "normal"):
            cur.execute(
                """
                UPDATE locations SET dice_leniency_floor = NULL
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                """,
                (location_id, campaign_id),
            )
            conn.commit()
            cur.execute(
                "SELECT dice_leniency_floor FROM locations WHERE id = %s",
                (location_id,),
            )
            row = cur.fetchone()
            current = row.get("dice_leniency_floor") if row else None
            display = (
                "**`/ai dice-diff restore`**\n\n"
                "Leniency is **off** for this room. Dice use full **1–10** randomness again."
            )
        else:
            parts = raw.replace(",", " ").split()
            try:
                v = int(parts[0])
            except (ValueError, IndexError) as e:
                raise ValueError(
                    "Usage: `/ai dice-diff <2–10>` or `/ai dice-diff restore`."
                ) from e
            if v < 2 or v > 10:
                raise ValueError("Floor must be between **2** and **10**.")
            cur.execute(
                """
                UPDATE locations SET dice_leniency_floor = %s
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                """,
                (v, location_id, campaign_id),
            )
            conn.commit()
            current = v
            display = (
                f"**`/ai dice-diff {v}`**\n\n"
                f"**This room** now uses leniency floor **{v}**: no **1**s; with multiple dice, "
                f"**at least one** die is **≥ {v}**. Clear with **`/ai dice-diff restore`**."
            )
        return {
            "ok": True,
            "command": "dice-diff",
            "dice_leniency_floor": current,
            "display_markdown": display,
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }
    finally:
        cur.close()
        conn.close()


def execute_roll_command(
    payload: str,
    user_id: int,
    campaign_id: Optional[int] = None,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    from services.wod_dice import (
        format_storyteller_roll_markdown,
        parse_roll_expression,
        roll_storyteller_pool,
    )

    game_system = _fetch_campaign_game_system(campaign_id)
    default_diff = 6
    pool, diff = parse_roll_expression(payload, default_difficulty=default_diff)
    lf = _fetch_location_dice_leniency_floor(campaign_id, location_id)
    result = roll_storyteller_pool(pool, diff, leniency_floor=lf)
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


def execute_roll_hidden_command(
    payload: str,
    user_id: int,
    campaign_id: Optional[int] = None,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Same dice math as /ai roll, but tagged so the frontend/backend can
    post dice animation + final messages as hidden.
    """
    res = execute_roll_command(
        payload, user_id, campaign_id=campaign_id, location_id=location_id
    )
    res["command"] = "roll-hidden"
    # Keep the markdown header accurate for UX.
    if isinstance(res.get("display_markdown"), str):
        res["display_markdown"] = res["display_markdown"].replace(
            "**`/ai roll`**", "**`/ai roll-hidden`**", 1
        )
    return res


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

    display = _format_respond_display(
        payload, received_at, completed_at, latency_ms, llm_text
    )

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
        return execute_roll_command(
            payload, user_id, campaign_id=campaign_id, location_id=location_id
        )
    if verb == "roll-hidden":
        return execute_roll_hidden_command(
            payload, user_id, campaign_id=campaign_id, location_id=location_id
        )
    if verb == "clean":
        if not campaign_id or location_id is None:
            raise ValueError(
                "Open a campaign location first — `/ai clean` runs per **room**."
            )
        return execute_clean_command(payload, user_id, campaign_id, location_id)
    if verb == "dice-diff":
        if not campaign_id or location_id is None:
            raise ValueError(
                "Open a campaign location first — `/ai dice-diff` applies to **this room**."
            )
        return execute_dice_diff_command(payload, user_id, campaign_id, location_id)
    raise ValueError(f"Unknown /ai subcommand: {verb}")
