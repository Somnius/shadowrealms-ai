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
            "advantages": [(179, 199)],
            "loresheets": [(382, 406)],
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
            "advantages": [(109, 122), (126, 128), (135, 136), (139, 151), (156, 191), (232, 238)],
            "loresheets": [(223, 229)],
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
            "advantages": [(30, 60)],
        },
        footer_samples=(8, 17, 25),
    ),
)

# Tier-2 books (supplements; Forge v2 part F). Their entries carry their own book_id, so a
# chronicle's allowed_books switch can turn them off; books.json marks them tier 2. dot_glyph None:
# the book draws its rating dots as graphics (no text), so ratings come from geometry or from the
# rendered page (manual records). Offsets from the inventory, re-checked with `pages <book_id>`.
TIER2: tuple[Book, ...] = (
    Book(book_id="v5-camarilla", offset=1, dot_glyph=None, tier=2,
         ranges={"loresheets": [(184, 190)]}, footer_samples=(50, 184)),
    Book(book_id="v5-cults-of-the-blood-gods", offset=3, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(220, 231)]}, footer_samples=(68, 220)),
    Book(book_id="v5-children-of-the-blood", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(101, 108)]}, footer_samples=(27, 101)),
    Book(book_id="v5-forbidden-religions", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(88, 93)]}, footer_samples=(23, 88)),
    Book(book_id="v5-blood-sigils", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(177, 180)]}, footer_samples=(92, 177)),
    Book(book_id="v5-gehenna-war", offset=2, dot_glyph=None, tier=2,
         ranges={"loresheets": [(157, 159)]}, footer_samples=(39, 157)),
    Book(book_id="v5-courts-of-the-damned", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(218, 222)]}, footer_samples=(55, 218)),
    Book(book_id="v5-in-memoriam", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(149, 154)]}, footer_samples=(39, 149)),
    Book(book_id="v5-succubus-club", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(158, 166)]}, footer_samples=(41, 158)),
    Book(book_id="v5-tattered-facade", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(171, 174)]}, footer_samples=(88, 171)),
    Book(book_id="v5-chicago-by-night", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(262, 287)]}, footer_samples=(89, 262)),
    Book(book_id="v5-chicago-folios", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(158, 169)]}, footer_samples=(44, 158)),
    Book(book_id="v5-nod-apocrypha", offset=2, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(37, 40)]}, footer_samples=(28, 37)),
    # one-sheet-per-page handouts: printed page = PDF page (LA by Night prints 1-10; the Choice
    # of Games file prints no page numbers, so its "page" is the PDF page)
    Book(book_id="v5-la-by-night-loresheets", offset=0, dot_glyph=None, tier=2,
         ranges={"loresheets": [(1, 10)]}, footer_samples=(1, 10)),
    Book(book_id="v5-choice-of-games-loresheets", offset=0, dot_glyph=None, tier=2,
         ranges={"loresheets": [(1, 4)]}),
    # adventures: the PDF of Let the Streets Run Red holds the book twice; pdf 1-252 is the
    # updated text (it fills the second copy's "XX" page references), so offset +1 reads it
    Book(book_id="v5-fall-of-london", offset=2, dot_glyph=None, tier=2,
         ranges={"loresheets": [(233, 238)]}, footer_samples=(65, 233)),
    Book(book_id="v5-let-the-streets-run-red", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(224, 233)]}, footer_samples=(76, 224)),
    Book(book_id="v5-trails-of-ash-and-bone", offset=1, dot_glyph="\u2022", tier=2,
         ranges={"loresheets": [(170, 172)]}, footer_samples=(49, 170)),
    # the Anarch PDF on disk is a Russian translation: nothing is extracted from it; its
    # entries are facts from the online source (source "online"), see manual/loresheets.json
    Book(book_id="v5-anarch", offset=0, dot_glyph=None, tier=2, extractable=False),
)

TIER1_IDS = {b.book_id for b in TIER1}
BY_ID = {b.book_id: b for b in TIER1 + TIER2}
ALL_CITED = BY_ID


def get(book_id: str) -> Book:
    try:
        return BY_ID[book_id]
    except KeyError:
        raise SystemExit(f"unknown book_id {book_id!r}; known: {', '.join(BY_ID)}") from None


def load_manifest() -> dict:
    """book_id -> manifest entry (needs pyyaml). Files the RAG import leaves out on purpose
    (`excluded:`) can still carry a book_id, title and precedence when the catalog cites them
    (the Russian Anarch PDF); those come back too, marked "excluded": True."""
    import yaml

    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    out = {b["book_id"]: b for b in data.get("books", [])}
    for x in data.get("excluded") or []:
        if isinstance(x, dict) and x.get("book_id"):
            out.setdefault(x["book_id"], dict(x, excluded=True))
    return out


def books_root() -> Path:
    env = os.environ.get("SR_BOOKS_DIR")
    return Path(env) if env else REPO_ROOT / "books" / "World_of_Darkness"


def pdf_path(book_id: str, manifest: dict | None = None) -> Path:
    manifest = manifest if manifest is not None else load_manifest()
    entry = manifest.get(book_id)
    if not entry:
        raise SystemExit(f"{book_id} is not in books/manifest.yaml")
    return books_root() / entry["path"]
