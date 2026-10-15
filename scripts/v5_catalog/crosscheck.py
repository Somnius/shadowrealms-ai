"""Compare the PDF intermediate with an online intermediate, if one exists.

Input:  data/catalog-build/v5/extracted/<catalog>.pdf.json and <catalog>.online.json
        (the online file is produced by a later `extract <catalog> online` step; until a
        fetch has been run there is none, and this prints that and does nothing).
Output: data/catalog-build/v5/crosscheck/<catalog>.md, one row per disagreement with both
        locators. Never resolves anything: a person decides, then writes a manual record.
"""

from __future__ import annotations

import json
from pathlib import Path

FACTS = ("name", "level", "amalgam", "prerequisite_text", "dots", "restriction", "book", "page")


def compare(pdf: list[dict], online: list[dict], facts: tuple = FACTS) -> list[dict]:
    by_id = {r["id"]: r for r in pdf}
    rows = []
    for o in online:
        p = by_id.get(o["id"])
        if p is None:
            rows.append({"id": o["id"], "field": "*", "pdf": None, "online": "present",
                         "locator": o.get("source_urls") or o.get("url")})
            continue
        for f in facts:
            if f in o and o.get(f) != p.get(f):
                rows.append({"id": o["id"], "field": f, "pdf": p.get(f), "online": o.get(f),
                             "locator": {"pdf": f"{p.get('book')} p.{p.get('page')}",
                                         "online": o.get("source_urls") or o.get("url")}})
    online_ids = {o["id"] for o in online}
    for p in pdf:
        if p["id"] not in online_ids:
            rows.append({"id": p["id"], "field": "*", "pdf": "present", "online": None,
                         "locator": f"{p.get('book')} p.{p.get('page')}"})
    return rows


def run(catalog: str, extracted_dir: Path, out_dir: Path) -> str:
    pdf_f = extracted_dir / f"{catalog}.pdf.json"
    online_f = extracted_dir / f"{catalog}.online.json"
    if not online_f.exists():
        return f"no online intermediate ({online_f.name}); nothing to cross-check"
    if not pdf_f.exists():
        return f"no PDF intermediate ({pdf_f.name}); run extract first"
    pdf = json.loads(pdf_f.read_text(encoding="utf-8"))
    online = json.loads(online_f.read_text(encoding="utf-8"))
    if isinstance(pdf, dict):  # clans.pdf.json holds {"clans": [...], ...}
        pdf = pdf.get(catalog, [])
    rows = compare(pdf, online)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = [f"# Cross-check: {catalog}", "", "| id | field | pdf | online | where |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['id']} | {r['field']} | {json.dumps(r['pdf'])} | {json.dumps(r['online'])} "
                  f"| {json.dumps(r['locator'])} |")
    (out_dir / f"{catalog}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return f"{len(rows)} disagreement(s) -> {out_dir / (catalog + '.md')}"
