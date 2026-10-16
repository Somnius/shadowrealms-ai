"""Checks on uploads and ffprobe output. Pure functions, no I/O."""

ALLOWED_CODECS = {"opus", "aac", "mp3", "vorbis", "pcm_s16le", "pcm_f32le", "flac"}
ALLOWED_FORMATS = {"ogg", "matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2", "mp3", "wav", "flac", "aac"}
STT_LANGS = ("el", "en")


class Refused(Exception):
    def __init__(self, code, detail=""):
        super().__init__(code)
        self.code, self.detail = code, detail


def check_text(text: str, max_chars: int):
    if not text or not text.strip():
        raise Refused("empty_text")
    if len(text) > max_chars:
        raise Refused("text_too_long", f"max {max_chars} chars")


def check_lang(lang: str):
    if lang not in STT_LANGS:
        raise Refused("unsupported_lang", "el or en")


def check_size(nbytes: int, max_bytes: int):
    if nbytes <= 0:
        raise Refused("empty_upload")
    if nbytes > max_bytes:
        raise Refused("too_large", f"max {max_bytes} bytes")


def check_probe(probe: dict, max_seconds: int) -> float:
    """probe is ffprobe -show_format -show_streams JSON. Returns the duration in seconds, or None when the container does not say."""
    fmt = (probe or {}).get("format") or {}
    if fmt.get("format_name") not in ALLOWED_FORMATS:
        raise Refused("bad_format", str(fmt.get("format_name")))
    audio = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if len(audio) != 1:
        raise Refused("bad_streams", "exactly one audio stream expected")
    if any(s.get("codec_type") == "video" for s in probe.get("streams", [])):
        raise Refused("bad_streams", "video not accepted")
    if audio[0].get("codec_name") not in ALLOWED_CODECS:
        raise Refused("bad_codec", str(audio[0].get("codec_name")))
    try:
        dur = float(fmt.get("duration") or audio[0].get("duration"))
    except (TypeError, ValueError):
        return None  # browser WebM often has no duration; the caller checks the transcode
    if dur <= 0.2:
        raise Refused("too_short")
    if dur > max_seconds + 0.5:
        raise Refused("too_long", f"max {max_seconds} s")
    return dur
