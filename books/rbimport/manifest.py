"""books/manifest.yaml: which books to import and how. See books/README.md for the fields."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

EDITIONS = {"v5", "classic"}
LINES = {"vampire", "werewolf", "mage", "all"}
VERSIONS = {"v5", "revised", "v20", "2nd"}
KINDS = {"rules", "lore", "adventure"}
COLLECTIONS = {"v5": "rule_books_v5", "classic": "rule_books_classic"}
CHRONICLE_COLLECTION = "rule_books_chronicle"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REQUIRED = ("book_id", "path", "title", "edition", "line", "version", "kind", "precedence", "year")
KNOWN = set(REQUIRED) | {"official", "include", "exclude", "page_offset", "notes", "sidebar_fonts",
                         "strip_lines", "toc_fixes", "skip_sections", "toc_strip_prefix", "outline"}
OUTLINES = {"auto", "toc", "sizes", "none"}
DEFAULT_SKIP_SECTIONS = [r"^(table of )?contents$", r"^index$", r"^credits$"]


class ManifestError(ValueError):
    pass


def parse_pages(spec: Any) -> List[tuple]:
    """'1-430, 440' / [1, '3-5'] / None -> [(1, 430), (440, 440)] (1-based, inclusive)."""
    if spec in (None, "", []):
        return []
    items = spec if isinstance(spec, list) else str(spec).split(",")
    out = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+))?", s)
        if not m:
            raise ManifestError(f"bad page range {s!r}")
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if a < 1 or b < a:
            raise ManifestError(f"bad page range {s!r}")
        out.append((a, b))
    return out


def page_list(book: Dict[str, Any], page_count: int) -> List[int]:
    """1-based PDF pages to use: include ranges (default all) minus exclude ranges."""
    inc = parse_pages(book.get("include")) or [(1, page_count)]
    exc = parse_pages(book.get("exclude"))
    pages: Set[int] = set()
    for a, b in inc:
        pages.update(range(a, min(b, page_count) + 1))
    for a, b in exc:
        pages.difference_update(range(a, b + 1))
    return sorted(pages)


def validate(data: Dict[str, Any], books_root: Optional[str] = None) -> List[str]:
    """Return a list of problems (empty = valid). books_root: also check that files exist."""
    errs: List[str] = []
    books = data.get("books")
    if not isinstance(books, list) or not books:
        return ["manifest has no 'books' list"]
    ids, paths = set(), set()
    for i, b in enumerate(books):
        where = f"books[{i}] ({b.get('book_id', '?') if isinstance(b, dict) else '?'})"
        if not isinstance(b, dict):
            errs.append(f"{where}: not a mapping")
            continue
        for k in REQUIRED:
            if b.get(k) in (None, ""):
                errs.append(f"{where}: missing {k}")
        for k in b:
            if k not in KNOWN:
                errs.append(f"{where}: unknown field {k}")
        bid = str(b.get("book_id", ""))
        if bid and not SLUG.match(bid):
            errs.append(f"{where}: book_id must be a lowercase slug")
        if bid in ids:
            errs.append(f"{where}: duplicate book_id")
        ids.add(bid)
        p = b.get("path")
        if p in paths:
            errs.append(f"{where}: duplicate path")
        paths.add(p)
        if b.get("edition") not in EDITIONS:
            errs.append(f"{where}: edition must be one of {sorted(EDITIONS)}")
        if b.get("line") not in LINES:
            errs.append(f"{where}: line must be one of {sorted(LINES)}")
        if b.get("version") not in VERSIONS:
            errs.append(f"{where}: version must be one of {sorted(VERSIONS)}")
        if b.get("kind") not in KINDS:
            errs.append(f"{where}: kind must be one of {sorted(KINDS)}")
        if b.get("edition") == "v5" and b.get("line") not in ("vampire", "all"):
            errs.append(f"{where}: V5 books are Vampire only")
        if b.get("edition") == "v5" and b.get("version") != "v5":
            errs.append(f"{where}: V5 books have version v5")
        for k in ("precedence", "year"):
            if k in b and not isinstance(b[k], int):
                errs.append(f"{where}: {k} must be an integer")
        if b.get("official", True) is not True:
            errs.append(f"{where}: only official books are imported")
        if b.get("outline", "auto") not in OUTLINES:
            errs.append(f"{where}: outline must be one of {sorted(OUTLINES)}")
        if b.get("page_offset") is not None and not isinstance(b["page_offset"], int):
            errs.append(f"{where}: page_offset must be an integer")
        for k in ("include", "exclude"):
            try:
                parse_pages(b.get(k))
            except ManifestError as e:
                errs.append(f"{where}: {k}: {e}")
        for k in ("strip_lines", "skip_sections", "sidebar_fonts"):
            for rx in b.get(k) or []:
                try:
                    re.compile(rx)
                except re.error as e:
                    errs.append(f"{where}: {k} regex {rx!r}: {e}")
        if books_root and p and not os.path.exists(os.path.join(books_root, p)):
            errs.append(f"{where}: file not found: {p}")
    for i, x in enumerate(data.get("excluded") or []):
        if not isinstance(x, dict) or not x.get("path") or not x.get("reason"):
            errs.append(f"excluded[{i}]: needs path and reason")
    return errs


def load(path: str, books_root: Optional[str] = None) -> Dict[str, Any]:
    import yaml  # local import: the tests can validate dicts without a file
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    errs = validate(data, books_root)
    if errs:
        raise ManifestError("manifest problems:\n  " + "\n  ".join(errs))
    for b in data["books"]:
        b.setdefault("official", True)
    return data


def collection_for(book: Dict[str, Any]) -> str:
    return COLLECTIONS[book["edition"]]
