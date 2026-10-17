"""
Per-chronicle settings of "The chronicle so far" (docs/CHRONICLE.md), stored as JSON text in
campaigns.chronicle_settings, and the server-wide caps from the environment.

Shape (every key optional when sent; the normaliser fills defaults):
{
  "v": 1,
  "gap_hours": 6,          # a night ends after this many hours with no message (2-24)
  "table_talk": false,     # exports include table talk unless the export says otherwise
  "nightly": false,        # the nightly run (services/chronicle_nightly.py)
  "model": null            # null = the chronicler roles; else {"provider", "model"} from model_options()
}
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from services.request_validation import RequestValidationError

GAP_RANGE = (2, 24)
DEFAULTS: Dict[str, Any] = {"v": 1, "gap_hours": 6, "table_talk": False, "nightly": False, "model": None}


def _envi(name: str, default: int, low: int = 1) -> int:
    try:
        return max(low, int(os.environ.get(name) or default))
    except ValueError:
        return default


def max_nights_per_job() -> int:
    """Chapters (nights) written per job; the next Update carries on."""
    return _envi("CHRONICLE_MAX_NIGHTS_PER_JOB", 40)


def max_seconds_per_job() -> int:
    """After this many seconds of writing nights a job stops after the current night (partial)."""
    return _envi("CHRONICLE_MAX_SECONDS_PER_JOB", 3600, low=60)


def job_keep_days() -> int:
    """Finished job rows older than this are pruned."""
    return _envi("CHRONICLE_JOB_KEEP_DAYS", 90)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def normalize(raw: Any) -> Dict[str, Any]:
    """Stored text or dict -> a complete settings dict; anything broken falls back to the default."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    out = dict(DEFAULTS)
    g = raw.get("gap_hours")
    if _is_int(g) and GAP_RANGE[0] <= g <= GAP_RANGE[1]:
        out["gap_hours"] = g
    for k in ("table_talk", "nightly"):
        if isinstance(raw.get(k), bool):
            out[k] = raw[k]
    m = raw.get("model")
    if isinstance(m, dict) and isinstance(m.get("provider"), str) and isinstance(m.get("model"), str) \
            and m["provider"].strip() and m["model"].strip():
        out["model"] = {"provider": m["provider"].strip(), "model": m["model"].strip()}
    return out


def validate(data: Any, current: Dict[str, Any], options: List[Dict[str, Any]], is_admin: bool) -> Dict[str, Any]:
    """A PUT body merged over the current settings. Raises RequestValidationError on any bad field."""
    if not isinstance(data, dict):
        raise RequestValidationError("expected a JSON object")
    out = normalize(current)
    unknown = set(data) - {"gap_hours", "table_talk", "nightly", "model", "v"}
    if unknown:
        raise RequestValidationError("unknown setting")
    if "gap_hours" in data:
        g = data["gap_hours"]
        if not _is_int(g) or not GAP_RANGE[0] <= g <= GAP_RANGE[1]:
            raise RequestValidationError(f"gap_hours must be a whole number from {GAP_RANGE[0]} to {GAP_RANGE[1]}")
        out["gap_hours"] = g
    for k in ("table_talk", "nightly"):
        if k in data:
            if not isinstance(data[k], bool):
                raise RequestValidationError(f"{k} must be true or false")
            out[k] = data[k]
    if "model" in data:
        m = data["model"]
        if m is None or m == "":
            out["model"] = None
        else:
            if not isinstance(m, dict):
                raise RequestValidationError("model must be null or {provider, model}")
            pick = next((o for o in options if o["provider"] == m.get("provider") and o["model"] == m.get("model")), None)
            if not pick:
                raise RequestValidationError("model is not one the admin AI panel lists")
            if pick["cloud"] and not is_admin:
                raise RequestValidationError("only a site admin can pick a cloud writer")
            out["model"] = {"provider": pick["provider"], "model": pick["model"]}
    return out


def model_options() -> List[Dict[str, Any]]:
    """The models the admin AI panel lists: each AI role's configured (provider, model), resolved,
    without the small Ollama model (the writer never uses it). Cloud ones are marked."""
    from services import ai_roles

    seen, out = set(), []
    for role in ai_roles.ROLES:
        try:
            cfg = ai_roles.get_role_config(role)
            prov = cfg["provider"]
            if prov == "ollama":
                continue
            model = ai_roles._model_for(prov, cfg["model"], role)
        except Exception:  # noqa: BLE001 - one broken role never hides the others
            continue
        if not model or (prov, model) in seen:
            continue
        seen.add((prov, model))
        out.append({"provider": prov, "model": model, "cloud": prov in ai_roles.CLOUD_PROVIDERS})
    return out


def load(cursor, campaign_id: int) -> Dict[str, Any]:
    """The chronicle's settings; the defaults when the column or row is missing."""
    try:
        cursor.execute("SELECT chronicle_settings FROM campaigns WHERE id = %s", (campaign_id,))
        row = cursor.fetchone() or {}
    except Exception:  # noqa: BLE001 - before the column exists
        try:
            cursor.connection.rollback()
        except Exception:  # noqa: BLE001
            pass
        row = {}
    return normalize(row.get("chronicle_settings"))


def save(cursor, campaign_id: int, settings: Dict[str, Any]) -> None:
    cursor.execute("UPDATE campaigns SET chronicle_settings = %s WHERE id = %s",
                   (json.dumps(normalize(settings)), campaign_id))


def writer_chain(settings: Dict[str, Any], role: str) -> Optional[list]:
    """The (provider, model) chain for the writer when the chronicle overrides the model, else None.
    An override the admin panel no longer lists is ignored (the chronicler role is used)."""
    m = (settings or {}).get("model")
    if not m:
        return None
    if not any(o["provider"] == m["provider"] and o["model"] == m["model"] for o in model_options()):
        return None
    from services.ai_roles import fallback_chain

    chain = [(m["provider"], m["model"])]
    for item in fallback_chain(role):
        if item not in chain:
            chain.append(item)
    return chain
