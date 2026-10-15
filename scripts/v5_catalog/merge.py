"""Extracted intermediates + manual fact records -> the committed catalog JSON.

Pure functions over plain dicts (no I/O), so the rules are unit-tested on synthetic records:
  * one id per entry; when several books print the same entry, `book`/`page` point at the
    book with the lowest `precedence` (PG 20 beats Companion 30), the rest go to `also_in`,
    and every fact that differs between them is reported (the lower precedence wins);
  * manual records (docs/rules/v5/catalog/manual/*.json) patch, add, merge or exclude
    entries; an added entry gets source "manual", a patched one lists the hand-entered
    fields in `manual_fields` (its other facts keep their source);
  * prerequisites are resolved to power ids; a name that does not resolve is reported and
    the prerequisite is left out rather than guessed.
"""

from __future__ import annotations

import copy
import re

from .parsers import common as c

LOCAL_ONLY = ("snippet", "cost_text", "dice_pool_text", "prerequisite_text", "page_pdf",
              "confidence", "bullets", "other_bullets", "pool_text", "amalgam_unparsed")


def strip_local(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in LOCAL_ONLY}


def apply_manual(records: list[dict], manual: dict, report: list[str]) -> list[dict]:
    """manual = {"exclude": [{id, why}], "merge": [{from, into, why}],
    "rename": [{from, into, name, book?, why}], "patch": [{id, set, book?, why}], "add": [records]}.
    `book` limits a rename or patch to that book's record (a reprint elsewhere shares the id).
    Returns a new list."""
    recs = [copy.deepcopy(r) for r in records]
    for ex in manual.get("exclude", []):
        before = len(recs)
        recs = [r for r in recs if r["id"] != ex["id"]]
        if len(recs) == before:
            report.append(f"- manual exclude matched nothing: {ex['id']}")
    for mg in manual.get("merge", []):
        hit = False
        for r in recs:
            if r["id"] == mg["from"]:
                hit = True
                r.setdefault("aliases", [])
                if r["name"] not in r["aliases"]:
                    r["aliases"].append(r["name"])
                r["id"] = mg["into"]
                r["merged_from"] = mg["from"]
        if not hit:
            report.append(f"- manual merge matched nothing: {mg['from']}")
    for rn in manual.get("rename", []):
        hit = [r for r in recs if r["id"] == rn["from"] and (not rn.get("book") or r.get("book") == rn["book"])]
        if not hit:
            report.append(f"- manual rename matched nothing: {rn['from']}")
        for r in hit:  # a garbled title fixed by hand: new id and name, no alias kept
            r["id"], r["name"] = rn["into"], rn["name"]
            mf = r.setdefault("manual_fields", [])
            if "name" not in mf:
                mf.append("name")
    for p in manual.get("patch", []):
        hit = False
        for r in recs:
            if r["id"] == p["id"] and (not p.get("book") or r.get("book") == p["book"]):
                hit = True
                r.update(copy.deepcopy(p["set"]))
                mf = r.setdefault("manual_fields", [])
                mf += [k for k in p["set"] if k not in mf]
        if not hit:
            report.append(f"- manual patch matched nothing: {p['id']} ({p.get('book')})")
    for a in manual.get("add", []):
        rec = copy.deepcopy(a)
        rec.setdefault("source", "manual")
        recs.append(rec)
    return recs


def consolidate(records: list[dict], precedence: dict, report: list[str],
                facts: tuple = ("level", "amalgam", "prerequisite_text", "discipline", "kind")) -> list[dict]:
    """Group records by id; the lowest-precedence book is the primary."""
    groups: dict = {}
    for r in records:
        groups.setdefault(r["id"], []).append(r)
    out = []
    for rid in sorted(groups):
        grp = sorted(groups[rid], key=lambda r: (precedence.get(r.get("book"), 99), r.get("page") or 0))
        primary = copy.deepcopy(grp[0])
        also = []
        aliases = list(primary.get("aliases", []))
        for other in grp[1:]:
            if other.get("book") == primary.get("book") and other.get("page") == primary.get("page"):
                continue
            also.append({"book": other["book"], "page": other["page"]})
            for f in facts:
                a, b = primary.get(f), other.get(f)
                if f == "prerequisite_text":
                    a, b = _norm_prereq(a), _norm_prereq(b)
                if a != b and b is not None:
                    report.append(f"- {rid}: {f} differs: {primary['book']} p.{primary['page']} "
                                  f"has {a!r}, {other['book']} p.{other['page']} has {b!r} "
                                  f"(kept {primary['book']}, lower precedence)")
            if other.get("name") != primary.get("name") and other.get("name") not in aliases:
                aliases.append(other["name"])
            for al in other.get("aliases", []):
                if al not in aliases and al != primary["name"]:
                    aliases.append(al)
            for k in other.get("manual_fields", []):
                if k not in primary.setdefault("manual_fields", []):
                    primary["manual_fields"].append(k)
        primary["also_in"] = sorted(also, key=lambda x: (precedence.get(x["book"], 99), x["page"]))
        primary["aliases"] = aliases
        out.append(primary)
    return out


def consolidate_loresheets(records: list[dict], precedence: dict, years: dict,
                           report: list[str]) -> list[dict]:
    """Loresheets printed in more than one book share one id. The primary is the book with the
    lowest precedence (corebook 10, PG 20, rules supplements 40, lore 50, adventures 60), then the
    earlier year, then the lower page: Tier-1 books keep their entries and a supplement reprint
    goes to also_in. Level names, restrictions and the structured restriction fields of every
    reprint are compared with the primary and each difference is reported (the primary wins)."""
    def order(r):
        return (precedence.get(r.get("book"), 99), years.get(r.get("book")) or 9999, r.get("page") or 0)

    def where(r):
        return f"{r.get('book')} p.{r.get('page')}"

    groups: dict = {}
    for r in records:
        groups.setdefault(r["id"], []).append(r)
    out = []
    for rid in sorted(groups):
        grp = sorted(groups[rid], key=order)
        primary = copy.deepcopy(grp[0])
        also, aliases = [], list(primary.get("aliases", []))
        plev = {lv["dots"]: lv.get("name") for lv in primary.get("levels", [])}
        for other in grp[1:]:
            also.append({"book": other["book"], "page": other["page"]})
            if other.get("name") != primary.get("name") and other.get("name") not in aliases:
                aliases.append(other["name"])
            for lv in other.get("levels", []):
                a, b = plev.get(lv["dots"]), lv.get("name")
                if a is not None and b is not None and _norm_name(a) != _norm_name(b):
                    report.append(f"- {rid}: level {lv['dots']} name differs: {where(primary)} {a!r}, "
                                  f"{where(other)} {b!r} (kept {primary['book']})")
            for f in ("clans_only", "clans_excluded", "disciplines_only", "thin_blood_only"):
                if other.get("source") != "online" and other.get(f) != primary.get(f):
                    report.append(f"- {rid}: {f} differs: {where(primary)} {primary.get(f)!r}, "
                                  f"{where(other)} {other.get(f)!r} (kept {primary['book']})")
        primary["also_in"] = sorted(also, key=lambda x: (precedence.get(x["book"], 99), x["book"], x["page"]))
        primary["aliases"] = aliases
        out.append(primary)
    return out


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.replace("’", "'").lower())


def _norm_prereq(s):
    if s is None:
        return None
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def resolve_prerequisite(text: str | None, name_to_id: dict, report: list[str], who: str):
    """'Animal Messenger, either Compel or Mesmerize' ->
    {"all_of": [{"power_id": a}, {"any_of": [b, c]}]}. Unknown names -> None + report."""
    if not text:
        return None
    t = c.norm_space(text).rstrip(".")
    t = re.sub(r"\s*\([^()]*\)", "", t)  # "(Players Guide, p. 88)", "(see Chicago by Night)"
    t = re.sub(r"\bTh (?=[a-z])", "Th", t)  # a split "Th" ligature: "Th ins"
    parts = [p.strip() for p in re.split(r",\s*|\s+and\s+", t) if p.strip()]
    clauses = []
    for p in parts:
        p = re.sub(r"(?i)^either\s+", "", p)
        p = re.sub(r"\s*\((?:see )?[^)]*\)\s*$", "", p)  # "(see Chicago by Night)"
        names = [x.strip() for x in re.split(r"\s+or\s+", p) if x.strip()]
        ids = []
        for n in names:
            pid = name_to_id.get(c.norm_space(n).lower())
            if not pid:
                report.append(f"- {who}: prerequisite name not found in the catalog: {n!r} "
                              f"(from {text!r}); prerequisite left out")
                return None
            ids.append(pid)
        clauses.append({"power_id": ids[0]} if len(ids) == 1 else {"any_of": ids})
    if len(clauses) == 1:
        return clauses[0]
    return {"all_of": clauses}


def amalgam_ref(am: dict | None) -> dict | None:
    if not am:
        return None
    return {"discipline": c.discipline_id(am["discipline"]), "level": am["level"]}


# --------------------------------------------------------------------------- descriptions

DESC_CATALOGS = ("clans", "disciplines", "rituals", "ceremonies", "formulae", "predator_types",
                 "advantages", "loresheets")
# clans carry three descriptions: the clan, its Bane and its Compulsion
CLAN_DESC_PARTS = ("bane", "compulsion")
# loresheets carry one more per level, under '<loresheet id>:<dots>' (1-5)
LEVEL_DESC_CATALOGS = ("loresheets",)


def desc_targets(files: dict):
    """Yield (key, holder) for every place a description can go: entries, powers, a clan's
    bane / compulsion objects under '<clan id>:bane' / '<clan id>:compulsion', and a
    loresheet's levels under '<loresheet id>:<dots>'."""
    for name in DESC_CATALOGS:
        if name not in files:
            continue
        for e in files[name]["entries"]:
            yield e["id"], e
            for p in e.get("powers", []):
                yield p["id"], p
            if name == "clans":
                for part in CLAN_DESC_PARTS:
                    if e.get(part):
                        yield f"{e['id']}:{part}", e[part]
            if name in LEVEL_DESC_CATALOGS:
                for lv in e.get("levels", []):
                    if lv.get("name") is None:
                        continue  # an online-only sheet whose level names are unknown: nothing to describe
                    yield f"{e['id']}:{lv['dots']}", lv


def _with_desc(holder: dict, desc: dict) -> None:
    """Put desc right after name (or first) so the committed JSON stays readable; in place."""
    items = [(k, v) for k, v in holder.items() if k != "desc"]
    holder.clear()
    placed = False
    for k, v in items:
        holder[k] = v
        if k == "name":
            holder["desc"] = {"en": desc["en"], "el": desc["el"]}
            placed = True
    if not placed:
        holder["desc"] = {"en": desc["en"], "el": desc["el"]}


def attach_descriptions(files: dict, descriptions: dict, report: list[str]) -> None:
    """descriptions = {catalog name: {key: {en, el}}} (docs/rules/v5/catalog/descriptions/<name>.json).
    Attaches each one to its target in place; keys that match nothing are reported and left out
    (never guessed onto another entry). Targets without a description are listed in the report
    so the gate can refuse them."""
    targets = dict(desc_targets(files))
    for name, descs in descriptions.items():
        for key, d in descs.items():
            if key not in targets:
                report.append(f"- descriptions/{name}.json: {key} is not in the catalog")
                continue
            if not isinstance(d, dict) or not d.get("en") or not d.get("el"):
                report.append(f"- descriptions/{name}.json: {key} needs both en and el")
                continue
            _with_desc(targets[key], d)
    missing = [k for k, h in targets.items() if "desc" not in h]
    if missing:
        report.append(f"- {len(missing)} catalog entries have no description: "
                      + ", ".join(missing[:12]) + (" …" if len(missing) > 12 else ""))
