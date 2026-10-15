"""Which books the V5 catalog is built from, where their PDFs are, and how to read their pages.

Only the facts needed to find text live here: book_id (the vocabulary of books/manifest.yaml),
the page offset (pdf index = printed page + offset, from the Forge v2 book inventory and
re-checked with `python -m scripts.v5_catalog pages <book_id>`), the dot glyph the book prints,
and the printed page ranges that each catalog is read from.

PDF location: books/manifest.yaml gives `path` relative to books/World_of_Darkness. The PDFs
are not in git; set SR_BOOKS_DIR to the World_of_Darkness folder when it lives elsewhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "books" / "manifest.yaml"
CATALOG_DIR = REPO_ROOT / "docs" / "rules" / "v5" / "catalog"
BUILD_DIR = REPO_ROOT / "data" / "catalog-build" / "v5"


@dataclass(frozen=True)
class Book:
    book_id: str
    offset: int  # pdf page index (1-based) = printed page + offset
    dot_glyph: str
    tier: int = 1
    extractable: bool = True
    # catalog name -> list of (first printed page, last printed page)
    ranges: dict = field(default_factory=dict)
    # printed pages whose footers the `pages` command prints to prove the offset
    footer_samples: tuple = ()

    def pdf_page(self, printed: int) -> int:
        return printed + self.offset

    def printed_page(self, pdf: int) -> int:
        return pdf - self.offset


TIER1: tuple[Book, ...] = (
    Book(
        book_id="v5-corebook",
        offset=2,
        dot_glyph="•",
        ranges={
            "clans": [(65, 113)],
            "compulsions": [(208, 211)],
            "predator_types": [(175, 178)],
            "predator_pools": [(307, 308)],
            "disciplines": [(243, 287)],
        },
        footer_samples=(48, 176, 249),
    ),
    Book(
        book_id="v5-players-guide",
        offset=2,
        dot_glyph="•",
        ranges={
            "clans": [(12, 13), (17, 59), (125, 136)],
            "predator_types": [(106, 109)],
            "disciplines": [(69, 106)],
        },
        footer_samples=(18, 70, 108),
    ),
    Book(
        book_id="v5-companion",
        offset=0,
        dot_glyph="●",
        ranges={
            "clans": [(6, 23)],
            "disciplines": [(24, 28)],
        },
        footer_samples=(8, 17, 25),
    ),
)

# Tier-2 books that Tier-1 catalogs cite (predator types first printed outside the Tier-1
# books, the Cults originals of PG's reprints). Offsets from the inventory; their pages are
# not extracted by this build (`pages` only caches Tier 1).
TIER2_CITED: tuple[Book, ...] = (
    Book(book_id="v5-cults-of-the-blood-gods", offset=3, dot_glyph="\u2022", tier=2),
    Book(book_id="v5-in-memoriam", offset=2, dot_glyph="\u2022", tier=2),
    Book(book_id="v5-let-the-streets-run-red", offset=1, dot_glyph="\u2022", tier=2),
)

BY_ID = {b.book_id: b for b in TIER1}
ALL_CITED = {b.book_id: b for b in TIER1 + TIER2_CITED}


def get(book_id: str) -> Book:
    try:
        return BY_ID[book_id]
    except KeyError:
        raise SystemExit(f"unknown book_id {book_id!r}; Tier-1 books: {', '.join(BY_ID)}") from None


def load_manifest() -> dict:
    """book_id -> manifest entry (needs pyyaml)."""
    import yaml

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return {b["book_id"]: b for b in data.get("books", [])}


def books_root() -> Path:
    env = os.environ.get("SR_BOOKS_DIR")
    return Path(env) if env else REPO_ROOT / "books" / "World_of_Darkness"


def pdf_path(book_id: str, manifest: dict | None = None) -> Path:
    manifest = manifest if manifest is not None else load_manifest()
    entry = manifest.get(book_id)
    if not entry:
        raise SystemExit(f"{book_id} is not in books/manifest.yaml")
    return books_root() / entry["path"]
