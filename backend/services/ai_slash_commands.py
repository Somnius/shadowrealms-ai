"""
Parse and execute /ai … slash commands from chat (diagnostics, tooling).

Extensible: add new verbs in execute_ai_slash_command().
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from services.request_validation import RequestValidationError

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
    "rouse",
    "clean",
    "dice-diff",
    "explain",
]

# `/ai explain` (and its Greek alias) is open to every member of the chronicle, not only staff.
GREEK_EXPLAIN_VERBS = frozenset({"εξήγησε", "εξηγησε"})
EXPLAIN_VERBS = frozenset({"explain"}) | GREEK_EXPLAIN_VERBS

# Shown in API hints / console (full detail: `/ai help`)
FUTURE_COMMAND_SUGGESTIONS = [
    "/ai help — list all /ai commands",
    "/ai health — LM Studio / Ollama / Chroma snapshot (no generation)",
    "/ai model — configured + active provider snapshot",
    "/ai ping — tiny generation for baseline latency",
    "/ai context — truncated context for this room",
    "/ai summarize <text> — OOC wall-of-text helper",
    "/ai roll <expr> — d10 pool by campaign rules: classic `4+3@7` (pool@TN), V5 `6@3h2` (pool@successes, Hunger)",
    "/ai roll-hidden <expr> — same as `/ai roll`, but hidden from normal players",
    "/ai explain — explain a dice roll step by step (reply to the dice card; any member)",
    "/ai rouse [hunger] — V5 Rouse check (one die, 6+ = no Hunger gain)",
    "/ai clean … — remove clutter (see `/ai clean`)",
    "/ai dice-diff … — room dice leniency (owner/admin): Classic `<2-10|restore>`, V5 `no-bestial on|off`, `no-messy on|off`, `successes <0-3>`, `restore`",
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


RESPOND_DIAGNOSTICS_NOTE = (
    "_Diagnostics only: this measures the LLM round-trip. It is not the Storyteller and doesn't read "
    "the chat or the message you replied to. To explain a dice roll, reply to the dice card with "
    "`/ai explain`._"
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
        f"{RESPOND_DIAGNOSTICS_NOTE}\n\n"
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


_ROLL_HELP_CLASSIC = (
    "- **`/ai roll …`** — Server-side **classic (Revised)** d10 pool: `5`, `4+3@8`, `6 tn 7` "
    "(pool@difficulty 2–10, default 6). 1s cancel successes; botch only if no die succeeded and a 1 showed. "
    "Uses this room’s leniency floor if **`/ai dice-diff`** is active."
)
_ROLL_HELP_V5 = (
    "- **`/ai roll …`** — Server-side **V5** pool: `pool[@difficulty][h<hunger>]`, e.g. `6`, `6@3`, `6@3h2` "
    "(difficulty = successes needed 0–10, default 1; Hunger 0–5). 6+ succeeds, pairs of 10s = criticals, "
    "messy criticals and bestial failures from Hunger dice. Uses this room’s V5 switches if **`/ai dice-diff`** set any.\n"
    "- **`/ai rouse [hunger]`** — V5 Rouse check: one die, 6+ = no Hunger gain, else Hunger +1 (max 5). "
    "Stateless: does not change any character sheet (the rouse API with a character does). "
    "Always a plain die: room leniency never applies to Rouse checks."
)

_DICE_DIFF_HELP_CLASSIC = (
    "- **`/ai dice-diff <2–10>`** — **Classic** lenient dice for this **room** only: no **1**s; with **2+** dice, "
    "**at least one** die is **≥** your floor (e.g. `7` → one die in 7–10, others 2–10). **Botches from 1s** "
    "cannot occur. Affects **Roll dice** in the sidebar for everyone in this channel.\n"
    "- **`/ai dice-diff restore`** — Clear leniency; rolls return to normal random d10s (1–10) and the "
    "campaign's standard rules."
)
_DICE_DIFF_HELP_V5 = (
    "- **`/ai dice-diff`** — **V5** room leniency for this **room** only: shows the current switches.\n"
    "- **`/ai dice-diff no-bestial on|off`** — Hunger dice never show **1** (no **bestial failure**).\n"
    "- **`/ai dice-diff no-messy on|off`** — Hunger dice never show **10** (no **messy critical** from Hunger tens).\n"
    "- **`/ai dice-diff successes <0–3>`** — At least that many dice show **6+** (capped at the pool; "
    "missing successes come from normal dice first, then Hunger dice).\n"
    "- **`/ai dice-diff restore`** — All switches off. Normal dice keep their 1s; Willpower rerolls and "
    "Rouse checks are always plain random dice."
)


def execute_help_command(user_id: int, campaign_id: Optional[int] = None) -> Dict[str, Any]:
    """List /ai subcommands. Most verbs are site-admin-only; see notes for exceptions."""
    _gs, edition = _fetch_campaign_rules(campaign_id)
    if not campaign_id:
        roll_help = (
            _ROLL_HELP_CLASSIC
            + "\n"
            + _ROLL_HELP_V5
            + "\n- _Inside a campaign room, `/ai roll` follows that campaign’s rules edition._"
        )
    elif edition == "v5":
        roll_help = _ROLL_HELP_V5
    else:
        roll_help = _ROLL_HELP_CLASSIC
    dice_doc = "docs/dice-v5.md" if edition == "v5" else "docs/dice-old-wod.md"
    if not campaign_id:
        dice_diff_help = (
            _DICE_DIFF_HELP_CLASSIC + "\n" + _DICE_DIFF_HELP_V5
            + "\n- _Inside a campaign room, `/ai dice-diff` takes the settings of that campaign’s edition._"
        )
    elif edition == "v5":
        dice_diff_help = _DICE_DIFF_HELP_V5
    else:
        dice_diff_help = _DICE_DIFF_HELP_CLASSIC
    display = """**`/ai help`** — slash commands

**Who can use what**
- **Site administrators** can use every `/ai` verb below.
- **Campaign owner** (creator of the campaign) can also use **`/ai clean …`** and **`/ai dice-diff …`** from inside a campaign room.
- **Every member** of the chronicle can use **`/ai explain`** (explain a dice roll).
- Everyone else: use **Roll dice** in the right sidebar for d10 pools in chat (classic or V5, per campaign).

**Commands**
- **`/ai help`** — This reference.
- **`/ai health`** — LM Studio, Ollama, and ChromaDB reachability — **no** text generation.
- **`/ai model`** — Env model names/URLs and router/provider snapshot.
- **`/ai ping`** — Smallest possible LLM round-trip to measure latency (needs a running LLM).
- **`/ai context`** — Truncated **location + recent messages + campaign** text the storyteller pipeline would see in the current room.
- **`/ai summarize …`** — OOC helper: compress a long pasted block into short bullets (needs LLM).
__ROLL_HELP__
- **`/ai roll-hidden …`** — Same roll math as **`/ai roll`**, but the result is hidden from normal players (shown to admin/storyteller only).
- **`/ai respond …`** — **Diagnostics only**: echoes the text through the LLM and shows the latency (needs LLM). It is not the Storyteller and doesn't read the chat; to explain a dice roll use **`/ai explain`**.
- **`/ai explain`** — Explains a dice roll step by step: reply to a dice card with **`/ai explain`** (or **`/ai explain this roll`**, Greek **`/ai εξήγησε`**); without a reply it explains the newest roll in this room you can see. The numbers come from the stored roll; the Storyteller may add a short line. **Every member of the chronicle** can use it.
- **`/ai clean`** — Lists what you can remove from the **current room** (more targets later).
- **`/ai clean ai`** — Deletes **admin `/ai` command lines** and the **assistant slash replies** tied to them in this room (does not remove normal storyteller chat).
__DICE_DIFF_HELP__

Site admins can also set the same option per room via **Admin Dice Rules** in the sidebar.

See **__DICE_DOC__** for the dice rules used by the app and the Roll dice UI.
"""
    display = (
        display.replace("__ROLL_HELP__", roll_help)
        .replace("__DICE_DIFF_HELP__", dice_diff_help)
        .replace("__DICE_DOC__", dice_doc)
    )
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
    from services.ai_runtime_settings import get_app_setting
    from services.lm_studio_model import get_effective_lm_studio_model_id

    lm_model = os.environ.get("LM_STUDIO_MODEL", "")
    ollama_model = os.environ.get("OLLAMA_MODEL", "")
    lm_url = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    lm_cfg = {
        "LM_STUDIO_URL": lm_url,
        "LM_STUDIO_API_KEY": os.environ.get("LM_STUDIO_API_KEY", ""),
        "LM_STUDIO_MODEL": os.environ.get("LM_STUDIO_MODEL", "") or "",
        "LM_STUDIO_TIMEOUT": int(os.environ.get("LM_STUDIO_TIMEOUT", "120") or 120),
    }
    effective_lm = get_effective_lm_studio_model_id(lm_cfg)
    admin_model = (get_app_setting("lm_studio_model") or "").strip()

    llm = get_llm_service()
    status = llm.get_system_status()
    primary = status.get("primary_provider") or "(none reachable)"
    router = status.get("model_router_status") or {}

    lines = [
        "**`/ai model`** — configured models & provider snapshot\n",
        f"- **Env LM_STUDIO_MODEL:** `{lm_model or '—'}` @ `{lm_url}`",
        f"- **Effective LM Studio model (requests):** `{effective_lm}`",
    ]
    if admin_model:
        lines.append(f"- **Admin panel override:** `{admin_model}` (empty override = use env + auto-loaded)")
    lines += [
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
        raise RequestValidationError(
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
            # reply language follows the pasted text, not the English instructions
            "player_message": text,
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


def _fetch_campaign_rules(campaign_id: Optional[int]) -> Tuple[str, str]:
    """(game_system, rules_edition) of an active campaign; ('', 'classic') when unknown."""
    from services.rules_edition import DEFAULT_RULES_EDITION, edition_of

    if not campaign_id:
        return "", DEFAULT_RULES_EDITION
    try:
        from database import get_db

        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                "SELECT game_system, rules_edition FROM campaigns WHERE id = %s AND is_active = TRUE",
                (campaign_id,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
            db.close()
        if row:
            return str(row.get("game_system") or ""), edition_of(row)
    except Exception as e:
        logger.warning("Could not load campaign rules: %s", e)
    return "", DEFAULT_RULES_EDITION


def _valid_floor(v: Any) -> Optional[int]:
    try:
        iv = int(v)
    except (TypeError, ValueError):
        return None
    return iv if 2 <= iv <= 10 else None


def _fetch_location_dice_leniency(
    campaign_id: Optional[int], location_id: Optional[int]
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """(Classic floor 2-10 or None, normalized V5 switches or None) of this room."""
    from services.v5_dice import normalize_v5_leniency

    if not campaign_id or location_id is None:
        return None, None
    try:
        from database import get_db

        db = get_db()
        cur = db.cursor()
        cur.execute(
            """
            SELECT dice_leniency_floor, dice_leniency_v5 FROM locations
            WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """,
            (location_id, campaign_id),
        )
        row = cur.fetchone()
        cur.close()
        db.close()
        if row:
            return (
                _valid_floor(row.get("dice_leniency_floor")),
                normalize_v5_leniency(row.get("dice_leniency_v5")),
            )
    except Exception as e:
        logger.warning("dice leniency lookup: %s", e)
    return None, None


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
    raise RequestValidationError(
        f"Unknown clean target `{payload.strip()!r}`. Use **`/ai clean`** to list options."
    )


_DICE_DIFF_RESTORE_WORDS = ("restore", "off", "none", "normal")
_DICE_DIFF_V5_WORDS = ("no-bestial", "no-messy", "successes")
_DICE_DIFF_V5_HINT = (
    "This is a **V5** chronicle: the 2–10 floor is a Classic setting. V5 rooms use switches: "
    "`/ai dice-diff no-bestial on|off`, `/ai dice-diff no-messy on|off`, "
    "`/ai dice-diff successes <0–3>`, `/ai dice-diff restore`."
)
_DICE_DIFF_CLASSIC_HINT = (
    "`no-bestial`, `no-messy` and `successes` are **V5** switches; this is a **Classic** chronicle. "
    "Use `/ai dice-diff <2–10>` (floor) or `/ai dice-diff restore`."
)
_DICE_DIFF_V5_USAGE = (
    "- **`/ai dice-diff no-bestial on|off`** — Hunger dice never show **1**, so no **bestial failure**.\n"
    "- **`/ai dice-diff no-messy on|off`** — Hunger dice never show **10**, so no **messy critical** "
    "from Hunger tens (normal 10s still make criticals).\n"
    "- **`/ai dice-diff successes <0–3>`** — At least that many dice show **6+** (never more than the pool). "
    "Missing successes are re-rolled on normal dice first, Hunger dice only if needed; other dice stay random.\n"
    "- **`/ai dice-diff restore`** — All switches off: normal random dice.\n\n"
    "_Normal dice keep their 1s (they don't matter in V5). Willpower rerolls and Rouse checks "
    "are always plain random dice._"
)


def _dice_diff_result(display: str, floor: Optional[int], v5: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ok": True,
        "command": "dice-diff",
        "dice_leniency_floor": floor,
        "dice_leniency_v5": v5,
        "display_markdown": display,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def _v5_active_line(v5: Optional[Dict[str, Any]]) -> str:
    from services.v5_dice import describe_v5_leniency

    desc = describe_v5_leniency(v5)
    return f"Active now: {desc}." if desc else "Active now: **nothing** (normal random dice)."


def _v5_switch_sentence(switch: str, value: Any) -> str:
    if switch == "no_bestial":
        return (
            "Hunger dice never show **1**, so a roll can't be a **bestial failure**."
            if value else "Hunger dice can show **1** again (bestial failures possible)."
        )
    if switch == "no_messy":
        return (
            "Hunger dice never show **10**, so no **messy critical** from Hunger tens."
            if value else "Hunger dice can show **10** again (messy criticals possible)."
        )
    if not value:
        return "No minimum successes."
    dice = "die shows" if value == 1 else "dice show"
    return f"At least **{value}** {dice} **6+** on every roll (never more than the pool)."


def _parse_v5_dice_diff(parts: List[str]) -> Tuple[str, Any]:
    """`no-bestial on`, `no-messy off`, `successes 2` -> (switch key, value)."""
    word = parts[0]
    arg = parts[1] if len(parts) > 1 else ""
    if word in ("no-bestial", "no-messy"):
        if len(parts) > 2:
            raise RequestValidationError(f"Usage: `/ai dice-diff {word} on` or `/ai dice-diff {word} off`.")
        if arg not in ("on", "off"):
            raise RequestValidationError(f"Usage: `/ai dice-diff {word} on` or `/ai dice-diff {word} off`.")
        return word.replace("-", "_"), arg == "on"
    # fullmatch on ASCII digits: str.isdigit() accepts "²", which int() can't parse
    if len(parts) > 2 or not re.fullmatch(r"[0-3]", arg):
        raise RequestValidationError("Usage: `/ai dice-diff successes <0–3>`.")
    return "min_successes", int(arg)


def _dice_diff_v5(raw: str, cur, conn, campaign_id: int, location_id: int) -> Dict[str, Any]:
    from services.v5_dice import normalize_v5_leniency

    cur.execute(
        """
        SELECT dice_leniency_floor, dice_leniency_v5 FROM locations
        WHERE id = %s AND campaign_id = %s AND is_active = TRUE
        """,
        (location_id, campaign_id),
    )
    row = cur.fetchone()
    if row is None:
        raise RequestValidationError("This room isn't part of the chronicle (or was removed).")
    floor = _valid_floor(row.get("dice_leniency_floor"))
    current = normalize_v5_leniency(row.get("dice_leniency_v5"))

    if not raw:
        note = ""
        if floor is not None:
            note = (
                f"\n\n_A Classic floor (**{floor}**) is stored for this room; V5 rolls ignore it. "
                "`/ai dice-diff restore` clears it._"
            )
        display = (
            "**`/ai dice-diff`** — V5 dice leniency in **this room only**\n\n"
            f"{_v5_active_line(current)}\n\n" + _DICE_DIFF_V5_USAGE + note
        )
        return _dice_diff_result(display, floor, current)

    parts = raw.replace(",", " ").split()
    if parts[0] in _DICE_DIFF_RESTORE_WORDS:
        cur.execute(
            """
            UPDATE locations SET dice_leniency_floor = NULL, dice_leniency_v5 = NULL
            WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """,
            (location_id, campaign_id),
        )
        conn.commit()
        display = (
            "**`/ai dice-diff restore`**\n\n"
            "Leniency is **off** for this room. All V5 switches are cleared; dice are fully random again."
        )
        return _dice_diff_result(display, None, None)
    if parts[0] not in _DICE_DIFF_V5_WORDS:
        raise RequestValidationError(_DICE_DIFF_V5_HINT)

    key, value = _parse_v5_dice_diff(parts)
    settings = dict(current or {"no_bestial": False, "no_messy": False, "min_successes": 0})
    settings[key] = value
    new = normalize_v5_leniency(settings)
    cur.execute(
        """
        UPDATE locations SET dice_leniency_v5 = %s
        WHERE id = %s AND campaign_id = %s AND is_active = TRUE
        """,
        (json.dumps(new) if new else None, location_id, campaign_id),
    )
    conn.commit()
    display = (
        f"**`/ai dice-diff {' '.join(parts)}`**\n\n"
        f"**This room** (V5): {_v5_switch_sentence(key, value)}\n\n"
        f"{_v5_active_line(new)} Clear all with **`/ai dice-diff restore`**."
    )
    return _dice_diff_result(display, floor, new)


def execute_dice_diff_command(
    payload: str,
    user_id: int,
    campaign_id: int,
    location_id: int,
) -> Dict[str, Any]:
    """
    Room dice leniency (owner or site admin). Classic chronicles: a floor 2-10
    (services.wod_dice). V5 chronicles: the no-bestial / no-messy / successes switches
    (services.v5_dice). Each edition refuses the other's settings with a hint.
    """
    from database import get_db

    _gs, edition = _fetch_campaign_rules(campaign_id)
    raw = (payload or "").strip().lower()
    if not raw and edition != "v5":
        display = (
            "**`/ai dice-diff`** — lenient **d10** rolls in **this room only** (Classic)\n\n"
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
        if edition == "v5":
            return _dice_diff_v5(raw, cur, conn, campaign_id, location_id)
        cur.execute(
            """
            SELECT dice_leniency_floor FROM locations
            WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """,
            (location_id, campaign_id),
        )
        if cur.fetchone() is None:
            raise RequestValidationError("This room isn't part of the chronicle (or was removed).")
        if raw in _DICE_DIFF_RESTORE_WORDS:
            cur.execute(
                """
                UPDATE locations SET dice_leniency_floor = NULL, dice_leniency_v5 = NULL
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
            if parts[0] in _DICE_DIFF_V5_WORDS:
                raise RequestValidationError(_DICE_DIFF_CLASSIC_HINT)
            try:
                v = int(parts[0])
            except (ValueError, IndexError) as e:
                raise RequestValidationError(
                    "Usage: `/ai dice-diff <2–10>` or `/ai dice-diff restore`."
                ) from e
            if v < 2 or v > 10:
                raise RequestValidationError("Floor must be between **2** and **10**.")
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
                f"**This room** now uses leniency floor **{v}** (Classic): no **1**s; with multiple dice, "
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

    game_system, edition = _fetch_campaign_rules(campaign_id)
    lf, v5_lenient = _fetch_location_dice_leniency(campaign_id, location_id)

    if edition == "v5":
        from services.v5_dice import format_v5_roll_markdown, parse_v5_roll_expression, roll_v5

        pool, diff, hunger = parse_v5_roll_expression(payload)
        res = roll_v5(pool, hunger, diff, v5_leniency=v5_lenient)
        return {
            "ok": True,
            "command": "roll",
            "display_markdown": format_v5_roll_markdown(res, game_system=game_system),
            "roll": {
                "rules_edition": "v5",
                "dice": res["results"],
                "normal_dice": res["normal_dice"],
                "hunger_dice": res["hunger_dice"],
                "pool": res["pool"],
                "hunger": res["hunger"],
                "difficulty": res["difficulty"],
                "successes": res["successes"],
                "net_successes": res["successes"],
                "margin": res["margin"],
                "outcome": res["outcome"],
                "is_critical": res["is_critical"],
                "is_messy_critical": res["is_messy_critical"],
                "is_bestial_failure": res["is_bestial_failure"],
                "is_total_failure": res["is_total_failure"],
                "botch": False,
                "v5_leniency": res["v5_leniency"],
            },
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }

    pool, diff = parse_roll_expression(payload, default_difficulty=6)
    result = roll_storyteller_pool(pool, diff, leniency_floor=lf)
    display = format_storyteller_roll_markdown(result, game_system=game_system)
    return {
        "ok": True,
        "command": "roll",
        "display_markdown": display,
        "roll": {
            "rules_edition": "classic",
            "dice": result.dice,
            "pool": result.pool,
            "difficulty": result.difficulty,
            "net_successes": result.net_successes,
            "botch": result.botch,
            "is_exceptional": result.exceptional,
            "leniency_floor": result.leniency_floor,
        },
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }


def execute_rouse_command(
    payload: str,
    user_id: int,
    campaign_id: Optional[int] = None,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    V5 Rouse check. Stateless: Hunger comes from the payload (default 0).
    Always a plain d10 against 6: room leniency never applies to Rouse checks.
    """
    from services.v5_dice import format_rouse_markdown, rouse_check

    _gs, edition = _fetch_campaign_rules(campaign_id)
    if campaign_id and edition != "v5":
        raise RequestValidationError("`/ai rouse` is a V5 rule; this campaign uses classic (Revised) rules.")
    raw = (payload or "").strip()
    hunger = 0
    if raw:
        if not re.fullmatch(r"[0-5]", raw):
            raise RequestValidationError("Usage: `/ai rouse` or `/ai rouse <hunger 0–5>`.")
        hunger = int(raw)
    res = rouse_check(hunger)
    display = "**`/ai rouse`** — V5\n\n" + format_rouse_markdown(res)
    return {
        "ok": True,
        "command": "rouse",
        "display_markdown": display,
        "rouse": {**res, "rules_edition": "v5"},
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
        display = (
            "**`/ai respond`** — needs an LLM\n\n" + RESPOND_DIAGNOSTICS_NOTE + "\n\n"
            + _llm_snapshot_for_errors()
        )
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
        "player_message": payload or "",
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


# The Storyteller line after /ai explain must not carry numbers (the breakdown has them all) nor
# contradict the outcome; storyteller_line_problem() checks both and the line is dropped
# (the deterministic explanation is posted alone).
EXPLAIN_LLM_CONFIG = {"max_tokens": 180, "temperature": 0.6, "top_p": 0.9}
EXPLAIN_HEALTH_TTL_S = 30.0
_explain_health = {"at": None, "ok": False}

_DIGIT_RE = re.compile(r"\d")
# Matched on lowercased text without Greek accents (_fold). Singular / verb forms only: a failed
# V5 roll can still have "some successes".
_SUCCESS_RE = re.compile(
    r"\b(succeed\w*|successful\w*|success\b|you (?:win|won|pass|passed|made it|pull it off)"
    r"|πετυχ\w*|επιτυχια\b|επιτυχημεν\w*|κερδισ\w*|τα καταφερ\w*|καταφερν\w*)"
)
_FAILURE_RE = re.compile(
    r"\b(fail\w*|botch\w*|you (?:lose|lost)|απετυχ\w*|αποτυχ\w*|αποτυγχ\w*|εχασ\w*)"
)
_NEGATIONS = frozenset(
    "not no never without nor cannot can't don't didn't won't isn't wasn't doesn't n't "
    "δεν δε μην μη οχι χωρις καμια κανενα ουτε".split()
)


def _fold(text: str) -> str:
    """Lowercase, Greek accents removed (πέτυχες -> πετυχες), apostrophes kept."""
    import unicodedata

    norm = unicodedata.normalize("NFD", (text or "").lower().replace("’", "'"))
    return "".join(c for c in norm if unicodedata.category(c) != "Mn")


def _says(regex: "re.Pattern[str]", folded: str) -> bool:
    """A match of regex that isn't negated by one of the three words before it."""
    for m in regex.finditer(folded):
        before = re.findall(r"[\w']+", folded[: m.start()])[-3:]
        if not any(w in _NEGATIONS or w.endswith("n't") for w in before):
            return True
    return False


def roll_succeeded(facts: Dict[str, Any]) -> bool:
    if facts.get("rouse"):
        return bool(facts.get("success"))
    if facts.get("rules_edition") == "v5":
        return facts.get("outcome") == "win"
    return int(facts.get("net_successes") or 0) > 0


def storyteller_line_problem(text: str, facts: Dict[str, Any]) -> Optional[str]:
    """Why the Storyteller line can't be posted ('digits' / 'outcome'), or None."""
    if _DIGIT_RE.search(text or ""):
        return "digits"
    folded = _fold(text)
    if roll_succeeded(facts):
        if _says(_FAILURE_RE, folded):
            return "outcome"
    elif _says(_SUCCESS_RE, folded):
        return "outcome"
    return None


def llm_available_cached(now: Optional[float] = None) -> bool:
    """The health check's llm_available, cached EXPLAIN_HEALTH_TTL_S seconds. Never raises."""
    now = time.monotonic() if now is None else now
    at = _explain_health["at"]
    if at is not None and now - at < EXPLAIN_HEALTH_TTL_S:
        return _explain_health["ok"]
    try:
        from services.health_check import get_health_check_service

        ok = bool(get_health_check_service().check_all_services().get("llm_available"))
    except Exception as e:  # noqa: BLE001
        logger.warning("/ai explain: health check failed: %s", e)
        ok = False
    _explain_health.update(at=now, ok=ok)
    return ok


def explain_language(verb: str, payload: str, user_id: Optional[int]) -> str:
    """Greek for the Greek alias or a Greek payload, else the requester's UI language, else English."""
    from services.language import detect_language, user_ui_language

    if verb in GREEK_EXPLAIN_VERBS or detect_language(payload or "") == "el":
        return "el"
    return user_ui_language(user_id) or "en"


def explain_storyteller_line(
    explanation: Dict[str, Any],
    lang: str,
    *,
    campaign_id: Optional[int],
    user_id: Optional[int],
    rules_edition: str,
    game_system: str,
) -> Optional[str]:
    """
    2-3 sentences from the Storyteller on what the explained roll means in play, or None
    (no LLM, a failed call, a reply with digits or one that contradicts the outcome).
    The rule books are searched with a dice intent (services.rules_edition.rule_book_plan).
    """
    if not llm_available_cached():
        return None
    try:
        from services.llm_service import get_llm_service

        outcome = "the roll SUCCEEDED" if roll_succeeded(explanation["facts"]) else "the roll FAILED"
        prompt = (
            "A player asked what this dice roll means. The app has already counted it; these facts "
            "are final:\n"
            f"{explanation['summary']}\n"
            f"In short: {outcome}.\n\n"
            "In 2-3 short sentences, as the Storyteller, say what this result means at the table now. "
            "Write no digits and no numbers at all, do not recount anything, do not list the dice, "
            "and never say the opposite of the outcome above."
        )
        context = {
            "system_prompt": (
                "You are the Storyteller of a World of Darkness chronicle, talking to a player out of "
                "character about a dice roll that was already resolved by the app. The numbers you are "
                "given are correct and final; never contradict them. No headings, no lists, no markdown."
            ),
            "campaign_id": campaign_id,
            "rules_edition": rules_edition,
            "game_system": game_system,
            "player_user_id": user_id,
            "reply_language": lang,
            "ai_role": "storyteller",
            # A question about dice: search the rule books' rules kinds (no classifier call).
            "laya_intent": {"label": "dice", "score": 1.0},
            "rag_budget_tokens": 600,
        }
        text = get_llm_service().generate_response(prompt, context, dict(EXPLAIN_LLM_CONFIG),
                                                   raise_on_error=True)
    except Exception as e:  # noqa: BLE001 - the deterministic part is posted without it
        logger.warning("/ai explain: no Storyteller line: %s", e)
        return None
    text = " ".join(str(text or "").split())
    if not text:
        return None
    problem = storyteller_line_problem(text, explanation["facts"])
    if problem:
        logger.warning("/ai explain: Storyteller line dropped (%s)", problem)
        return None
    return text


def execute_explain_command(
    verb: str,
    payload: str,
    user_id: int,
    campaign_id: Optional[int],
    location_id: Optional[int],
    reply_to_id: Optional[int] = None,
    *,
    with_storyteller: bool = True,
) -> Dict[str, Any]:
    """
    `/ai explain` — explain a dice roll (services.roll_explainer). Any member of the chronicle
    (checked at the HTTP layer). The target is the replied-to dice card, else the newest roll
    in the room the requester can see; hidden rolls only for admin / helper / the owner.
    """
    from services import roll_explainer as rx

    if not campaign_id or location_id is None:
        raise RequestValidationError("Open a campaign location first — `/ai explain` explains a roll in **this room**.")
    lang = explain_language(verb, payload, user_id)
    from database import get_db

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.role, c.created_by, c.game_system, c.rules_edition "
            "FROM users u, campaigns c WHERE u.id = %s AND c.id = %s",
            (user_id, campaign_id),
        )
        who = cur.fetchone() or {}
        sees_hidden = rx.can_see_hidden(who.get("role"), user_id, who.get("created_by"))
        game_system = str(who.get("game_system") or "")
        rec, note = rx.find_roll(cur, int(campaign_id), int(location_id), reply_to_id, sees_hidden, game_system)
        cur.close()
    finally:
        conn.close()

    if rec is None:
        return {
            "ok": True,
            "command": "explain",
            "language": lang,
            "display_markdown": rx.message_text(note if note in ("nothing", "no_record") else "nothing", lang),
            "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
        }
    hidden = bool(rec.get("hidden"))
    explanation = rx.explain(rec, lang, note)
    display = explanation["markdown"]
    line = None
    if with_storyteller:
        from services.rules_edition import edition_of

        line = explain_storyteller_line(
            explanation, lang, campaign_id=campaign_id, user_id=user_id,
            rules_edition=edition_of(who), game_system=game_system,
        )
        if line:
            display += "\n\n" + rx.storyteller_line_markdown(line, lang)
    out = {
        "ok": True,
        "command": "explain",
        "language": lang,
        "explain": {
            "facts": explanation["facts"],
            "mismatches": explanation["mismatches"],
            "target": "reply" if note is None else note,
            "hidden": hidden,
        },
        "storyteller_line": line,
        "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
    }
    if hidden:
        # A hidden roll is never posted to the room: no display_markdown (the route grants that
        # text for saving as a Storyteller line); the chat shows private_markdown to the
        # requester only.
        out["private_markdown"] = display
    else:
        out["display_markdown"] = display
    return out


def execute_ai_slash_command(
    verb: str,
    payload: str,
    user_id: int,
    *,
    campaign_id: Optional[int] = None,
    location_id: Optional[int] = None,
    reply_to_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Dispatch subcommand. Raises RequestValidationError for unknown verb or bad args."""
    if verb in EXPLAIN_VERBS:
        return execute_explain_command(
            verb, payload, user_id, campaign_id, location_id, reply_to_id
        )
    if verb == "help":
        return execute_help_command(user_id, campaign_id=campaign_id)
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
            raise RequestValidationError(
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
    if verb == "rouse":
        return execute_rouse_command(
            payload, user_id, campaign_id=campaign_id, location_id=location_id
        )
    if verb == "clean":
        if not campaign_id or location_id is None:
            raise RequestValidationError(
                "Open a campaign location first — `/ai clean` runs per **room**."
            )
        return execute_clean_command(payload, user_id, campaign_id, location_id)
    if verb == "dice-diff":
        if not campaign_id or location_id is None:
            raise RequestValidationError(
                "Open a campaign location first — `/ai dice-diff` applies to **this room**."
            )
        return execute_dice_diff_command(payload, user_id, campaign_id, location_id)
    raise RequestValidationError(f"Unknown /ai subcommand: {verb}")
