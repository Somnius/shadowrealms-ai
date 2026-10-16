"""
Ghouls and their domitors (docs/CHARACTER_SHEET_BLOCKS.md, "V5: Ghoul").

A ghoul is a characters row with wod_meta.sheet_kind = 'ghoul', no chronicle of its own
(campaign_id NULL) and the same owner as its domitor; wod_meta.ghoul.domitor.character_id is the
link. There is no column for it: a vampire's ghouls are found among its owner's rows that have no
chronicle (one user's characters, a short list), so the routes, the AI prompt and the sheet share
these helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.character_sheet_v5 import is_ghoul
from services.classic_ghoul import domitor_generation
from services.rules_edition import V5, edition_of

# What GET /api/characters/<id> lists of a vampire's ghouls (the portrait included) ...
SUMMARY_COLUMNS = "id, name, portrait_url, wod_meta, rules_edition, is_active"
# ... and what the AI prompt formats (services/character_prompt.py): the sheet, no portrait.
SHEET_COLUMNS = (
    "id, name, user_id, campaign_id, system_type, attributes, skills, background, merits_flaws, wod_meta, "
    "rules_edition, is_active"
)
# A loose SQL prefilter so that only (likely) ghoul rows are read in full. It matches the JSON text
# with or without spaces after the colon (json.dumps defaults or compact separators); is_ghoul on the
# parsed wod_meta, in ghouls_of, is the source of truth.
_GHOUL_MARK = '%"sheet_kind"%"ghoul"%'


def _meta(row: Any) -> Dict[str, Any]:
    raw = row.get("wod_meta") if isinstance(row, dict) else None
    if isinstance(raw, dict):
        return raw
    try:
        out = json.loads(raw) if isinstance(raw, str) and raw else {}
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def ghoul_block(wod_meta: Any) -> Dict[str, Any]:
    """wod_meta.ghoul of a ghoul's sheet ({} for anything else)."""
    meta = wod_meta if isinstance(wod_meta, dict) else _meta({"wod_meta": wod_meta})
    g = meta.get("ghoul") if is_ghoul(meta) else None
    return g if isinstance(g, dict) else {}


def domitor_id(wod_meta: Any) -> Optional[int]:
    """The domitor's character id a ghoul's sheet names, or None."""
    dom = ghoul_block(wod_meta).get("domitor")
    cid = dom.get("character_id") if isinstance(dom, dict) else None
    return cid if isinstance(cid, int) and not isinstance(cid, bool) and cid > 0 else None


def ghouls_of(cursor: Any, owner_id: Any, character_id: Any, columns: str = SHEET_COLUMNS) -> List[Dict[str, Any]]:
    """The ghoul rows whose domitor is this character, among its owner's rows without a chronicle
    (oldest first), with `columns` (SHEET_COLUMNS or SUMMARY_COLUMNS; wod_meta is always needed)."""
    if owner_id is None or character_id is None:
        return []
    cursor.execute(
        f"SELECT {columns} FROM characters WHERE user_id = %s AND campaign_id IS NULL AND wod_meta LIKE %s "
        "ORDER BY id ASC",
        (owner_id, _GHOUL_MARK),
    )
    want = str(character_id)
    out = []
    for r in cursor.fetchall() or []:
        meta = _meta(r)
        if is_ghoul(meta) and str(domitor_id(meta)) == want:
            out.append(dict(r))
    return out


def retainer_summaries(cursor: Any, owner_id: Any, character_id: Any) -> List[Dict[str, Any]]:
    """GET /api/characters/<id> of a vampire: its ghouls as [{id, name, portrait_url, template (V5),
    kind (Classic: vassal / independent / revenant), retainer_dots, rules_edition, is_active}]."""
    out = []
    for r in ghouls_of(cursor, owner_id, character_id, SUMMARY_COLUMNS):
        g = ghoul_block(_meta(r))
        out.append({
            "id": r["id"],
            "name": r.get("name"),
            "portrait_url": r.get("portrait_url"),
            "template": g.get("template"),
            "kind": g.get("kind"),
            "retainer_dots": g.get("retainer_dots"),
            "rules_edition": edition_of(r),
            "is_active": bool(r.get("is_active", True)),
        })
    return out


def load_domitor(cursor: Any, character_id: Any) -> Optional[Dict[str, Any]]:
    """The row a ghoul's domitor id names (with its chronicle's name and creation settings), or None."""
    if character_id is None:
        return None
    cursor.execute(
        """
        SELECT ch.id, ch.name, ch.user_id, ch.campaign_id, ch.rules_edition, ch.system_type, ch.wod_meta,
               c.name AS campaign_name, c.creation_settings AS creation_settings
        FROM characters ch
        LEFT JOIN campaigns c ON ch.campaign_id = c.id
        WHERE ch.id = %s
        """,
        (character_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def domitor_summary(cursor: Any, ghoul_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """GET /api/characters/<id> of a ghoul: {id, name, clan, generation, campaign_id, campaign_name,
    exists} (generation: a Classic domitor's, as a number; null on V5).
    The name and clan the sheet stored at creation stand in when the domitor's row is gone (or
    belongs to someone else since)."""
    g = ghoul_block(_meta(ghoul_row))
    dom = g.get("domitor") if isinstance(g.get("domitor"), dict) else {}
    cid = domitor_id(_meta(ghoul_row))
    if cid is None:
        return None
    row = load_domitor(cursor, cid)
    exists = bool(row) and str(row.get("user_id")) == str(ghoul_row.get("user_id"))
    if not exists:
        return {"id": cid, "name": dom.get("name"), "clan": dom.get("clan"), "generation": dom.get("generation"),
                "campaign_id": None, "campaign_name": None, "exists": False}
    classic = edition_of(row) != V5
    return {
        "id": row["id"],
        "name": row.get("name"),
        "clan": _meta(row).get("clan") or dom.get("clan"),
        "generation": domitor_generation(_meta(row)) if classic else None,
        "campaign_id": row.get("campaign_id"),
        "campaign_name": row.get("campaign_name"),
        "exists": True,
    }
