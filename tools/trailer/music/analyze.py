#!/usr/bin/env python3
"""
Analytic listen for the trailer score: loudness, true peak, clipping, RMS per 2 s window,
the 68.0 hit onset, the 68.5-69.5 silence, the end silence, and a spectrogram PNG.

    python tools/trailer/music/analyze.py [data/trailer/music/score.wav]
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


def to_db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/trailer/music/score.wav")
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    n = len(x)
    info = sf.info(path)
    print(f"{path}: {info.samplerate} Hz, {info.channels} ch, {info.subtype}, {n / sr:.3f} s ({n} samples)")

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
        seg = x[s:s + 2 * sr]
        rows.append((s / sr, float(to_db(np.sqrt(np.mean(seg ** 2))))))
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
        y = signal.sosfilt(sos, seg, axis=0)
        return float(to_db(np.sqrt(np.mean(y ** 2))))

    print("\nBand RMS per section (dBFS): <120 | 120-500 | 500-2k | 2k-6k | 6k-16k")
    sections = [(0, 15, "intro"), (15, 27, "organ"), (27, 41, "toms"), (41, 60, "pulse"), (60, 68, "riser"),
                (69.5, 76, "tension"), (76, 86, "choir"), (86, 98, "tight pulse"), (98, 108, "theme"), (108, 120, "outro")]
    for a, b, name in sections:
        seg = x[int(a * sr):int(b * sr)]
        vals = [band_rms(seg, 20, 120), band_rms(seg, 120, 500), band_rms(seg, 500, 2000), band_rms(seg, 2000, 6000), band_rms(seg, 6000, 16000)]
        print(f"  {name:12s} {a:5.1f}-{b:5.1f}: " + " | ".join(f"{v:6.1f}" for v in vals))

    # the hit: energy envelope at 1 ms, find the biggest jump between 67.0 and 68.6
    hop = sr // 1000
    env = np.array([np.sqrt(np.mean(x[s:s + hop] ** 2)) for s in range(int(67.0 * sr), int(68.6 * sr), hop)])
    env_db = to_db(env)
    jump = np.diff(env_db)
    i0 = int(np.argmax(jump))
    print(f"\nlargest 1 ms energy jump anywhere in 67.0-68.6: {67.0 + (i0 + 1) / 1000:.3f} s ({jump[i0]:.1f} dB)")
    lo, hi = 850, 1150  # 67.85-68.15
    i = lo + int(np.argmax(jump[lo:hi]))
    onset = 67.0 + (i + 1) / 1000
    print(f"hit onset (largest 1 ms energy jump in 67.85-68.15): {onset:.3f} s (jump {jump[i]:.1f} dB, "
          f"level before {env_db[i]:.1f} dBFS, after {env_db[i + 1]:.1f} dBFS)")
    w50 = sr // 20
    r50 = np.array([np.sqrt(np.mean(x[s:s + w50] ** 2)) for s in range(0, n - w50, w50)])
    j = int(np.argmax(r50))
    print(f"loudest 50 ms window of the piece: {j * 0.05:.2f} s at {float(to_db(r50[j])):.1f} dBFS; "
          f"hit window 68.00-68.05: {float(to_db(r50[1360])):.1f} dBFS")
    pre = x[int(67.70 * sr):int(67.98 * sr)]
    print(f"pre-hit gap 67.70-67.98 RMS: {float(to_db(np.sqrt(np.mean(pre ** 2)))):.1f} dBFS")
    sil = x[int(68.5 * sr):int(69.5 * sr)]
    print(f"silence 68.5-69.5: max |x| = {float(np.max(np.abs(sil))):.2e} ({float(to_db(np.max(np.abs(sil)))):.1f} dBFS)")
    tail = x[int(119.6 * sr):]
    print(f"end 119.6-120.0: max |x| = {float(np.max(np.abs(tail))):.2e}")
    head = x[: int(0.05 * sr)]
    print(f"start 0-0.05: max |x| = {float(np.max(np.abs(head))):.2e}")
    for t in (73.0, 113.0, 15.0, 24.5, 41.0, 76.0, 98.0):
        a = x[int((t - 0.1) * sr):int(t * sr)]
        b = x[int(t * sr):int((t + 0.1) * sr)]
        print(f"  level around {t:6.1f}: before {float(to_db(np.sqrt(np.mean(a ** 2)))):6.1f} -> after {float(to_db(np.sqrt(np.mean(b ** 2)))):6.1f} dBFS")

    # spectrogram
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    mono = x.mean(axis=1)
    f, t, S = signal.spectrogram(mono, fs=sr, nperseg=4096, noverlap=3072, scaling="spectrum", mode="magnitude")
    Sdb = to_db(S)
    fig, ax = plt.subplots(figsize=(24, 8), dpi=100)
    im = ax.pcolormesh(t, f, Sdb, shading="nearest", cmap="magma", vmin=-110, vmax=-20)
    ax.set_yscale("symlog", linthresh=200)
    ax.set_ylim(20, 20000)
    ax.set_yticks([30, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_yticklabels(["30", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    ax.set_xticks(range(0, 121, 5))
    for ct, lab in [(2, "hb"), (6, "bell"), (15, "organ"), (24.5, "create"), (27, "toms"), (41, "pulse"), (60, "riser"),
                    (68, "HIT"), (73, "botch"), (76, "choir"), (86, "tight"), (98, "theme"), (108, "fade"), (113, "bell")]:
        ax.axvline(ct, color="cyan", lw=0.6, alpha=0.6)
        ax.text(ct + 0.2, 15000, lab, color="cyan", fontsize=8)
    ax.set_xlabel("s")
    ax.set_ylabel("Hz")
    ax.set_title(f"{path.name}: {lufs:.1f} LUFS, true peak {tp:.1f} dBTP")
    fig.colorbar(im, ax=ax, pad=0.01, label="dB")
    fig.tight_layout()
    png = path.parent / "spectrogram.png"
    fig.savefig(png)
    print(f"\nspectrogram -> {png}")
    json.dump({"lufs": lufs, "true_peak_dbtp": tp, "sample_peak_dbfs": peak, "clipped_samples": clipped,
               "hit_onset_s": onset, "rms_2s": rows}, open(path.parent / "analysis.json", "w"), indent=1)


if __name__ == "__main__":
    main()
