"""Catalog gate: schema, unique ids, references, and no 8-word runs of book text.

`structural(catalog_dir)` needs only the committed files (CI runs it through
backend/tests/unit/test_v5_catalog.py). `overlap(...)` needs the local page cache
(data/catalog-build/, never in git) and runs in `python -m scripts.v5_catalog check`.

Every problem is a line starting with "- "; other lines are information.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import schema_lite

CATALOGS = ("books", "clans", "disciplines", "rituals", "ceremonies", "formulae", "predator_types")
SHINGLE = 8
_ID_PREFIX = {"clans": "clan:", "disciplines": "discipline:", "rituals": "ritual:",
              "ceremonies": "ceremony:", "formulae": "formula:", "predator_types": "predator:"}
# advantage ids are referenced by predator grants before Part C builds advantages.json
ADVANTAGE_PREFIXES = ("background:", "merit:", "flaw:")


def load_catalog(catalog_dir: Path) -> dict:
    return {name: json.loads((catalog_dir / f"{name}.json").read_text(encoding="utf-8"))
            for name in CATALOGS}


def schema_problems(catalog_dir: Path, data: dict) -> list[str]:
    out = []
    for name in CATALOGS:
        sp = catalog_dir / "schema" / f"{name}.schema.json"
        if not sp.exists():
            out.append(f"- schema file missing: schema/{name}.schema.json")
            continue
        schema = json.loads(sp.read_text(encoding="utf-8"))
        out += [f"- {name}.json {e}" for e in schema_lite.validate(data[name], schema)]
    return out


def all_ids(data: dict) -> list[str]:
    ids = []
    for name in CATALOGS:
        if name == "books":
            continue
        for e in data[name]["entries"]:
            ids.append(e["id"])
            for p in e.get("powers", []):
                ids.append(p["id"])
    return ids


def id_problems(data: dict) -> list[str]:
    out = []
    seen = set()
    for i in all_ids(data):
        if i in seen:
            out.append(f"- duplicate id {i}")
        seen.add(i)
    for name, prefix in _ID_PREFIX.items():
        for e in data[name]["entries"]:
            if not e["id"].startswith(prefix):
                out.append(f"- {name}: id {e['id']} should start with {prefix}")
    books = [b["book_id"] for b in data["books"]["entries"]]
    if len(books) != len(set(books)):
        out.append("- books.json: duplicate book_id")
    return out


def _book_refs(e: dict):
    if "book" in e:
        yield e["book"], e.get("page")
    for a in e.get("also_in", []) or []:
        yield a["book"], a["page"]


def reference_problems(data: dict) -> list[str]:
    out = []
    books = {b["book_id"] for b in data["books"]["entries"]}
    ids = set(all_ids(data))
    clan_ids = {e["id"] for e in data["clans"]["entries"]}
    disc_ids = {e["id"] for e in data["disciplines"]["entries"]}
    power_ids = {p["id"] for d in data["disciplines"]["entries"] for p in d["powers"]}

    def check_book(where, e):
        for b, _p in _book_refs(e):
            if b not in books:
                out.append(f"- {where}: book {b!r} is not in books.json")

    def check_prereq(where, pre):
        if pre is None:
            return
        for pid in re.findall(r'"(power:[^"]+)"', json.dumps(pre)):
            if pid not in power_ids:
                out.append(f"- {where}: prerequisite {pid} does not exist")

    for e in data["clans"]["entries"]:
        check_book(e["id"], e)
        for d in e["disciplines"]:
            if d not in disc_ids:
                out.append(f"- {e['id']}: Discipline {d} does not exist")
        for v in e.get("bane_variants", []):
            check_book(e["id"] + " bane variant", v)
        if e.get("compulsion"):
            check_book(e["id"] + " compulsion", e["compulsion"])
    for d in data["disciplines"]["entries"]:
        check_book(d["id"], d)
        for p in d["powers"]:
            check_book(p["id"], p)
            if p.get("amalgam") and p["amalgam"]["discipline"] not in disc_ids:
                out.append(f"- {p['id']}: amalgam Discipline {p['amalgam']['discipline']} does not exist")
            check_prereq(p["id"], p.get("prerequisite"))
            if not p["id"].startswith(d["id"].replace("discipline:", "power:") + ":"):
                out.append(f"- {p['id']}: power id does not match its Discipline {d['id']}")
    for name in ("rituals", "ceremonies", "formulae"):
        for e in data[name]["entries"]:
            check_book(e["id"], e)
            check_prereq(e["id"], e.get("prerequisite"))
            if e["discipline"] not in disc_ids:
                out.append(f"- {e['id']}: Discipline {e['discipline']} does not exist")
    for e in data["predator_types"]["entries"]:
        check_book(e["id"], e)
        for d in e["discipline_choice"]:
            if d["discipline"] not in disc_ids:
                out.append(f"- {e['id']}: Discipline {d['discipline']} does not exist")
            for cl in d.get("clans_only") or []:
                if cl not in clan_ids:
                    out.append(f"- {e['id']}: clan {cl} does not exist")
        for cl in e.get("forbidden_clans", []):
            if cl not in clan_ids:
                out.append(f"- {e['id']}: forbidden clan {cl} does not exist")
        for grant in e.get("advantages", []) + e.get("flaws", []):
            for opt in grant["options"]:
                oid = opt["id"]
                if not (oid in ids or oid.startswith(ADVANTAGE_PREFIXES)):
                    out.append(f"- {e['id']}: grant option {oid} is neither a catalog id nor an "
                               f"advantage id ({', '.join(ADVANTAGE_PREFIXES)})")
    return out


def structural(catalog_dir: Path) -> list[str]:
    data = load_catalog(catalog_dir)
    return schema_problems(catalog_dir, data) + id_problems(data) + reference_problems(data)


# --------------------------------------------------------------------------- overlap gate

def words(text: str) -> list[str]:
    text = re.sub(r"-\s*\n\s*", "", text)  # undo hyphenation at line ends
    text = text.replace("’", "'").lower()
    return re.findall(r"[a-z0-9']+", text)


def shingles(tokens: list[str], n: int = SHINGLE) -> set:
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def catalog_strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in catalog_strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in catalog_strings(v)]
    return []


def overlap(strings: list[str], source_texts: list[str], n: int = SHINGLE) -> list[str]:
    """Strings that share an n-word run with any of the source texts."""
    src = set()
    for t in source_texts:
        src |= shingles(words(t), n)
    out = []
    for s in strings:
        hit = shingles(words(s), n) & src
        if hit:
            out.append(f"- shares {n}-word run(s) with book/online text: {sorted(hit)[0]!r} in {s[:80]!r}")
    return out


def page_cache_texts(build_dir: Path) -> list[str]:
    texts = []
    for f in sorted(build_dir.glob("*/*/pages/*.txt")):
        texts.append(f.read_text(encoding="utf-8"))
    online = build_dir.parent / "online"
    for f in sorted(online.glob("**/*.json")) if online.exists() else []:
        try:
            texts.append(json.loads(f.read_text(encoding="utf-8")).get("text", ""))
        except (OSError, ValueError):
            pass
    return texts


def run_all(catalog_dir: Path, page_cache: bool = True) -> list[str]:
    from . import books

    out = structural(catalog_dir)
    if page_cache:
        texts = page_cache_texts(books.BUILD_DIR)
        if not texts:
            out.append("overlap gate skipped: no page cache under data/catalog-build/v5")
        else:
            strings = []
            for f in sorted(catalog_dir.glob("*.json")) + sorted(catalog_dir.glob("*/*.json")):
                if f.parent.name == "schema":
                    continue
                strings += catalog_strings(json.loads(f.read_text(encoding="utf-8")))
            strings = [s for s in strings if len(words(s)) >= SHINGLE]
            found = overlap(strings, texts)
            out += found
            out.append(f"overlap gate: {len(strings)} catalog strings of >= {SHINGLE} words checked "
                       f"against {len(texts)} cached pages; {len(found)} hits")
    return out
