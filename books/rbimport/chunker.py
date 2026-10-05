"""Blocks -> chunks per docs/rules/RULE_BOOKS_RAG.md.

Inside one outline section the blocks are split into streams (main text, examples, sidebars,
fiction) so a sidebar or a fiction box never interrupts a rules sentence. Each stream is cut into
groups at sub-headings (a Discipline power, a sidebar title). A group that fits in the hard max
stays whole (so a power's "Cost: ... Duration:" lines stay together); small neighbouring groups
are packed up to the target; a longer group is packed sentence by sentence up to ~target tokens
with a one-sentence overlap. Chunks never cross a section boundary.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .textutil import TokenCounter, norm_key, sha1, split_sentences

CHUNKER_VERSION = 4
TARGET = 300
MAX_TOKENS = 512
SEP = " › "   # " › "
STREAMS = {"body": "main", "example": "example", "sidebar": "sidebar", "fiction": "fiction"}


def kind_for(stream: str, book_kind: str) -> str:
    if book_kind == "adventure":
        return "adventure"
    return {"main": book_kind, "example": "example", "sidebar": "sidebar", "fiction": "fiction"}[stream]


def _junk(text: str) -> bool:
    """Index pages, number tables, dot leaders: few letters or mostly numeric tokens."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return True
    letters = sum(c.isalpha() for c in chars)
    toks = text.split()
    nums = sum(bool(re.fullmatch(r"[\d,.\-–—/]+", t)) for t in toks)
    return letters < 0.5 * len(chars) or (len(toks) >= 8 and nums > 0.4 * len(toks))


class _Unit:
    __slots__ = ("text", "tokens", "page", "page_pdf", "sub", "order", "seq", "para_start", "group_start", "sticky")

    def __init__(self, text, tokens, page, page_pdf, sub, order, seq=0, para_start=False, group_start=False, sticky=False):
        self.text, self.tokens, self.page, self.page_pdf, self.seq = text, tokens, page, page_pdf, seq
        self.sub, self.order, self.para_start, self.group_start, self.sticky = sub, order, para_start, group_start, sticky


def _split_long(text: str, counter: TokenCounter, limit: int) -> List[str]:
    """A sentence longer than the limit is cut at '; ' or, failing that, by words."""
    parts = [p.strip() for p in re.split(r"(?<=;)\s+", text) if p.strip()]
    out: List[str] = []
    for p in parts:
        if counter.count(p) <= limit:
            out.append(p)
            continue
        words, cur = p.split(), []
        for w in words:
            cur.append(w)
            if counter.count(" ".join(cur)) >= limit:
                out.append(" ".join(cur[:-1]) if len(cur) > 1 else cur[0])
                cur = cur[-1:] if len(cur) > 1 else []
        if cur:
            out.append(" ".join(cur))
    return out


def _units_for_section(blocks: List[dict], section_title: str, counter: TokenCounter, limit: int):
    """Sentence units per stream for one section's blocks (in reading order)."""
    streams: Dict[str, List[_Unit]] = {}
    sub: Optional[str] = None
    pending = {s: False for s in STREAMS.values()}
    title_key = norm_key(section_title)
    for b in blocks:
        if b["kind"] == "heading":
            k = norm_key(b["text"])
            if k and (k == title_key or title_key.startswith(k) or k.startswith(title_key)):
                continue  # the section's own heading
            sub = b["text"].strip()
            for s in pending:
                pending[s] = True
            continue
        stream = STREAMS[b["kind"]]
        if len(b["text"]) >= 20 and _junk(b["text"]):
            continue   # a number table / index / dot-leader paragraph
        sents = split_sentences(b["text"])
        para_tokens = 0
        units: List[_Unit] = []
        for s in sents:
            n = counter.count(s)
            pieces = [s] if n <= limit else _split_long(s, counter, limit)
            for p in pieces:
                t = n if p is s else counter.count(p)
                units.append(_Unit(p, t, b["page"], b["page_pdf"], sub, b["order"], len(units)))
                para_tokens += t
        if not units:
            continue
        units[0].para_start = True
        if pending[stream] or b.get("headline"):
            units[0].group_start = True
            pending[stream] = False
        if b.get("runin") and para_tokens <= 60:
            for u in units:
                u.sticky = True
        streams.setdefault(stream, []).extend(units)
    return streams


def _groups(units: List[_Unit]) -> List[List[_Unit]]:
    out: List[List[_Unit]] = []
    for u in units:
        if not out or u.group_start:
            out.append([])
        out[-1].append(u)
    return out


def _pack(units: List[_Unit], target: int, limit: int) -> List[Tuple[List[_Unit], int]]:
    """Returns [(units, n_overlap)]; n_overlap leading units repeat the previous chunk's last one."""
    chunks: List[Tuple[List[_Unit], int]] = []
    cur: List[_Unit] = []
    cur_tok, n_over = 0, 0

    def close(overlap: bool):
        nonlocal cur, cur_tok, n_over
        if cur and len(cur) > n_over:
            chunks.append((cur, n_over))
        last = cur[-1] if cur else None
        cur, cur_tok, n_over = [], 0, 0
        if overlap and last is not None and last.tokens <= target // 4:
            cur, cur_tok, n_over = [last], last.tokens, 1

    for grp in _groups(units):
        g_tok = sum(u.tokens for u in grp)
        if g_tok <= limit:
            if cur and cur_tok + g_tok > target:
                close(False)
            cur.extend(grp)
            cur_tok += g_tok
            continue
        # long group: sentence packing with a one-sentence overlap
        if cur:
            close(False)
        for u in grp:
            if cur and len(cur) > n_over:
                if cur_tok + u.tokens > limit:
                    close(True)
                elif cur_tok + u.tokens > target and cur_tok >= target // 2 and not u.sticky:
                    close(True)
            cur.append(u)
            cur_tok += u.tokens
        close(False)
    close(False)
    # a tiny tail joins the previous chunk when it fits
    merged: List[Tuple[List[_Unit], int]] = []
    for units_, n_o in chunks:
        new = units_[n_o:]
        tok = sum(u.tokens for u in new)
        if merged and tok < target // 4 and not new[0].group_start:
            prev, pn = merged[-1]
            if sum(u.tokens for u in prev) + tok <= limit:
                merged[-1] = (prev + new, pn)
                continue
        merged.append((units_, n_o))
    return merged


def _fit(units: List[_Unit], n_o: int, header, counter: TokenCounter, max_tokens: int):
    """Guarantee the hard max on the whole document (sentence token sums can undercount).
    header(unit) -> the document header for a chunk starting with that unit."""
    new = units[n_o:]
    if len(new) < 2 or counter.count(header(new[0]) + _join(units)) <= max_tokens:
        return [(units, n_o)]
    half = len(new) // 2
    return _fit(units[:n_o] + new[:half], n_o, header, counter, max_tokens) + \
        _fit(new[half:], 0, header, counter, max_tokens)


def _join(units: Iterable[_Unit]) -> str:
    out = ""
    for u in units:
        if not out:
            out = u.text
        else:
            out += ("\n" if u.para_start else " ") + u.text
    return out


def _heading_path(hp_base: str, sub: Optional[str]) -> str:
    if sub and norm_key(sub) != (norm_key(hp_base.split(SEP)[-1]) if hp_base else ""):
        return f"{hp_base}{SEP}{sub}" if hp_base else sub
    return hp_base


def chunk_book(ext: Dict[str, Any], book: Dict[str, Any], counter: TokenCounter,
               target: int = TARGET, max_tokens: int = MAX_TOKENS,
               seen: Optional[Dict[str, str]] = None, campaign_id: int = 0) -> Dict[str, Any]:
    """Chunks for one extracted book. seen: content_sha -> book_id of higher-precedence books
    (chunks found there are skipped as duplicates)."""
    title = book["title"]
    sections = {s["id"]: s for s in ext.get("sections", [])}
    by_sec: Dict[int, List[dict]] = {}
    for i, b in enumerate(ext.get("blocks", [])):
        b = dict(b, order=i)
        by_sec.setdefault(b["section"], []).append(b)
    raw: List[tuple] = []
    for sid, blocks in by_sec.items():
        sec = sections.get(sid)
        path = list(sec["path"]) if sec else []
        hp_base = SEP.join(path)
        header_tok = counter.count(f"{title}{SEP}{hp_base}") + 4
        limit = max(64, max_tokens - header_tok - 16)
        streams = _units_for_section(blocks, path[-1] if path else "", counter, limit)
        def header(u, hp_base=hp_base):
            return f"{title}{SEP}{_heading_path(hp_base, u.sub)}\n\n"
        for stream, units in streams.items():
            for packed, n_o in _pack(units, target, limit):
                for units_, n_o2 in _fit(packed, n_o, header, counter, max_tokens):
                    new = units_[n_o2:]
                    raw.append(((new[0].order, new[0].seq), stream, hp_base, units_, new[0]))
    raw.sort(key=lambda r: r[0])

    chunks, stats = [], {"dropped_junk": 0, "dropped_dup": 0, "dup_of": {}}
    seen = seen if seen is not None else {}
    own: Set[str] = set()
    for idx, (_, stream, hp_base, units_, first) in enumerate(raw):
        text = _join(units_)
        hp = _heading_path(hp_base, first.sub)
        if _junk(text):
            stats["dropped_junk"] += 1
            continue
        csha = sha1(text)
        if csha in own or (csha in seen and seen[csha] != book["book_id"]):
            stats["dropped_dup"] += 1
            if csha in seen and seen[csha] != book["book_id"]:
                stats["dup_of"][seen[csha]] = stats["dup_of"].get(seen[csha], 0) + 1
            continue
        own.add(csha)
        doc = f"{title}{SEP}{hp}\n\n{text}" if hp else f"{title}\n\n{text}"
        meta = {
            "book_id": book["book_id"], "title": title, "edition": book["edition"], "line": book["line"],
            "version": book["version"], "kind": kind_for(stream, book["kind"]), "heading_path": hp,
            "page": int(first.page), "page_pdf": int(first.page_pdf), "chunk_index": idx,
            "precedence": int(book["precedence"]), "official": bool(book.get("official", True)),
            "year": int(book["year"]), "campaign_id": int(campaign_id), "content_sha": csha,
        }
        chunks.append({"id": chunk_id(book["book_id"], idx, campaign_id), "document": doc, "metadata": meta,
                       "tokens": counter.count(doc)})
    stats["chunks"] = len(chunks)
    return {"chunks": chunks, "stats": stats}


def chunk_id(book_id: str, idx: int, campaign_id: int = 0) -> str:
    """Contract id; in rule_books_chronicle prefixed with the chronicle (one adventure can be
    attached to several chronicles)."""
    base = f"{book_id}:{idx:05d}"
    return f"c{campaign_id}:{base}" if campaign_id else base
