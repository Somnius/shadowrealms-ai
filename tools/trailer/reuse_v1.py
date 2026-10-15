#!/usr/bin/env python3
"""Bring the v1 assets that trailer v2 reuses into the v2 data folder (the v1 folder is only read).

From the timeline's "reuse" block: every listed clip is copied for both languages under its new
name, with its shots.json entry (the marks) carried over; the fonts and the fog texture are copied
too when missing. Idempotent: existing files of the same size are left alone.

Usage: python3 tools/trailer/reuse_v1.py [--timeline tools/trailer/timeline_v2.json] [--from DIR]
  --from DIR   where the v1 assets are (default: the timeline's reuse.from, relative to the repo root;
               from a git worktree point it at the main checkout's data/trailer)
"""
import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def copy(src, dst):
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return "="
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "+"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=str(HERE / "timeline_v2.json"))
    ap.add_argument("--from", dest="src", help="folder with the v1 assets (default: the timeline's reuse.from)")
    args = ap.parse_args()
    tl = json.loads(Path(args.timeline).read_text())
    data = ROOT / tl.get("data_dir", "data/trailer")
    reuse = tl.get("reuse")
    if not reuse:
        raise SystemExit(f"{args.timeline}: no 'reuse' block")
    src_root = Path(args.src).resolve() if args.src else ROOT / reuse["from"]
    if src_root.resolve() == data.resolve():
        raise SystemExit("reuse source and data_dir are the same folder")
    if not (src_root / "clips/en/shots.json").exists():
        raise SystemExit(f"no v1 clips under {src_root} (pass --from <main checkout>/data/trailer)")

    for sub in ("fonts", "cache"):
        for f in sorted((src_root / sub).glob("*")):
            if f.is_file():
                print(f"  {copy(f, data / sub / f.name)} {(data / sub / f.name).relative_to(ROOT)}")

    for lang in ("en", "el"):
        meta_path = data / "clips" / lang / "shots.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        src_meta = json.loads((src_root / "clips" / lang / "shots.json").read_text())
        for new, old in reuse["clips"].items():
            src = src_root / "clips" / lang / f"{old}.mp4"
            dst = data / "clips" / lang / f"{new}.mp4"
            tag = copy(src, dst)
            entry = dict(src_meta[old])
            entry["path"] = str(dst.relative_to(ROOT))
            entry["reused_from"] = str(src)
            meta[new] = entry
            print(f"  {tag} {dst.relative_to(ROOT)}  <- {src}  marks: "
                  + ", ".join(k for k, v in entry.items() if k.endswith("_at")))
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        print(f"  shots.json -> {meta_path.relative_to(ROOT)} ({len(meta)} clips)")


if __name__ == "__main__":
    main()
