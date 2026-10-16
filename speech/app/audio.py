"""ffmpeg / ffprobe helpers (two threads each, to stay inside the CPU cap)."""
import json
import subprocess

from .limits import Refused


def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", path], capture_output=True, timeout=20)
    if r.returncode != 0:
        raise Refused("bad_audio", "ffprobe could not read the file")
    return json.loads(r.stdout or b"{}")


def duration(path: str) -> float:
    d = probe(path).get("format", {}).get("duration")
    return float(d) if d else 0.0


def _ff(args, timeout=120):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-threads", "2", *args],
                       capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise Refused("transcode_failed", r.stderr.decode(errors="replace")[-300:])


def to_opus(src: str, dst: str, bitrate: str, max_seconds: int = None):
    extra = ["-t", str(max_seconds + 1)] if max_seconds else []
    _ff(["-i", src, *extra, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", bitrate,
         "-application", "voip", "-f", "ogg", dst])


def to_m4a(src: str, dst: str):
    _ff(["-i", src, "-vn", "-ac", "1", "-c:a", "aac", "-b:a", "48k", "-movflags", "+faststart",
         "-f", "ipod", dst])
