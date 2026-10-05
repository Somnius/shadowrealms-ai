#!/usr/bin/env python3
"""Rule-book importer: PDFs listed in books/manifest.yaml -> chunks -> ChromaDB.

Deterministic script (PyMuPDF + rules, no AI). Data contract: docs/rules/RULE_BOOKS_RAG.md.
Usage: see books/README.md ("Importing rule books") or `python books/import_books.py -h`.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rbimport import evaluate, manifest, pipeline  # noqa: E402
from rbimport.textutil import TokenCounter  # noqa: E402


def log(msg: str):
    print(msg, flush=True)


def select(args, data) -> list:
    books = data["books"]
    if args.only:
        want = [x.strip() for x in args.only.split(",") if x.strip()]
        known = {b["book_id"] for b in books}
        bad = [w for w in want if w not in known]
        if bad:
            sys.exit(f"unknown book_id(s): {', '.join(bad)}")
        books = [b for b in books if b["book_id"] in want]
    if args.edition:
        books = [b for b in books if b["edition"] == args.edition]
    return books


def find_book(data, book_id: str) -> dict:
    for b in data["books"]:
        if b["book_id"] == book_id:
            return b
    sys.exit(f"unknown book_id: {book_id}")


def summary_rows(books, results) -> list:
    rows = []
    for b in books:
        r = results.get(b["book_id"]) or {}
        ch = r.get("chunks") or []
        toks = [c["tokens"] for c in ch]
        kinds = collections.Counter(c["metadata"]["kind"] for c in ch)
        st = r.get("stats") or {}
        rows.append({
            "book_id": b["book_id"], "edition": b["edition"], "kind": b["kind"], "status": r.get("status", "?"),
            "pages": r.get("pages_used") or 0, "chunks": len(ch),
            "avg_tokens": round(sum(toks) / len(toks)) if toks else 0, "max_tokens": max(toks) if toks else 0,
            "pct_heading_path": round(100 * sum(bool(c["metadata"]["heading_path"]) for c in ch) / len(ch)) if ch else 0,
            "kinds": dict(kinds.most_common()), "outline": r.get("outline", ""), "page_numbers": r.get("page_numbers", ""),
            "dup": st.get("dropped_dup", 0), "junk": st.get("dropped_junk", 0), "warnings": r.get("warnings", []),
        })
    return rows


def print_summary(rows, out_base: str = None):
    head = "| book | ed | status | pages | chunks | avg tok | max tok | % path | kinds | dup/junk | outline | warnings |"
    lines = [head, "|" + "---|" * 12]
    for r in rows:
        kinds = ", ".join(f"{k} {v}" for k, v in r["kinds"].items())
        warn = "; ".join(r["warnings"])[:120]
        lines.append(f"| {r['book_id']} | {r['edition']} | {r['status']} | {r['pages']} | {r['chunks']} | {r['avg_tokens']} | "
                     f"{r['max_tokens']} | {r['pct_heading_path']} | {kinds} | {r['dup']}/{r['junk']} | {r['outline']} | {warn} |")
    ok = [r for r in rows if r["status"] == "ok"]
    skipped = [r for r in rows if r["status"] != "ok"]
    lines.append("")
    lines.append(f"{len(ok)} book(s) chunked, {sum(r['chunks'] for r in ok)} chunks; "
                 f"{len(skipped)} skipped: " + (", ".join(f"{r['book_id']} ({r['status']})" for r in skipped) or "none"))
    text = "\n".join(lines)
    print(text)
    if out_base:
        os.makedirs(os.path.dirname(out_base), exist_ok=True)
        with open(out_base + ".md", "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        with open(out_base + ".json", "w", encoding="utf-8") as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)


def cmd_extract(args, data, paths):
    books = select(args, data)
    res = pipeline.extract_books(books, paths, workers=args.workers, force=args.force, log=log)
    image_only = [b for b in books if res.get(b["book_id"], {}).get("status") == "image-only"]
    for b in books:
        r = res.get(b["book_id"], {})
        if r.get("status") != "ok":
            log(f"skipped {b['book_id']}: {r.get('status')} - {'; '.join(r.get('warnings', []))[:160]}")
    log(f"extract: {sum(1 for b in books if res.get(b['book_id'], {}).get('status') == 'ok')} ok, "
        f"{len(image_only)} image-only (need OCR)")
    return res


def cmd_chunk(args, data, paths):
    books = select(args, data)
    ext = pipeline.extract_books(books, paths, workers=args.workers, force=args.force, log=log)
    counter = _counter(args, strict=False)
    res = pipeline.chunk_books(books, data["books"], ext, paths, counter, write=not args.dry_run)
    print_summary(summary_rows(books, res), os.path.join(paths.data, "chunk_summary"))
    return res


def _counter(args, strict: bool) -> TokenCounter:
    """The token counter. Chunk ids and hashes depend on it, so import/attach refuse a silent
    fallback to the estimate (that would re-embed every book)."""
    counter = TokenCounter(args.tokenizer)
    if counter.fallback:
        if strict:
            sys.exit(f"error: {counter.fallback}. Fix that, or pass --tokenizer estimate on purpose "
                     f"(chunks then differ from bge-m3-counted ones and get re-embedded).")
        log(f"warning: {counter.fallback}; using the words x 1.35 estimate")
    log(f"token counter: {counter.name}")
    return counter


def _chunks_for(book, paths, args, data, counter, campaign_id=0):
    res = pipeline.load_chunks(book, paths, campaign_id, counter.name, data["books"])
    if res is not None:
        return res
    ext = pipeline.extract_books([book], paths, workers=1, log=log)
    return pipeline.chunk_books([book], data["books"], ext, paths, counter, campaign_id=campaign_id)[book["book_id"]]


def _fail(msg: str):
    sys.exit(f"error: {msg}")


def _store(args):
    from rbimport.store import Store
    try:
        return Store(args.chroma_host, args.chroma_port, args.lmstudio_url)
    except Exception as e:  # noqa: BLE001 - one line, not a traceback
        _fail(f"cannot reach Chroma at {args.chroma_host}:{args.chroma_port} ({type(e).__name__}: {str(e)[:160]})")


def cmd_import(args, data, paths):
    from rbimport.store import ImportFailed, upsert_book
    if not (args.only or args.edition or args.all):
        _fail("say what to import: --only <book_id,...>, --edition v5|classic, or --all")
    # precedence order, so a book is de-duplicated against the current chunks of the books above it
    books = sorted(select(args, data), key=pipeline._book_order)
    counter = _counter(args, strict=True)
    state = pipeline.State(paths.state)
    store = None
    for b in books:
        if b["kind"] == "adventure":
            log(f"{b['book_id']}: adventure, not imported globally (use: attach --book {b['book_id']} --campaign <id>)")
            continue
        res = _chunks_for(b, paths, args, data, counter)
        if res.get("status") != "ok":
            log(f"{b['book_id']}: skipped ({res.get('status')})")
            continue
        name = pipeline.target_collection(b)
        e = state.entry(b["book_id"])
        same = e.get("chunks_sha") == res["chunks_sha"]
        start = int(e.get("done") or 0) if same and args.resume and not args.force else 0
        if args.dry_run:
            what = "up to date" if same and e.get("status") == "done" and not args.force else \
                f"would upsert {len(res['chunks']) - start} of {len(res['chunks'])} chunks"
            log(f"[dry-run] {b['book_id']} -> {name}: {what}")
            continue
        if store is None:
            store = _store(args)
        try:
            upsert_book(store, state, b, res, batch=args.batch, pace_ms=args.pace_ms, resume=args.resume,
                        force=args.force, log=log)
        except ImportFailed as e:
            _fail(str(e))


def cmd_attach(args, data, paths):
    from rbimport.store import ImportFailed, upsert_book
    b = find_book(data, args.book)
    if args.campaign <= 0:
        _fail("--campaign must be a chronicle id (> 0)")
    if b["kind"] != "adventure" and not args.force:
        _fail(f"{b['book_id']} is kind {b['kind']}, not an adventure; pass --force to attach it anyway")
    counter = _counter(args, strict=True)
    res = _chunks_for(b, paths, args, data, counter, campaign_id=args.campaign)
    if res.get("status") != "ok":
        sys.exit(f"{b['book_id']}: cannot attach ({res.get('status')})")
    if args.dry_run:
        log(f"[dry-run] would attach {len(res['chunks'])} chunks of {b['book_id']} to chronicle {args.campaign} "
            f"in {pipeline.target_collection(b, args.campaign)}")
        return
    state = pipeline.State(paths.state)
    try:
        upsert_book(_store(args), state, b, res, batch=args.batch, pace_ms=args.pace_ms, resume=args.resume,
                    force=args.force, campaign_id=args.campaign, log=log)
    except ImportFailed as e:
        _fail(str(e))


def cmd_delete(args, data, paths):
    b = find_book(data, args.book)
    name = pipeline.target_collection(b, args.campaign)
    if args.dry_run:
        log(f"[dry-run] would delete {b['book_id']} from {name}" + (f" (chronicle {args.campaign})" if args.campaign else ""))
        return
    n = _store(args).delete_book(name, b["book_id"], args.campaign)
    state = pipeline.State(paths.state)
    state.drop(b["book_id"], args.campaign)
    state.save()
    log(f"deleted {n} chunks of {b['book_id']} from {name}")


def cmd_status(args, data, paths):
    books = select(args, data)
    state = pipeline.State(paths.state)
    store = _store(args) if args.chroma else None
    print("| book | kind | extract | chunks | import | in chroma |")
    print("|---|---|---|---|---|---|")
    for b in books:
        ext = pipeline._read_json(paths.extract_file(b)) or {}
        ch = pipeline.load_chunks(b, paths, all_books=data["books"])
        e = state.data["books"].get(b["book_id"], {})
        imp = f"{e.get('status')} {e.get('done')}/{e.get('chunks')}" if e else "-"
        inc = store.count_book(pipeline.target_collection(b), b["book_id"]) if store else ""
        print(f"| {b['book_id']} | {b['kind']} | {ext.get('status', '-')} | {len(ch['chunks']) if ch else '-'} | {imp} | {inc} |")
    for k, e in state.data["attachments"].items():
        print(f"| {k} (attached) | adventure | | | {e.get('status')} {e.get('done')}/{e.get('chunks')} | |")


def cmd_eval(args, data, paths):
    books = select(args, data)
    if args.questions:
        questions = evaluate.load_questions(args.questions, data["books"])
        if args.check:
            log(f"{args.questions}: {len(questions)} questions, every gold book is in the manifest")
            return
    state = pipeline.State(paths.state)
    books = [b for b in books if state.data["books"].get(b["book_id"], {}).get("status") == "done"]
    if not books:
        _fail("no imported books to evaluate (import first)")
    if args.questions:
        have = {b["book_id"] for b in books}
        todo = [q for q in questions if q["book_id"] in have]
        log(f"eval: {len(todo)} of {len(questions)} questions (the rest are about books not imported)")
        report = evaluate.run_questions(books, todo, _store(args).query, k=args.k)
        base = evaluate.write_report(report, paths.eval)
        with open(base + ".md", encoding="utf-8") as fh:
            print(fh.read())
        log(f"report: {base}.json / .md")
        return
    queries = {}
    for b in books:
        ext = pipeline._read_json(paths.extract_file(b))
        ch = pipeline.load_chunks(b, paths, all_books=data["books"])
        if not ext or not ch:
            log(f"{b['book_id']}: no current extract/chunk cache, skipped")
            continue
        queries[b["book_id"]] = evaluate.sample_queries(b, ext, ch["chunks"], n=args.per_book, seed=args.seed)
    store = _store(args)
    total = sum(len(q) for q in queries.values())
    log(f"eval: {total} queries over {len(queries)} book(s)")
    report = evaluate.run(books, queries, store.query, k=args.k)
    base = evaluate.write_report(report, paths.eval)
    with open(base + ".md", encoding="utf-8") as fh:
        print(fh.read())
    log(f"report: {base}.json / .md")


def add_common(p, suppress: bool):
    """Options accepted before or after the subcommand (after it, they override)."""
    def opt(*names, default=None, **kw):
        p.add_argument(*names, default=argparse.SUPPRESS if suppress else default, **kw)
    opt("--manifest", default=os.path.join(pipeline.HERE, "manifest.yaml"))
    opt("--books-root", default=os.environ.get("RULE_BOOKS_ROOT") or pipeline.BOOKS_ROOT,
        help="folder the manifest paths are relative to (env RULE_BOOKS_ROOT)")
    opt("--data-dir", default=pipeline.DATA, help="cache, state and eval reports (default data/rule_books)")
    opt("--only", help="comma-separated book_ids")
    opt("--edition", choices=sorted(manifest.EDITIONS))
    opt("--dry-run", default=False, action="store_true", help="no writes to Chroma or state.json (chunk: no chunk cache)")
    opt("--chroma-host", default=os.environ.get("CHROMADB_HOST") or "localhost")
    opt("--chroma-port", type=int, default=int(os.environ.get("CHROMADB_PORT") or 8000))
    opt("--lmstudio-url", default=os.environ.get("LM_STUDIO_URL") or "http://localhost:1234")
    opt("--pace-ms", type=int, default=200, help="sleep between upsert batches (LM Studio is shared)")
    opt("--batch", type=int, default=64, help="chunks per upsert")
    opt("--resume", dest="resume", default=True, action="store_true", help="continue a partial import (default)")
    opt("--no-resume", dest="resume", default=True, action="store_false")
    opt("--force", default=False, action="store_true", help="re-extract / re-import even when unchanged")
    opt("--workers", type=int, default=4, help="extract processes (max 8)")
    opt("--tokenizer", default="auto", help="auto (bge-m3 tokenizer.json if found), bge-m3, estimate, or a tokenizer.json path")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common(p, suppress=False)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("extract", help="PDF -> cached blocks/sections (keyed by file sha256)")
    sub.add_parser("chunk", help="blocks -> chunks + summary table")
    im = sub.add_parser("import", help="embed + upsert into rule_books_v5 / rule_books_classic (not adventures)")
    im.add_argument("--all", action="store_true", help="every non-adventure book in the manifest")
    st = sub.add_parser("status", help="extract/chunk/import state per book")
    st.add_argument("--chroma", action="store_true", help="also count each book's chunks in Chroma")
    d = sub.add_parser("delete", help="remove one book from its collection")
    d.add_argument("--book", required=True)
    d.add_argument("--campaign", type=int, default=0, help="chronicle id (for an attached book)")
    a = sub.add_parser("attach", help="import a book (an adventure) into rule_books_chronicle for one chronicle")
    a.add_argument("--book", required=True)
    a.add_argument("--campaign", type=int, required=True)
    ev = sub.add_parser("eval", help="deterministic retrieval eval on imported books")
    ev.add_argument("--per-book", type=int, default=40)
    ev.add_argument("--seed", type=int, default=0)
    ev.add_argument("-k", type=int, default=5)
    ev.add_argument("--questions", help="hand-written question file (books/eval_questions.yaml) instead of sampled headings")
    ev.add_argument("--check", action="store_true", help="with --questions: only validate the file")
    for sp in sub.choices.values():
        add_common(sp, suppress=True)
    args = p.parse_args(argv)
    args.workers = max(1, min(args.workers, 8))
    data = manifest.load(args.manifest)
    paths = pipeline.Paths(args.books_root, args.data_dir)
    cmd = {"extract": cmd_extract, "chunk": cmd_chunk, "import": cmd_import, "status": cmd_status,
           "delete": cmd_delete, "attach": cmd_attach, "eval": cmd_eval}[args.cmd]
    try:
        cmd(args, data, paths)
    except Exception as e:  # noqa: BLE001 - one line for the operator; RB_DEBUG=1 for the traceback
        if os.environ.get("RB_DEBUG"):
            raise
        _fail(f"{type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
