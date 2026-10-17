import hashlib

# Bump when an engine, its settings or the text preparation change, so old audio is not reused.
ENGINE_VERSIONS = {"piper": "piper-1.8.0/1", "pocket": "pocket-3.3.0/1", "gemini": "gemini/1"}


def tts_key(engine: str, voice: str, text: str, bitrate: str) -> str:
    raw = "\x1f".join([ENGINE_VERSIONS.get(engine, engine), voice, bitrate, text])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
