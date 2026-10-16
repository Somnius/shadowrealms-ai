"""Settings from the environment. Everything has a default so tests import cleanly."""
import os


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MODELS_DIR = os.environ.get("VOICE_MODELS_DIR", "/models")
CACHE_DIR = os.environ.get("VOICE_CACHE_DIR", "/cache")
SECRET = os.environ.get("SPEECH_SECRET", "")
HOST = os.environ.get("SPEECH_HOST", "127.0.0.1")
PORT = _int("SPEECH_PORT", 5055)

TEXT_MAX_CHARS = _int("VOICE_TTS_MAX_CHARS", 5000)
TEXT_PART_CHARS = _int("VOICE_TTS_PART_CHARS", 1200)
CLIP_MAX_SECONDS = _int("VOICE_CLIP_MAX_SECONDS", 180)
CLIP_MAX_BYTES = _int("VOICE_CLIP_MAX_BYTES", 8 * 1024 * 1024)
CLIP_BITRATE = os.environ.get("VOICE_CLIP_BITRATE", "16k")
TTS_BITRATE = os.environ.get("VOICE_TTS_BITRATE", "24k")
STT_QUEUE_MAX = _int("VOICE_STT_QUEUE_MAX", 8)
TTS_QUEUE_MAX = _int("VOICE_TTS_QUEUE_MAX", 64)
STT_IDLE_SECONDS = _int("VOICE_STT_IDLE_SECONDS", 600)
# measured resident +1.6 GB for large-v3-turbo int8_float16, plus 512 MB headroom
STT_VRAM_MB = _int("VOICE_STT_VRAM_MB", 2150)
STT_MODEL = os.environ.get("VOICE_STT_MODEL", "large-v3-turbo")
STT_COMPUTE = os.environ.get("VOICE_STT_COMPUTE", "int8_float16")
JOB_KEEP_SECONDS = _int("VOICE_JOB_KEEP_SECONDS", 3600)
# Transcript check (phase 6): Laya-words on a few CPU threads, a time budget, a capped Whisper prompt
LAYA_THREADS = _int("VOICE_LAYA_THREADS", 4)
LAYA_BUDGET_S = _int("VOICE_LAYA_BUDGET_MS", 2000) / 1000
PROMPT_MAX_CHARS = _int("VOICE_STT_PROMPT_MAX_CHARS", 400)


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


TTS_CACHE_BYTES = int(_float("VOICE_TTS_CACHE_GB", 5) * 1024 ** 3)
