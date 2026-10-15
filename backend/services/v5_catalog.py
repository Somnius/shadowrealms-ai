"""
The V5 rules catalog (docs/rules/v5/catalog/*.json, built by scripts/v5_catalog): clans,
Disciplines and their powers, rituals, ceremonies, formulae and predator types, with book and
page, plus Merits/Backgrounds/Flaws (advantages.json) and loresheets when those are installed
(a missing file reads as an empty list). Facts only; short descriptions in our own words come
from descriptions/<catalog>.json ({id: {en, el}}) and are laid over the entries here.

Pure file reading (no Flask, no DB), cached by the files' modification times.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Any, Dict, List, Optional

CATALOGS = (
    "books", "clans", "disciplines", "rituals", "ceremonies", "formulae", "predator_types",
    "advantages", "loresheets",
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_CANDIDATES = (
    # docker-compose mounts ./docs read-only at /app/project_docs
    "/app/project_docs/rules/v5/catalog",
    # repo checkout (CI, local runs): backend/services -> <repo>/docs
    os.path.normpath(os.path.join(_HERE, "..", "..", "docs", "rules", "v5", "catalog")),
)

_lock = threading.Lock()
_cache: Dict[str, Any] = {"key": None, "data": None, "etag": None}


def catalog_dir() -> Optional[str]:
    """The catalog directory: $V5_CATALOG_DIR, the docs mount, or the repo copy."""
    env = os.getenv("V5_CATALOG_DIR")
    for path in ((env,) if env else ()) + _CANDIDATES:
        if path and os.path.isfile(os.path.join(path, "clans.json")):
            return path
    return None


def _entries(doc: Any) -> List[dict]:
    if isinstance(doc, dict):
        doc = doc.get("entries")
    return [e for e in doc or [] if isinstance(e, dict)]


def _overlay(entries: List[dict], descs: Dict[str, Any]) -> None:
    """Put desc {en, el} on every entry (and Discipline power, and loresheet or Background level,
    keyed "<id>:<dots>") that has one."""
    for e in entries:
        d = descs.get(e.get("id"))
        if isinstance(d, dict):
            e["desc"] = {k: v for k, v in d.items() if isinstance(v, str)}
        for p in e.get("powers") or []:
            if isinstance(p, dict):
                pd = descs.get(p.get("id"))
                if isinstance(pd, dict):
                    p["desc"] = {k: v for k, v in pd.items() if isinstance(v, str)}
        for lv in e.get("levels") or []:
            if isinstance(lv, dict) and e.get("id"):
                ld = descs.get(f"{e['id']}:{lv.get('dots')}")
                if isinstance(ld, dict):
                    lv["desc"] = {k: v for k, v in ld.items() if isinstance(v, str)}


def _files(path: str) -> List[str]:
    out = [os.path.join(path, f"{c}.json") for c in CATALOGS]
    ddir = os.path.join(path, "descriptions")
    if os.path.isdir(ddir):
        out += sorted(os.path.join(ddir, f) for f in os.listdir(ddir) if f.endswith(".json"))
    return [f for f in out if os.path.isfile(f)]


def load_catalog() -> Optional[Dict[str, Any]]:
    """
    {books, clans, disciplines, rituals, ceremonies, formulae, predator_types, advantages,
    loresheets}: lists of entries, descriptions laid over. None when no catalog is installed.
    """
    path = catalog_dir()
    if not path:
        return None
    files = _files(path)
    key = tuple((f, os.path.getmtime(f), os.path.getsize(f)) for f in files)
    with _lock:
        if _cache["key"] == key:
            return _cache["data"]
        data: Dict[str, Any] = {}
        h = hashlib.sha1()
        for c in CATALOGS:
            f = os.path.join(path, f"{c}.json")
            if not os.path.isfile(f):
                data[c] = []
                continue
            with open(f, "rb") as fh:
                raw = fh.read()
            h.update(raw)
            data[c] = _entries(json.loads(raw))
        ddir = os.path.join(path, "descriptions")
        if os.path.isdir(ddir):
            for f in sorted(os.listdir(ddir)):
                if not f.endswith(".json"):
                    continue
                with open(os.path.join(ddir, f), "rb") as fh:
                    raw = fh.read()
                h.update(raw)
                descs = json.loads(raw)
                if isinstance(descs, dict):
                    for c in CATALOGS:
                        _overlay(data[c], descs)
        _cache.update(key=key, data=data, etag=h.hexdigest()[:20])
        return data


def catalog_etag() -> Optional[str]:
    """A short hash of the catalog files (changes whenever a file does)."""
    if load_catalog() is None:
        return None
    return _cache["etag"]


def find(catalog: Dict[str, Any], kind: str, name_or_id: str) -> Optional[dict]:
    """An entry of one catalog by id, name or alias (case and spaces ignored)."""
    want = " ".join(str(name_or_id or "").split()).lower()
    if not want:
        return None
    for e in catalog.get(kind) or []:
        names = [e.get("id"), e.get("name"), *(e.get("aliases") or [])]
        if any(isinstance(n, str) and " ".join(n.split()).lower() == want for n in names):
            return e
    return None
