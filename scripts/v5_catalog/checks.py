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

CATALOGS = ("books", "clans", "disciplines", "rituals", "ceremonies", "formulae", "predator_types",
            "advantages", "loresheets")
SHINGLE = 8
MAX_DESC = 240
_ID_PREFIX = {"clans": "clan:", "disciplines": "discipline:", "rituals": "ritual:",
              "ceremonies": "ceremony:", "formulae": "formula:", "predator_types": "predator:",
              "loresheets": "loresheet:"}
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
    clan_ids = {e["id"] for e in data["clans"]["entries"]}
    disc_ids = {e["id"] for e in data["disciplines"]["entries"]}
    power_ids = {p["id"] for d in data["disciplines"]["entries"] for p in d["powers"]}
    adv_ids = {e["id"] for e in data["advantages"]["entries"]}
    adv_groups = {(e["kind"], re.sub(r"[^a-z0-9]+", "-", e["group"].lower()).strip("-"))
                  for e in data["advantages"]["entries"]}

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
        for kind, grants in (("merit/background", e.get("advantages", [])), ("flaw", e.get("flaws", []))):
            for grant in grants:
                for opt in grant["options"]:
                    out += _grant_problems(e["id"], opt, kind, adv_ids, adv_groups)
    for e in data["advantages"]["entries"]:
        check_book(e["id"], e)
        if not e["id"].startswith(e["kind"] + ":"):
            out.append(f"- {e['id']}: id prefix does not match kind {e['kind']}")
        for cl in (e.get("clans_only") or []) + [x["clan"] for x in e.get("cannot_buy_for", [])]:
            if cl not in clan_ids:
                out.append(f"- {e['id']}: clan {cl} does not exist")
        for ex in e.get("excludes", []):
            if ex not in adv_ids:
                out.append(f"- {e['id']}: excluded entry {ex} does not exist")
    for e in data["loresheets"]["entries"]:
        check_book(e["id"], e)
        if [lv["dots"] for lv in e["levels"]] != [1, 2, 3, 4, 5]:
            out.append(f"- {e['id']}: levels must be dots 1-5 once each")
        level_clans = [cl for lv in e["levels"] for cl in lv.get("clans_only") or []]
        for cl in (e.get("clans_only") or []) + (e.get("clans_excluded") or []) + level_clans:
            if cl not in clan_ids:
                out.append(f"- {e['id']}: clan {cl} does not exist")
        if e.get("source") != "online" and any(lv.get("name") is None for lv in e["levels"]):
            out.append(f"- {e['id']}: a level name is null on an entry read from a book (only online facts may lack it)")
        if e.get("source") == "online" and not e.get("source_urls"):
            out.append(f"- {e['id']}: an online entry needs source_urls")
        for d in e.get("disciplines_only") or []:
            if d not in disc_ids:
                out.append(f"- {e['id']}: Discipline {d} does not exist")
    for e in data["clans"]["entries"]:
        for fl in (e.get("creation") or {}).get("flaws", []):
            if fl["id"] not in adv_ids:
                out.append(f"- {e['id']}: creation flaw {fl['id']} is not in advantages.json")
    return out


def _grant_problems(owner: str, opt: dict, kind: str, adv_ids: set, adv_groups: set) -> list[str]:
    """A predator grant option must name an advantages.json entry, or (group: true) a group."""
    oid = opt["id"]
    if opt.get("group"):
        k, _, g = oid.partition(":")
        if (k, g) not in adv_groups:
            return [f"- {owner}: grant group {oid} matches no {k} group in advantages.json"]
        return []
    if oid not in adv_ids:
        return [f"- {owner}: grant option {oid} is not in advantages.json"]
    if kind == "flaw" and not oid.startswith("flaw:"):
        return [f"- {owner}: {oid} is granted as a Flaw but is not one"]
    if kind != "flaw" and oid.startswith("flaw:"):
        return [f"- {owner}: {oid} is granted as an Advantage but is a Flaw"]
    return []


def description_problems(catalog_dir: Path, data: dict) -> list[str]:
    """Every entry, power, clan Bane, clan Compulsion and loresheet level carries desc.en and
    desc.el (non-empty, <= 240 chars), and every key in descriptions/*.json names something in
    the catalog."""
    from . import merge

    out = []
    targets = dict(merge.desc_targets(data))
    for key, holder in targets.items():
        d = holder.get("desc")
        if not isinstance(d, dict):
            out.append(f"- {key}: no description (desc.en + desc.el)")
            continue
        for lang in ("en", "el"):
            text = d.get(lang)
            if not isinstance(text, str) or not text.strip():
                out.append(f"- {key}: desc.{lang} missing")
            elif len(text) > MAX_DESC:
                out.append(f"- {key}: desc.{lang} is {len(text)} chars (max {MAX_DESC})")
    ddir = catalog_dir / "descriptions"
    for f in sorted(ddir.glob("*.json")) if ddir.exists() else []:
        if f.stem not in merge.DESC_CATALOGS:
            out.append(f"- descriptions/{f.name}: not a catalog name ({', '.join(merge.DESC_CATALOGS)})")
            continue
        for key in json.loads(f.read_text(encoding="utf-8")):
            if key not in targets:
                out.append(f"- descriptions/{f.name}: {key} is not in the catalog")
    return out


def structural(catalog_dir: Path) -> list[str]:
    data = load_catalog(catalog_dir)
    return (schema_problems(catalog_dir, data) + id_problems(data) + reference_problems(data)
            + description_problems(catalog_dir, data))


# --------------------------------------------------------------------------- overlap gate

def words(text: str) -> list[str]:
    text = re.sub(r"[-\u00ad]\s*\n\s*", "", text)  # undo hyphenation at line ends (soft hyphens too)
    text = text.replace("\u00ad", "").replace("’", "'").lower()
    return re.findall(r"[a-z0-9']+", text)


def shingles(tokens: list[str], n: int = SHINGLE) -> set:
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


# printed facts the catalog must carry as printed (names, dice pools, restrictions): not prose
FACT_KEYS = {"name", "aliases", "dice_pool", "pool", "restriction", "title"}


def catalog_strings(obj) -> list[str]:
    """Every prose string in a catalog file (descriptions, notes); FACT_KEYS values are skipped."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() if k not in FACT_KEYS for s in catalog_strings(v)]
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
    """Every cached page twice: the -layout text, and the reading-order text from the cached
    boxes (column by column). The layout text puts two columns on one physical line, so a run
    copied across a line break inside a column is only contiguous in the reading-order text."""
    from .sources.pdf import column_order

    texts = []
    for f in sorted(build_dir.glob("*/*/pages/*.txt")):
        texts.append(f.read_text(encoding="utf-8"))
    for f in sorted(build_dir.glob("*/*/pages/*.json")):
        try:
            boxes = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        texts.append("\n".join(b["t"] for b in column_order(boxes)))
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
