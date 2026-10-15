#!/usr/bin/env python3
"""
Shared V5 creation test vectors (docs/rules/v5/tests/creation-cases.json).

The vectors are real forge payloads: the jest helper builds them with the frontend's
buildV5Payload from the case definitions in
frontend/src/characterSheet/v5/__fixtures__/creationCaseDefs.js, against a snapshot of the
catalog stored in the same file (so both validators read the same facts). Regenerate:

    python3 scripts/v5_creation_cases.py catalog        # catalog snapshot -> the frontend fixture
    WRITE_CREATION_CASES=1 ./scripts/run-frontend-tests.sh src/characterSheet/v5/creationCases
    python3 scripts/v5_creation_cases.py sync           # frontend fixture -> docs/rules/v5/tests

backend/tests/unit/test_v5_chargen.py runs the server validator over the cases and checks that
the two copies are byte-equal; frontend/src/characterSheet/v5/creationCases.test.js checks that
the client validator agrees and that the fixture is current.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parents[1]
FRONT = REPO / "frontend" / "src" / "characterSheet" / "v5" / "__fixtures__" / "creation-cases.json"
DOCS = REPO / "docs" / "rules" / "v5" / "tests" / "creation-cases.json"

ABOUT = (
    "Shared V5 creation test vectors: {name, settings, client, expect, payload}. payload is what "
    "buildV5Payload makes of a forge sheet (changed by hand afterwards where client is false: the "
    "forge can't send it), expect the problem codes both validators report, against the catalog "
    "snapshot below. Generated (scripts/v5_creation_cases.py); do not edit by hand."
)

# The facts the validators read, per catalog (descriptions and pipeline fields left out). also_in:
# the other books an entry is printed in (a chronicle's allowed books, creation_settings.book_allowed).
KEEP = {
    "clans": ("id", "name", "aliases", "book", "also_in", "page", "disciplines", "caitiff", "thin_blood", "creation",
              "bane", "compulsion"),
    "disciplines": ("id", "name", "aliases", "book", "also_in", "page", "powers"),
    "predator_types": ("id", "name", "aliases", "book", "also_in", "page", "specialty_choice", "discipline_choice",
                       "humanity", "blood_potency", "max_blood_potency", "forbidden_clans", "advantages",
                       "flaws", "ancilla_only"),
    "rituals": ("id", "name", "aliases", "book", "also_in", "page", "level", "discipline", "prerequisite", "koldunic"),
    "ceremonies": ("id", "name", "aliases", "book", "also_in", "page", "level", "discipline", "prerequisite"),
    # forge v2 C: only when the catalog has them (advantages.json, loresheets.json)
    "advantages": ("id", "name", "aliases", "kind", "group", "dots", "book", "also_in", "page", "thin_blood", "caitiff",
                   "ghoul_only", "coterie", "clans_only", "cannot_buy_for", "repeatable", "max_instances",
                   "requires", "levels"),
    "loresheets": ("id", "name", "aliases", "book", "also_in", "page", "restriction", "clans_only", "clans_excluded",
                   "disciplines_only", "thin_blood_only", "levels"),
}
OPTIONAL = ("advantages", "loresheets")
POWER_KEEP = ("id", "name", "aliases", "book", "also_in", "page", "level", "amalgam", "prerequisite", "clans_only",
              "repeatable", "at_first_dot")
NAMED_KEEP = ("name",)  # clan bane / compulsion: the name only


def _facts(entry: Dict[str, Any], keep) -> Dict[str, Any]:
    """The kept keys of an entry; an empty also_in is left out (most entries are in one book)."""
    return {k: entry[k] for k in keep if k in entry and not (k == "also_in" and not entry[k])}


def snapshot(catalog: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for kind, keep in KEEP.items():
        rows = []
        for e in catalog.get(kind) or []:
            row = _facts(e, keep)
            if kind == "disciplines":
                row["powers"] = [_facts(p, POWER_KEEP) for p in e.get("powers") or []]
            for k in ("bane", "compulsion"):
                if isinstance(row.get(k), dict):
                    row[k] = {n: row[k][n] for n in NAMED_KEEP if n in row[k]}
            if kind == "predator_types":
                row["discipline_choice"] = [
                    {k: d[k] for k in ("discipline", "clans_only") if k in d} for d in row.get("discipline_choice") or []
                ]
            if isinstance(row.get("levels"), list):  # names, dots and a level's own clan restriction
                row["levels"] = [{k: lv[k] for k in ("dots", "name", "clans_only") if k in lv} for lv in row["levels"]
                                 if isinstance(lv, dict)]
            rows.append(row)
        if rows or kind not in OPTIONAL:
            out[kind] = rows
    return out


def dump(doc: Dict[str, Any]) -> str:
    """The file's text: one JSON line per catalog entry and per case (formatCasesFile in
    creationCaseDefs.js writes the same layout)."""

    def line(x: Any) -> str:
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))

    def lst(arr: list, pad: str) -> str:
        if not arr:
            return "[]"
        return "[\n" + ",\n".join(f"{pad} {line(x)}" for x in arr) + f"\n{pad}]"

    catalog = ",\n".join(f"  {line(k)}: {lst(v, '  ')}" for k, v in doc["catalog"].items())
    return (
        f'{{\n "version": {line(doc["version"])},\n "about": {line(doc["about"])},\n'
        f' "catalog": {{\n{catalog}\n }},\n "cases": {lst(doc["cases"], " ")}\n}}\n'
    )


def cmd_catalog() -> None:
    sys.path.insert(0, str(REPO / "backend"))
    from services.v5_catalog import load_catalog

    catalog = load_catalog()
    if not catalog:
        sys.exit("no V5 catalog found (docs/rules/v5/catalog)")
    doc = json.loads(FRONT.read_text("utf-8")) if FRONT.exists() else {}
    doc = {"version": 1, "about": ABOUT, "catalog": snapshot(catalog), "cases": doc.get("cases", [])}
    FRONT.parent.mkdir(parents=True, exist_ok=True)
    FRONT.write_text(dump(doc), "utf-8")
    print(f"catalog snapshot written to {FRONT.relative_to(REPO)}")


def cmd_sync() -> None:
    DOCS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FRONT, DOCS)
    print(f"{FRONT.relative_to(REPO)} -> {DOCS.relative_to(REPO)}")


if __name__ == "__main__":
    cmds = {"catalog": cmd_catalog, "sync": cmd_sync}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(f"usage: {sys.argv[0]} {'|'.join(cmds)}")
    cmds[sys.argv[1]]()
