"""extract / build / crosscheck / check commands (see __main__.py)."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from . import books, checks, crosscheck, merge
from .parsers import advantages as adv_parser
from .parsers import clans as clan_parser
from .parsers import loresheets as lore_parser
from .parsers import common as c
from .parsers import powers as power_parser
from .parsers import predators as pred_parser

EXTRACTED = books.BUILD_DIR / "extracted"
REPORT = books.BUILD_DIR / "report.md"
MANUAL_DIR = books.CATALOG_DIR / "manual"
DESC_DIR = books.CATALOG_DIR / "descriptions"
KIND_FILE = {"ritual": "rituals", "ceremony": "ceremonies", "formula": "formulae"}
CATALOG_FILES = ("books", "clans", "disciplines", "rituals", "ceremonies", "formulae", "predator_types",
                 "advantages", "loresheets")
# chapter pages scanned for Advantage entries (the coterie-type write-ups, corebook pr 197-199 and
# PG pr 156-168, only suggest Advantages for a coterie and are left out of the scan)
ADVANTAGE_CHAPTERS = {
    "v5-corebook": [(179, 196)],
    "v5-players-guide": [(109, 122), (126, 128), (135, 136), (139, 151), (169, 191)],
    "v5-companion": [(30, 60)],
}
MASTER_LIST = ("v5-players-guide", 232, 238)
LORESHEET_LEVEL_HEIGHTS = {"v5-corebook": {13.9, 13.4}}


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- extract

def extract() -> list[str]:
    from .sources.pdf import PdfBook

    manifest = books.load_manifest()
    report = ["# V5 catalog build report", "", "Local only (data/ is gitignored). Never commit.", "",
              "## Extraction"]
    powers, sections, clan_recs, preds = [], [], [], []
    compulsions, bane_variants, pools = {}, {}, {}
    for b in books.TIER1:
        pb = PdfBook(b.book_id, manifest=manifest)
        lines = []
        for a, z in b.ranges.get("disciplines", []):
            lines += pb.lines(a, z)
        recs, rep = power_parser.parse(lines)
        powers += recs
        sections += power_parser.section_pages(lines)
        report += [f"### {b.book_id}: {len(recs)} powers/rituals/ceremonies/formulae"] + rep
        for clan, (a, z) in clan_parser.CLAN_SPANS.get(b.book_id, {}).items():
            rec, rep = clan_parser.parse_block(clan, pb.lines(a, z))
            clan_recs.append(rec)
            report += rep
        if b.book_id == "v5-corebook":
            compulsions = clan_parser.parse_compulsions(pb.lines(208, 211))
            pools = pred_parser.parse_pools(pb.lines(307, 308))
        if b.book_id == "v5-players-guide":
            bane_variants, rep = clan_parser.parse_bane_variants(pb.lines(56, 59))
            report += rep
        for a, z in b.ranges.get("predator_types", []):
            recs, rep = pred_parser.parse(pb.lines(a, z))
            preds += recs
            report += rep
    for r in clan_recs:
        if r["name"] in compulsions and not r["compulsion"]:
            r["compulsion"], r["compulsion_page"] = compulsions[r["name"]]
    for p in preds:
        if p["name"] in pools:
            p["core_pool_text"] = pools[p["name"]]["pool_text"]
            p["core_pool_page"] = pools[p["name"]]["page"]
    adv, lore, rep = extract_advantages(manifest)
    report += ["### Advantages and loresheets"] + rep
    lore_t2, rep = extract_loresheets_tier2(manifest)
    report += ["### Tier-2 loresheets (supplements)"] + rep
    _dump(EXTRACTED / "advantages.pdf.json", adv)
    _dump(EXTRACTED / "loresheets.pdf.json", lore)
    _dump(EXTRACTED / "loresheets.tier2.pdf.json", lore_t2)
    _dump(EXTRACTED / "powers.pdf.json", powers)
    _dump(EXTRACTED / "sections.pdf.json", sections)
    _dump(EXTRACTED / "clans.pdf.json", {"clans": clan_recs, "bane_variants": bane_variants})
    _dump(EXTRACTED / "predator_types.pdf.json", preds)
    report.append("")
    report.append(f"Extracted: {len(powers)} power-like records, {len(clan_recs)} clan blocks, "
                  f"{len(preds)} predator types, {sum(len(v) for v in bane_variants.values())} bane variants.")
    return report


def extract_advantages(manifest: dict) -> tuple[dict, list[dict], list[str]]:
    from .sources.pdf import PdfBook

    report: list[str] = []
    pdfs = {bid: PdfBook(bid, manifest=manifest) for bid in books.TIER1_IDS}
    precedence = _precedence(manifest)
    master, rep = adv_parser.parse_master(pdfs[MASTER_LIST[0]].lines(MASTER_LIST[1], MASTER_LIST[2]))
    report += rep
    lines = []
    for bid, spans in ADVANTAGE_CHAPTERS.items():
        for a, z in spans:
            lines += pdfs[bid].lines(a, z)
    hits = adv_parser.scan_chapter(lines)
    adv_parser.match(master, hits, report, precedence)
    core = pdfs["v5-corebook"]
    levels = {}
    for e in master:
        if e["kind"] == "background":
            lv = adv_parser.background_levels(core.lines(184, 194), e["name"])
            if lv:
                levels[e["name"]] = {"levels": lv, "book": "v5-corebook"}
    only = [{k: h[k] for k in ("name", "dots_text", "tag", "book", "page", "group")}
            for h in adv_parser.chapter_only(master, hits)]
    lore, rep = [], []
    for b in books.TIER1:
        for a, z in b.ranges.get("loresheets", []):
            recs, r = lore_parser.parse([pdfs[b.book_id].lines(p, p) for p in range(a, z + 1)],
                                        LORESHEET_LEVEL_HEIGHTS.get(b.book_id))
            lore += recs
            rep += r
    report += rep
    report.append(f"Advantages: {len(master)} master-list entries, {len(only)} chapter-only lines; "
                  f"{len(lore)} loresheets.")
    return {"master": master, "chapter_only": only, "levels": levels}, lore, report


def extract_loresheets_tier2(manifest: dict) -> tuple[list[dict], list[str]]:
    """Every supplement's loresheet pages (books.TIER2 ranges) through the box parser."""
    from .sources.pdf import PdfBook

    out, report = [], []
    for b in books.TIER2:
        if not b.extractable or "loresheets" not in b.ranges:
            continue
        pb = PdfBook(b.book_id, manifest=manifest)
        for a, z in b.ranges["loresheets"]:
            recs, rep = lore_parser.parse_book([(p, pb.boxes(b.pdf_page(p))) for p in range(a, z + 1)],
                                               b.book_id, b.dot_glyph is not None)
            out += recs
            report += rep
    report.append(f"Tier-2 loresheets: {len(out)} sheets read from {len({r['book'] for r in out})} books.")
    return out, report


# --------------------------------------------------------------------------- build

def _manual(name: str) -> dict:
    p = MANUAL_DIR / f"{name}.json"
    return _load(p) if p.exists() else {}


def _precedence(manifest: dict) -> dict:
    return {bid: int(manifest[bid]["precedence"]) for bid in books.ALL_CITED if bid in manifest}


def _years(manifest: dict) -> dict:
    return {bid: int(manifest[bid].get("year") or 0) or None for bid in books.ALL_CITED if bid in manifest}


def build_books(manifest: dict) -> dict:
    entries = []
    for b in books.TIER1 + books.TIER2:
        m = manifest[b.book_id]
        entries.append({
            "book_id": b.book_id, "title": m["title"], "precedence": int(m["precedence"]),
            "tier": b.tier, "extractable": b.extractable, "page_offset": b.offset,
            "dot_glyph": b.dot_glyph,
        })
    return {"catalog": "books", "version": 1, "entries": entries}


def build_powers(extracted: list[dict], sections: list[dict], prec: dict, report: list[str]) -> dict:
    recs = merge.apply_manual(extracted, _manual("powers"), report)
    recs = merge.consolidate(recs, prec, report)
    name_to_id = {}
    for r in recs:
        if r["kind"] == "power":
            name_to_id[r["name"].lower()] = r["id"]
            for al in r.get("aliases", []):
                name_to_id.setdefault(al.lower(), r["id"])
    out = {"disciplines": [], "ritual": [], "ceremony": [], "formula": []}
    for r in recs:
        pre = r.get("prerequisite")
        if pre is None and r.get("prerequisite_text"):
            pre = merge.resolve_prerequisite(r["prerequisite_text"], name_to_id, report, r["id"])
        entry = {
            "id": r["id"], "name": r["name"], "level": r["level"],
            "book": r["book"], "page": r["page"], "also_in": r.get("also_in", []),
            "aliases": r.get("aliases", []), "source": r.get("source", "pdf"),
            "prerequisite": pre,
        }
        if r.get("manual_fields"):
            entry["manual_fields"] = sorted(r["manual_fields"])
        if r["kind"] == "power":
            entry["amalgam"] = merge.amalgam_ref(r.get("amalgam"))
        if r["kind"] in ("power", "formula"):
            entry["rouse_cost"] = r.get("rouse_cost")
            entry["rouse_cost_conditional"] = bool(r.get("rouse_cost_conditional"))
            entry["dice_pool"] = r.get("dice_pool")
        if r["kind"] == "power":
            entry["discipline"] = c.discipline_id(r["discipline"])
            out["disciplines"].append(entry)
        else:
            if r["kind"] == "ritual":
                entry["koldunic"] = bool(r.get("koldunic", False))
            entry["discipline"] = c.discipline_id(r["discipline"])
            out[r["kind"]].append(entry)
    # discipline records
    first = {}
    for s in sorted(sections, key=lambda s: (prec.get(s["book"], 99), s["page"])):
        if s["kind"] == "power":
            first.setdefault(s["discipline"], s)
    discs = []
    for name in c.DISCIPLINES:
        sec = first.get(name)
        if name == "Thin-Blood Alchemy":
            sec = next((s for s in sorted(sections, key=lambda s: (prec.get(s["book"], 99), s["page"]))
                        if s["kind"] == "formula"), None)
        if not sec:
            report.append(f"- no section heading found for Discipline {name}")
            continue
        pw = sorted((p for p in out["disciplines"] if p.get("discipline") == c.discipline_id(name)),
                    key=lambda p: (p["level"], p["name"]))
        for p in pw:
            p.pop("discipline")
        discs.append({
            "id": c.discipline_id(name), "name": name, "book": sec["book"], "page": sec["page"],
            "source": "pdf", "powers": pw,
            "rituals": "rituals" if name == "Blood Sorcery" else None,
            "ceremonies": "ceremonies" if name == "Oblivion" else None,
            "formulae": "formulae" if name == "Thin-Blood Alchemy" else None,
        })
    for d in discs:
        for k in ("rituals", "ceremonies", "formulae"):
            if d[k] is None:
                del d[k]
    for p in _manual("disciplines").get("patch", []):
        hit = [d for d in discs if d["id"] == p["id"]]
        if not hit:
            report.append(f"- manual discipline patch matched nothing: {p['id']}")
        for d in hit:
            d.update(p["set"])
    result = {"disciplines": {"catalog": "disciplines", "version": 1, "entries": discs}}
    for kind, fname in KIND_FILE.items():
        result[fname] = {"catalog": fname, "version": 1,
                         "entries": sorted(out[kind], key=lambda e: (e["level"], e["name"]))}
    return result


def build_clans(extracted: dict, prec: dict, report: list[str]) -> dict:
    man = _manual("clans")
    recs = merge.apply_manual(extracted["clans"], man, report)
    recs = merge.consolidate(recs, prec, report, facts=("disciplines", "compulsion"))
    variants = extracted.get("bane_variants", {})
    entries = []
    for r in recs:
        name = r["name"]
        e = {
            "id": r["id"], "name": name, "book": r["book"], "page": r["page"],
            "also_in": r.get("also_in", []), "aliases": r.get("aliases", []),
            "source": r.get("source", "pdf"),
            "disciplines": [c.discipline_id(d) for d in r["disciplines"]],
            "disciplines_page": r.get("disciplines_page"),
            "bane": {"name": r.get("bane_name"), "page": r.get("bane_page"),
                     "name_ref": r.get("bane_name_ref")},
            "compulsion": ({"name": r["compulsion"], "page": r.get("compulsion_page"),
                            "book": r.get("compulsion_book", r["book"])} if r.get("compulsion") else None),
            "bane_variants": [{"name": v["name"], "book": "v5-players-guide", "page": v["page"]}
                              for v in variants.get(name, [])],
            "caitiff": name == "Caitiff",
            "thin_blood": name == "Thin-blood",
        }
        if r.get("creation"):
            e["creation"] = r["creation"]
        if r.get("manual_fields"):
            rename = {"bane_name": "bane.name", "bane_name_ref": "bane.name_ref", "bane_page": "bane"}
            e["manual_fields"] = sorted(rename.get(k, k) for k in r["manual_fields"])
        if e["bane"]["page"] is None and e["bane"]["name"] is None:
            e["bane"] = None
        elif e["bane"]["name_ref"] is None:
            del e["bane"]["name_ref"]
        entries.append(e)
    entries.sort(key=lambda e: e["name"])
    return {"catalog": "clans", "version": 1, "entries": entries}


def build_predators(extracted: list[dict], prec: dict, report: list[str]) -> dict:
    man = _manual("predator_types")
    by_id = {p["id"]: p for p in extracted}
    entries = []
    for rec in man.get("add", []):
        e = {k: v for k, v in rec.items() if not k.startswith("_")}
        e.setdefault("source", "manual")
        e.setdefault("also_in", [])
        e.setdefault("aliases", [])
        ex = by_id.get(e["id"])
        if ex:
            compare_predator(e, ex, report)
        elif e["book"] in books.TIER1_IDS:
            report.append(f"- {e['id']}: manual record has no PDF extraction to compare with")
        entries.append(e)
    missing = set(by_id) - {e["id"] for e in entries}
    for m in sorted(missing):
        report.append(f"- {m}: extracted from the PDF but no manual record (not in the catalog)")
    entries.sort(key=lambda e: e["name"])
    return {"catalog": "predator_types", "version": 1, "entries": entries}


def compare_predator(e: dict, ex: dict, report: list[str]) -> None:
    def spec(lst):
        return sorted((s["skill"], s["name"].lower()) for s in lst)

    if spec(e["specialty_choice"]) != spec(ex["specialty_choice"]):
        report.append(f"- {e['id']}: specialties differ from the PDF parse: manual "
                      f"{spec(e['specialty_choice'])} vs pdf {spec(ex['specialty_choice'])}")
    md = sorted((d["discipline"], tuple(d.get("clans_only") or ())) for d in e["discipline_choice"])
    pd = sorted((c.discipline_id(d["discipline"]),
                 tuple(f"clan:{c.slug(x)}" for x in d.get("clans_only") or ())) for d in ex["discipline_choice"])
    if md != pd:
        report.append(f"- {e['id']}: Discipline choices differ from the PDF parse: {md} vs {pd}")
    for f in ("humanity", "blood_potency"):
        if e.get(f, 0) != ex.get(f, 0):
            report.append(f"- {e['id']}: {f} differs from the PDF parse: {e.get(f)} vs {ex.get(f)}")
    if (e["book"], e["page"]) != (ex["book"], ex["page"]):
        report.append(f"- {e['id']}: page differs: manual {e['book']} p.{e['page']} vs pdf "
                      f"{ex['book']} p.{ex['page']}")


def build_advantages(extracted: dict, prec: dict, report: list[str]) -> dict:
    man = _manual("advantages")
    recs = []
    for e in extracted["master"]:
        group = e["group"] or (e["name"] if e["kind"] == "background" else e.get("chapter_group"))
        book, page = e["ref"] if e.get("ref") else (None, None)
        rec = {
            "id": adv_parser.entry_id(e["kind"], e["name"], e["group"]), "name": e["name"],
            "kind": e["kind"], "group": group, "dots": e["dots"], "book": book, "page": page,
            "also_in": e.get("also_in", []), "aliases": [], "source": "pdf",
            "master_list_page": e["master_page"],
            "thin_blood": bool(e.get("thin_blood")), "caitiff": bool(e.get("caitiff")),
            "ghoul_only": bool(e.get("ghoul_only")), "coterie": bool(e.get("coterie")),
            "clans_only": e.get("clans_only"), "cannot_buy_for": [],
            "repeatable": False, "requires": None, "levels": [],
        }
        if e["kind"] == "background":
            rec["repeatable"] = True  # core pr 184: the same Background can be taken several times
            lv = extracted.get("levels", {}).get(e["name"])
            if lv:
                rec["levels"] = lv["levels"]
        recs.append(rec)
    recs = merge.apply_manual(recs, man, report)
    for r in recs:
        if r["group"] is None:
            report.append(f"- {r['id']}: no group found in the chapter text")
    ids = [r["id"] for r in recs]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        report.append(f"- duplicate advantage id {d}")
    for r in recs:
        r.setdefault("aliases", [])
        r.setdefault("also_in", [])
        r.pop("merged_from", None)
        if r.get("manual_fields"):
            r["manual_fields"] = sorted(r["manual_fields"])
    order = {"background": 0, "merit": 1, "flaw": 2}
    recs.sort(key=lambda r: (order[r["kind"]], r["group"] or "", r["name"]))
    for oid in man.get("expect_chapter_only", []):
        if not any(r["id"] == oid for r in recs):
            report.append(f"- manual expects {oid} but it is missing")
    return {"catalog": "advantages", "version": 1, "entries": recs}


def tier2_loresheets(extracted: list[dict], sheets: list[dict], report: list[str]) -> list[dict]:
    """Supplement pages (book, page, title_raw, restriction_raw, levels) + the sheet list in
    manual/loresheets.json "sheets" (name with its word spacing, restriction as printed, an id
    when a reprint is named differently) -> loresheet records. The printed title and restriction
    must equal the listed ones once spaces are removed; any difference is reported."""
    table = {(x["book"], x["page"]): x for x in sheets}
    used = set()
    out = []
    for r in extracted:
        key = (r["book"], r["page"])
        sh = table.get(key)
        if sh is None:
            report.append(f"- loresheet page {r['book']} p.{r['page']} ({r['title_raw']!r}) is not in "
                          f"manual/loresheets.json sheets")
            continue
        used.add(key)
        if lore_parser.despace(sh["name"]) not in lore_parser.despace(r["title_raw"]):
            report.append(f"- {r['book']} p.{r['page']}: printed title {r['title_raw']!r} is not {sh['name']!r}")
        if lore_parser.despace(sh.get("restriction")) != lore_parser.despace(r["restriction_raw"]):
            report.append(f"- {r['book']} p.{r['page']}: printed restriction {r['restriction_raw']!r} "
                          f"is not {sh.get('restriction')!r}")
        levels = []
        for lv in r["levels"]:
            name, restr = lore_parser.split_level_restriction(lv["name"])
            level = {"dots": lv["dots"], "name": name}
            if restr:
                level["restriction"] = restr
                struct = lore_parser.structured_restriction(restr)
                if struct["clans_only"]:
                    level["clans_only"] = struct["clans_only"]
            levels.append(level)
        rec = {"id": sh.get("id") or f"loresheet:{c.slug(sh['name'])}", "name": sh["name"],
               "book": r["book"], "page": r["page"], "restriction": sh.get("restriction"),
               "levels": levels, "source": "pdf"}
        rec.update(lore_parser.structured_restriction(sh.get("restriction")))
        out.append(rec)
    for key in sorted(set(table) - used):
        report.append(f"- manual/loresheets.json sheets: {key[0]} p.{key[1]} matched no extracted page")
    return out


def build_loresheets(extracted: list[dict], extracted_t2: list[dict], prec: dict, years: dict,
                     report: list[str]) -> dict:
    man = _manual("loresheets")
    recs = list(extracted) + tier2_loresheets(extracted_t2, man.get("sheets", []), report)
    recs = merge.apply_manual(recs, man, report)
    recs = merge.consolidate_loresheets(recs, prec, years, report)
    out = []
    for r in recs:
        e = {k: r.get(k) for k in ("id", "name", "book", "page", "restriction", "clans_only",
                                   "disciplines_only", "thin_blood_only")}
        if r.get("clans_excluded"):
            e["clans_excluded"] = r["clans_excluded"]
        e["levels"] = [{k: lv[k] for k in ("dots", "name", "restriction", "clans_only") if k in lv}
                       for lv in r["levels"]]
        e["thin_blood_only"] = bool(e["thin_blood_only"])
        e["also_in"] = r.get("also_in", [])
        e["aliases"] = r.get("aliases", [])
        e["source"] = r.get("source", "pdf")
        if r.get("source_urls"):
            e["source_urls"] = r["source_urls"]
        if r.get("manual_fields"):
            e["manual_fields"] = sorted(r["manual_fields"])
        if [lv["dots"] for lv in e["levels"]] != [1, 2, 3, 4, 5]:
            report.append(f"- {e['id']}: levels are not 1-5 after the manual records")
        out.append(e)
    out.sort(key=lambda e: (prec.get(e["book"], 99), e["book"], e["page"]))
    return {"catalog": "loresheets", "version": 1, "entries": out}


def build(out_dir: Path | None = None) -> list[str]:
    out_dir = out_dir or books.CATALOG_DIR
    manifest = books.load_manifest()
    prec = _precedence(manifest)
    report = ["", "## Build"]
    for f in ("powers.pdf.json", "sections.pdf.json", "clans.pdf.json", "predator_types.pdf.json",
              "advantages.pdf.json", "loresheets.pdf.json", "loresheets.tier2.pdf.json"):
        if not (EXTRACTED / f).exists():
            raise SystemExit(f"missing {EXTRACTED / f}: run `python -m scripts.v5_catalog extract` first")
    files = {"books": build_books(manifest)}
    files.update(build_powers(_load(EXTRACTED / "powers.pdf.json"), _load(EXTRACTED / "sections.pdf.json"),
                              prec, report))
    files["clans"] = build_clans(_load(EXTRACTED / "clans.pdf.json"), prec, report)
    files["predator_types"] = build_predators(_load(EXTRACTED / "predator_types.pdf.json"), prec, report)
    files["advantages"] = build_advantages(_load(EXTRACTED / "advantages.pdf.json"), prec, report)
    files["loresheets"] = build_loresheets(_load(EXTRACTED / "loresheets.pdf.json"),
                                           _load(EXTRACTED / "loresheets.tier2.pdf.json"), prec,
                                           _years(manifest), report)
    merge.attach_descriptions(files, load_descriptions(), report)
    for name, data in files.items():
        _dump(out_dir / f"{name}.json", data)
    report += ["", "## Counts", ""] + counts(files)
    report += ["", "## Needs review (facts left null rather than guessed)", ""] + needs_review(files)
    return report


def load_descriptions() -> dict:
    """docs/rules/v5/catalog/descriptions/<catalog>.json -> {catalog: {key: {en, el}}}."""
    out = {}
    for name in merge.DESC_CATALOGS:
        p = DESC_DIR / f"{name}.json"
        if p.exists():
            out[name] = _load(p)
    return out


def needs_review(files: dict) -> list[str]:
    out = []
    no_cost = [p["id"] for d in files["disciplines"]["entries"] for p in d["powers"] if p["rouse_cost"] is None]
    no_cost += [e["id"] for e in files["formulae"]["entries"] if e["rouse_cost"] is None]
    out.append(f"- rouse_cost null (page prints alternatives or no plain count) for {len(no_cost)}: "
               + ", ".join(no_cost))
    for e in files["predator_types"]["entries"]:
        for kind in ("advantages", "flaws"):
            for g in e[kind]:
                for o in g["options"]:
                    if o["dots"] is None and g["pick"] != "split":
                        out.append(f"- {e['id']}: {kind} option {o['id']} has no printed rating")
        if e["pool"] is None:
            out.append(f"- {e['id']}: no predator pool printed")
    for e in files["advantages"]["entries"]:
        if e["dots"] is None and not e["thin_blood"]:
            out.append(f"- {e['id']}: no dot rating printed (dots null)")
    for e in files["loresheets"]["entries"]:
        unnamed = [lv["dots"] for lv in e["levels"] if lv["name"] is None]
        if unnamed:
            out.append(f"- {e['id']} ({e['book']} p.{e['page']}, source {e['source']}): level names "
                       f"{unnamed} unknown (no English text to verify them; names null)")
        if "levels" in (e.get("manual_fields") or []) and e["book"] not in books.TIER1_IDS:
            out.append(f"- {e['id']}: level ratings set by a manual record (see manual/loresheets.json why)")
    for e in files["clans"]["entries"]:
        if e["bane"] is None:
            out.append(f"- {e['id']}: no clan bane (bane null)")
        if e["compulsion"] is None:
            out.append(f"- {e['id']}: no Compulsion printed (compulsion null)")
    return out


def counts(files: dict) -> list[str]:
    lines = [f"- {name}: {len(files[name]['entries'])} entries" for name in CATALOG_FILES]
    for d in files["disciplines"]["entries"]:
        per = Counter(p["level"] for p in d["powers"])
        lines.append(f"  - {d['name']}: {len(d['powers'])} powers, by level "
                     + ", ".join(f"L{lv} {per[lv]}" for lv in range(1, 6)))
    for name in ("rituals", "ceremonies", "formulae"):
        per = Counter(e["level"] for e in files[name]["entries"])
        lines.append(f"  - {name} by level: " + ", ".join(f"L{lv} {per[lv]}" for lv in range(1, 6)))
    adv = files["advantages"]["entries"]
    lines.append("  - advantages by kind: " + ", ".join(f"{k} {n}" for k, n in sorted(Counter(e["kind"] for e in adv).items())))
    flags = ("thin_blood", "caitiff", "ghoul_only", "coterie")
    lines.append("  - advantages flagged: " + ", ".join(f"{f} {sum(1 for e in adv if e[f])}" for f in flags))
    per = Counter(e["book"] for e in files["loresheets"]["entries"])
    lines.append("  - loresheets by book: " + ", ".join(f"{b} {n}" for b, n in sorted(per.items())))
    return lines


def crosscheck_loresheets() -> list[str]:
    """Loresheets vs the cached VTM Wiki list (fetch paradoxwikis Loresheets), for review."""
    f = books.BUILD_DIR.parent / "online" / "paradoxwikis" / "loresheets.json"
    if not f.exists():
        return ["", "## Cross-check: loresheets vs VTM Wiki", "", "no cached wiki page (fetch paradoxwikis Loresheets)"]
    rec = _load(f)
    entries = _load(books.CATALOG_DIR / "loresheets.json")["entries"]
    rows = crosscheck.wiki_loresheet_rows(rec["text"])
    out = crosscheck.loresheets_vs_wiki(entries, rows, c.slug)
    return ["", "## Cross-check: loresheets vs VTM Wiki", "",
            f"Wiki revision {rec['revision']} ({rec['fetched']}): {len(rows)} rows; {len(out)} disagreements "
            "(the catalog keeps what the PDF prints).", ""] + out


# --------------------------------------------------------------------------- commands

def run(cmd: str, args: list[str]) -> int:
    if cmd == "extract":
        rep = extract()
        rep += build()
        rep += crosscheck_loresheets()
        rep += ["", "## Checks", ""] + checks.run_all(books.CATALOG_DIR, page_cache=True)
        REPORT.write_text("\n".join(rep) + "\n", encoding="utf-8")
        print(f"wrote {REPORT}")
        return 0
    if cmd == "build":
        rep = build()
        print("\n".join(rep))
        return 0
    if cmd == "check":
        problems = checks.run_all(books.CATALOG_DIR, page_cache=True)
        if "--diff" in args:
            with tempfile.TemporaryDirectory() as tmp:
                build(Path(tmp))
                for name in CATALOG_FILES:
                    a = (books.CATALOG_DIR / f"{name}.json").read_text(encoding="utf-8")
                    b = (Path(tmp) / f"{name}.json").read_text(encoding="utf-8")
                    if a != b:
                        problems.append(f"- {name}.json differs from a fresh build")
        bad = [p for p in problems if p.startswith("- ")]
        print("\n".join(problems) if problems else "ok")
        return 1 if bad else 0
    if cmd == "crosscheck":
        if not args:
            raise SystemExit("usage: crosscheck <catalog>")
        out = crosscheck.run(args[0], EXTRACTED, books.BUILD_DIR / "crosscheck")
        print(out)
        return 0
    raise SystemExit(f"unknown command {cmd!r}; see --help")
