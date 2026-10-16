#!/usr/bin/env python3
"""Measure the hits in the audio of rendered trailers against the cue sheet (music/cues.py).

Decodes each MP4's AAC track with ffmpeg (encoder delay and edit list handled by ffmpeg) and runs
music/analyze.py's onset() (first attack on a >200 Hz 1 ms envelope) at the big hit, the second
hit, the theme downbeat and the last bell. The picture side is checked by eye on the
review_hits_*.png sheets edit.py writes (the frames either side of each flash).

    uv run --with numpy --with scipy --with soundfile python3 tools/trailer/check_hits.py \
        data/trailer-v2/out/trailer_en_draft_1080p.mp4 [...] [--preset v2]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "music"))
from analyze import onset  # noqa: E402
from cues import PRESETS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4", nargs="+")
    ap.add_argument("--preset", default="v2", choices=sorted(PRESETS))
    ap.add_argument("--tolerance", type=float, default=0.005, help="allowed error in seconds (default 5 ms)")
    args = ap.parse_args()
    c = PRESETS[args.preset]
    bad = 0
    for mp4 in args.mp4:
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "a.wav"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", mp4, "-vn", "-c:a", "pcm_f32le", str(wav)], check=True)
            x, sr = sf.read(wav, dtype="float64", always_2d=True)
        print(f"{mp4}: audio {len(x) / sr:.3f} s @ {sr} Hz")
        for name, t in (("hit", c.hit), ("hit2 (botch)", c.hit2), ("theme downbeat", c.theme), ("last bell", c.last_bell)):
            o = onset(x, sr, t)
            off = abs(o["t"] - t) > args.tolerance
            bad += off
            print(f"  {name:15s} cue {t:7.3f}: first attack {o['attack_t']} s, largest jump {o['jump_t']:.3f} s "
                  f"({o['jump_db']:.1f} dB){'   <-- OFF by %+.3f s' % (o['t'] - t) if off else ''}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
