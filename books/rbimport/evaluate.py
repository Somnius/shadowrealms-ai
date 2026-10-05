"""Deterministic retrieval eval (no AI judge).

For each imported book, up to N outline leaf headings are sampled (seeded). Each heading is asked
twice: as is, and as "How does <heading> work?". Gold = the PDF page range of that section in that
book. A query hits at rank r when result r is from the book and its page_pdf is inside the range.
Queries go to the edition collection like the backend's (Classic: filtered to the book's line or
'all'). Every result is also checked for edition leaks (a V5 query returning Classic or the
reverse) and, for Classic, line leaks (a Vampire query returning Werewolf/Mage).
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional

from .manifest import collection_for
from .textutil import norm_key

GENERIC = re.compile(r"^(introduction|credits|contents|table of contents|index|appendix\b.*|chapter [a-z]+|prologue|"
                     r"epilogue|foreword|legal|thanks|acknowledg\w*|cover|title page|how to use this book|"
                     r"sample chapter|playtest\w*|special thanks)$", re.I)

QueryFn = Callable[[str, str, int, Optional[dict]], List[dict]]


def sample_queries(book: dict, ext: dict, chunks: List[dict], n: int = 40, seed: int = 0) -> List[dict]:
    with_chunks = {c["metadata"]["heading_path"] for c in chunks}
    usable = []
    for s in ext.get("sections", []):
        title = s["title"].strip()
        if not s.get("leaf") or len(norm_key(title)) < 4 or GENERIC.match(title):
            continue
        path = " › ".join(s["path"])
        if not any(h == path or h.startswith(path + " › ") for h in with_chunks):
            continue
        usable.append(s)
    rng = random.Random(f"{seed}:{book['book_id']}")
    picked = rng.sample(usable, min(n, len(usable)))
    picked.sort(key=lambda s: s["id"])
    out = []
    for s in picked:
        gold = [s["page_pdf"], max(s["page_pdf"], s["page_end_pdf"])]
        for style, q in (("heading", s["title"]), ("paraphrase", f"How does {s['title']} work?")):
            out.append({"book_id": book["book_id"], "section": " › ".join(s["path"]), "query": q,
                        "style": style, "gold_pages_pdf": gold})
    return out


def load_questions(path: str, books: List[dict]) -> List[dict]:
    """Hand-written questions (books/eval_questions.yaml); raises ValueError on a bad entry."""
    import yaml
    from .manifest import parse_pages
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    by_id = {b["book_id"]: b for b in books}
    out, ids, errs = [], set(), []
    for i, q in enumerate(data.get("questions") or []):
        where = f"questions[{i}] ({q.get('id', '?')})"
        if not q.get("id") or not q.get("q") or not q.get("book") or not q.get("pages"):
            errs.append(f"{where}: needs id, q, book and pages")
            continue
        if q["id"] in ids:
            errs.append(f"{where}: duplicate id")
        ids.add(q["id"])
        if q["book"] not in by_id:
            errs.append(f"{where}: book {q['book']} is not in the manifest")
            continue
        try:
            rngs = parse_pages(str(q["pages"]))
            lo, hi = min(a for a, _ in rngs), max(b for _, b in rngs)
        except Exception:  # noqa: BLE001
            errs.append(f"{where}: bad pages {q['pages']!r}")
            continue
        out.append({"id": q["id"], "book_id": q["book"], "query": q["q"], "pages": [lo, hi]})
    if errs:
        raise ValueError("eval questions:\n  " + "\n  ".join(errs))
    return out


def run_questions(books: List[dict], questions: List[dict], query_fn: QueryFn, k: int = 5, slack: int = 1) -> Dict[str, Any]:
    """Score hand-written questions: hit when a result is from the gold book and its printed page
    is within the gold pages +- slack."""
    by_id = {b["book_id"]: b for b in books}
    rows, per = [], {}
    leaks = {"edition": 0, "line": 0, "results": 0}
    for q in questions:
        b = by_id.get(q["book_id"])
        if b is None:
            continue
        res = query_fn(collection_for(b), q["query"], k, where_for(b))
        rank = None
        for i, m in enumerate(res, 1):
            leaks["results"] += 1
            leaks["edition"] += m.get("edition") != b["edition"]
            leaks["line"] += b["edition"] == "classic" and m.get("line") not in (b["line"], "all")
            if rank is None and m.get("book_id") == b["book_id"] and \
                    q["pages"][0] - slack <= int(m.get("page", -999)) <= q["pages"][1] + slack:
                rank = i
        st = per.setdefault(b["edition"], {"n": 0, "hit1": 0, "hit3": 0, "hit5": 0, "rr": 0.0})
        st["n"] += 1
        st["hit1"] += rank is not None and rank <= 1
        st["hit3"] += rank is not None and rank <= 3
        st["hit5"] += rank is not None and rank <= 5
        st["rr"] += 1.0 / rank if rank else 0.0
        rows.append(dict(q, rank=rank, top=[f"{m.get('book_id')} p{m.get('page')}" for m in res[:3]]))
    return {"k": k, "mode": "questions", "per_edition": {e: _rates(v) for e, v in per.items()},
            "leaks": leaks, "queries": rows}


def where_for(book: dict) -> Optional[dict]:
    if book["edition"] == "classic":
        return {"line": {"$in": [book["line"], "all"]}}
    return None


def run(books: List[dict], queries: Dict[str, List[dict]], query_fn: QueryFn, k: int = 5) -> Dict[str, Any]:
    per_book, rows = {}, []
    leaks = {"edition": 0, "line": 0, "results": 0}
    for b in books:
        qs = queries.get(b["book_id"], [])
        if not qs:
            continue
        name = collection_for(b)
        stats = {s: {"n": 0, "hit1": 0, "hit3": 0, "hit5": 0, "rr": 0.0} for s in ("heading", "paraphrase")}
        for q in qs:
            res = query_fn(name, q["query"], k, where_for(b))
            rank = None
            for i, m in enumerate(res, 1):
                leaks["results"] += 1
                if m.get("edition") != b["edition"]:
                    leaks["edition"] += 1
                if b["edition"] == "classic" and m.get("line") not in (b["line"], "all"):
                    leaks["line"] += 1
                if rank is None and m.get("book_id") == b["book_id"] and \
                        q["gold_pages_pdf"][0] <= int(m.get("page_pdf", -1)) <= q["gold_pages_pdf"][1]:
                    rank = i
            st = stats[q["style"]]
            st["n"] += 1
            st["hit1"] += rank is not None and rank <= 1
            st["hit3"] += rank is not None and rank <= 3
            st["hit5"] += rank is not None and rank <= 5
            st["rr"] += 1.0 / rank if rank else 0.0
            rows.append(dict(q, rank=rank, top=[f"{m.get('book_id')} p{m.get('page_pdf')} d={m.get('_distance', 0):.3f}"
                                                 for m in res[:3]]))
        per_book[b["book_id"]] = {s: _rates(v) for s, v in stats.items()}
    total = {s: {"n": 0, "hit1": 0, "hit3": 0, "hit5": 0, "rr": 0.0} for s in ("heading", "paraphrase")}
    for r in rows:
        t = total[r["style"]]
        t["n"] += 1
        rk = r["rank"]
        t["hit1"] += rk is not None and rk <= 1
        t["hit3"] += rk is not None and rk <= 3
        t["hit5"] += rk is not None and rk <= 5
        t["rr"] += 1.0 / rk if rk else 0.0
    return {"k": k, "per_book": per_book, "overall": {s: _rates(v) for s, v in total.items()},
            "leaks": leaks, "queries": rows}


def _rates(v: dict) -> dict:
    n = max(1, v["n"])
    return {"n": v["n"], "hit@1": round(v["hit1"] / n, 3), "hit@3": round(v["hit3"] / n, 3),
            "hit@5": round(v["hit5"] / n, 3), "mrr": round(v["rr"] / n, 3)}


def write_report(report: Dict[str, Any], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(out_dir, f"eval-{stamp}" + ("-questions" if report.get("mode") == "questions" else ""))
    with open(base + ".json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    if report.get("mode") == "questions":
        lines = [f"# Rule book retrieval eval, hand-written questions ({stamp})", "",
                 "Gold: the printed page the repo's rules specs cite, +-1 page.", "",
                 "| edition | n | hit@1 | hit@3 | hit@5 | MRR |", "|---|---|---|---|---|---|"]
        for ed, r in report["per_edition"].items():
            lines.append(f"| {ed} | {r['n']} | {r['hit@1']} | {r['hit@3']} | {r['hit@5']} | {r['mrr']} |")
        lk = report["leaks"]
        lines += ["", f"Edition leaks: {lk['edition']} of {lk['results']} results. Classic line leaks: {lk['line']}."]
        with open(base + ".md", "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return base
    lines = [f"# Rule book retrieval eval ({stamp})", "",
             "Deterministic: queries are sampled outline headings; gold is that section's page range.", "",
             "| book | style | n | hit@1 | hit@3 | hit@5 | MRR |", "|---|---|---|---|---|---|---|"]
    for bid, st in report["per_book"].items():
        for style, r in st.items():
            if r["n"]:
                lines.append(f"| {bid} | {style} | {r['n']} | {r['hit@1']} | {r['hit@3']} | {r['hit@5']} | {r['mrr']} |")
    for style, r in report["overall"].items():
        if r["n"]:
            lines.append(f"| **all** | {style} | {r['n']} | {r['hit@1']} | {r['hit@3']} | {r['hit@5']} | {r['mrr']} |")
    lk = report["leaks"]
    lines += ["", f"Edition leaks: {lk['edition']} of {lk['results']} results. "
              f"Classic line leaks: {lk['line']} of {lk['results']} results."]
    with open(base + ".md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return base
