"""PDF pages as text, one page at a time, cached on disk.

Two extractions per page, both from poppler's `pdftotext`, run with `nice -n 10`, one at a time:
  NNNN.txt   `-layout -f N -l N`: the page as laid out (what the overlap gate compares against,
             and what `show --layout` prints). The column splitter below puts it in reading order.
  NNNN.json  `-bbox-layout -f N -l N`: poppler's own flows/blocks/lines with word boxes. This is
             what the parsers read: it keeps reading order on the three-column corebook pages
             (where a single gutter split is not enough) and keeps word spacing that `-raw`
             loses in the Players Guide and the Companion. Each line carries its height, which
             tells headings from body text.

Cache: data/catalog-build/v5/<book_id>/<sha1[:16]>/pages/ (data/ is gitignored). The key is the
file's sha1, so a different printing of the same book never reuses old text. The sha1 itself is
cached per (size, mtime) because hashing the 200 MB Players Guide takes a while.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

from .. import books
from .base import Line


def file_sha1(path: Path, cache_dir: Path) -> str:
    st = path.stat()
    stamp = cache_dir / "sha1.json"
    key = f"{st.st_size}:{int(st.st_mtime)}"
    try:
        saved = json.loads(stamp.read_text())
        if saved.get("key") == key:
            return saved["sha1"]
    except (OSError, ValueError):
        pass
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp.write_text(json.dumps({"key": key, "sha1": h.hexdigest(), "file": path.name}))
    return h.hexdigest()


def pdftotext_page(path: Path, pdf_page: int, mode: str = "-layout") -> str:
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext (poppler) is not installed")
    out = subprocess.run(
        ["nice", "-n", "10", "pdftotext", mode, "-enc", "UTF-8",
         "-f", str(pdf_page), "-l", str(pdf_page), str(path), "-"],
        check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8", errors="replace")


_LINE = re.compile(
    r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', re.S)
_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">(.*?)</word>', re.S)
COLUMN_GAP = 8.0  # points (at least); a wider word gap splits a poppler line into two columns


def parse_bbox(doc: str) -> list[dict]:
    """`-bbox-layout` HTML -> [{t, x, y, h, f}] in poppler's reading order (f = flow number).

    poppler sometimes glues the ends of two neighbouring columns into one line ("...This
    Dominate: Some Malkavians use"); such lines are split where the gap between two words is
    wider than COLUMN_GAP, and each piece keeps its own x so column_order() can place it.
    """
    out = []
    for f, flow in enumerate(re.findall(r"<flow>(.*?)</flow>", doc, re.S)):
        for m in _LINE.finditer(flow):
            y, y2 = float(m.group(2)), float(m.group(4))
            gap = max(COLUMN_GAP, 0.5 * (y2 - y))  # big type has wide word spaces
            pieces: list[list] = []
            last_x2 = None
            for wm in _WORD.finditer(m.group(5)):
                x1, x2, w = float(wm.group(1)), float(wm.group(2)), html.unescape(wm.group(3))
                if not w:
                    continue
                if last_x2 is None or x1 - last_x2 > gap:
                    pieces.append([x1, []])
                pieces[-1][1].append(w)
                last_x2 = x2
            for x1, words in pieces:
                text = " ".join(words)
                if text.strip():
                    out.append({"t": text, "x": round(x1, 1), "y": round(y, 1),
                                "h": round(y2 - y, 1), "f": f})
    return out


class PdfBook:
    """Cached page access for one Tier-1 book."""

    def __init__(self, book_id: str, build_dir: Path | None = None, manifest: dict | None = None):
        self.book = books.get(book_id)
        self.path = books.pdf_path(book_id, manifest)
        root = (build_dir or books.BUILD_DIR) / book_id
        self._root = root
        self._pages_dir: Path | None = None

    @property
    def pages_dir(self) -> Path:
        if self._pages_dir is None:
            if not self.path.exists():
                raise SystemExit(f"PDF not found: {self.path} (set SR_BOOKS_DIR)")
            sha = file_sha1(self.path, self._root)
            self._pages_dir = self._root / sha[:16] / "pages"
            self._pages_dir.mkdir(parents=True, exist_ok=True)
        return self._pages_dir

    def raw(self, pdf_page: int) -> str:
        f = self.pages_dir / f"{pdf_page:04d}.txt"
        if f.exists():
            return f.read_text(encoding="utf-8")
        text = pdftotext_page(self.path, pdf_page)
        f.write_text(text, encoding="utf-8")
        return text

    def boxes(self, pdf_page: int) -> list[dict]:
        f = self.pages_dir / f"{pdf_page:04d}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        data = parse_bbox(pdftotext_page(self.path, pdf_page, "-bbox-layout"))
        f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    def cache(self, pdf_page: int) -> None:
        self.raw(pdf_page)
        self.boxes(pdf_page)

    def cached_text_pages(self) -> list[Path]:
        return sorted(self.pages_dir.glob("*.txt"))

    def lines(self, first_printed: int, last_printed: int) -> list[Line]:
        """Reading-order lines (from the bbox extraction) for a printed page range, inclusive."""
        out: list[Line] = []
        for printed in range(first_printed, last_printed + 1):
            pdf = self.book.pdf_page(printed)
            for box in column_order(self.boxes(pdf)):
                if is_noise(box["t"], box["h"]):
                    continue
                out.append(Line(text=collapse_spacing(box["t"]), book=self.book.book_id,
                                page=printed, page_pdf=pdf, height=box["h"], x=box["x"]))
        return out

    def layout_lines(self, printed: int) -> list[str]:
        return reading_order(self.raw(self.book.pdf_page(printed)))


# --------------------------------------------------------------------------- text helpers


def column_order(boxes: list[dict], min_lines: int = 4, merge: float = 30.0) -> list[dict]:
    """Put a page's lines in reading order: left column top to bottom, then the next column.

    poppler's flows keep each paragraph in order, but on multi-column pages a flow from
    column 2 can come before one from column 1, or interleave with it. So lines are placed
    by geometry: column anchors are the x positions where at least `min_lines` lines start
    (anchors closer than `merge` points are one column, which absorbs indents); each line
    belongs to the right-most anchor at or left of its x; lines are sorted by (column, y).
    """
    if not boxes:
        return []
    counts: dict[int, int] = {}
    for b in boxes:
        k = round(b["x"])
        counts[k] = counts.get(k, 0) + 1
    anchors: list[int] = []
    for x in sorted(k for k, n in counts.items() if n >= min_lines):
        if not anchors or x - anchors[-1] > merge:
            anchors.append(x)
    if not anchors:
        anchors = [0]

    def col(x: float) -> int:
        idx = 0
        for i, a in enumerate(anchors):
            if x + 0.5 >= a:
                idx = i
        return idx

    return sorted(boxes, key=lambda b: (col(b["x"]), b["y"]))


_SPACED = re.compile(r"^(?:\S ){3,}\S(?: {2,}(?:\S ){0,}\S)*$")


def collapse_spacing(s: str) -> str:
    """'T H E  W O L F' -> 'THE WOLF'; 'VA M P I R E' style headers too. Other text unchanged."""
    t = s.strip()
    toks = t.split(" ")
    words = [w for w in toks if w]
    if len(words) >= 4 and sum(len(w) == 1 for w in words) / len(words) > 0.6:
        parts = re.split(r" {2,}", t)
        return " ".join(p.replace(" ", "") for p in parts)
    return t


_RUNNING = re.compile(r"^(?:Chapter [A-Za-z]+: .{3,40}|Part [IVX]+: .{3,50})$")


def is_noise(s: str, height: float | None = None) -> bool:
    """Page numbers and running headers (book title, chapter title, small caps section name)."""
    t = s.strip()
    if not t:
        return True
    if re.fullmatch(r"\d{1,3}", t):
        return True
    letters = re.sub(r"[^A-Z]", "", collapse_spacing(t).upper())
    if letters.startswith("VAMPIRETHEMASQUERADE") and len(t) < 70:
        return True
    if _RUNNING.match(collapse_spacing(t)):
        return True
    if height is not None and height < 9.0 and t.upper() == t:
        return True
    return False


def find_gutter(lines: list[str], min_share: float = 0.9) -> int | None:
    """Column where a two-column page splits, or None.

    A gutter position x is one where, for >= min_share of the non-blank lines, the line is
    blank at x-1, x and x+1 (or ends before x). Among the runs of such positions in the
    middle band of the page, the widest one wins; the split is at its right edge, so the
    right column keeps its first character.
    """
    body = [ln.rstrip() for ln in lines if ln.strip()]
    if len(body) < 6:
        return None
    width = max(len(ln) for ln in body)
    if width < 50:
        return None

    def blank(ln: str, x: int) -> bool:
        seg = ln[x - 1:x + 2]
        return seg.strip() == ""

    # lines that have text on both sides of the middle band decide the gutter
    lo, hi = int(width * 0.3), int(width * 0.7)
    ok = []
    for x in range(lo, hi):
        n = sum(1 for ln in body if blank(ln, x))
        ok.append(n / len(body) >= min_share)
    best = None
    run_start = None
    for i, good in enumerate(ok + [False]):
        if good and run_start is None:
            run_start = i
        elif not good and run_start is not None:
            length = i - run_start
            if best is None or length > best[1]:
                best = (run_start, length)
            run_start = None
    if best is None:
        return None
    # require that a real share of lines continue to the right of the gutter
    split = lo + best[0] + best[1]
    right = sum(1 for ln in body if ln[split:].strip())
    left = sum(1 for ln in body if ln[:split].strip())
    if right < 3 or left < 3:
        return None
    return split


def reading_order(page_text: str) -> list[str]:
    """Strip, de-noise and column-order one `-layout` page. Returns non-empty lines."""
    raw = page_text.replace("\f", "").splitlines()
    split = find_gutter(raw)
    if split is None:
        cols = [raw]
    else:
        cols = [[ln[:split] for ln in raw], [ln[split:] for ln in raw]]
    out = []
    for col in cols:
        for ln in col:
            if is_noise(ln):
                continue
            out.append(collapse_spacing(ln))
    return out
