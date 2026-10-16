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
