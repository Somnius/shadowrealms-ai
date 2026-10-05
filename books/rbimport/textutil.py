"""Text helpers: line cleaning, dehyphenation, sentence splitting, token counting, hashing.

Curly quotes, apostrophes and dashes are kept as they are; only whitespace, ligatures,
soft hyphens and control characters are normalised.
"""
from __future__ import annotations

import glob
import hashlib
import math
import os
import re
from typing import Callable, Iterable, List, Optional

LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
             "ﬅ": "st", "ﬆ": "st"}
_SPACES = re.compile(r"[ \t  -   　]+")
_LEADER = re.compile(r"(?:[.\u2026\u00b7] ?){4,}|\u2026{2,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​﻿￾]")
HYPHENS = ("-", "­", "‐")


def clean_line(s: str) -> str:
    """Normalise one extracted line (keeps a trailing hyphen / soft hyphen for dehyphenation)."""
    for k, v in LIGATURES.items():
        if k in s:
            s = s.replace(k, v)
    s = _CONTROL.sub("", s)
    s = _LEADER.sub(" \u2026 ", s)   # dot leaders (character sheets, tables of contents)
    s = _SPACES.sub(" ", s)
    return s.strip()


def letterspaced(s: str) -> bool:
    """'C O R E B O O K' style running heads: single characters separated by spaces."""
    parts = s.split(" ")
    return len(parts) >= 4 and sum(len(p) == 1 for p in parts) >= 0.8 * len(parts)


_HYPH_PAIR = re.compile(r"\b([A-Za-z]+)-([A-Za-z]+)\b")
_WORD = re.compile(r"[A-Za-z]+")


class HyphenVocab:
    """Counts, from the book itself, hyphenated compounds written mid-line and plain words, so a
    line-end hyphen is kept for 'blood-bound' style compounds and dropped for split words."""

    def __init__(self):
        self.hyph = {}
        self.words = {}

    def add(self, line: str):
        body = line[:-1] if line.endswith(HYPHENS) else line
        for a, b in _HYPH_PAIR.findall(body):
            k = (a + "-" + b).lower()
            self.hyph[k] = self.hyph.get(k, 0) + 1
        for w in _WORD.findall(body):
            w = w.lower()
            self.words[w] = self.words.get(w, 0) + 1

    def keep_hyphen(self, left: str, right: str) -> bool:
        k = (left + "-" + right).lower()
        return self.hyph.get(k, 0) > self.words.get((left + right).lower(), 0)


def join_lines(lines: Iterable[str], keep_hyphen: Optional[Callable[[str, str], bool]] = None) -> str:
    """Join the lines of one paragraph: dehyphenate line-end hyphens before a lowercase letter,
    glue em/en dashes without a space, otherwise join with one space."""
    out = ""
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
            continue
        m = re.search(r"([A-Za-z]+)[-­‐]$", out)
        if m and ln[:1].islower():
            w2 = re.match(r"[A-Za-z]+", ln)
            right = w2.group(0) if w2 else ""
            if keep_hyphen and right and keep_hyphen(m.group(1), right):
                out = out[:-1] + "-" + ln
            else:
                out = out[:-1] + ln
        elif m and (ln[:1].isupper() or ln[:1].isdigit()):
            out = out[:-1] + "-" + ln          # "Camarilla-" + "Anarch": keep the hyphen, no space
        elif out.endswith(("—", "–")) or ln.startswith(("—",)):
            out = out + ln
        else:
            out = out + " " + ln
    return out.replace("­", "")


ABBREV = {"e.g", "i.e", "etc", "vs", "p", "pp", "dr", "mr", "mrs", "ms", "st", "mt", "no", "vol",
          "ch", "fig", "cf", "approx", "jr", "sr", "ed", "eds", "inc", "ltd", "co", "op", "cit"}
_SENT_END = re.compile(r"([.!?…]+[\"”’')\]]*)(\s+)(?=[\"“‘'(\[]?[A-Z0-9•—])")


def split_sentences(text: str) -> List[str]:
    """Split a paragraph into sentences (abbreviations and initials don't end a sentence)."""
    out, start = [], 0
    for m in _SENT_END.finditer(text):
        end = m.end(1)
        before = text[start:m.start(1) + 1]
        word = re.search(r"([A-Za-z.]+)\.$", before)
        if word:
            w = word.group(1).lower().rstrip(".")
            if w in ABBREV or (len(w) == 1 and m.group(1) == "."):
                continue
        s = text[start:end].strip()
        if s:
            out.append(s)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def find_bge_tokenizer() -> Optional[str]:
    p = os.environ.get("BGE_M3_TOKENIZER")
    if p and os.path.exists(p):
        return p
    hf = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    hits = sorted(glob.glob(os.path.join(hf, "hub", "models--BAAI--bge-m3", "snapshots", "*", "tokenizer.json")))
    return hits[-1] if hits else None


class TokenCounter:
    """bge-m3 tokenizer when `tokenizers` and its tokenizer.json are available, else words x 1.35."""

    def __init__(self, mode: str = "auto"):
        self.name = "estimate"
        self._tok = None
        if mode == "estimate":
            return
        path = mode if mode not in ("auto", "bge-m3") else find_bge_tokenizer()
        if not path:
            if mode == "bge-m3":
                raise RuntimeError("bge-m3 tokenizer.json not found (set BGE_M3_TOKENIZER)")
            return
        try:
            from tokenizers import Tokenizer  # type: ignore
            self._tok = Tokenizer.from_file(path)
            self.name = "bge-m3"
        except Exception:  # noqa: BLE001 - optional dependency
            if mode == "bge-m3":
                raise

    def count(self, text: str) -> int:
        if self._tok is not None:
            return len(self._tok.encode(text, add_special_tokens=False).ids)
        return math.ceil(len(text.split()) * 1.35)


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def norm_key(s: str) -> str:
    """Lowercase letters and digits only (for heading/title matching)."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def roman_to_int(s: str) -> Optional[int]:
    s = s.lower()
    if not s or any(c not in _ROMAN for c in s):
        return None
    total, prev = 0, 0
    for c in reversed(s):
        v = _ROMAN[c]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def label_to_int(label: str) -> Optional[int]:
    label = (label or "").strip()
    if re.fullmatch(r"\d{1,4}", label):
        return int(label)
    return roman_to_int(label) if re.fullmatch(r"[ivxlcdmIVXLCDM]{1,7}", label) else None
