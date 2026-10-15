#!/usr/bin/env python3
"""
Analytic listen for the trailer score: loudness, true peak, clipping, RMS per 2 s window,
band balance per section, the onsets of the hit / the botch hit / the theme downbeat / the last
bell against the cue sheet, the silence after the hit, the end silence, and a spectrogram PNG.

    python tools/trailer/music/analyze.py [score.wav] [--preset v1|v2]

The cue sheet (cues.py) is chosen by --preset, else by the "preset" of the cues.json next to the
file, else by the file's length. Default file: <preset data_dir>/music/score.wav.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cues import DEFAULT, PRESETS, by_duration  # noqa: E402


def to_db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def rms_db(seg):
    return float(to_db(np.sqrt(np.mean(seg ** 2)))) if len(seg) else float("nan")


def onset(x, sr, t, search=0.15, window=(1.0, 0.6), hp_hz=200.0, rise_db=6.0):
    """Onset of the event cued at t, on a 1 ms RMS envelope of the signal high-passed at hp_hz
    (unfiltered, the sub drone's 37 Hz cycles swing the envelope by 15 dB and hide a quiet bell).
    First attack: the first 1 ms frame within +-search s of t that is >= 3 dB above the loudest
    frame 5-25 ms before it (so a ramped attack is not its own baseline) and is followed within
    5 ms by a frame >= rise_db above that baseline. Also the largest single-frame jump (within
    +-search, and anywhere in [t-window[0], t+window[1]]). 't' is the first attack, or the largest
    jump when nothing rises that much."""
    hop = sr // 1000
    a, b = int((t - window[0]) * sr), int((t + window[1]) * sr)
    lead = min(a, int(0.5 * sr))
    seg = x[a - lead:b]
    if hp_hz:
        seg = signal.sosfilt(signal.butter(2, hp_hz, btype="high", fs=sr, output="sos"), seg, axis=0)
    seg = seg[lead:]
    env_db = to_db(np.array([np.sqrt(np.mean(seg[s:s + hop] ** 2)) for s in range(0, b - a, hop)]))
    jump = np.diff(env_db)
    i_any = int(np.argmax(jump))
    lo, hi = int((window[0] - search) * 1000), int((window[0] + search) * 1000)
    i = lo + int(np.argmax(jump[lo:hi]))
    attack = base = None
    for j in range(lo + 1, hi + 1):
        base = float(env_db[max(0, j - 25):max(1, j - 5)].max())
        peak = float(env_db[j:j + 6].max())
        # the entry frame must belong to the attack (within 12 dB of its level), and the attack must be
        # a real event (>= -45 dBFS), not the noise floor of a near-silent stem
        if env_db[j] >= base + 3.0 and peak >= base + rise_db and peak >= -45.0 and env_db[j] >= peak - 12.0:
            attack = j
            break
    t0 = t - window[0]
    at = None if attack is None else round(t0 + attack / 1000, 3)
    return {"t": at if at is not None else round(t0 + (i + 1) / 1000, 3), "attack_t": at,
            "attack_before_dbfs": None if attack is None else round(base, 1),
            "attack_dbfs": None if attack is None else round(float(env_db[attack:attack + 6].max()), 1),
            "jump_t": round(t0 + (i + 1) / 1000, 3), "jump_db": round(float(jump[i]), 1),
            "before_dbfs": round(float(env_db[i]), 1), "after_dbfs": round(float(env_db[i + 1]), 1),
            "largest_anywhere_t": round(t0 + (i_any + 1) / 1000, 3), "largest_anywhere_db": round(float(jump[i_any]), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    args = ap.parse_args()
    C = PRESETS[args.preset] if args.preset else None
    path = Path(args.path or f"{(C or PRESETS[DEFAULT]).data_dir}/music/score.wav")
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    n = len(x)
    info = sf.info(path)
    if C is None:
        sib = path.parent / "cues.json"
        if sib.exists() and json.loads(sib.read_text()).get("preset") in PRESETS:
            C = PRESETS[json.loads(sib.read_text())["preset"]]
        else:
            C = by_duration(n / sr)
    if C is None:
        sys.exit(f"{path}: {n / sr:.3f} s matches no preset; pass --preset")
    print(f"{path}: {info.samplerate} Hz, {info.channels} ch, {info.subtype}, {n / sr:.3f} s ({n} samples); cue sheet: preset {C.name} ({C.dur} s)")
    if abs(n / sr - C.dur) > 1e-3:
        print(f"WARNING: length {n / sr:.3f} s differs from the preset's {C.dur} s")

    import pyloudnorm as pyln
    meter = pyln.Meter(sr)
    lufs = meter.integrated_loudness(x)
    up = signal.resample_poly(x, 4, 1, axis=0)
    tp = float(to_db(np.max(np.abs(up))))
    peak = float(to_db(np.max(np.abs(x))))
    clipped = int(np.sum(np.abs(x) >= 0.9999))
    print(f"integrated {lufs:.2f} LUFS | sample peak {peak:.2f} dBFS | true peak {tp:.2f} dBTP | samples >= -0.001 dBFS: {clipped}")

    # short-term loudness (3 s) max, for the dynamics range
    win = 3 * sr
    st = []
    for s in range(0, n - win, sr):
        seg = x[s:s + win]
        if np.max(np.abs(seg)) > 1e-5:
            st.append((s / sr, meter.integrated_loudness(seg)))
    st_vals = [v for _, v in st if np.isfinite(v)]
    print(f"short-term (3 s) loudness: max {max(st_vals):.1f} LUFS at {[t for t, v in st if v == max(st_vals)][0]:.0f} s, "
          f"min {min(st_vals):.1f} LUFS")

    # RMS per 2 s window (both channels)
    print("\nRMS per 2 s window (dBFS):")
    rows = []
    for s in range(0, n, 2 * sr):
        rows.append((s / sr, rms_db(x[s:s + 2 * sr])))
    line = []
    for t, r in rows:
        line.append(f"{t:5.0f}s {r:6.1f}")
        if len(line) == 6:
            print("  " + " | ".join(line))
            line = []
    if line:
        print("  " + " | ".join(line))

    # band energy (low/mid/high) per section, to spot mud or harshness
    def band_rms(seg, lo, hi):
        sos = signal.butter(4, [lo, hi], btype="band", fs=sr, output="sos")
        return rms_db(signal.sosfilt(sos, seg, axis=0))

    print("\nBand RMS per section (dBFS): <120 | 120-500 | 500-2k | 2k-6k | 6k-16k")
    for a, b, name in C.sections:
        seg = x[int(a * sr):int(b * sr)]
        vals = [band_rms(seg, 20, 120), band_rms(seg, 120, 500), band_rms(seg, 500, 2000), band_rms(seg, 2000, 6000), band_rms(seg, 6000, 16000)]
        print(f"  {name:12s} {a:5.1f}-{b:5.1f}: " + " | ".join(f"{v:6.1f}" for v in vals))

    # the hits: 1 ms energy envelope (high-passed at 200 Hz), first attack and biggest jump near each
    # cue, on the master and (when the stems are next to it) on the perc and fx stems
    onsets = {}
    stems = {k: sf.read(path.parent / "score_stems" / f"{k}.wav", dtype="float64", always_2d=True)[0]
             for k in ("perc", "fx") if (path.parent / "score_stems" / f"{k}.wav").exists()}
    print("\nonsets (1 ms RMS envelope, > 200 Hz): first attack = first frame >= 3 dB over the 5-25 ms before it, "
          "+6 dB within 5 ms; tolerance +-5 ms")
    for name, t in (("hit", C.hit), ("hit2 (botch)", C.hit2), ("theme downbeat", C.theme), ("last bell", C.last_bell)):
        o = onsets[name] = onset(x, sr, t)
        flag = "" if abs(o["t"] - t) <= 0.005 else "   <-- OFF by {:+.3f} s".format(o["t"] - t)
        att = (f"first attack {o['attack_t']:7.3f} s ({o['attack_before_dbfs']:6.1f} -> {o['attack_dbfs']:6.1f} dBFS)" if o["attack_t"] is not None
               else "no 6 dB attack in the window")
        print(f"{name:15s} cue {t:7.3f}: {att}; largest jump {o['jump_t']:7.3f} s ({o['jump_db']:4.1f} dB, "
              f"{o['before_dbfs']:6.1f} -> {o['after_dbfs']:6.1f}); largest in [{t - 1.0:.1f}, {t + 0.6:.1f}] at {o['largest_anywhere_t']:.3f}{flag}")
        for k, s in stems.items():
            so = o[f"stem_{k}"] = onset(s, sr, t)
            sflag = "" if abs(so["t"] - t) <= 0.005 else "   <-- OFF by {:+.3f} s".format(so["t"] - t)
            print(f"{'':15s}   {k:4s} stem: first attack {so['attack_t'] if so['attack_t'] is not None else '   none'} s, "
                  f"largest jump {so['jump_t']:7.3f} s ({so['jump_db']:4.1f} dB){sflag}")
    w50 = sr // 20
    r50 = np.array([np.sqrt(np.mean(x[s:s + w50] ** 2)) for s in range(0, n - w50, w50)])
    j = int(np.argmax(r50))
    jh = int(round(C.hit / 0.05))
    print(f"loudest 50 ms window of the piece: {j * 0.05:.2f} s at {float(to_db(r50[j])):.1f} dBFS; "
          f"hit window {C.hit:.2f}-{C.hit + 0.05:.2f}: {float(to_db(r50[jh])):.1f} dBFS")
    print(f"pre-hit gap {C.hit - 0.30:.2f}-{C.hit - 0.02:.2f} RMS: {rms_db(x[int((C.hit - 0.30) * sr):int((C.hit - 0.02) * sr)]):.1f} dBFS")
    sil = x[int(C.silence[0] * sr):int(C.silence[1] * sr)]
    sil_max = float(np.max(np.abs(sil)))
    print(f"silence {C.silence[0]}-{C.silence[1]}: max |x| = {sil_max:.2e} ({float(to_db(sil_max)):.1f} dBFS)")
    tail = x[int(C.end_gate[1] * sr):]
    print(f"end {C.end_gate[1]}-{C.dur}: max |x| = {float(np.max(np.abs(tail))):.2e}")
    head = x[: int(0.05 * sr)]
    print(f"start 0-0.05: max |x| = {float(np.max(np.abs(head))):.2e}")
    for t in C.level_checks:
        a = x[int((t - 0.1) * sr):int(t * sr)]
        b = x[int(t * sr):int((t + 0.1) * sr)]
        print(f"  level around {t:6.1f}: before {rms_db(a):6.1f} -> after {rms_db(b):6.1f} dBFS")

    # spectrogram
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mono = x.mean(axis=1)
    f, t, S = signal.spectrogram(mono, fs=sr, nperseg=4096, noverlap=3072, scaling="spectrum", mode="magnitude")
    Sdb = to_db(S)
    fig, ax = plt.subplots(figsize=(24 * C.dur / 120.0, 8), dpi=100)
    im = ax.pcolormesh(t, f, Sdb, shading="nearest", cmap="magma", vmin=-110, vmax=-20)
    ax.set_yscale("symlog", linthresh=200)
    ax.set_ylim(20, 20000)
    ax.set_yticks([30, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_yticklabels(["30", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    ax.set_xticks(range(0, int(C.dur) + 1, 5))
    for ct, lab in C.labels:
        ax.axvline(ct, color="cyan", lw=0.6, alpha=0.6)
        ax.text(ct + 0.2, 15000, lab, color="cyan", fontsize=8)
    ax.set_xlabel("s")
    ax.set_ylabel("Hz")
    ax.set_title(f"{path.name} (preset {C.name}): {lufs:.1f} LUFS, true peak {tp:.1f} dBTP")
    fig.colorbar(im, ax=ax, pad=0.01, label="dB")
    fig.tight_layout()
    png = path.parent / "spectrogram.png"
    fig.savefig(png)
    print(f"\nspectrogram -> {png}")
    json.dump({"preset": C.name, "lufs": lufs, "true_peak_dbtp": tp, "sample_peak_dbfs": peak, "clipped_samples": clipped,
               "hit_onset_s": onsets["hit"]["t"], "onsets": onsets, "silence_max_abs": sil_max,
               "rms_2s": rows}, open(path.parent / "analysis.json", "w"), indent=1)


if __name__ == "__main__":
    main()
