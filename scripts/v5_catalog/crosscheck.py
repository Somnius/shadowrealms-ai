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


# --------------------------------------------------------------------------- loresheets vs the VTM Wiki

WIKI_LORE_SECTIONS = {
    "Corebook": "v5-corebook", "Anarch": "v5-anarch", "Camarilla": "v5-camarilla",
    "Chicago by Night": "v5-chicago-by-night", "Chicago Folios": "v5-chicago-folios",
    "Let the Streets Run Red": "v5-let-the-streets-run-red",
    "Cults of the Blood Gods / Players Guide": "v5-cults-of-the-blood-gods",
    "Children of the Blood": "v5-children-of-the-blood", "Forbidden Religions": "v5-forbidden-religions",
    "Trails of Ash and Bone": "v5-trails-of-ash-and-bone", "Fall of London": "v5-fall-of-london",
    "Blood Sigils": "v5-blood-sigils", "Book of Nod Apocrypha": "v5-nod-apocrypha",
    "Gehenna War": "v5-gehenna-war", "In Memoriam": "v5-in-memoriam", "Tattered Façade": "v5-tattered-facade",
    "Live from the Succubus Club": "v5-succubus-club", "Courts of the Damned": "v5-courts-of-the-damned",
}


def wiki_loresheet_rows(wikitext: str) -> list[dict]:
    """The wiki's Loresheets page -> [{section, book (None when not on disk), name, restriction, page}]."""
    from .sources import mediawiki as mw

    rows = []
    for section, body in mw.sections(wikitext, 2).items():
        key = section.replace(" Loresheets", "").strip()
        for table in mw.parse_tables(body):
            for row in table[1:]:
                if len(row) < 4 or not row[0]:
                    continue
                m = __import__("re").search(r"[Pp]ages?\s+(\d+)", row[-1])
                rows.append({"section": key, "book": WIKI_LORE_SECTIONS.get(key), "name": row[0],
                             "restriction": None if row[1] in ("", "N/A") else row[1],
                             "page": int(m.group(1)) if m else None})
    return rows


def loresheets_vs_wiki(entries: list[dict], rows: list[dict], slug) -> list[str]:
    """Disagreements between the catalog and the wiki's list (names, book + page, clan restriction).
    For review only: the catalog keeps what the PDF prints."""
    import re as _re

    def norm(s):
        return _re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("the ", ""))

    by_key = {}
    for e in entries:
        for n in [e["name"]] + e.get("aliases", []):
            by_key.setdefault(norm(n), e)
        by_key.setdefault(norm(e["id"].split(":", 1)[1]), e)
    out = []
    seen = set()
    for r in rows:
        e = next((by_key[norm(n)] for n in r["name"].split(" / ") if norm(n) in by_key), None)
        if e is None:
            where = r["book"] or f"not on disk ({r['section']})"
            out.append(f"- wiki lists {r['name']!r} ({where}, p.{r['page']}); not in the catalog")
            continue
        seen.add(e["id"])
        refs = [(e["book"], e["page"])] + [(a["book"], a["page"]) for a in e.get("also_in", [])]
        if r["book"] and r["page"] and (r["book"], r["page"]) not in refs:
            out.append(f"- {e['id']}: wiki gives {r['book']} p.{r['page']}; catalog has "
                       + ", ".join(f"{b} p.{p}" for b, p in refs))
        wiki_clans = {f"clan:{slug(w)}" for w in _re.findall(
            r"(Banu Haqim|Brujah|Gangrel|Hecata|Lasombra|Malkavian|Ministry|Nosferatu|Ravnos|Salubri|"
            r"Toreador|Tremere|Tzimisce|Ventrue)", r["restriction"] or "")}
        cat_clans = set(e.get("clans_only") or []) | set(e.get("clans_excluded") or []) | {
            c for lv in e["levels"] for c in lv.get("clans_only") or []}
        if wiki_clans != cat_clans:
            out.append(f"- {e['id']}: wiki restriction {r['restriction']!r}; catalog clans "
                       f"{sorted(cat_clans) or None} (restriction printed: {e.get('restriction')!r})")
    for e in entries:
        if e["id"] not in seen:
            out.append(f"- {e['id']} ({e['book']} p.{e['page']}): not on the wiki's list")
    return out
