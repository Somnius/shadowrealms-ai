"""
Load WoD / crossover location-naming guidance from docs/ for AI suggestion prompts.

Canonical file (edit in repo): docs/location-naming-world-of-darkness.md
Docker: mount repo docs to /app/project_docs (see docker-compose).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_GUIDE_CACHE: Optional[str] = None
_GUIDE_MTIME: Optional[float] = None


def _candidate_paths() -> list[Path]:
    env = os.getenv("LOCATION_NAMING_DOCS_PATH", "").strip()
    paths: list[Path] = []
    if env:
        paths.append(Path(env))
    # Docker compose: ./docs -> /app/project_docs
    paths.append(Path("/app/project_docs/location-naming-world-of-darkness.md"))
    # Repo layout: backend/services/this.py -> parents[2] == repo root
    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    paths.append(repo_root / "docs" / "location-naming-world-of-darkness.md")
    return paths


def load_full_guide_text() -> str:
    """Return full markdown guide, or empty string if missing."""
    global _GUIDE_CACHE, _GUIDE_MTIME
    for p in _candidate_paths():
        try:
            if not p.is_file():
                continue
            mtime = p.stat().st_mtime
            if _GUIDE_CACHE is not None and _GUIDE_MTIME == mtime:
                return _GUIDE_CACHE
            text = p.read_text(encoding="utf-8", errors="replace")
            _GUIDE_CACHE = text
            _GUIDE_MTIME = mtime
            logger.info("Loaded location naming guide from %s", p)
            return text
        except OSError as e:
            logger.debug("Could not read %s: %s", p, e)
    logger.warning("Location naming guide not found; suggestions use campaign text only")
    return ""


def _slice_md_section(full: str, heading_line: str) -> str:
    """Extract markdown from `heading_line` (e.g. '## Foo') until next `## ` heading."""
    idx = full.find(heading_line)
    if idx < 0:
        return ""
    rest = full[idx:]
    nxt = rest.find("\n## ", len(heading_line))
    if nxt < 0:
        return rest.strip()
    return rest[:nxt].strip()


def excerpt_for_game_system(game_system: Optional[str]) -> str:
    """
    Return a focused excerpt for the LLM to reduce tokens while keeping tone.
    Falls back to capped full guide if section detection fails.
    """
    full = load_full_guide_text()
    if not full:
        return ""

    gs = (game_system or "").lower()
    if "vampire" in gs or "masquerade" in gs or "vtm" in gs or "kindred" in gs:
        main_h = "## Vampire: The Masquerade"
    elif "werewolf" in gs or "apocalypse" in gs or "wta" in gs or "garou" in gs:
        main_h = "## Werewolf: The Apocalypse"
    elif "mage" in gs or "ascension" in gs or "mta" in gs or "awakening" in gs:
        main_h = "## Mage: The Ascension"
    else:
        main_h = "## Generic / crossover WoD"

    how = _slice_md_section(full, "## How to use")
    body = _slice_md_section(full, main_h)
    if body:
        parts = [p for p in (how, body) if p]
        return "\n\n---\n\n".join(parts).strip()

    if len(full) > 12000:
        return full[:12000] + "\n\n[… truncated …]"
    return full


def build_enriched_suggestion_prompt(
    *,
    game_system: str,
    campaign_name: str,
    setting_description: str,
) -> Tuple[str, str]:
    """
    Returns (user_prompt, system_prompt) for the LLM service.
    """
    guide = excerpt_for_game_system(game_system)
    guide_block = (
        "\n\n--- NAMING & TONE REFERENCE (follow vocabulary and patterns) ---\n"
        + guide
        + "\n--- END REFERENCE ---\n"
        if guide
        else ""
    )

    user_prompt = f"""You are a storyteller for a {game_system} tabletop RPG campaign.

Campaign: {campaign_name}
Setting: {setting_description}
{guide_block}
Suggest 5 atmospheric locations that are SPECIFIC to this campaign's setting. Use terminology and naming style consistent with the reference above when it applies.

For each location, provide:
- Name (short, evocative, fitting the setting and game tone)
- Type (prefer WoD-flavored types when appropriate: elysium, haven, domain, caern, bawn, chantry, node, umbra, custom — not only generic fantasy labels)
- Description (2-3 sentences, atmospheric and setting-specific)

IMPORTANT: Make these locations unique to THIS campaign's world. Avoid bland generic fantasy unless the setting explicitly demands it.

Format your response as ONLY a JSON array, nothing else:
[
  {{"name": "Location Name", "type": "custom", "description": "Description here"}},
  ...
]

Be specific, evocative, and true to the campaign's theme."""

    system_prompt = (
        f"You are a creative storyteller for {game_system} RPGs. "
        "Generate unique, setting-specific locations using mature World of Darkness tone when the reference material applies."
    )
    return user_prompt, system_prompt
