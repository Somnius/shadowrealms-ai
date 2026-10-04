#!/usr/bin/env python3
"""Generate PLACEHOLDER inputs so the edit can be tested before the real recordings/music exist.

Writes to data/trailer/placeholder/ (never to the real clips/ or music/ folders):
  clips/{en,el}/shotNN.mp4   1920x1080 60 fps test patterns, labelled, with a source timecode
  clips/{en,el}/shots.json   durations and key moments, in the format edit.py reads
  clips/el/sigil.mp4         a stand-in for the recorded login sigil (exercises that code path)
  music/score.wav            48 kHz stereo, 120.0 s: low drone + a beep on every cue in CUES.md

Key moments are made visible: from each key time a red box fills the top-left quadrant for
0.4 s, so a still at the timeline time it is aligned to proves the alignment frame-exactly.

Usage: python3 tools/trailer/placeholders.py
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/trailer/placeholder"
FONT = ROOT / "data/trailer/fonts/EBGaramond.ttf"
NICE = ["nice", "-n", "10"]

# shot -> (duration, colour, {key: time in clip})
SHOTS = {
    "shot02": (10.0, "0x203050", {}),
    "shot03": (16.0, "0x304020", {"create_click_at": 11.0}),
    "shot04": (42.0, "0x403020", {}),                    # long: edit.py speeds it up to fit 14 s
    "shot05": (23.0, "0x302040", {}),
    "shot06": (21.0, "0x402028", {"dice_result_at": 9.0, "botch_result_at": 16.5}),
    "shot07": (13.0, "0x204040", {}),
    "shot08": (15.0, "0x383820", {}),
    "shot09": (17.0, "0x282848", {}),
}
EXTRA_EN = {"shot06b": (8.0, "0x501818", {"botch_result_at": 3.0})}  # EN tests the separate-clip botch


def ff(*args):
    subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "8", *args], check=True)


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def make_clip(path, label, dur, colour, keys):
    vf = [
        f"drawgrid=w=160:h=90:t=1:c=white@0.12",
        f"drawtext=fontfile={FONT}:text='{esc(label)}':fontsize=110:fontcolor=white@0.85:x=(w-tw)/2:y=h*0.30",
        f"drawtext=fontfile={FONT}:text='src %{{pts\\:hms}}':fontsize=64:fontcolor=white@0.8:x=(w-tw)/2:y=h*0.48",
        # A busy band where captions sit, to judge caption contrast.
        "drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.2:color=0xe0e0e0@0.35:t=fill",
        f"drawtext=fontfile={FONT}:text='busy UI text busy UI text busy UI text busy UI text':fontsize=48:fontcolor=black@0.7:x=(w-tw)/2:y=h*0.79",
    ]
    for k, t in keys.items():
        vf.append(f"drawbox=x=0:y=0:w=iw/2:h=ih/2:color=red:t=fill:enable='between(t,{t},{t + 0.4})'")
        vf.append(f"drawtext=fontfile={FONT}:text='{esc(k)} = {t}':fontsize=60:fontcolor=white:x=40:y=40:enable='between(t,{t},{t + 0.4})'")
    ff("-f", "lavfi", "-i", f"color=c={colour}:s=1920x1080:r=60:d={dur}",
       "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "60", str(path))


def main():
    for lang in ("en", "el"):
        d = OUT / "clips" / lang
        d.mkdir(parents=True, exist_ok=True)
        shots = dict(SHOTS)
        if lang == "en":
            shots.update(EXTRA_EN)
        meta = {}
        for name, (dur, colour, keys) in shots.items():
            make_clip(d / f"{name}.mp4", f"PLACEHOLDER {lang.upper()} {name}", dur, colour, keys)
            meta[name] = {"duration": dur, **keys}
            print("  +", (d / f"{name}.mp4").relative_to(ROOT))
        if lang == "el":
            make_clip(d / "sigil.mp4", "PLACEHOLDER sigil.mp4 (recorded login sigil)", 10.0, "0x0f0f1e", {"sigil_done_at": 4.0})
            meta["sigil"] = {"duration": 10.0, "sigil_done_at": 4.0}
        (d / "shots.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Music stand-in: quiet drone, a beep on every cue; the 68.0 hit is the loudest and highest.
    cues = [2.0, 6.0, 15.0, 24.5, 27.0, 41.0, 60.0, 73.0, 76.0, 86.0, 98.0, 112.0, 113.0]
    beeps = "+".join(f"0.35*sin(2*PI*660*t)*between(t,{c},{c + 0.08})" for c in cues)
    expr = f"0.08*sin(2*PI*55*t)+0.04*sin(2*PI*82.5*t)+{beeps}+0.7*sin(2*PI*1320*t)*between(t,68.0,68.12)"
    m = OUT / "music"
    m.mkdir(parents=True, exist_ok=True)
    ff("-f", "lavfi", "-i", f"aevalsrc='{expr}|{expr}':s=48000:d=120", "-c:a", "pcm_s24le", str(m / "score.wav"))
    print("  +", (m / "score.wav").relative_to(ROOT))


if __name__ == "__main__":
    main()
