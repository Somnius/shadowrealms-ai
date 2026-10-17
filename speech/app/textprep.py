"""Turn chat text into something a TTS voice can read."""
import re

_MD = [
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),       # images
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),        # links
    (re.compile(r"```.*?```", re.S), " "),                 # code blocks
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),         # headings
    (re.compile(r"^\s*>\s?", re.M), ""),                  # quotes
    (re.compile(r"^\s*[-*+]\s+", re.M), ""),              # bullets
    (re.compile(r"(\*\*|__)(.+?)\1", re.S), r"\2"),
    (re.compile(r"(?<!\w)[*_](.+?)[*_](?!\w)", re.S), r"\1"),
    (re.compile(r"~~(.+?)~~", re.S), r"\1"),
    (re.compile(r"https?://\S+"), ""),
]

_EL_UNITS = ["μηδέν", "ένα", "δύο", "τρία", "τέσσερα", "πέντε", "έξι", "επτά", "οκτώ", "εννέα",
             "δέκα", "έντεκα", "δώδεκα"]
_EL_TENS = {10: "δέκα", 20: "είκοσι", 30: "τριάντα", 40: "σαράντα", 50: "πενήντα",
            60: "εξήντα", 70: "εβδομήντα", 80: "ογδόντα", 90: "ενενήντα"}
_EL_HUNDREDS = {100: "εκατό", 200: "διακόσια", 300: "τριακόσια", 400: "τετρακόσια",
                500: "πεντακόσια", 600: "εξακόσια", 700: "επτακόσια", 800: "οκτακόσια",
                900: "εννιακόσια"}


def greek_number(n: int) -> str:
    """0..9999 as Greek words (neuter). Larger numbers stay as digits."""
    if n < 0 or n > 9999:
        return str(n)
    if n <= 12:
        return _EL_UNITS[n]
    if n < 20:
        return "δεκα" + _EL_UNITS[n - 10]
    if n < 100:
        t, u = divmod(n, 10)
        return _EL_TENS[t * 10] + ("" if u == 0 else " " + _EL_UNITS[u])
    if n < 1000:
        h, r = divmod(n, 100)
        head = "εκατόν" if h == 1 and r else _EL_HUNDREDS[h * 100]
        return head + ("" if r == 0 else " " + greek_number(r))
    th, r = divmod(n, 1000)
    head = "χίλια" if th == 1 else greek_number(th) + " χιλιάδες"
    return head + ("" if r == 0 else " " + greek_number(r))


_GREEK_WORD = re.compile(r"[Ͱ-Ͽἀ-῿]+")
_EL_VOWELS = set("αεηιουω")
_EL_FRONT = set("εηιυ")
_EL_VOICELESS = set("θκξπσςτφχψ")
_EL_SIMPLE = {"α": "a", "β": "v", "δ": "d", "ζ": "z", "θ": "th", "κ": "k", "λ": "l", "μ": "m",
              "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t",
              "φ": "f", "χ": "h", "ψ": "ps", "ω": "o"}


def _greek_letters(word):
    """[(base letter, stressed, diaeresis)] for a lower-cased Greek word."""
    import unicodedata
    out = []
    for ch in unicodedata.normalize("NFD", word.lower()):
        if unicodedata.combining(ch):
            if out:
                b, s, d = out[-1]
                out[-1] = (b, s or ch in "́͂", d or ch == "̈")
            continue
        out.append((ch, False, False))
    return out


def greek_to_english_sound(word: str) -> str:
    """Spell a Greek word so an English voice says it the Greek way (Κατακουζηνός → Katakoozeenos)."""
    L = _greek_letters(word)
    n = len(L)
    out = []

    def at(i):
        return L[i][0] if i < n else ""

    def front_next(i):  # the sound at i is e/i (γ before it is a "y")
        c, d = at(i), at(i + 1)
        if c in ("α", "ο") and d == "ι" and not L[i + 1][2]:
            return True
        return c in _EL_FRONT or (c == "ε" and d == "ι")

    i = 0
    while i < n:
        c, stressed, _ = L[i]
        nx = at(i + 1)
        nx_dia = L[i + 1][2] if i + 1 < n else False
        start = i == 0
        if c in "αεη" and nx == "υ" and not nx_dia:  # αυ/ευ/ηυ: v, or f before a voiceless sound
            after = at(i + 2)
            out.append({"α": "a", "ε": "e", "η": "ee"}[c] + ("f" if not after or after in _EL_VOICELESS else "v"))
            i += 2
            continue
        if c == "ο" and nx == "υ" and not nx_dia:
            out.append("oo")
            i += 2
            continue
        if c == "α" and nx == "ι" and not nx_dia:
            out.append("e")
            i += 2
            continue
        if (c in "εου" and nx == "ι" and not nx_dia) or c in "ιηυ":
            step = 2 if c in "εου" and nx == "ι" and not nx_dia else 1  # ει/οι/υι, or ι/η/υ
            stressed_i = L[i + step - 1][1] or stressed
            nxt = at(i + step)
            if not stressed_i and nxt in _EL_VOWELS:
                if not (out and out[-1].endswith("y")):
                    out.append("y")
            else:
                out.append("ee")
            i += step
            continue
        if c == "μ" and nx == "π":
            out.append("b" if start else "mb")
            i += 2
            continue
        if c == "ν" and nx == "τ":
            out.append("d" if start else "nd")
            i += 2
            continue
        if c == "γ" and nx == "κ":
            out.append("g" if start else "ng")
            i += 2
            continue
        if c == "γ" and nx in ("γ", "χ", "ξ"):
            out.append({"γ": "ng", "χ": "nh", "ξ": "nx"}[nx])
            i += 2
            continue
        if c == "τ" and nx in ("σ", "ζ"):
            out.append("ts" if nx == "σ" else "dz")
            i += 2
            continue
        if c == "γ":
            out.append("y" if front_next(i + 1) else "g")
        elif c == "ε":
            out.append("eh" if i == n - 1 else "e")
        else:
            out.append(_EL_SIMPLE.get(c, ""))
        i += 1
    s = "".join(out)
    return s[:1].upper() + s[1:] if word[:1].isupper() else s


def greek_words_for_english(text: str) -> str:
    """An English voice spells Greek letters one by one; give it the Greek words as sounds."""
    return _GREEK_WORD.sub(lambda m: greek_to_english_sound(m.group()), text)


def strip_markdown(text: str) -> str:
    for pat, rep in _MD:
        text = pat.sub(rep, text)
    return text


def normalise(text: str, lang: str) -> str:
    text = strip_markdown(text or "")
    text = text.replace(" ", " ")
    if lang == "el":
        text = re.sub(r"\d+", lambda m: greek_number(int(m.group())), text)
        text = text.replace("?", ";")
    else:
        text = greek_words_for_english(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


_SENT_END = re.compile(r"(?<=[.!?;…·])\s+|\n+")


def split_parts(text: str, max_chars: int = 1200) -> list:
    """Split at sentence ends into parts of at most max_chars (long sentences cut at spaces)."""
    parts, cur = [], ""
    for sent in (s.strip() for s in _SENT_END.split(text)):
        if not sent:
            continue
        while len(sent) > max_chars:
            cut = sent.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if cur and len(cur) + 1 + len(sent) > max_chars:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return parts
