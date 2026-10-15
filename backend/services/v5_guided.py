"""
Guided mode of the V5 forge (Forge v2 part E): the scenario questions in
docs/rules/v5/guided/questions.json (format: docs/rules/v5/guided/README.md). The browser scores
the answers (frontend/src/characterSheet/v5/guided.js); the server serves the file
(GET /api/rules/v5/guided) and can check it against the catalog (problems()).

Pure file reading (no Flask, no DB), cached by the file's modification time.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional

from services.character_sheet_v5 import V5_ATTRIBUTES, V5_SKILLS

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = (
    # docker-compose mounts ./docs read-only at /app/project_docs
    "/app/project_docs/rules/v5/guided/questions.json",
    # repo checkout (CI, local runs): backend/services -> <repo>/docs
    os.path.normpath(os.path.join(_HERE, "..", "..", "docs", "rules", "v5", "guided", "questions.json")),
)

AXES = ("clan", "predator", "attributes", "skills", "distribution")
ATTRIBUTE_CATEGORIES = ("physical", "social", "mental")
DISTRIBUTIONS = ("jack", "balanced", "specialist")
LANGUAGES = ("en", "el")
WEIGHT_MIN, WEIGHT_MAX = 1, 5
TEXT_MAX = 300
MAX_QUESTIONS, MIN_OPTIONS, MAX_OPTIONS = 30, 2, 10
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_TOP_KEYS = {"version", "author", "thresholds", "questions", "note"}
_QUESTION_KEYS = {"id", "axis", "text", "options", "note"}
_OPTION_KEYS = {"id", "text", "weights", "note"}

_lock = threading.Lock()
_cache: Dict[str, Any] = {"key": None, "data": None, "etag": None}


def guided_path() -> Optional[str]:
    """The questions file: $V5_GUIDED_FILE, the docs mount, or the repo copy."""
    env = os.getenv("V5_GUIDED_FILE")
    for path in ((env,) if env else ()) + _CANDIDATES:
        if path and os.path.isfile(path):
            return path
    return None


def load_guided() -> Optional[Dict[str, Any]]:
    """The question set as a dict; None when the file is missing or is not a JSON object."""
    path = guided_path()
    if not path:
        return None
    key = (path, os.path.getmtime(path), os.path.getsize(path))
    with _lock:
        if _cache["key"] == key:
            return _cache["data"]
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            data = json.loads(raw)
        except ValueError:
            logger.warning("guided questions: %s is not valid JSON", path)
            data = None
        if not isinstance(data, dict):
            data = None
        _cache.update(key=key, data=data, etag=hashlib.sha1(raw).hexdigest()[:20] if data else None)
        return data


def guided_etag() -> Optional[str]:
    """A short hash of the file (changes whenever it does); None without a usable file."""
    if load_guided() is None:
        return None
    return _cache["etag"]


def _is_weight(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and WEIGHT_MIN <= v <= WEIGHT_MAX


def _text_problems(where: str, text: Any) -> List[str]:
    if not isinstance(text, dict):
        return [f"{where}: text must be an object with 'en' and 'el'"]
    out = []
    for lang in LANGUAGES:
        v = text.get(lang)
        if not isinstance(v, str) or not v.strip():
            out.append(f"{where}: text.{lang} is missing or empty")
        elif len(v) > TEXT_MAX:
            out.append(f"{where}: text.{lang} is longer than {TEXT_MAX} characters")
    return out


def problems(data: Any, catalog: Dict[str, Any]) -> List[str]:
    """
    Everything wrong with a question set, as readable lines (empty when it is fine): shape, ids,
    EN + EL text, and that every weight key is a catalog clan or predator type name (English, as
    in the catalog), an Attribute category or Attribute key, a skill key, or a distribution.
    """
    if not isinstance(data, dict):
        return ["the file must hold a JSON object"]
    clans = {c.get("name") for c in catalog.get("clans") or [] if isinstance(c, dict)}
    predators = {p.get("name") for p in catalog.get("predator_types") or [] if isinstance(p, dict)}
    allowed = {
        "clan": clans,
        "predator": predators,
        "attributes": set(ATTRIBUTE_CATEGORIES) | set(V5_ATTRIBUTES),
        "skills": {k for names in V5_SKILLS.values() for k in names},
        "distribution": set(DISTRIBUTIONS),
    }
    out: List[str] = []
    out += [f"unknown key '{k}' at the top" for k in sorted(set(data) - _TOP_KEYS)]
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        out.append("version must be a whole number, 1 or more")
    th = data.get("thresholds")
    if not isinstance(th, dict):
        out.append("thresholds must be an object with min_score_share and min_lead")
    else:
        share, lead = th.get("min_score_share"), th.get("min_lead")
        if isinstance(share, bool) or not isinstance(share, (int, float)) or not 0 < share <= 1:
            out.append("thresholds.min_score_share must be a number above 0 and at most 1")
        if isinstance(lead, bool) or not isinstance(lead, (int, float)) or lead < 0:
            out.append("thresholds.min_lead must be a number, 0 or more")
        out += [f"unknown key '{k}' in thresholds" for k in sorted(set(th) - {"min_score_share", "min_lead"})]
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        return out + ["questions must be a non-empty list"]
    if len(questions) > MAX_QUESTIONS:
        out.append(f"at most {MAX_QUESTIONS} questions")
    seen_q = set()
    for qi, q in enumerate(questions):
        where = f"question {qi + 1}"
        if not isinstance(q, dict):
            out.append(f"{where}: must be an object")
            continue
        qid = q.get("id")
        if not isinstance(qid, str) or not ID_RE.match(qid):
            out.append(f"{where}: id must be lowercase letters, digits, '_' or '-' (at most 40)")
        elif qid in seen_q:
            out.append(f"{where}: id '{qid}' is used twice")
        else:
            seen_q.add(qid)
            where = f"question '{qid}'"
        out += [f"{where}: unknown key '{k}'" for k in sorted(set(q) - _QUESTION_KEYS)]
        out += _text_problems(where, q.get("text"))
        options = q.get("options")
        if not isinstance(options, list) or not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
            out.append(f"{where}: needs {MIN_OPTIONS} to {MAX_OPTIONS} options")
            continue
        seen_o = set()
        for oi, o in enumerate(options):
            ow = f"{where} option {oi + 1}"
            if not isinstance(o, dict):
                out.append(f"{ow}: must be an object")
                continue
            oid = o.get("id")
            if not isinstance(oid, str) or not ID_RE.match(oid):
                out.append(f"{ow}: id must be lowercase letters, digits, '_' or '-' (at most 40)")
            elif oid in seen_o:
                out.append(f"{ow}: id '{oid}' is used twice in this question")
            else:
                seen_o.add(oid)
                ow = f"{where} option '{oid}'"
            out += [f"{ow}: unknown key '{k}'" for k in sorted(set(o) - _OPTION_KEYS)]
            out += _text_problems(ow, o.get("text"))
            weights = o.get("weights", {})
            if not isinstance(weights, dict):
                out.append(f"{ow}: weights must be an object")
                continue
            for axis, w in weights.items():
                if axis not in AXES:
                    out.append(f"{ow}: unknown weight group '{axis}' (use {', '.join(AXES)})")
                    continue
                if not isinstance(w, dict):
                    out.append(f"{ow}: weights.{axis} must be an object")
                    continue
                for key, v in w.items():
                    if key not in allowed[axis]:
                        out.append(f"{ow}: weights.{axis} has an unknown key '{key}'")
                    if not _is_weight(v):
                        out.append(f"{ow}: weights.{axis}.{key} must be a whole number from {WEIGHT_MIN} to {WEIGHT_MAX}")
    return out
