"""Voice catalog and the (lang, accent, gender, role) -> voice mapping.

Picks follow the Phase 0 measurements: Piper for English, Pocket TTS Greek for Greek,
Piper rapunzelina as the instant Greek fallback when Pocket TTS cannot load.
"""

VOICES = {
    # id: engine, model, lang, accent, gender, licence
    "en_US-lessac-medium": dict(engine="piper", lang="en", accent="us", gender="female", licence="Blizzard 2013 (see model card)"),
    "en_US-ryan-high": dict(engine="piper", lang="en", accent="us", gender="male", licence="CC BY-NC-SA 4.0"),
    "en_GB-alan-medium": dict(engine="piper", lang="en", accent="gb", gender="male", licence="see model card"),
    "en_GB-jenny_dioco-medium": dict(engine="piper", lang="en", accent="gb", gender="female", licence="see model card"),
    "en_GB-cori-high": dict(engine="piper", lang="en", accent="gb", gender="female", licence="public domain"),
    "el_GR-rapunzelina-medium": dict(engine="piper", lang="el", accent="gr", gender="female", licence="CC0"),
    "el-kostas": dict(engine="pocket", lang="el", accent="gr", gender="male", licence="CC BY 4.0 (myned-ai/pocket-tts-greek)"),
    "el-spyros": dict(engine="pocket", lang="el", accent="gr", gender="male", licence="CC BY 4.0 (myned-ai/pocket-tts-greek)"),
    "el-eleni": dict(engine="pocket", lang="el", accent="gr", gender="female", licence="CC BY 4.0 (myned-ai/pocket-tts-greek)"),
    "el-athina": dict(engine="pocket", lang="el", accent="gr", gender="female", licence="CC BY 4.0 (myned-ai/pocket-tts-greek)"),
}

# (lang, accent) -> role -> voice id. "neutral" is used for unset gender and OOC lines.
DEFAULTS = {
    ("en", "us"): {"female": "en_US-lessac-medium", "male": "en_US-ryan-high",
                   "neutral": "en_US-lessac-medium", "narrator": "en_US-ryan-high"},
    ("en", "gb"): {"female": "en_GB-jenny_dioco-medium", "male": "en_GB-alan-medium",
                   "neutral": "en_GB-cori-high", "narrator": "en_GB-alan-medium"},
    ("el", "gr"): {"female": "el-athina", "male": "el-kostas",
                   "neutral": "el-eleni", "narrator": "el-spyros"},
}
DEFAULT_ACCENT = {"en": "us", "el": "gr"}
GREEK_FALLBACK = "el_GR-rapunzelina-medium"
LANGS = ("en", "el")


def resolve(lang: str, voice: str = None, gender: str = None, accent: str = None,
            role: str = None, pocket_ok: bool = True) -> str:
    """Return a voice id. An explicit voice wins if it exists and matches the language."""
    if lang not in LANGS:
        raise ValueError("unsupported_lang")
    if voice:
        meta = VOICES.get(voice)
        if not meta or meta["lang"] != lang:
            raise ValueError("unknown_voice")
        chosen = voice
    else:
        acc = accent if (lang, accent) in DEFAULTS else DEFAULT_ACCENT[lang]
        table = DEFAULTS[(lang, acc)]
        key = role if role == "narrator" else (gender if gender in ("female", "male") else "neutral")
        chosen = table[key]
    if VOICES[chosen]["engine"] == "pocket" and not pocket_ok:
        return GREEK_FALLBACK
    return chosen


def listing():
    out = []
    for vid, m in VOICES.items():
        roles = [r for (lg, ac), t in DEFAULTS.items() for r, v in t.items() if v == vid]
        out.append(dict(id=vid, **m, default_for=sorted(set(roles))))
    return out
