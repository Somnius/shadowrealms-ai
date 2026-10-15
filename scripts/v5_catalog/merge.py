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
    "rename": [{from, into, name, why}], "patch": [{id, set, why}], "add": [records]}.
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
        hit = [r for r in recs if r["id"] == rn["from"]]
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
