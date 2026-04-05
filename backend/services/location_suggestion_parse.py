"""
Parse location suggestion JSON from LLM output (handles markdown fences, prose, trailing commas).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def _strip_markdown_fences(text: str) -> str:
    t = text.strip()
    if "```" not in t:
        return t
    # Prefer fenced block that looks like JSON array
    for part in t.split("```"):
        p = part.strip()
        if p.lower().startswith("json"):
            p = p[4:].lstrip()
        if p.startswith("["):
            return p
    return t


def _trailing_comma_fix(s: str) -> str:
    """Remove trailing commas before } or ] (common LLM mistake)."""
    return re.sub(r",(\s*[\]}])", r"\1", s)


def _try_parse_json_from_first_struct(raw: str) -> Any:
    """
    Parse first JSON value starting at first '[' or '{' (handles wrapped objects, prose before JSON).
    """
    text = _strip_markdown_fences(raw).strip()
    if not text:
        return None
    dec = json.JSONDecoder()
    for start_ch in ("[", "{"):
        i = text.find(start_ch)
        if i < 0:
            continue
        frag = _trailing_comma_fix(text[i:])
        try:
            obj, _ = dec.raw_decode(frag)
            return obj
        except json.JSONDecodeError:
            continue
    return None


def extract_json_array(raw: str) -> Optional[List[Any]]:
    """
    Extract the first top-level JSON array from model output.
    Uses bracket depth outside of quoted strings so descriptions with ] work.
    """
    if not raw or not raw.strip():
        return None

    text = _strip_markdown_fences(raw)
    start = text.find("[")
    if start < 0:
        return None

    in_string = False
    escape = False
    depth = 0

    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                for candidate in (chunk, _trailing_comma_fix(chunk)):
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, list):
                            return parsed
                    except json.JSONDecodeError:
                        continue
                logger.warning("Could not json.loads extracted array; first 120 chars: %s", chunk[:120])
                return None

    return None


def normalize_suggestion_items(items: List[Any]) -> List[dict]:
    """Ensure list of dicts with name, type, description keys."""
    out: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("Name") or "").strip()
        typ = (item.get("type") or item.get("Type") or "custom").strip()
        desc = (item.get("description") or item.get("Description") or "").strip()
        if name:
            out.append({"name": name, "type": typ or "custom", "description": desc})
    return out


def parse_location_suggestions(raw_response: str) -> Optional[List[dict]]:
    """
    Full pipeline: extract JSON array, normalize, return None if unusable.
    """
    if not raw_response:
        return None
    stripped = raw_response.strip()
    if stripped.startswith("Error") or stripped.startswith("Error:"):
        logger.warning("LLM returned error string instead of JSON: %s", stripped[:200])
        return None

    arr = extract_json_array(raw_response)
    if not arr:
        obj = _try_parse_json_from_first_struct(raw_response)
        if isinstance(obj, list):
            arr = obj
        elif isinstance(obj, dict):
            for key in ("locations", "suggestions", "items", "data", "places"):
                v = obj.get(key)
                if isinstance(v, list):
                    arr = v
                    break
    if not arr:
        # Last resort: whole body is JSON
        try:
            t = _strip_markdown_fences(raw_response).strip()
            parsed = json.loads(_trailing_comma_fix(t))
            if isinstance(parsed, list):
                arr = parsed
            elif isinstance(parsed, dict):
                for key in ("locations", "suggestions", "items", "data", "places"):
                    v = parsed.get(key)
                    if isinstance(v, list):
                        arr = v
                        break
        except json.JSONDecodeError:
            pass

    if not arr:
        return None

    normalized = normalize_suggestion_items(arr)
    return normalized if normalized else None
