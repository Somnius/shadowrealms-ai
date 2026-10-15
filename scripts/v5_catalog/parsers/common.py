"""Small helpers shared by the parsers: names, ids, labels, dots, heading detection."""

from __future__ import annotations

import re
import unicodedata

DISCIPLINES = (
    "Animalism", "Auspex", "Blood Sorcery", "Celerity", "Dominate", "Fortitude",
    "Obfuscate", "Oblivion", "Potence", "Presence", "Protean", "Thin-Blood Alchemy",
)
DISCIPLINE_BY_KEY = {d.lower(): d for d in DISCIPLINES}

_SMALL = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of", "on",
          "or", "the", "to", "with", "against", "over", "upon"}
_DOTS = "•●"  # • and ●


def norm_space(s: str) -> str:
    s = s.replace(" ", " ")
    # "cat ’ s grace" -> "cat's grace", "GORGON’S" -> "GORGON'S" (case kept: titles are all one case)
    s = re.sub(r"\s*[’']\s*([sS])\b", r"'\1", s)
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"\s+-$", "-", s)


def join_wrapped(prev: str | None, nxt: str) -> str:
    """Join a wrapped line, undoing end-of-line hyphenation ('Animal-' + 'ism')."""
    prev = (prev or "").rstrip()
    nxt = nxt.strip()
    if prev.endswith("-") and nxt[:1].islower():
        return prev[:-1] + nxt
    return f"{prev} {nxt}".strip()


def strip_bullet(s: str) -> str:
    """Drop list markers: '■ ■', '■', '•' at the start of a line, and the private-use glyph."""
    s = s.replace("", "").replace("", "")
    return re.sub(r"^(?:[■▪]\s*)+", "", s.strip()).strip()


def title_case(s: str) -> str:
    """'a taste for blood' / 'A TASTE FOR BLOOD' -> 'A Taste for Blood'."""
    words = norm_space(s).lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if i and w in _SMALL:
            out.append(w)
            continue
        out.append("-".join(p[:1].upper() + p[1:] for p in w.split("-")))
    return " ".join(out)


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", norm_space(s)).encode("ascii", "ignore").decode()
    s = s.lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def discipline_id(name: str) -> str:
    return f"discipline:{slug(name)}"


def power_id(discipline: str, name: str) -> str:
    return f"power:{slug(discipline)}:{slug(name)}"


def count_dots(s: str) -> int:
    return sum(1 for ch in s if ch in _DOTS)


WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "a": 1, "an": 1}


def word_number(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return WORDS.get(s)


LABELS = (
    "Amalgam", "Prerequisite Power", "Prerequisite", "Prerequisites", "Activation Cost", "Cost",
    "Dice Pools", "Dice Pool", "System", "Duration", "Ingredients", "Process", "Type",
    "Masquerade threat", "Blood Resonance", "Opposing Pool",
)
_LABEL_RE = re.compile(r"^(" + "|".join(re.escape(x) for x in LABELS) + r")\s*:\s*(.*)$", re.I)


def label(s: str) -> tuple[str, str] | None:
    """'■ ■ Cost: One Rouse Check' -> ('cost', 'One Rouse Check')."""
    m = _LABEL_RE.match(strip_bullet(s))
    if not m:
        return None
    key = m.group(1).lower()
    key = {"prerequisite power": "prerequisite", "prerequisites": "prerequisite",
           "activation cost": "cost", "dice pools": "dice_pool", "dice pool": "dice_pool"}.get(key, key)
    return key.replace(" ", "_"), m.group(2).strip()


_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z' .,&\-]*[A-Za-z]-?$")


def looks_like_name(text: str) -> bool:
    """A power/ritual title line: letters and a few marks, all upper or all lower case."""
    t = norm_space(strip_bullet(text))
    if not (2 <= len(t) <= 48) or ":" in t or not _NAME_RE.match(t):
        return False
    letters = [c for c in t if c.isalpha()]
    return all(c.isupper() for c in letters) or all(c.islower() for c in letters)


def rouse_cost(text: str | None) -> tuple[int | None, bool]:
    """-> (base Rouse Checks, conditional).

    'One Rouse Check' -> (1, False); 'Free' / 'No additional cost' -> (0, False);
    'One Rouse Check per turn', 'One or more Rouse Checks', 'One to three Rouse Checks',
    'One additional Rouse Check' -> (1, True): the printed minimum, with more in the text.
    Real alternatives ('Free or one Rouse Check', 'One or Three Rouse Checks') and anything
    else -> (None, False).
    """
    if not text:
        return None, False
    t = norm_space(text).strip()
    t = re.sub(r"(?i)rouse\.\s*check", "Rouse Check", t)  # 'One Rouse. Check.' misprint
    n = r"(one|two|three|four|1|2|3|4)"
    m = re.match(rf"(?i){n}\s+(?:or more|to {n}|additional)\s+rouse checks?\b", t)
    if m:
        return word_number(m.group(1)), True
    m = re.match(rf"(?i)(free|none|no additional cost|no cost|{n} rouse checks?)\b(.*)$", t)
    if not m:
        return None, False
    rest = m.group(3).strip(" .;,")
    if re.match(r"(?i)or\b", rest):
        return None, False
    base = word_number(m.group(2)) if m.group(2) else 0
    return base, bool(rest)


_POOL_WORD = (r"(?:Strength|Dexterity|Stamina|Charisma|Manipulation|Composure|Intelligence|Wits|"
              r"Resolve|[A-Z][a-z]+(?: [A-Z][a-z]+)?)")
_POOL_RE = re.compile(
    r"^" + _POOL_WORD + r"(?: ?(?:\+|or|/|vs\.?) ?" + _POOL_WORD + r")*$")


def dice_pool(text: str | None) -> str | None:
    """Keep a pool only when it is a plain list of trait names ('Wits + Auspex vs Resolve').

    A trailing parenthetical note ('(if resisted)') is dropped; several pools separated by
    commas are kept as printed ('Manipulation + Animalism, Charisma + Animalism').
    """
    if not text:
        return None
    t = norm_space(text).rstrip(".").strip()
    t = re.sub(r"\s*\([^()]*\)\.?$", "", t).strip()
    t = re.sub(r"\s*\+\s*", " + ", t)
    t = re.sub(r"\bvs\.?\s", "vs ", t)
    parts = [x.strip() for x in t.split(",")]
    if len(t) > 90 or not all(_POOL_RE.match(x) and "+" in x for x in parts):
        return None
    return ", ".join(parts)
