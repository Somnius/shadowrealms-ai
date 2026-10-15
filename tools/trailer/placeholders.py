#!/usr/bin/env python3
"""Generate PLACEHOLDER inputs so the edit can be dry-run before the recordings (or the music) exist.

Everything is derived from the timeline, so the stand-ins always match the cut:
  <data_dir>/placeholder/clips/{en,el}/<clip>.mp4   1920x1080 60 fps test patterns for every clip the
                                                    timeline names, labelled, with a source timecode
  <data_dir>/placeholder/clips/{en,el}/shots.json   durations and every key moment the timeline aligns by,
                                                    at source times that fit the slots
  <data_dir>/placeholder/music/score.wav            48 kHz stereo, the preset's length: a low drone and a
                                                    beep on every mark of the music preset (cues.py); the
                                                    hit is the loudest and highest, the other hits medium
Never writes to the real clips/ or music/ folders.

Key moments are made visible: from each key time a red box fills the top-left quadrant for 0.4 s,
so a still at the timeline time it is aligned to proves the alignment frame-exactly.

Usage: python3 tools/trailer/placeholders.py [--timeline tools/trailer/timeline_v2.json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "music"))
from cues import PRESETS, by_duration  # noqa: E402

NICE = ["nice", "-n", "10"]
COLOURS = ["0x203050", "0x304020", "0x403020", "0x302040", "0x402028", "0x204040", "0x383820", "0x282848",
           "0x501818", "0x1e2a3a", "0x3a2a1e", "0x2a3a1e", "0x3a1e2a", "0x1e3a2a", "0x2a1e3a"]


def ff(*args):
    subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "8", *args], check=True)


def esc(s):
    """For a drawtext text='...' value: a straight quote would end the string, so it becomes the
    typographic one; ':' and '%' are escaped for the option parser."""
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def derive_clips(tl, lang):
    """Every clip the timeline names -> {'duration': s, key: source time, ...}, so that each piece's
    in-point is >= 0.5 s into the clip and the pieces of one clip follow each other in source time."""
    clips, cursor, scene = {}, {}, {}
    for s in tl["shots"]:
        pieces = s.get("pieces") or [{"clip": s.get("clip"), "align": s.get("align")}]
        start = float(s["start"])
        for k, pc in enumerate(pieces):
            end = float(pc.get("until", s["end"])) if k < len(pieces) - 1 else float(s["end"])
            name = pc.get("clip")
            if not name:
                start = end
                continue
            m = clips.setdefault(name, {})
            scene.setdefault(name, s.get("scene", ""))
            speed = float(pc.get("speed", 1.0))
            al = pc.get("align") or {"src": 0.0, "at": start}
            at = float(al["at"])
            ostart = start - 0.5          # room for the transition into the piece
            if "src" in al:
                src = al["src"]
                src = float(src[lang] if isinstance(src, dict) else src)
                need = src + (end + 0.5 - at) * speed
            elif al["key"] == "duration":  # the clip's end is pinned to `at`
                need = (at - ostart) * speed - float(al.get("offset", 0)) + 0.5
            else:
                key, off = al["key"], float(al.get("offset", 0))
                if key in m:               # a key already placed by an earlier piece: follow it
                    src_in = m[key] + off - (at - ostart) * speed
                else:
                    src_in = cursor.get(name, 0.5)
                    m[key] = round(src_in + (at - ostart) * speed - off, 3)
                need = max(src_in, 0.0) + (end + 0.5 - ostart) * speed
            cursor[name] = max(cursor.get(name, 0.5), need + 0.5)
            m["duration"] = max(m.get("duration", 0.0), round(need + 1.0, 3))
            start = end
    return clips, scene


def make_clip(path, font, label, scene, dur, colour, keys):
    vf = [
        "drawgrid=w=160:h=90:t=1:c=white@0.12",
        f"drawtext=fontfile={font}:text='{esc(label)}':fontsize=110:fontcolor=white@0.85:x=(w-tw)/2:y=h*0.26",
        f"drawtext=fontfile={font}:text='{esc(scene[:70])}':fontsize=40:fontcolor=white@0.7:x=(w-tw)/2:y=h*0.40",
        f"drawtext=fontfile={font}:text='src %{{pts\\:hms}}':fontsize=64:fontcolor=white@0.8:x=(w-tw)/2:y=h*0.50",
        # A busy band where captions sit, to judge caption contrast.
        "drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.2:color=0xe0e0e0@0.35:t=fill",
        f"drawtext=fontfile={font}:text='busy UI text busy UI text busy UI text busy UI text':fontsize=48:fontcolor=black@0.7:x=(w-tw)/2:y=h*0.79",
    ]
    for k, t in keys.items():
        vf.append(f"drawbox=x=0:y=0:w=iw/2:h=ih/2:color=red:t=fill:enable='between(t,{t},{t + 0.4})'")
        vf.append(f"drawtext=fontfile={font}:text='{esc(k)} = {t}':fontsize=60:fontcolor=white:x=40:y=40:enable='between(t,{t},{t + 0.4})'")
    ff("-f", "lavfi", "-i", f"color=c={colour}:s=1920x1080:r=60:d={dur}",
       "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "60", str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=str(HERE / "timeline.json"))
    args = ap.parse_args()
    tl = json.loads(Path(args.timeline).read_text())
    data = ROOT / tl.get("data_dir", "data/trailer")
    out = data / "placeholder"
    font = data / "fonts/EBGaramond.ttf"
    if not font.exists():
        sys.exit(f"missing {font} (tools/trailer/reuse_v1.py copies the fonts)")
    preset = PRESETS[tl["music_preset"]] if tl.get("music_preset") else by_duration(float(tl["duration"]))
    if preset is None:
        sys.exit("the timeline names no music_preset and its duration matches none")

    for lang in ("en", "el"):
        d = out / "clips" / lang
        d.mkdir(parents=True, exist_ok=True)
        clips, scene = derive_clips(tl, lang)
        meta = {}
        for i, (name, m) in enumerate(clips.items()):
            keys = {k: v for k, v in m.items() if k != "duration"}
            make_clip(d / f"{name}.mp4", font, f"PLACEHOLDER {lang.upper()} {name}", scene[name], m["duration"], COLOURS[i % len(COLOURS)], keys)
            meta[name] = {"duration": m["duration"], **keys}
            print(f"  + {(d / f'{name}.mp4').relative_to(ROOT)}  {m['duration']:.1f} s  {keys}")
        (d / "shots.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Music stand-in: quiet drone, a beep on every mark; the hit is the loudest and highest, the
    # other hits (the botch, the theme downbeat) medium.
    beeps = "+".join(f"0.35*sin(2*PI*660*t)*between(t,{c},{c + 0.08})" for c in preset.marks)
    hits = [f"0.7*sin(2*PI*1320*t)*between(t,{preset.hit},{preset.hit + 0.12})"]
    hits += [f"0.5*sin(2*PI*990*t)*between(t,{c},{c + 0.1})" for c in (preset.hit2, preset.theme)]
    expr = f"0.08*sin(2*PI*55*t)+0.04*sin(2*PI*82.5*t)+{beeps}+" + "+".join(hits)
    m = out / "music"
    m.mkdir(parents=True, exist_ok=True)
    ff("-f", "lavfi", "-i", f"aevalsrc='{expr}|{expr}':s=48000:d={preset.dur}", "-c:a", "pcm_s24le", str(m / "score.wav"))
    print("  +", (m / "score.wav").relative_to(ROOT), f"({preset.dur} s, preset {preset.name})")


if __name__ == "__main__":
    main()
