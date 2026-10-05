"""PDF -> normalised blocks with sections, kinds and printed page numbers (PyMuPDF, no AI).

Steps, all deterministic:
  1. read every used page with get_text("dict"); keep horizontal text lines with their spans
  2. drop running headers/footers and page numbers: lines in the top/bottom band whose text
     (digits masked) repeats on many pages, number-only lines in the bands, letter-spaced
     running heads, and manifest `strip_lines` regexes
  3. reading order per page: full-width lines (> 55% of the page width) are their own band;
     the rest is clustered into columns by line x0 (2 or 3 columns), each column read top-down
  4. paragraphs: break on style change (heading / sidebar font / italic run / small print),
     blank-line gaps, first-line indents after a sentence end, run-in bold labels
  5. kinds: >= 4 consecutive italic lines -> fiction; sidebar font -> sidebar; paragraphs
     starting with EXAMPLE -> example; the rest is the book's default kind
  6. sections from the PDF outline (get_toc) matched to the heading lines; without an outline,
     headings by font size (up to 3 levels). Bold stand-alone lines inside a section are kept as
     sub-headings.
  7. printed page numbers: PDF page labels, else the manifest page_offset, else the offset
     detected from the page numbers printed in the footer/header bands
"""
from __future__ import annotations

import bisect
import collections
import re
from typing import Any, Dict, List, Optional, Tuple

from .textutil import (HyphenVocab, clean_line, join_lines, label_to_int, letterspaced, norm_key)
from .manifest import DEFAULT_SKIP_SECTIONS, page_list

EXTRACTOR_VERSION = 5
V5_SIDEBAR_FONTS = [r"GillSans", r"Futura", r"IBMPlexSans"]
BAND = 0.09            # top/bottom fraction of the page treated as header/footer band
FULL_WIDTH = 0.55      # a line wider than this fraction of the page is a full-width band
COL_GAP = 25           # x0 gap (pt) that starts a new x0 cluster
IMAGE_ONLY_CHARS = 100  # median characters per page below this -> image-only (needs OCR)
_BOLD = re.compile(r"Bold|Semi|Demi|Black|Heavy|SC700", re.I)
_ITALIC = re.compile(r"Italic|Oblique|-It\b|Ital", re.I)
_NUMBER_ONLY = re.compile(r"^[\divxlcIVXLC][\d ivxlcIVXLC]{0,8}$")
_TERMINAL = ("." , "!", "?", "”", "\"", "’", ":", ")", "…")
_EXAMPLE = re.compile(r"^(EXAMPLE|Example)S?\b")


# --- 1. reading lines ------------------------------------------------------------------------

def _span_bold(s) -> bool:
    return bool(s["flags"] & 16) or bool(_BOLD.search(s["font"]))


def _span_italic(s) -> bool:
    return bool(s["flags"] & 2) or bool(_ITALIC.search(s["font"]))


def read_page_lines(page, pno: int) -> List[Dict[str, Any]]:
    """Text lines of one page (1-based pno) with geometry and style."""
    out = []
    import pymupdf
    d = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES)
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            dx, dy = ln.get("dir", (1, 0))
            if abs(dy) > 0.1 or dx < 0:
                continue  # rotated text (page-edge tabs, decorations)
            spans = [s for s in ln["spans"] if s["text"]]
            text = clean_line("".join(s["text"] for s in spans))
            if not text or not any(ch.isalnum() for ch in text):
                continue  # empty, or only bullets / rating dots / ornaments
            chars = collections.Counter()
            for s in spans:
                chars[(s["font"], round(s["size"], 1))] += len(s["text"].strip())
            (font, size), _ = chars.most_common(1)[0]
            vis = [s for s in spans if s["text"].strip()]
            bold_all = bool(vis) and all(_span_bold(s) for s in vis)
            italic_all = bool(vis) and all(_span_italic(s) for s in vis)
            runin = None
            if vis and _span_bold(vis[0]) and not bold_all:
                pre = []
                for s in vis:
                    if not _span_bold(s):
                        break
                    pre.append(s["text"])
                label = clean_line("".join(pre))
                if 2 <= len(label) <= 60 and re.search(r"[A-Za-z]{2}", label):
                    runin = label
            x0, y0, x1, y1 = ln["bbox"]
            out.append(dict(page=pno, x0=x0, y0=y0, x1=x1, y1=y1, text=text, font=font,
                            size=float(size), bold=bold_all, italic=italic_all, runin=runin))
    return out


# --- 2. headers / footers --------------------------------------------------------------------

def _mask(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower())[:60]


def find_running_lines(pages: List[Tuple[int, float, List[dict]]]) -> set:
    """Masked texts that repeat in the top/bottom band (or anywhere, if short and very frequent)."""
    band, anywhere = collections.Counter(), collections.Counter()
    for pno, h, lines in pages:
        seen_b, seen_a = set(), set()
        for l in lines:
            k = _mask(l["text"])
            if l["y1"] < BAND * h or l["y0"] > (1 - BAND) * h:
                seen_b.add(k)
            if len(l["text"]) <= 40:
                seen_a.add(k)
        band.update(seen_b)
        anywhere.update(seen_a)
    n = len(pages)
    keys = {k for k, c in band.items() if c >= max(3, 0.04 * n)}
    keys |= {k for k, c in anywhere.items() if n >= 20 and c >= 0.25 * n}
    return keys


def is_page_number(text: str) -> bool:
    t = text.strip()
    return bool(_NUMBER_ONLY.match(t)) and (any(ch.isdigit() for ch in t) or len(t) <= 5)


def strip_running(pages, running: set, strip_res: List[re.Pattern]):
    """Remove headers/footers/page numbers; also return detected footer page numbers per page."""
    numbers: Dict[int, int] = {}
    out = []
    for pno, h, w, lines in pages:
        keep = []
        for l in lines:
            t = l["text"]
            in_band = l["y1"] < BAND * h or l["y0"] > (1 - BAND) * h
            if in_band and is_page_number(t):
                digits = t.replace(" ", "")
                if digits.isdigit() and len(digits) <= 4:
                    numbers.setdefault(pno, int(digits))
                continue
            if _mask(t) in running and (in_band or len(t) <= 40):
                continue
            if letterspaced(t) and (in_band or len(t) <= 60):
                continue
            if any(rx.search(t) for rx in strip_res):
                continue
            keep.append(l)
        out.append((pno, h, w, keep))
    return out, numbers


# --- 3. reading order ------------------------------------------------------------------------

def column_starts(lines: List[dict], width: float) -> List[float]:
    """Left edges of the text columns on a page, from clustering line x0 values."""
    if not lines:
        return [0.0]
    xs = sorted(l["x0"] for l in lines)
    clusters: List[List[float]] = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= COL_GAP:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    need = max(3, 0.08 * len(lines))
    majors = [c[0] for c in clusters if len(c) >= need] or [clusters[0][0]]
    starts: List[float] = []
    for s in majors:
        if not starts or s - starts[-1] >= 0.2 * width:
            starts.append(s)
    return starts


def order_page(lines: List[dict], width: float) -> List[dict]:
    """Reading order: bands split by full-width lines; inside a band, columns left to right."""
    full = sorted([l for l in lines if (l["x1"] - l["x0"]) > FULL_WIDTH * width], key=lambda l: (l["y0"], l["x0"]))
    rest = [l for l in lines if (l["x1"] - l["x0"]) <= FULL_WIDTH * width]
    starts = column_starts(rest, width)
    for l in rest:
        i = bisect.bisect_right(starts, l["x0"] + 3) - 1
        l["col"] = max(i, 0)
        l["colx"] = starts[l["col"]]
    fys = [l["y0"] for l in full]
    segs: Dict[int, List[dict]] = collections.defaultdict(list)
    for l in rest:
        segs[bisect.bisect_right(fys, l["y0"])].append(l)
    out: List[dict] = []
    for k in range(len(full) + 1):
        seg = sorted(segs.get(k, []), key=lambda l: (l["col"], round(l["y0"]), l["x0"]))
        out.extend(_merge_same_baseline(seg))
        if k < len(full):
            f = full[k]
            f["col"], f["colx"] = -1, f["x0"]
            out.append(f)
    return out


def _merge_same_baseline(seg: List[dict]) -> List[dict]:
    """PyMuPDF sometimes splits one visual line into pieces; glue pieces sharing a baseline."""
    out: List[dict] = []
    for l in seg:
        p = out[-1] if out else None
        if p and p["col"] == l["col"] and abs(p["y1"] - l["y1"]) < 2 and l["x0"] >= p["x1"] - 1:
            p["text"] = p["text"] + " " + l["text"]
            p["x1"] = l["x1"]
            p["bold"] = p["bold"] and l["bold"]
            p["italic"] = p["italic"] and l["italic"]
            continue
        out.append(dict(l))
    return out


# --- 4/5. styles, paragraphs, kinds ----------------------------------------------------------

def body_style(pages) -> Tuple[float, str]:
    c = collections.Counter()
    for _, _, _, lines in pages:
        for l in lines:
            c[(round(l["size"]), l["font"])] += len(l["text"])
    if not c:
        return 10.0, ""
    (size, font), _ = c.most_common(1)[0]
    sizes = collections.Counter()
    for _, _, _, lines in pages:
        for l in lines:
            if l["font"] == font:
                sizes[l["size"]] += len(l["text"])
    return float(sizes.most_common(1)[0][0]), font


def classify_lines(seq: List[dict], body_size: float, sidebar_res: List[re.Pattern]):
    """Set l['cat'] in heading/sidebar/sidebar_heading/fiction/small/body and l['heading']."""
    for l in seq:
        t = l["text"]
        letters = sum(ch.isalpha() for ch in t)
        side = any(rx.search(l["font"]) for rx in sidebar_res) and l["size"] <= body_size * 1.35
        big = l["size"] >= body_size * 1.15
        headish = (letters >= 2 and len(t) <= 90 and not t.endswith((",", ";"))
                   and not l["runin"] and (big or (l["bold"] and not l["italic"])))
        l["heading"] = bool(headish)
        if side:
            l["cat"] = "sidebar"
        elif headish:
            l["cat"] = "heading"
        elif l["italic"]:
            l["cat"] = "italic"
        elif l["size"] <= body_size * 0.88:
            l["cat"] = "small"
        else:
            l["cat"] = "body"
    # italic runs: >= 4 consecutive italic lines are fiction, shorter runs are body text
    i = 0
    while i < len(seq):
        if seq[i]["cat"] != "italic":
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j]["cat"] == "italic":
            j += 1
        cat = "fiction" if j - i >= 4 else "body"
        for k in range(i, j):
            seq[k]["cat"] = cat
        i = j
    # a bold or big first line that runs on into a lowercase line is a typographic lead-in, not a
    # heading ("The players engage in heated" / "debate for a couple of minutes")
    for i in range(len(seq) - 1, -1, -1):
        l = seq[i]
        if l["cat"] != "heading" or i + 1 >= len(seq):
            continue
        n = seq[i + 1]
        if n["page"] == l["page"] and n.get("col") == l.get("col") and n["cat"] in ("body", "italic", "fiction", "small") \
                and 0 <= n["y0"] - l["y1"] < l["size"] and (n["text"][:1].islower() or l["text"].endswith(("-", ",", "—"))):
            l["cat"] = n["cat"]
            l["heading"] = False
    # a "heading" made of more than 3 consecutive lines is bold body text, not a heading
    i = 0
    while i < len(seq):
        if seq[i]["cat"] != "heading":
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j]["cat"] == "heading" and seq[j]["page"] == seq[i]["page"] \
                and abs(seq[j]["size"] - seq[i]["size"]) < 0.6:
            j += 1
        if j - i > 3:
            for k in range(i, j):
                seq[k]["cat"] = "body"
                seq[k]["heading"] = False
        i = j


def _ends_sentence(t: str) -> bool:
    return t.rstrip().endswith(_TERMINAL)


def build_paragraphs(seq: List[dict], forced: set, vocab: HyphenVocab, col_width: Dict[Tuple[int, int], float]):
    """Group ordered lines into paragraphs. forced: indexes where a new paragraph must start."""
    paras: List[dict] = []
    cur: Optional[dict] = None

    def flush():
        nonlocal cur
        if cur:
            cur["text"] = join_lines(cur.pop("lines"), vocab.keep_hyphen).strip()
            if cur["text"]:
                paras.append(cur)
        cur = None

    for i, l in enumerate(seq):
        brk = cur is None or i in forced
        if not brk:
            p = cur["last"]
            cat_p = "sidebar" if cur["cat"] in ("sidebar", "sidebar_heading") else cur["cat"]
            cat_l = "sidebar" if l["cat"] == "sidebar" else l["cat"]
            same_flow = p["page"] == l["page"] and p.get("col") == l.get("col")
            if cur["cat"] == "heading":
                # only a multi-line heading continues
                brk = not (l["cat"] == "heading" and same_flow and abs(p["size"] - l["size"]) < 0.6
                           and l["y0"] - p["y1"] < p["size"])
            elif cat_p != cat_l:
                brk = True
            elif cur.get("headline") and len(cur["lines"]) == 1:
                brk = bool(l["heading"])   # a sidebar's title line stays the first line of its text
            elif l["runin"]:
                brk = True
            elif cat_l == "sidebar" and l["heading"]:
                brk = True
            elif same_flow and l["y0"] - p["y1"] > 0.8 * p["size"]:
                brk = True
            elif _ends_sentence(p["text"]) and l["x0"] > l.get("colx", l["x0"]) + 6 and l.get("col", 0) >= 0:
                brk = True
            elif same_flow and _ends_sentence(p["text"]):
                w = col_width.get((p["page"], p.get("col", 0)))
                if w and p["x1"] < p.get("colx", p["x0"]) + 0.75 * w:
                    brk = True
        if brk:
            flush()
            cat = l["cat"]
            headline = False
            if cat == "sidebar" and l["heading"]:
                headline = True
            cur = dict(cat=cat, lines=[], page=l["page"], idx=i, runin=l["runin"], headline=headline,
                       size=l["size"])
        cur["lines"].append(l["text"])
        cur["last"] = l
    flush()
    for p in paras:
        p.pop("last", None)
    return paras


# --- 6. sections -----------------------------------------------------------------------------

def _apply_fixes(t: str, fixes: Optional[Dict[str, str]]) -> str:
    for a, b in (fixes or {}).items():
        t = re.sub(r"\b%s\b" % re.escape(a), b, t)
    return t


def normalise_title(t: str, fixes: Dict[str, str]) -> str:
    t = clean_line(t.replace("\r", " ").replace("\n", " "))
    t = re.sub(r"\s*(\.{2,}|\u2026)\s*\d*$", "", t)        # dot leaders
    return _fix_case(_apply_fixes(t, fixes)).strip(" :")


_SMALL_WORDS = {"a", "an", "the", "of", "and", "or", "in", "on", "to", "for", "at", "by", "with", "vs"}


def _fix_case(t: str) -> str:
    """ALL CAPS and small-caps (all lowercase) headings -> title case."""
    if (t.isupper() and len(t) > 3) or (t.islower() and len(t) > 2):
        words = t.lower().split(" ")
        t = " ".join(w if (i and w in _SMALL_WORDS) else w[:1].upper() + w[1:] for i, w in enumerate(words))
    return t


def _common_prefix(titles: List[str]) -> str:
    if len(titles) < 3:
        return ""
    pre = titles[0]
    for t in titles[1:]:
        while not t.startswith(pre):
            pre = pre[:-1]
            if not pre:
                return ""
    k = pre.rfind(" - ")
    return pre[:k + 3] if k > 0 else ""


def toc_entries(doc, book: Dict[str, Any], used: set) -> List[Tuple[int, str, int]]:
    if book.get("use_toc") is False:
        return []
    raw = [(lvl, title, page) for lvl, title, page in doc.get_toc(simple=True)]
    raw = [(lvl, normalise_title(t, book.get("toc_fixes") or {}), p) for lvl, t, p in raw]
    raw = [(lvl, t, p) for lvl, t, p in raw if p >= 1 and t]
    pre = book.get("toc_strip_prefix") or _common_prefix([t for _, t, _ in raw])
    if pre:
        raw = [(lvl, t[len(pre):] if t.startswith(pre) else t, p) for lvl, t, p in raw]
    raw = [(l, t, p) for l, t, p in raw if p in used or any(q in used for q in range(p, p + 3))]
    while raw:
        top = min(l for l, _, _ in raw)
        raw = [(l - top + 1, t, p) for l, t, p in raw]
        roots = [i for i, (l, _, _) in enumerate(raw) if l == 1]
        if len(roots) == 1 and roots[0] == 0 and len(raw) > 1:
            raw = raw[1:]   # one root wrapping the whole book ("... (Cover)"): drop it
            continue
        break
    return raw


def place_sections(entries, seq: List[dict], fixes: Optional[Dict[str, str]] = None) -> List[int]:
    """Position (line index) of each outline entry: the heading line matching its title on its page
    (or the next one), else the first line of that page. Positions never go backwards."""
    first_on_page: Dict[int, int] = {}
    by_page: Dict[int, List[int]] = collections.defaultdict(list)
    for i, l in enumerate(seq):
        first_on_page.setdefault(l["page"], i)
        by_page[l["page"]].append(i)
    pages_sorted = sorted(first_on_page)
    pos, last = [], 0
    for lvl, title, page in entries:
        t = norm_key(title)
        found = None
        cands = [i for p in (page, page + 1) for i in by_page.get(p, []) if i >= last]
        for heading_only in (True, False):
            for i in cands:
                if heading_only and not seq[i]["heading"]:
                    continue
                n = norm_key(_apply_fixes(seq[i]["text"], fixes))
                if n and (n == t or (len(n) >= 4 and t.startswith(n)) or (len(t) >= 4 and n.startswith(t))):
                    found = i
                    break
            if found is not None:
                break
        if found is None:
            k = bisect.bisect_left(pages_sorted, page)
            found = first_on_page[pages_sorted[k]] if k < len(pages_sorted) else len(seq)
            found = max(found, last)
        pos.append(found)
        last = found
    return pos


def heading_entries_by_size(seq: List[dict], body_size: float) -> Tuple[List[Tuple[int, str, int]], List[int]]:
    """Fallback outline for books without one: big non-italic heading lines, up to 3 size levels."""
    cands: List[Tuple[float, str, int]] = []   # (size, text, line index)
    i = 0
    while i < len(seq):
        l = seq[i]
        if l["size"] >= body_size * 1.25 and not l["italic"] and sum(c.isalpha() for c in l["text"]) >= 3 \
                and len(l["text"]) <= 80 and not l["text"].endswith((".", ",", "!", "?", "”", "\"")):
            j, text = i + 1, l["text"]
            while j < len(seq) and seq[j]["page"] == l["page"] and abs(seq[j]["size"] - l["size"]) < 0.6 \
                    and len(text) < 120 and not seq[j]["italic"]:
                text += " " + seq[j]["text"]
                j += 1
            cands.append((round(l["size"]), text, i))
            i = j
            continue
        i += 1
    sizes = collections.Counter(s for s, _, _ in cands)
    common = sorted([s for s, c in sizes.items() if c >= 2], reverse=True)[:3]
    entries, pos = [], []
    for s, text, idx in cands:
        lvl = common.index(s) + 1 if s in common else (1 if not common or s > common[0] else None)
        if lvl is None:
            continue
        entries.append((lvl, normalise_title(text, {}), seq[idx]["page"]))
        pos.append(idx)
    return entries, pos


# --- 7. page numbers -------------------------------------------------------------------------

def printed_pages(doc, used: List[int], numbers: Dict[int, int], book: Dict[str, Any], warnings: List[str]):
    """{pdf page: printed page}. Labels, else manifest page_offset, else detected footer offset."""
    deltas = collections.Counter(n - p for p, n in numbers.items())
    detected = None
    if deltas:
        d, c = deltas.most_common(1)[0]
        if c >= 5 and c >= 0.3 * len(numbers):
            detected = d
    out: Dict[int, int] = {}
    if book.get("page_offset") is not None:
        return {p: p + book["page_offset"] for p in used}, "manifest offset %+d" % book["page_offset"]
    labels = doc.get_page_labels() if hasattr(doc, "get_page_labels") else []
    if labels:
        agree = total = 0
        for p in used:
            v = label_to_int(doc[p - 1].get_label())
            if v is not None:
                out[p] = v
                if p in numbers:
                    total += 1
                    agree += numbers[p] == v
        if total >= 5 and agree < 0.5 * total and detected is not None:
            warnings.append(f"page labels disagree with printed page numbers ({agree}/{total}); using footer offset {detected:+d}")
            out = {}
        else:
            for p in used:
                if p not in out:
                    out[p] = p + detected if detected is not None else 0
            return out, "page labels"
    if detected is not None:
        return {p: p + detected for p in used}, "footer offset %+d" % detected
    warnings.append("no page labels and no printed page numbers found: page = PDF page")
    return {p: p for p in used}, "pdf page"


# --- main ------------------------------------------------------------------------------------

def text_layer_stats(doc) -> Dict[str, Any]:
    counts = [len(doc[i].get_text("text").strip()) for i in range(doc.page_count)]
    s = sorted(counts)
    return {"pages": doc.page_count, "median_chars": s[len(s) // 2] if s else 0,
            "text_pages": sum(c >= IMAGE_ONLY_CHARS for c in counts)}


def extract_book(pdf_path: str, book: Dict[str, Any]) -> Dict[str, Any]:
    import pymupdf  # imported here so the manifest/chunker work without PyMuPDF

    doc = pymupdf.open(pdf_path)
    warnings: List[str] = []
    layer = text_layer_stats(doc)
    result: Dict[str, Any] = {"book_id": book["book_id"], "extractor_version": EXTRACTOR_VERSION,
                              "text_layer": layer, "warnings": warnings}
    if layer["median_chars"] < IMAGE_ONLY_CHARS:
        result["status"] = "image-only"
        warnings.append(f"image-only: median {layer['median_chars']} chars/page (needs OCR)")
        return result
    used = page_list(book, doc.page_count)
    raw = []
    for p in used:
        page = doc[p - 1]
        raw.append((p, page.rect.height, page.rect.width, read_page_lines(page, p)))
    running = find_running_lines([(p, h, ls) for p, h, _, ls in raw])
    strip_res = [re.compile(rx) for rx in book.get("strip_lines") or []]
    pages, numbers = strip_running(raw, running, strip_res)
    body_size, body_font = body_style(pages)
    side_src = book.get("sidebar_fonts")
    if side_src is None:
        side_src = V5_SIDEBAR_FONTS if book["edition"] == "v5" else []
    sidebar_res = [re.compile(rx) for rx in side_src]
    if any(rx.search(body_font) for rx in sidebar_res):
        sidebar_res = []   # the body font itself: nothing is a sidebar
        warnings.append("sidebar font is the body font; sidebar detection off")

    seq: List[dict] = []
    col_width: Dict[Tuple[int, int], float] = {}
    vocab = HyphenVocab()
    for p, h, w, lines in pages:
        ordered = order_page(lines, w)
        for l in ordered:
            key = (p, l.get("col", 0))
            col_width[key] = max(col_width.get(key, 0.0), l["x1"] - l.get("colx", l["x0"]))
            vocab.add(l["text"])
        seq.extend(ordered)
    classify_lines(seq, body_size, sidebar_res)

    entries = toc_entries(doc, book, set(used))
    outline = "pdf outline"
    if entries:
        pos = place_sections(entries, seq, book.get("toc_fixes"))
    else:
        entries, pos = heading_entries_by_size(seq, body_size)
        outline = "font sizes" if entries else "none"
    paras = build_paragraphs(seq, set(pos), vocab, col_width)
    page_map, page_src = printed_pages(doc, used, numbers, book, warnings)

    # sections: path per outline entry, page range for eval
    sections, stack = [], []
    for k, ((lvl, title, page), at) in enumerate(zip(entries, pos)):
        stack = [s for s in stack if s[0] < lvl] + [(lvl, title)]
        sections.append({"id": k, "level": lvl, "title": title, "path": [t for _, t in stack],
                         "pos": at, "page_pdf": seq[at]["page"] if at < len(seq) else page})
    first_line: Dict[int, int] = {}
    for i, l in enumerate(seq):
        first_line.setdefault(l["page"], i)
    for k, s in enumerate(sections):
        end = used[-1] if used else doc.page_count
        for t in sections[k + 1:]:
            if t["level"] <= s["level"]:
                # the next section starting at the top of its page ends this one a page earlier
                top = t["pos"] < len(seq) and first_line.get(t["page_pdf"]) == t["pos"]
                end = max(s["page_pdf"], t["page_pdf"] - (1 if top else 0))
                break
        s["page_end_pdf"] = end
        s["leaf"] = not (k + 1 < len(sections) and sections[k + 1]["level"] > s["level"])
    starts = [s["pos"] for s in sections]
    skip_res = [re.compile(rx, re.I) for rx in (book.get("skip_sections") or DEFAULT_SKIP_SECTIONS)]

    blocks = []
    for para in paras:
        k = bisect.bisect_right(starts, para["idx"]) - 1
        sec = sections[k] if k >= 0 else None
        if sec and any(rx.search(t) for rx in skip_res for t in sec["path"]):
            continue
        cat = para["cat"]
        text = para["text"]
        if cat == "heading":
            kind = "heading"
        elif cat in ("sidebar", "sidebar_heading"):
            kind = "sidebar"
        elif cat == "fiction":
            kind = "fiction"
        elif _EXAMPLE.match(text) or (para.get("runin") or "").upper().startswith("EXAMPLE"):
            kind = "example"
        else:
            kind = "body"
        blocks.append({"section": sec["id"] if sec else -1, "page_pdf": para["page"],
                       "page": page_map.get(para["page"], para["page"]), "kind": kind,
                       "text": text, "runin": para.get("runin"), "headline": bool(para.get("headline")),
                       "small": cat == "small"})
    for i, b in enumerate(blocks):
        # a title line in the sidebar font followed by main text is a main-text sub-heading
        # (V5 Discipline power names are set in Gill Sans small caps)
        if b["kind"] == "sidebar" and b["headline"] and len(b["text"]) <= 90 \
                and not b["text"].endswith((".", ",", ";")):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt is not None and nxt["kind"] in ("body", "example", "fiction") and nxt["section"] == b["section"]:
                b["kind"] = "heading"
    _mark_examples(blocks)
    for b in blocks:
        if b["kind"] == "heading":
            b["text"] = _fix_case(_apply_fixes(b["text"], book.get("toc_fixes")))
    result.update({
        "status": "ok", "pages_used": len(used), "page_range": [used[0], used[-1]] if used else [],
        "body_size": body_size, "body_font": body_font, "outline": outline, "page_numbers": page_src,
        "sections": [{k: v for k, v in s.items() if k != "pos"} for s in sections],
        "blocks": blocks,
    })
    if not entries:
        warnings.append("no outline and no size-based headings: heading_path empty")
    return result


def _mark_examples(blocks: List[dict]):
    """An 'EXAMPLE:' label on its own line makes the next paragraph an example; small-print
    paragraphs right after an example paragraph belong to it."""
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["kind"] == "heading" and re.fullmatch(r"EXAMPLES?\s*:?", b["text"].strip(), re.I):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt is not None and nxt["kind"] != "heading" and nxt["section"] == b["section"]:
                nxt["kind"] = "example"
                nxt["text"] = b["text"].strip() + " " + nxt["text"]
                del blocks[i]
                continue
        i += 1
    prev = None
    for b in blocks:
        if b["kind"] == "body" and b.get("small") and prev is not None and prev["kind"] == "example" \
                and prev["section"] == b["section"]:
            b["kind"] = "example"
        prev = b
