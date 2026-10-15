"""python -m scripts.v5_catalog <command> (run from the repo root).

Commands
  pages <book_id>|all      cache every page the catalogs read (pdftotext -layout, one page at a
                           time, nice 10) and print footer samples that prove the page offset
  show <book_id> <printed> print one page in reading order (column-split), for review
  extract [all]            parse the cached pages -> data/catalog-build/v5/extracted/*.json
                           + data/catalog-build/v5/report.md
  fetch <site> <title>...  cache MediaWiki pages (only sites with "fetch": true in
                           docs/rules/v5/catalog/sources.json; rate-limited)
  crosscheck <catalog>     compare the PDF intermediate with an online one, if present
  build                    extracted + manual -> docs/rules/v5/catalog/*.json
  check [--diff]           schema, ids, references, no 8-word overlap with the page cache;
                           --diff also proves the committed catalog equals a rebuild
"""

from __future__ import annotations

import re
import sys

from . import books


def cmd_pages(args: list[str]) -> int:
    from .sources.pdf import PdfBook

    ids = list(books.BY_ID) if not args or args[0] == "all" else args
    manifest = books.load_manifest()
    for book_id in ids:
        pb = PdfBook(book_id, manifest=manifest)
        b = pb.book
        wanted = set()
        for spans in b.ranges.values():
            for a, z in spans:
                wanted.update(range(a, z + 1))
        wanted.update(b.footer_samples)
        for printed in sorted(wanted):
            pb.cache(b.pdf_page(printed))
        print(f"{book_id}: {len(wanted)} pages cached under {pb.pages_dir}")
        for printed in b.footer_samples:
            raw = pb.raw(b.pdf_page(printed))
            nums = [ln.strip() for ln in raw.splitlines() if re.fullmatch(r"\s*\d{1,3}\s*", ln)]
            ok = str(printed) in nums
            print(f"  printed {printed} = pdf {b.pdf_page(printed)}: footer numbers {nums} "
                  f"{'OK' if ok else 'MISMATCH'}")
    return 0


def cmd_show(args: list[str]) -> int:
    from .sources.pdf import PdfBook

    layout = "--layout" in args
    args = [a for a in args if a != "--layout"]
    book_id, first = args[0], int(args[1])
    last = int(args[2]) if len(args) > 2 else first
    pb = PdfBook(book_id)
    for printed in range(first, last + 1):
        print(f"# {book_id} printed {printed} (pdf {pb.book.pdf_page(printed)})")
        if layout:
            print("\n".join(pb.layout_lines(printed)))
            continue
        for ln in pb.lines(printed, printed):
            print(f"{ln.height:5.1f} | {ln.text}")
    return 0


def cmd_fetch(args: list[str]) -> int:
    from .sources.mediawiki import MediaWikiSource, load_sources

    if len(args) < 2:
        raise SystemExit("usage: fetch <site> <title> [<title> ...]")
    src = MediaWikiSource(args[0], load_sources(books.CATALOG_DIR / "sources.json"),
                          books.BUILD_DIR.parent / "online")
    for title in args[1:]:
        rec = src.page(title)
        print(f"{rec['title']}: revision {rec['revision']}, {len(rec['text'])} chars")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "pages":
        return cmd_pages(rest)
    if cmd == "show":
        return cmd_show(rest)
    if cmd == "fetch":
        return cmd_fetch(rest)
    from . import pipeline

    return pipeline.run(cmd, rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
