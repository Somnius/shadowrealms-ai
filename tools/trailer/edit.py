#!/usr/bin/env python3
"""ShadowRealms AI trailer: edit + render (one ffmpeg run per language).

Reads tools/trailer/timeline.json (encoded from CUES.md), the clips and their shots.json,
the cards (built by cards.mjs, run automatically and cached) and the score, and renders
  data/trailer/out/trailer_{lang}_1080p60.mp4   (final)   or  trailer_{lang}_draft_{res}.mp4 (draft)
  data/trailer/out/poster*_{lang}[...].png      poster frames (times in timeline.json "posters")
  data/trailer/out/contact_{lang}[...].png      contact sheet, one frame per second, 10 x 12
then checks the result: 120.0 s, 7200 frames, audio length, A/V start.

Usage:
  python3 tools/trailer/edit.py --lang en --draft            # NVENC, 960x540, fast; for iteration
  python3 tools/trailer/edit.py --lang en --draft --res 1080 # NVENC at full size
  python3 tools/trailer/edit.py --lang both --final          # x264 crf 18 preset slow, 1080p60
Options:
  --placeholder     use data/trailer/placeholder/{clips,music} instead of the real inputs
  --fill-missing    per shot: use the placeholder clip when the real one is missing (and say so)
  --no-cards        don't run cards.mjs first (use what is in data/trailer/cards/)
  --print-graph     print the ffmpeg command and filter graph, don't render

Machine limits (CLAUDE.md): runs under nice -n 10, encoder -threads 12, decoders 2 threads each,
filter graph 6 threads. One render at a time.
"""
import argparse
import json
import math
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data/trailer"
FONT = DATA / "fonts/EBGaramond.ttf"
NICE = ["nice", "-n", "10"]
TL = json.loads((HERE / "timeline.json").read_text())
FPS = TL["fps"]
TOTAL = float(TL["duration"])
NFRAMES = round(TOTAL * FPS)


def log(*a):
    print("[edit]", *a, flush=True)


def warn(*a):
    print("[edit] WARNING:", *a, file=sys.stderr, flush=True)


def fr(t):
    """Seconds -> whole frames."""
    return round(t * FPS)


def f6(x):
    return f"{x:.6f}"


def ffprobe_duration(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ------------------------------------------------------------------ shots.json (lenient)
def norm_name(n):
    n = str(n).strip()
    if n.lower().endswith(".mp4"):
        n = n[:-4]
    m = re.fullmatch(r"(?:shot)?0*(\d+)([a-z]?)", n, re.I)
    return f"shot{int(m.group(1)):02d}{m.group(2).lower()}" if m else n


def load_meta(clips_dir):
    p = clips_dir / "shots.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text())
    if isinstance(raw, dict) and isinstance(raw.get("shots"), (list, dict)):
        raw = raw["shots"]
    items = raw.items() if isinstance(raw, dict) else [
        (e.get("shot") or e.get("id") or e.get("name") or e.get("file"), e) for e in raw]
    meta = {}
    for name, e in items:
        if name is None or not isinstance(e, dict):
            continue
        flat = dict(e)
        for nest in ("keys", "moments", "key_moments", "markers"):  # nested key moments
            if isinstance(e.get(nest), dict):
                flat.update(e[nest])
        meta[norm_name(name)] = flat
    return meta


# ------------------------------------------------------------------ segment plan
class Seg:
    def __init__(self, sid, start, end):
        self.sid, self.start, self.end = sid, start, end
        self.t_in = 0.0      # transition into this segment (seconds, even frames)
        self.t_in_type = "fade"
        self.t_out = 0.0
        self.base = None     # "black" or a clip dict

    @property
    def ostart(self):
        return self.start - self.t_in / 2

    @property
    def oend(self):
        return self.end + self.t_out / 2

    @property
    def nframes(self):
        return fr(self.oend) - fr(self.ostart)


def even_frames_sec(frames):
    frames = max(2, int(frames))
    frames += frames % 2
    return frames / FPS


class Planner:
    def __init__(self, lang, clips_dir, fallback_dir, fill_missing):
        self.lang, self.clips_dir, self.fallback_dir = lang, clips_dir, fallback_dir
        self.fill = fill_missing
        self.meta = load_meta(clips_dir)
        self.fb_meta = load_meta(fallback_dir) if fallback_dir else {}
        self.notes = []

    def find(self, name, need_key=None):
        """-> (path, meta) for clip `name`, the real one first; None when missing."""
        for d, meta, tag in ((self.clips_dir, self.meta, "real"), (self.fallback_dir, self.fb_meta, "PLACEHOLDER")):
            if d is None or (tag == "PLACEHOLDER" and not self.fill):
                continue
            p = d / f"{name}.mp4"
            if p.exists():
                m = dict(meta.get(name, {}))
                if need_key and need_key not in m:
                    continue
                if tag == "PLACEHOLDER" and self.clips_dir != self.fallback_dir:
                    self.notes.append(f"{name}: real clip missing, using placeholder")
                return p, m
        return None

    def resolve_src(self, name, m, align):
        """Source time named by an align spec: {'src': t | {lang: t}} or {'key': k, 'offset': o}."""
        if "src" in align:
            v = align["src"]
            return float(v[self.lang] if isinstance(v, dict) else v)
        key = align["key"]
        if key == "duration" and key not in m:
            m[key] = None
        if key == "duration":
            return float(m.get("duration") or 0) + float(align.get("offset", 0))
        if key not in m:
            raise SystemExit(f"{self.lang} {name}: no '{key}' in shots.json (needed to place it at {align['at']} s)")
        return float(m[key]) + float(align.get("offset", 0))

    def clip_source(self, name, path, m, seg_start, seg_frames, align=None, fit=False, speed=None, label="", quiet_pad=False):
        """Work out in-point and speed so that the segment [seg_start, +seg_frames) is filled."""
        dur_full = ffprobe_duration(path)
        keep = m.get("keep") or m.get("segments")  # optional jump cuts: [[a,b], ...] in clip time
        ranges = [(float(a), float(b)) for a, b in keep] if keep else [(0.0, dur_full)]
        edited_len = sum(b - a for a, b in ranges)

        def to_edited(t):
            acc = 0.0
            for a, b in ranges:
                if a <= t <= b:
                    return acc + (t - a)
                acc += b - a
            raise ValueError(f"{name}: time {t} is outside the keep ranges {ranges}")

        L = seg_frames / FPS
        speed = float(speed if speed is not None else m.get("speed", 1.0))
        t_in = to_edited(float(m["in"])) if "in" in m else 0.0
        if fit and "speed" not in m:
            speed = max(1.0, (edited_len - t_in) / L)
        if align:
            t_in = to_edited(self.resolve_src(name, m, align)) - (align["at"] - seg_start) * speed
        t_in = round(t_in * FPS) / FPS
        pad_start = max(0.0, -t_in) / speed
        t_in = max(0.0, t_in)
        need = t_in + (L - pad_start) * speed
        pad_end = max(0.0, need - edited_len) / speed
        if pad_start > 1e-6 and not quiet_pad:
            self.notes.append(f"{name}: starts {pad_start:.2f} s too late for its slot, first frame held")
        if pad_end > 1.5 / FPS:
            self.notes.append(f"{name}: {pad_end:.2f} s too short for its slot, last frame held")
        return {"name": name, "path": path, "ranges": ranges, "in": t_in, "speed": speed,
                "pad_start": pad_start, "pad_end": pad_end, "frames": seg_frames, "label": label,
                "src_span": (t_in, t_in + (L - pad_start) * speed)}

    def plan(self):
        """Every shot is one or more pieces (see timeline.json); each piece becomes one segment."""
        segs = []
        for s in TL["shots"]:
            pieces = s.get("pieces") or [{"clip": s.get("clip"), "align": s.get("align"), "fit": s.get("fit", False)}]
            start = float(s["start"])
            for k, pc in enumerate(pieces):
                end = float(pc.get("until", s["end"])) if k < len(pieces) - 1 else float(s["end"])
                seg = Seg(s["id"] + ("" if len(pieces) == 1 else "abcdefgh"[k]), start, end)
                tr = s.get("transition_in", {"type": "fade", "frames": 12}) if k == 0 else pc.get("transition", {"type": "fade", "frames": 2})
                seg.t_in_type = tr["type"]
                seg.t_in = 0.0 if not segs else even_frames_sec(tr["frames"])
                seg.piece = pc
                seg.shot = s
                if segs:
                    segs[-1].t_out = seg.t_in
                segs.append(seg)
                start = end
        for seg in segs:
            pc = seg.piece
            got = self.find(pc["clip"]) if pc.get("clip") else None
            if not got:
                self.notes.append(f"shot {seg.sid}: {pc.get('clip')}.mp4 MISSING, slot left black")
                seg.base = "black"
                continue
            p, m = got
            seg.base = self.clip_source(pc["clip"], p, m, seg.ostart, seg.nframes, align=pc.get("align"),
                                        fit=pc.get("fit", False), speed=pc.get("speed"),
                                        quiet_pad=bool(pc.get("fade_in")))
            seg.base["crop"] = pc.get("crop")
            seg.base["fade_in"] = pc.get("fade_in")
        # Sanity: the plan covers exactly 0..TOTAL.
        total = sum(sg.nframes for sg in segs) - sum(fr(sg.t_in) for sg in segs)
        assert total == NFRAMES, f"plan is {total} frames, want {NFRAMES}"
        return segs


# ------------------------------------------------------------------ filter graph
class Graph:
    def __init__(self):
        self.inputs, self.chains, self.n = [], [], 0

    def inp(self, *args):
        self.inputs.append(list(args))
        return len(self.inputs) - 1

    def label(self, p="v"):
        self.n += 1
        return f"{p}{self.n}"

    def add(self, s):
        self.chains.append(s)


# The recordings are full-range BT.601 (yuvj420p, pc, bt470bg). Everything is converted
# explicitly to BT.709 limited range, the overlays (RGBA cards, fog, flashes) too, so no
# auto-inserted conversion guesses, and the output is tagged bt709/tv.
TAG709 = "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"


def to709(fmt):
    return f"scale=out_color_matrix=bt709:out_range=tv,format={fmt},{TAG709}"


def build(lang, segs, music, cards_dir, W, H, pix, card_v=""):
    g = Graph()
    opix = "yuva444p" if pix == "yuv444p" else "yuva420p"   # overlay pixel format
    sc = W / TL["width"]
    scale = (f"scale={W}:{H}:flags=lanczos:force_original_aspect_ratio=decrease:out_color_matrix=bt709:out_range=tv,"
             f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")

    # ---- base segments
    seg_labels = []
    for seg in segs:
        out = g.label("seg")
        n = seg.nframes
        if seg.base == "black":
            g.add(f"color=c=0x07070f:s={W}x{H}:r={FPS}:d={f6(n / FPS + 1)},trim=end_frame={n},setpts=PTS-STARTPTS,format=rgb24,{to709(pix)},settb=AVTB[{out}]")
        else:
            b = seg.base
            i = g.inp("-threads", "2", "-i", str(b["path"]))
            parts = []
            if len(b["ranges"]) > 1 or b["ranges"][0][0] > 0:
                k = len(b["ranges"])
                sl = [g.label("k") for _ in range(k)]
                g.add(f"[{i}:v]split={k}" + "".join(f"[{x}]" for x in sl))
                cc = []
                for x, (a, e) in zip(sl, b["ranges"]):
                    y = g.label("k")
                    g.add(f"[{x}]trim=start={f6(a)}:end={f6(e)},setpts=PTS-STARTPTS[{y}]")
                    cc.append(f"[{y}]")
                src = g.label("k")
                g.add("".join(cc) + f"concat=n={k}:v=1:a=0[{src}]")
                src = f"[{src}]"
            else:
                src = f"[{i}:v]"
            parts.append("setpts=PTS-STARTPTS")
            if b["in"] > 0:
                parts += [f"trim=start={f6(b['in'] - 0.5 / FPS)}", "setpts=PTS-STARTPTS"]
            if abs(b["speed"] - 1) > 1e-6:
                parts.append(f"setpts=PTS/{b['speed']:.6f}")
            parts.append(f"fps={FPS}")
            if b["pad_start"] > 0:
                parts.append(f"tpad=start_mode=clone:start_duration={f6(b['pad_start'])}")
            parts += [f"tpad=stop_mode=clone:stop_duration={f6(n / FPS + 1)}", f"trim=end_frame={n}",
                      "setpts=PTS-STARTPTS"]
            if b.get("crop"):  # static zoom: [x, y, w] in source pixels, 16:9
                cx, cy, cw = b["crop"]
                ch = int(round(cw * 9 / 16 / 2)) * 2
                parts.append(f"crop={int(cw)}:{ch}:{int(cx)}:{int(cy)}")
            parts += [scale, f"format={pix}", TAG709, "settb=AVTB"]
            if b.get("fade_in"):
                parts.append(f"fade=t=in:st=0:d={b['fade_in']}")
            g.add(src + ",".join(parts) + f"[{out}]")
        seg_labels.append(out)

    # ---- transitions (xfade chain). Output offset of transition k = boundary - d/2.
    cur = seg_labels[0]
    for seg, lab in zip(segs[1:], seg_labels[1:]):
        out = g.label("x")
        d = seg.t_in
        g.add(f"[{cur}][{lab}]xfade=transition={seg.t_in_type}:duration={f6(d)}:offset={f6((fr(seg.start - d / 2) - 0.5) / FPS)}[{out}]")
        # (half a frame early: an offset of exactly k/60 s can round above frame k's pts in
        # microseconds, and xfade then starts the next clip one frame late)
        cur = out

    # ---- look: crushed blacks, teal shadows / warm-red highlights, vignette (not on cards)
    gr = TL["grade"]
    out = g.label("g")
    g.add(f"[{cur}]curves={gr['curves']},colorbalance={gr['colorbalance']},eq=saturation={gr['saturation']},"
          f"vignette=angle={gr['vignette']}:mode=forward[{out}]")
    cur = out

    # ---- fog (intro/outro): a big blurred-noise texture scrolled two ways, as alpha of a cold grey
    fog_png = DATA / "cache/fog.png"
    for k, fz in enumerate(TL["fog"]):
        dur = fz["end"] - fz["start"]
        i = g.inp("-loop", "1", "-framerate", str(FPS), "-t", f6(dur), "-i", str(fog_png))
        a, b, m, c, o = (g.label("f") for _ in range(5))
        g.add(f"[{i}:v]format=gray,split[{a}0][{b}0]")
        g.add(f"[{a}0]crop=1920:1080:x='120+t*38':y=0,scale={W}:{H}[{a}]")
        g.add(f"[{b}0]hflip,crop=1920:1080:x='1500-t*24':y=0,scale={W}:{H}[{b}]")
        g.add(f"[{a}][{b}]blend=all_mode=screen,lut=y='val*{fz['opacity']}'[{m}]")
        g.add(f"color=c=0x9aa3bd:s={W}x{H}:r={FPS}:d={f6(dur)},format=rgba[{c}]")
        g.add(f"[{c}][{m}]alphamerge,fade=t=in:st=0:d={fz['fade_in']}:alpha=1,"
              f"fade=t=out:st={f6(dur - fz['fade_out'])}:d={fz['fade_out']}:alpha=1,{to709(opix)},setpts=PTS+{f6(fz['start'])}/TB[{o}]")
        nxt = g.label("g")
        g.add(f"[{cur}][{o}]overlay=eof_action=pass:format=auto[{nxt}]")
        cur = nxt

    # ---- intro / outro animated cards
    intro_out = segs[1].t_in
    i = g.inp("-threads", "2", "-i", str(cards_dir / f"intro{card_v}.mov"))
    o, nxt = g.label("c"), g.label("g")
    g.add(f"[{i}:v]format=rgba,scale={W}:{H},tpad=stop_mode=clone:stop_duration={f6(intro_out)},"
          f"fade=t=out:st={f6(segs[1].start - intro_out / 2)}:d={f6(intro_out)}:alpha=1,{to709(opix)}[{o}]")
    g.add(f"[{cur}][{o}]overlay=eof_action=pass:format=auto[{nxt}]")
    cur = nxt
    outro = segs[-1]
    i = g.inp("-threads", "2", "-i", str(cards_dir / f"outro{card_v}.mov"))
    o, nxt = g.label("c"), g.label("g")
    g.add(f"[{i}:v]format=rgba,scale={W}:{H},trim=end={f6(TOTAL - outro.start)},{to709(opix)},setpts=PTS+{f6(outro.start)}/TB[{o}]")
    g.add(f"[{cur}][{o}]overlay=eof_action=pass:format=auto[{nxt}]")
    cur = nxt

    # ---- captions: one PNG each, faded and risen a few px in ffmpeg
    fd = TL["caption_fade"]
    for cap in TL["captions"]:
        png = cards_dir / f"cap_{cap['id']}.png"
        dur = cap["out"] - cap["in"]
        i = g.inp("-loop", "1", "-framerate", str(FPS), "-t", f6(dur), "-i", str(png))
        o, nxt = g.label("c"), g.label("g")
        g.add(f"[{i}:v]format=rgba,scale={W}:{H},fade=t=in:st=0:d={fd}:alpha=1,"
              f"fade=t=out:st={f6(dur - fd)}:d={fd}:alpha=1,{to709(opix)},setpts=PTS+{f6(cap['in'])}/TB[{o}]")
        rise = 14 * sc
        g.add(f"[{cur}][{o}]overlay=x=0:y='{rise:.2f}*max(0,1-(t-{cap['in']})/0.8)':eval=frame:eof_action=pass:format=auto[{nxt}]")
        cur = nxt

    # ---- blood flashes on the dice hits
    for fl in TL["flashes"]:
        d = fl["attack"] + fl["release"]
        o, nxt = g.label("r"), g.label("g")
        g.add(f"color=c={fl['color']}:s={W}x{H}:r={FPS}:d={f6(d)},format=rgba,colorchannelmixer=aa={fl['opacity']},"
              f"fade=t=in:st=0:d={fl['attack']}:alpha=1,fade=t=out:st={fl['attack']}:d={fl['release']}:alpha=1,"
              f"{to709(opix)},setpts=PTS+{f6(fl['at'])}/TB[{o}]")
        g.add(f"[{cur}][{o}]overlay=eof_action=pass:format=auto[{nxt}]")
        cur = nxt

    # ---- grain over everything, final fade to black, exact length
    a, b = TL["outro"]["fade_to_black"]
    g.add(f"[{cur}]noise=c0s={gr['grain']}:c0f=t,fade=t=out:st={f6(a)}:d={f6(b - a)},"
          f"trim=end_frame={NFRAMES},format=yuv420p,{TAG709}[vout]")

    # ---- audio
    ai = g.inp("-i", str(music))
    au = TL["audio"]
    g.add(f"[{ai}:a]aresample=48000,atrim=0:{TOTAL},apad=whole_dur={TOTAL},afade=t=in:st=0:d={au['fade_in']},"
          f"afade=t=out:st={f6(TOTAL - au['fade_out'])}:d={au['fade_out']},asetpts=PTS-STARTPTS[aout]")
    return g


def ensure_fog():
    p = DATA / "cache/fog.png"
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    # Two octaves of smoothed value noise (noise filter, not geq random(): that one stripes), 2x wide to scroll.
    subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=0x808080:s=28x8,format=gray,noise=alls=100:allf=u,scale=3840:1080:flags=bicubic,gblur=sigma=90",
                    "-f", "lavfi", "-i", "color=c=0x808080:s=112x32,format=gray,noise=alls=100:allf=u,scale=3840:1080:flags=bicubic,gblur=sigma=28",
                    "-filter_complex", "[0][1]blend=all_expr='A*0.72+B*0.28',eq=contrast=2.6:brightness=-0.22,geq=lum='lum(X\\,Y)*(0.3+0.7*Y/H)',gblur=sigma=8,format=gray",
                    "-frames:v", "1", str(p)], check=True)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", default="both", choices=["en", "el", "both"])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--draft", action="store_true", help="NVENC, fast (default)")
    mode.add_argument("--final", action="store_true", help="x264 crf 18 preset slow, 1080p")
    ap.add_argument("--res", type=int, choices=[540, 720, 1080], help="draft height (default 540; final is always 1080)")
    ap.add_argument("--placeholder", action="store_true")
    ap.add_argument("--fill-missing", action="store_true")
    ap.add_argument("--no-cards", action="store_true")
    ap.add_argument("--print-graph", action="store_true")
    args = ap.parse_args()
    final = args.final
    H = 1080 if final else (args.res or 540)
    W = H * 16 // 9
    langs = ["en", "el"] if args.lang == "both" else [args.lang]
    outdir = DATA / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    ensure_fog()

    for lang in langs:
        ph = DATA / "placeholder"
        clips_dir = (ph if args.placeholder else DATA) / "clips" / lang
        music = (ph if args.placeholder else DATA) / "music/score.wav"
        if not music.exists():
            if args.fill_missing and (ph / "music/score.wav").exists():
                warn(f"{music} missing, using the placeholder score")
                music = ph / "music/score.wav"
            else:
                sys.exit(f"missing {music} (use --placeholder or --fill-missing)")
        recorded = (clips_dir / "sigil_clean.mp4").exists()
        if not args.no_cards:
            cmd = ["node", str(HERE / "cards.mjs"), "--lang", lang] + (["--recorded"] if recorded else [])
            subprocess.run(cmd, check=True)
        planner = Planner(lang, clips_dir, ph / "clips" / lang, args.fill_missing or args.placeholder)
        segs = planner.plan()
        # Over the login page recording, the cards without our own sigil.
        card_v = "_rec" if (segs[0].base != "black" and segs[0].base["name"].startswith("sigil")) else ""
        log(f"--- {lang}: clips from {clips_dir.relative_to(ROOT)}, music {music.relative_to(ROOT)}")
        for sg in segs:
            b = sg.base
            desc = "black" if b == "black" else (f"{b['name']} src {b['src_span'][0]:.2f}-{b['src_span'][1]:.2f} s x{b['speed']:.2f}"
                                                 + (f" padstart={b['pad_start']:.2f}" if b['pad_start'] else "")
                                                 + (f" crop={b['crop']}" if b.get('crop') else ""))
            log(f"  {sg.sid:>4} {sg.start:6.2f}-{sg.end:6.2f}  (+{sg.t_in_type} {fr(sg.t_in)}f)  {desc}")
        for n in planner.notes:
            warn(n)

        g = build(lang, segs, music, DATA / "cards" / lang, W, H, "yuv444p" if final else "yuv420p", card_v)
        suffix = "1080p60" if final else f"draft_{H}p"
        out = outdir / f"trailer_{lang}_{suffix}.mp4"
        graph_file = outdir / f".graph_{lang}_{suffix}.txt"
        graph_file.write_text(";\n".join(g.chains))
        if final:
            venc = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-tune", "film", "-profile:v", "high",
                    "-maxrate", "30M", "-bufsize", "60M",  # grain makes crf 18 alone ~105 Mbps
                    "-threads", "12", "-g", "120"]
        elif nvenc_ok(W, H):
            venc = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0",
                    "-profile:v", "high", "-g", "120"]
        else:
            warn("NVENC can't open (GPU memory full?); draft falls back to x264 veryfast")
            venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-profile:v", "high",
                    "-threads", "8", "-g", "120"]
        cmd = [*NICE, "ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-stats", "-stats_period", "15",
               *[x for i in g.inputs for x in i],
               "-filter_complex_threads", "6", "-/filter_complex", str(graph_file),
               "-map", "[vout]", "-map", "[aout]", *venc, "-pix_fmt", "yuv420p", "-r", str(FPS),
               "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
               "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", f6(TOTAL), "-movflags", "+faststart", str(out)]
        if args.print_graph:
            print(shlex.join(cmd))
            print(graph_file.read_text())
            continue
        log(f"rendering {out.relative_to(ROOT)} ({W}x{H}, {'x264 final' if final else 'draft'})")
        t0 = time.time()
        subprocess.run(cmd, check=True)
        log(f"rendered in {time.time() - t0:.1f} s")
        verify(out)
        tag = "" if final else f"_draft_{H}p"
        for p in TL["posters"]:
            png = outdir / f"{p['name']}_{lang}{tag}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f6(p["at"]), "-i", str(out),
                            "-frames:v", "1", str(png)], check=True)
            log(f"  poster {png.relative_to(ROOT)} @ {p['at']} s")
        sheet = outdir / f"contact_{lang}{tag}.png"
        subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-vf",
                        f"select='eq(mod(n\\,{FPS})\\,{FPS // 2})',scale=384:216,drawtext=fontfile={FONT}:text='%{{eif\\:t\\:d}}s':"
                        "fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6:x=6:y=6,tile=10x12:padding=4:color=black",
                        "-frames:v", "1", str(sheet)], check=True)
        log(f"  contact sheet {sheet.relative_to(ROOT)}")
        review(out, outdir, lang, tag, segs)
        preview(out, outdir / f"preview_{lang}{tag}.webp")


def frames_sheet(src, frames, cols, width, dst):
    """Tile the given frame numbers of `src` (one decode pass), each labelled with its time."""
    sel = "+".join(f"eq(n\\,{n})" for n in sorted(set(frames)))
    subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "8", "-i", str(src), "-vf",
                    f"select='{sel}',scale={width}:-2,drawtext=fontfile={FONT}:text='%{{pts\\:hms}}  f%{{eif\\:t*{FPS}\\:d}}':"
                    f"fontsize={max(16, width // 24)}:fontcolor=yellow:box=1:boxcolor=black@0.7:x=6:y=6,"
                    f"tile={cols}x{math.ceil(len(set(frames)) / cols)}:padding=4:color=black",
                    "-frames:v", "1", "-fps_mode", "passthrough", str(dst)], check=True)


def review(out, outdir, lang, tag, segs):
    """Stills for review: just after every cut (once the transition is over), and the frames
    either side of each hit (68.0 / 73.0)."""
    cuts = [fr(sg.start + sg.t_in / 2) + 2 for sg in segs[1:]]
    before = [fr(sg.start - sg.t_in / 2) - 3 for sg in segs[1:]]
    frames_sheet(out, sorted(set(cuts + before)), 6, 480, outdir / f"review_cuts_{lang}{tag}.png")
    hits = []
    for fl in TL["flashes"]:
        n = fr(fl["at"])
        hits += [n - 1, n, n + 12, n + 30]
    frames_sheet(out, hits, 4, 960, outdir / f"review_hits_{lang}{tag}.png")
    log(f"  review sheets {outdir.relative_to(ROOT)}/review_{{cuts,hits}}_{lang}{tag}.png")


def preview(out, dst, max_bytes=8_000_000):
    """Silent looping animated WebP for the README (timeline.json "preview"); grain removed first."""
    pv = TL["preview"]
    for q in (88, 80, 70, 60, 50, 40):
        subprocess.run([*NICE, "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f6(pv["start"]),
                        "-t", f6(pv["end"] - pv["start"]), "-i", str(out), "-an",
                        "-vf", f"hqdn3d=4:3:6:4,scale={pv['width']}:-2:flags=lanczos,fps={pv['fps']}",
                        "-c:v", "libwebp_anim", "-lossless", "0", "-q:v", str(q), "-compression_level", "6",
                        "-loop", "0", str(dst)], check=True)
        size = dst.stat().st_size
        if size <= max_bytes:
            break
    log(f"  preview {dst.relative_to(ROOT)} ({size / 1e6:.1f} MB, q {q})")


def nvenc_ok(W, H):
    """NVENC needs free GPU memory; LM Studio/ComfyUI can fill it. Probe with a 1 s encode."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"color=c=black:s={W}x{H}:r={FPS}:d=1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                       capture_output=True)
    return r.returncode == 0


def verify(out):
    q = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                        "stream=codec_name,profile,pix_fmt,width,height,r_frame_rate,nb_read_packets,duration,start_time,sample_rate",
                        "-show_entries", "format=duration", "-of", "json", str(out)], capture_output=True, text=True, check=True)
    info = json.loads(q.stdout)
    v = next(s for s in info["streams"] if s["codec_name"] == "h264")
    a = next(s for s in info["streams"] if s["codec_name"] == "aac")
    ok = int(v["nb_read_packets"]) == NFRAMES and abs(float(v["duration"]) - TOTAL) < 1e-3 and abs(float(a["duration"]) - TOTAL) < 0.03
    log(f"  check: video {v['width']}x{v['height']} {v['profile']} {v['pix_fmt']} {v['r_frame_rate']} "
        f"{v['nb_read_packets']} frames {float(v['duration']):.3f} s start {v['start_time']}; "
        f"audio {a['sample_rate']} Hz {float(a['duration']):.3f} s start {a['start_time']}; "
        f"container {float(info['format']['duration']):.3f} s -> {'OK' if ok else 'MISMATCH'}")
    if not ok:
        warn("duration/frame count check failed")


if __name__ == "__main__":
    main()
