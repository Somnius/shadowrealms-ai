#!/usr/bin/env python3
"""
Original score for the ShadowRealms AI trailer (120.0 s), synthesized from code.

Everything here is generated: no samples, no loops, no external audio. The render
is deterministic (fixed seed). Cue times follow tools/trailer/CUES.md.

Usage (from the repo root, inside the python:3.12-slim container or any Python
with numpy/scipy/soundfile/pyloudnorm):

    python tools/trailer/music/compose.py [--out data/trailer/music]

Outputs: score.wav (48 kHz / 24-bit / stereo / 120.000 s), score_stems/*.wav
(32-bit float, same gain as the master, no limiter), cues.json.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import ndimage, signal

SR = 48000
DUR = 120.0
N = int(SR * DUR)
SEED = 20261004
TWO_PI = 2.0 * math.pi
rng = np.random.default_rng(SEED)

# Binding cue times (tools/trailer/CUES.md)
T_HIT = 68.0
T_SILENCE = (68.5, 69.5)
T_HIT2 = 73.0
T_LAST_BELL = 113.0

CUES: list[tuple[float, str]] = []


def cue(t: float, text: str) -> None:
    CUES.append((round(float(t), 3), text))


# ----------------------------------------------------------------------------- utils
def sec(s: float) -> int:
    return int(round(s * SR))


def taxis(n: int) -> np.ndarray:
    return np.arange(n) / SR


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def to_db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-12))


NOTE_PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6,
           "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def hz(name: str) -> float:
    pc, octv = (name[:2], name[2:]) if name[1] in "#b" else (name[:1], name[1:])
    midi = 12 * (int(octv) + 1) + NOTE_PC[pc]
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def gate_env(n: int, att: float, rel: float) -> np.ndarray:
    """Raised-cosine attack, sustain, raised-cosine release occupying the last `rel` s."""
    env = np.ones(n)
    a = min(sec(att), n)
    r = min(sec(rel), n)
    if a > 0:
        env[:a] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    if r > 0:
        env[n - r:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, r))
    return env


def stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """Equal-power pan, pan in [-1, 1]."""
    a = (pan + 1.0) * math.pi / 4.0
    return np.stack([mono * math.cos(a), mono * math.sin(a)], axis=1)


def place(buf: np.ndarray, sig: np.ndarray, t: float, gain: float = 1.0) -> None:
    i = sec(t)
    if sig.ndim == 1:
        sig = stereo(sig)
    m = min(len(sig), N - i)
    if m > 0:
        buf[i:i + m] += sig[:m] * gain


def butter_sos(order: int, fc, btype: str):
    return signal.butter(order, fc, btype=btype, fs=SR, output="sos")


def hp(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(butter_sos(order, fc, "high"), x, axis=0)


def lp(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(butter_sos(order, fc, "low"), x, axis=0)


def bp(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(butter_sos(order, [lo, hi], "band"), x, axis=0)


def biquad_var(x: np.ndarray, kind: str, fc, q, block: int = 256) -> np.ndarray:
    """RBJ biquad with time-varying cutoff/Q, coefficients updated per block."""
    n = len(x)
    fc = np.broadcast_to(np.asarray(fc, float), (n,))
    q = np.broadcast_to(np.asarray(q, float), (n,))
    y = np.empty(n)
    zi = np.zeros((1, 2))
    for s in range(0, n, block):
        e = min(n, s + block)
        f = min(float(fc[s]), SR * 0.45)
        w0 = TWO_PI * f / SR
        cw, sw = math.cos(w0), math.sin(w0)
        alpha = sw / (2.0 * float(q[s]))
        if kind == "lp":
            b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
        elif kind == "hp":
            b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
        elif kind == "bp":
            b0, b1, b2 = alpha, 0.0, -alpha
        else:
            raise ValueError(kind)
        a0, a1, a2 = 1 + alpha, -2 * cw, 1 - alpha
        sos = np.array([[b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0]])
        y[s:e], zi = signal.sosfilt(sos, x[s:e], zi=zi)
    return y


def saw(freq, n: int, phase0: float = 0.0) -> np.ndarray:
    """PolyBLEP band-limited sawtooth; freq scalar or per-sample array (Hz)."""
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    dt = f / SR
    ph = (phase0 + np.cumsum(dt)) % 1.0
    y = 2.0 * ph - 1.0
    m = ph < dt
    tt = ph[m] / dt[m]
    y[m] -= tt + tt - tt * tt - 1.0
    m = ph > 1.0 - dt
    tt = (ph[m] - 1.0) / dt[m]
    y[m] -= tt * tt + tt + tt + 1.0
    return y


def soft(x: np.ndarray, drive: float = 1.3) -> np.ndarray:
    return np.tanh(drive * x) / math.tanh(drive)


def normalize(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(x)))
    return x * (peak / m) if m > 1e-9 else x


# ----------------------------------------------------------------------------- instruments
ORGAN_REGS = {
    # partial ratio -> drawbar level (16', 8', 5 1/3', 4', 2 2/3', 2', 1 3/5', 1 1/3', 1')
    "doom":   {0.5: 1.0, 1.0: 0.9, 1.5: 0.3, 2.0: 0.35, 3.0: 0.1, 4.0: 0.06, 6.0: 0.03},
    "warm":   {0.5: 0.5, 1.0: 1.0, 2.0: 0.5, 3.0: 0.18, 4.0: 0.12, 6.0: 0.04},
    "bright": {1.0: 1.0, 1.5: 0.4, 2.0: 0.8, 3.0: 0.45, 4.0: 0.55, 5.0: 0.2, 6.0: 0.18, 8.0: 0.22, 10.0: 0.1, 12.0: 0.08, 16.0: 0.05},
    "full":   {0.5: 0.9, 1.0: 1.0, 1.5: 0.5, 2.0: 0.8, 3.0: 0.45, 4.0: 0.55, 5.0: 0.25, 6.0: 0.2, 8.0: 0.25, 10.0: 0.12, 12.0: 0.1, 16.0: 0.06},
}


def organ(freq: float, dur: float, reg: str = "doom", vel: float = 1.0, att: float = 0.04,
          rel: float = 0.3, leslie=0.7, vib: float = 0.0025, drive: float = 1.3) -> np.ndarray:
    """Additive drawbar organ with slow vibrato and a leslie-like AM that is opposite in L/R.
    leslie: rate in Hz, or (start, end) for a ramp."""
    n = sec(dur + rel)
    t = taxis(n)
    if isinstance(leslie, tuple):
        rate = np.linspace(leslie[0], leslie[1], n)
    else:
        rate = np.full(n, float(leslie))
    les_phase = TWO_PI * np.cumsum(rate) / SR
    regs = ORGAN_REGS[reg]
    out = np.zeros((n, 2))
    for ch in (0, 1):
        vibr = 1.0 + vib * np.sin(TWO_PI * 5.6 * t + rng.uniform(0, TWO_PI))
        ph = np.cumsum(freq * vibr) / SR
        sig = np.zeros(n)
        for ratio, amp in regs.items():
            if freq * ratio >= 18000:
                continue
            sig += amp * np.sin(TWO_PI * ratio * ph + rng.uniform(0, TWO_PI))
        am = 1.0 + 0.1 * np.sin(les_phase + ch * math.pi)
        out[:, ch] = sig * am
    out /= sum(regs.values())
    # chiff: a short breath of filtered noise at key-on
    nb = sec(0.012)
    chiff = bp(rng.standard_normal(nb), 800, 4000) * np.exp(-np.arange(nb) / (nb / 3))
    out[:nb] += 0.05 * chiff[:, None]
    out = soft(out, drive) * gate_env(n, att, rel)[:, None]
    return out * vel


BELL_MODES = [  # (frequency ratio, amplitude, relative decay) - church bell-ish inharmonic set
    (0.5, 0.9, 1.0), (1.0, 1.0, 0.85), (1.183, 0.55, 0.6), (1.5, 0.45, 0.55), (2.0, 0.7, 0.45),
    (2.52, 0.3, 0.3), (2.98, 0.25, 0.28), (3.41, 0.12, 0.2), (4.07, 0.1, 0.15), (5.33, 0.05, 0.1),
]


def bell(freq: float, dur: float = 7.0, vel: float = 1.0, t60: float = 6.0, bright: float = 1.0) -> np.ndarray:
    """Modal bell: inharmonic decaying partials, slightly detuned per channel (warble), strike noise."""
    n = sec(dur)
    t = taxis(n)
    out = np.zeros((n, 2))
    for ratio, amp, rel in BELL_MODES:
        fr = freq * ratio
        if fr > 16000:
            continue
        tau = t60 * rel / 6.91
        a = amp * (bright if ratio > 1.5 else 1.0)
        for ch in (0, 1):
            det = 1.0 + rng.uniform(-0.0012, 0.0012)
            out[:, ch] += a * np.exp(-t / tau) * np.sin(TWO_PI * fr * det * t + rng.uniform(0, TWO_PI))
    nb = sec(0.012)
    strike = bp(rng.standard_normal(nb), 1500, 7000) * np.exp(-np.arange(nb) / (nb / 4))
    out[:nb] += 0.35 * strike[:, None]
    a = sec(0.0015)
    out[:a] *= np.linspace(0, 1, a)[:, None]
    return normalize(out) * vel


def thump(f0: float, f1: float, dur: float, amp: float = 1.0, drop: float = 0.08) -> np.ndarray:
    """Sine with exponential pitch drop (f0 -> f1) and exponential decay: kicks, hearts, booms."""
    n = sec(dur)
    t = taxis(n)
    f = f1 + (f0 - f1) * np.exp(-t / drop)
    env = np.exp(-t / (dur / 4.5)) * (1.0 - np.exp(-t / 0.003))
    return amp * np.sin(TWO_PI * np.cumsum(f) / SR) * env


def heartbeat(vel: float = 1.0) -> np.ndarray:
    n = sec(0.9)
    y = np.zeros(n)
    a = thump(64, 38, 0.5, 1.0)
    y[:len(a)] += a
    b = thump(72, 44, 0.38, 0.6)
    o = sec(0.19)
    y[o:o + len(b)] += b
    y = lp(y, 160, 2)
    return normalize(stereo(y)) * vel


def tom(freq: float = 73.0, vel: float = 1.0, dur: float = 0.7, pan: float = 0.0) -> np.ndarray:
    n = sec(dur)
    t = taxis(n)
    f = freq * (1.0 + 0.7 * np.exp(-t / 0.045))
    body = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t / (dur / 4.0))
    skin = bp(rng.standard_normal(n), 150, 1200) * np.exp(-t / 0.025) * 0.6
    y = soft(body + skin, 1.6) * (1.0 - np.exp(-t / 0.001))
    return normalize(stereo(y, pan)) * vel


def kick(vel: float = 1.0, dur: float = 0.4) -> np.ndarray:
    n = sec(dur)
    t = taxis(n)
    f = 48.0 * (1.0 + 2.8 * np.exp(-t / 0.028))
    body = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t / 0.11)
    nc = sec(0.004)
    click = hp(rng.standard_normal(nc), 2500) * np.exp(-np.arange(nc) / (nc / 3)) * 0.35
    body[:nc] += click
    y = soft(body, 1.8) * (1.0 - np.exp(-t / 0.0008))
    return normalize(stereo(y)) * vel


def hat(vel: float = 1.0, dur: float = 0.035) -> np.ndarray:
    n = sec(dur)
    out = np.zeros((n, 2))
    for ch in (0, 1):
        out[:, ch] = hp(rng.standard_normal(n), 7000, 4) * np.exp(-np.arange(n) / (n / 4))
    return normalize(out) * vel


def burst(dur: float = 0.06, lo: float = 200.0, hi: float = 8000.0, vel: float = 1.0) -> np.ndarray:
    n = sec(dur)
    out = np.zeros((n, 2))
    for ch in (0, 1):
        out[:, ch] = bp(rng.standard_normal(n), lo, hi) * np.exp(-np.arange(n) / (n / 4))
    return normalize(out) * vel


def riser(dur: float, f0: float = 150.0, f1: float = 7000.0, q: float = 2.5, curve: float = 2.2,
          vel: float = 1.0) -> np.ndarray:
    """Band-passed noise whose centre sweeps up exponentially while the level rises."""
    n = sec(dur)
    t = taxis(n)
    fc = f0 * (f1 / f0) ** (t / dur)
    env = (t / dur) ** curve
    out = np.zeros((n, 2))
    for ch in (0, 1):
        out[:, ch] = biquad_var(rng.standard_normal(n), "bp", fc, q, block=256) * env
    out *= gate_env(n, 0.0, 0.06)[:, None]
    return normalize(out) * vel


VOWELS = {  # formant (Hz, level dB, bandwidth Hz)
    "oo": [(300, 0, 55), (870, -16, 80), (2240, -24, 110), (2800, -30, 130)],
    "oh": [(430, 0, 60), (850, -8, 80), (2620, -22, 120), (3000, -28, 140)],
    "ah": [(700, 0, 90), (1200, -5, 100), (2600, -20, 130), (3300, -26, 150)],
}


def choir_note(freq: float, dur: float, vel: float = 1.0, vowels=("oo", "ah"), morph=(0.0, 1.0),
               att: float = 1.0, rel: float = 1.2, nvoices: int = 3) -> np.ndarray:
    """Choir-like voice: detuned saws with slow vibrato and breath, through a formant bank that
    morphs between two vowels over the note."""
    n = sec(dur + rel)
    t = taxis(n)
    m = np.interp(t, [0.0, dur], [morph[0], morph[1]])
    out = np.zeros((n, 2))
    for ch in (0, 1):
        src = np.zeros(n)
        for _ in range(nvoices):
            det = 2.0 ** (rng.uniform(-9, 9) / 1200.0)
            vib = 1.0 + rng.uniform(0.003, 0.006) * np.sin(TWO_PI * rng.uniform(4.6, 5.8) * t + rng.uniform(0, TWO_PI)) \
                * np.clip(t / 1.2, 0, 1)
            src += saw(freq * det * vib, n, rng.uniform(0, 1))
        src /= nvoices
        src += 0.03 * rng.standard_normal(n)
        y = np.zeros(n)
        for i in range(4):
            fa, ga, ba = VOWELS[vowels[0]][i]
            fb, gb, bb = VOWELS[vowels[1]][i]
            fc = fa * (1 - m) + fb * m
            bw = ba * (1 - m) + bb * m
            g = ga * (1 - m) + gb * m
            y += (10 ** (g / 20.0)) * biquad_var(src, "bp", fc, fc / bw, block=256)
        out[:, ch] = y
    out = normalize(out) * gate_env(n, att, rel)[:, None]
    return out * vel


def pad(names, dur: float, vel: float = 1.0, att: float = 2.0, rel: float = 2.5,
        cutoff=(300.0, 1200.0), q: float = 0.8, width: float = 0.12) -> np.ndarray:
    """Four detuned, spread polyBLEP saws per note through a slowly opening low-pass."""
    n = sec(dur + rel)
    t = taxis(n)
    out = np.zeros((n, 2))
    pans = [-0.75, -0.25, 0.25, 0.75]
    dets = [-width, -width / 3, width / 3, width]
    for name in names:
        f0 = hz(name)
        for d, p in zip(dets, pans):
            drift = 1.0 + 0.0015 * np.sin(TWO_PI * rng.uniform(0.05, 0.2) * t + rng.uniform(0, TWO_PI))
            out += stereo(saw(f0 * 2.0 ** (d / 12.0) * drift, n, rng.uniform(0, 1)), p)
    c = np.interp(t, [0.0, dur], [cutoff[0], cutoff[1]])
    for ch in (0, 1):
        out[:, ch] = biquad_var(out[:, ch], "lp", c, q, block=512)
    out = normalize(out) * gate_env(n, att, rel)[:, None]
    return out * vel


def bass_note(freq: float, dur: float, vel: float = 1.0, cut=(2200.0, 260.0), q: float = 1.6,
              sub: float = 0.5, rel: float = 0.04) -> np.ndarray:
    """Darkwave synth bass: two slightly detuned saws through a snappy filter envelope + sine sub."""
    n = sec(dur + rel)
    t = taxis(n)
    s = saw(freq, n, rng.uniform(0, 1)) + 0.45 * saw(freq * 1.003, n, rng.uniform(0, 1))
    c = cut[1] + (cut[0] - cut[1]) * np.exp(-t / 0.09)
    y = biquad_var(s, "lp", c, q, block=96)
    y = y / 1.45 + sub * np.sin(TWO_PI * freq * t)
    env = gate_env(n, 0.004, rel) * (0.6 + 0.4 * np.exp(-t / 0.15))
    return stereo(soft(y, 1.6) * env) * vel


def drone(freq: float, dur: float, vel: float = 1.0, att: float = 3.0, rel: float = 2.0) -> np.ndarray:
    """Sub drone: sine at f, sine at 2f, a dark saw at 2f; slow breathing."""
    n = sec(dur + rel)
    t = taxis(n)
    y = 0.6 * np.sin(TWO_PI * freq * t) + 0.6 * np.sin(TWO_PI * 2 * freq * t + 1.0)
    y += 0.3 * lp(saw(2 * freq, n, rng.uniform(0, 1)), 220, 2)
    y *= 1.0 + 0.12 * np.sin(TWO_PI * 0.13 * t + rng.uniform(0, TWO_PI))
    y = normalize(y) * gate_env(n, att, rel)
    return stereo(y) * vel


# ----------------------------------------------------------------------------- reverb
def make_ir(length: float = 4.0, predelay: float = 0.018) -> np.ndarray:
    """Cathedral-ish impulse response: sparse early reflections + decorrelated late noise with
    frequency-dependent decay (lows ~4.2 s, mids ~3.4 s, highs ~1.6 s)."""
    n = sec(length)
    t = taxis(n)
    ir = np.zeros((n, 2))
    for ch in (0, 1):
        noise = rng.standard_normal(n)
        late = (lp(noise, 250) * np.exp(-6.91 * t / 4.2)
                + bp(noise, 250, 2500) * np.exp(-6.91 * t / 3.4)
                + hp(noise, 2500) * np.exp(-6.91 * t / 1.6) * 0.7)
        late *= 1.0 - np.exp(-t / 0.025)
        early = np.zeros(n)
        for _ in range(12):
            early[sec(rng.uniform(0.006, 0.085))] += rng.uniform(0.15, 0.5) * rng.choice([-1, 1])
        ir[:, ch] = lp(early, 4500) * 0.6 + late
    ir = np.concatenate([np.zeros((sec(predelay), 2)), ir])
    ir /= np.sqrt(np.sum(ir ** 2, axis=0))
    return ir


def reverb(x: np.ndarray, ir: np.ndarray, wet: float, hp_wet: float = 140.0, gate=None) -> np.ndarray:
    """Dry + wet convolution. With `gate` (a, b) in seconds, audio before a and after b are
    reverberated separately so the tail of the hit does not bleed back after the silence."""
    def conv(src):
        w = np.zeros_like(src)
        for ch in (0, 1):
            w[:, ch] = signal.oaconvolve(src[:, ch], ir[:, ch])[:len(src)]
        return hp(w, hp_wet)

    if gate is None:
        return x + wet * conv(x)
    a, b = sec(gate[0]), sec(gate[1])
    pre = x.copy()
    pre[a:] = 0.0
    post = x.copy()
    post[:b] = 0.0
    wpre = conv(pre)
    wpre[a:] = 0.0
    return x + wet * (wpre + conv(post))


# ----------------------------------------------------------------------------- harmony
ORG = {
    "Dm": ["D2", "A2", "D3", "F3", "A3"], "Bb": ["Bb2", "F3", "Bb3", "D4"],
    "Gm": ["G2", "D3", "G3", "Bb3"], "A": ["A2", "E3", "A3", "C#4"],
    "Eb": ["Eb2", "Bb2", "Eb3", "G3"], "A7": ["A2", "E3", "G3", "C#4"],
    "Dm_hit": ["D2", "A2", "D3", "F3", "G#3", "A3", "D4"],
}
CHOIR = {
    "Dm": ["D3", "A3", "D4", "F4", "A4"], "Bb": ["F3", "Bb3", "D4", "F4", "Bb4"],
    "Gm": ["G3", "D4", "G4", "Bb4", "D5"], "A": ["A3", "E4", "A4", "C#5", "E5"],
}
PAD = {
    "Dm": ["D3", "A3", "D4", "F4"], "Bb": ["Bb2", "F3", "Bb3", "D4"],
    "Gm": ["G2", "D3", "G3", "Bb3"], "A": ["A2", "E3", "A3", "C#4"], "Eb": ["Eb3", "Bb3", "Eb4", "G4"],
}
ROOT = {"Dm": "D2", "Bb": "Bb1", "Gm": "G1", "A": "A1", "Eb": "Eb2"}
SUB = {"Dm": "D1", "Bb": "Bb1", "Gm": "G1", "A": "A1", "Eb": "Eb1"}
APPROACH = {("Dm", "Bb"): "C2", ("Bb", "Dm"): "C#2", ("Dm", "Gm"): "F#1", ("Gm", "A"): "G#1",
            ("A", "Dm"): "C#2", ("Bb", "A"): "Bb1", ("Dm", "Dm"): None, ("Bb", "Bb"): None,
            ("A", "A"): None, ("Bb", "Gm"): "A1", ("Dm", "A"): "G#1"}

# Motif (stated by the organ, echoed by bells): D F G# A - F
MOTIF = ["D", "F", "G#", "A"]


def organ_chord(buf, t, name, dur, reg="doom", vel=0.3, **kw):
    for nn in ORG[name]:
        place(buf, organ(hz(nn), dur, reg=reg, vel=vel, **kw), t)


def pad_chord(buf, t, name, dur, vel=0.5, **kw):
    place(buf, pad(PAD[name], dur, vel=vel, **kw), t)


def choir_chord(buf, t, name, dur, vel=0.5, **kw):
    for i, nn in enumerate(CHOIR[name]):
        v = choir_note(hz(nn), dur, vel=vel, **kw)
        pan = (-0.6, 0.6, -0.3, 0.3, 0.0)[i % 5]
        g = np.array([math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)]) * math.sqrt(2)
        place(buf, v * g, t)


def bass_bar(buf, t0, beat, chord, nxt=None, vel=0.9, gate=0.8, octave_on=(3, 7)):
    """Eight driving eighths on the root, octave jumps, approach note into the next chord."""
    eighth = beat / 2.0
    root = hz(ROOT[chord])
    app = APPROACH.get((chord, nxt)) if nxt else None
    for j in range(8):
        f = root * (2.0 if j in octave_on else 1.0)
        if j == 7 and app:
            f = hz(app)
        v = vel * (1.0 if j % 2 == 0 else 0.8)
        place(buf, bass_note(f, eighth * gate, vel=v), t0 + j * eighth)


# ----------------------------------------------------------------------------- the piece
def compose() -> dict[str, np.ndarray]:
    S = {k: np.zeros((N, 2)) for k in ("organ", "bass", "perc", "pads", "fx")}
    organ_s, bass_s, perc_s, pads_s, fx_s = (S[k] for k in ("organ", "bass", "perc", "pads", "fx"))

    # ---------------- Shot 01-02 (0-15): drone, one heartbeat, bell, pad swell, heartbeat
    cue(0.0, "drone in (D1 sub + dark pad)")
    place(bass_s, drone(hz("D1"), 27.0, vel=0.28, att=3.5, rel=0.4), 0.0)
    place(pads_s, pad(["D2", "A2", "D3"], 12.0, vel=0.28, att=5.0, rel=3.0, cutoff=(220, 700)), 2.0)
    cue(2.0, "single heartbeat")
    place(perc_s, heartbeat(0.7), 2.0)
    cue(6.0, "bell D4 (first motif note)")
    place(fx_s, bell(hz("D4"), 8.0, vel=0.7, t60=7.0), 6.0)
    cue(8.0, "heartbeat continues, ~50 bpm (period 1.1875 s) until 27.0")
    hb_period = 19.0 / 16
    for k in range(16):
        place(perc_s, heartbeat(0.55 + 0.2 * k / 15), 8.0 + k * hb_period)
    place(pads_s, pad(PAD["Dm"], 7.0, vel=0.4, att=3.0, rel=2.0, cutoff=(250, 1100)), 8.0)

    # ---------------- Shot 03 (15-27): organ chord, the motif, second chord on "create" (24.5)
    cue(15.0, "organ chord Dm (doom registration); motif D-F-G#-A from 17.6")
    organ_chord(organ_s, 15.0, "Dm", 9.5, reg="doom", vel=0.32, att=0.03)
    pad_chord(pads_s, 15.0, "Dm", 9.5, vel=0.4, att=1.0, rel=1.5, cutoff=(400, 900))
    motif_a = [("D4", 17.6, 1.2), ("F4", 18.8, 1.2), ("G#4", 20.0, 0.6), ("A4", 20.6, 3.9)]
    for nn, t, d in motif_a:
        place(organ_s, organ(hz(nn), d, reg="warm", vel=0.3, att=0.05, rel=0.25), t)
    cue(24.5, "organ chord Bb (the create click), motif lands on F")
    organ_chord(organ_s, 24.5, "Bb", 2.5, reg="doom", vel=0.34, att=0.03)
    place(organ_s, organ(hz("F4"), 2.5, reg="warm", vel=0.32, att=0.05, rel=0.3), 24.5)
    pad_chord(pads_s, 24.5, "Bb", 2.5, vel=0.4, att=0.8, rel=1.5, cutoff=(500, 1100))

    # ---------------- Shot 04 (27-41): low toms, organ progression Dm Bb Gm A, drone follows roots
    cue(27.0, "low toms start (period 1.1667 s, 12 beats to 41.0); organ Dm > Bb > Gm > A")
    tom_period = 14.0 / 12
    for k in range(12):
        t = 27.0 + k * tom_period
        place(perc_s, tom(73.0, vel=0.6 + 0.25 * k / 11), t)
        if k % 4 == 3:
            place(perc_s, tom(98.0, vel=0.45, pan=0.3), t - 0.2)
        if k >= 8:
            place(perc_s, tom(98.0, vel=0.35, pan=-0.3), t + tom_period / 2)
    prog_a = [("Dm", 27.0), ("Bb", 30.5), ("Gm", 34.0), ("A", 37.5)]
    for i, (ch, t) in enumerate(prog_a):
        d = (prog_a[i + 1][1] if i + 1 < len(prog_a) else 41.0) - t
        organ_chord(organ_s, t, ch, d, reg="doom", vel=0.3, att=0.08, rel=0.2)
        pad_chord(pads_s, t, ch, d, vel=0.4, att=0.6, rel=1.0, cutoff=(500, 1300))
        place(bass_s, drone(hz(SUB[ch]), d, vel=0.32, att=0.3, rel=0.3), t)
    # a soft heartbeat keeps breathing under the toms
    for k in range(12):
        place(perc_s, heartbeat(0.35), 27.0 + k * tom_period + 0.55)

    # ---------------- Shot 05 (41-60) + riser (60-68): darkwave pulse, 11 bars, hit on bar 11 = 68.0
    B0, BBAR = 41.0, 27.0 / 11
    BEAT = BBAR / 4
    cue(41.0, f"darkwave pulse enters: synth bass eighths, kick, {60 / BEAT:.1f} bpm (11 bars to 68.0)")
    chords_b = ["Dm", "Dm", "Bb", "Bb", "Dm", "Dm", "Gm", "A", "Dm", "Bb", "A"]
    for k, ch in enumerate(chords_b):
        t0 = B0 + k * BBAR
        nxt = chords_b[k + 1] if k + 1 < len(chords_b) else "Dm"
        vel = 0.6 if k < 4 else (0.75 if k < 8 else 0.85)
        if k < 10:
            bass_bar(bass_s, t0, BEAT, ch, nxt, vel=vel)
        else:  # last bar: pump on A, climb, leave the gap before the hit
            eighth = BEAT / 2
            climb = ["A1", "A1", "A1", "A2", "A1", "C#2", "E2"]
            for j, nn in enumerate(climb):
                place(bass_s, bass_note(hz(nn), eighth * 0.8, vel=0.85), t0 + j * eighth)
        # organ chords
        dur = BBAR if k < 10 else (67.5 - t0)
        reg = "doom" if k < 8 else "full"
        if k < 10:
            organ_chord(organ_s, t0, ch, dur, reg=reg, vel=0.28 if k < 8 else 0.3, att=0.05, rel=0.15)
        else:
            cue(65.5, "organ A7 with leslie speeding up (riser)")
            for nn in ORG["A7"]:
                place(organ_s, organ(hz(nn), dur, reg="full", vel=0.3, att=0.1, rel=0.08, leslie=(0.7, 7.5)), t0)
        # pads
        pad_chord(pads_s, t0, ch, dur if k < 10 else dur - 0.1, vel=0.35, att=0.5, rel=0.15 if k == 10 else 1.0,
                  cutoff=(600, 1400) if k < 8 else (900, 3500))
        # kick
        beats = (0, 2) if k < 4 else (0, 1, 2, 3)
        for b in beats:
            place(perc_s, kick(0.72 + 0.08 * (k >= 8)), t0 + b * BEAT)
        if k == 10:
            for j in range(4, 7):
                place(perc_s, kick(0.65), t0 + j * BEAT / 2)
        # hats
        if k >= 2:
            for j in range(8 if k < 10 else 7):
                place(perc_s, hat(0.22 if j % 2 == 0 else 0.15), t0 + j * BEAT / 2)
        # toms on 2 and 4, fills at the ends of bars 3 and 7
        if k < 8:
            for b in (1, 3):
                place(perc_s, tom(73.0, vel=0.45), t0 + b * BEAT)
        if k in (3, 7):
            for j in range(4):
                place(perc_s, tom(98.0 if j % 2 else 73.0, vel=0.5 + 0.1 * j, pan=0.3 - 0.2 * j), t0 + 3 * BEAT + j * BEAT / 4)
    # motif restated by the organ (bars 4-5), answered (bars 6-7)
    cue(B0 + 4 * BBAR, "organ motif restated over the pulse (bars 5-8)")
    b4 = B0 + 4 * BBAR
    motif_b = [("D4", 0, 2), ("F4", 2, 2), ("G#4", 4, 1), ("A4", 5, 3),
               ("Bb4", 8, 1), ("A4", 9, 1), ("G4", 10, 2), ("F4", 12, 1), ("E4", 13, 1), ("C#4", 14, 2),
               ("D4", 16, 4), ("F4", 20, 4)]
    for nn, b, d in motif_b:
        place(organ_s, organ(hz(nn), d * BEAT, reg="bright", vel=0.3, att=0.03, rel=0.2), b4 + b * BEAT)
    # riser 60-68
    cue(60.0, "riser: filtered-noise sweep, tom roll accelerating 64-67.6")
    place(fx_s, riser(7.8, vel=0.8), 60.0)
    t, k = 64.0, 0
    while t < 67.5:
        x = (t - 64.0) / 3.6
        place(perc_s, tom(73.0 if k % 2 == 0 else 98.0, vel=0.25 + 0.25 * x, dur=0.45, pan=0.25 * (1 if k % 2 else -1)), t)
        t += max(0.06, 0.32 - 0.27 * x ** 1.3)
        k += 1
    cue(67.6, "pre-hit breath (band out, riser ends 67.8)")

    # ---------------- 68.0 THE HIT, then silence 68.5-69.5
    cue(T_HIT, "BIG HIT: sub boom + kick + tom + bells D2/D3 + organ Dm cluster with G#")
    place(perc_s, stereo(lp(thump(95, 30, 1.6, 1.0, drop=0.3), 160)), T_HIT, 0.75)
    place(perc_s, kick(0.7), T_HIT)
    place(perc_s, tom(55.0, vel=0.6, dur=1.0), T_HIT)
    place(fx_s, bell(hz("D3"), 2.0, vel=1.0, t60=6.0), T_HIT)
    place(fx_s, bell(hz("D2"), 2.0, vel=0.9, t60=7.0), T_HIT)
    place(fx_s, burst(0.08, 150, 9000, vel=1.0), T_HIT)
    for nn in ORG["Dm_hit"]:
        place(organ_s, organ(hz(nn), 0.5, reg="full", vel=0.6, att=0.005, rel=0.1), T_HIT)
    cue(T_SILENCE[0], "silence")
    cue(T_SILENCE[1], "drone creeps back, heartbeat")

    # ---------------- 69.5-76: tension, the botch hit at 73.0
    place(bass_s, drone(hz("D1"), 6.5, vel=0.3, att=1.5, rel=1.0), 69.5)
    place(pads_s, pad(["D2", "A2", "D3"], 6.0, vel=0.3, att=2.0, rel=2.0, cutoff=(200, 500)), 69.6)
    for t, v in ((70.0, 0.7), (71.2, 0.7), (72.4, 0.75), (74.2, 0.5), (75.4, 0.35)):
        place(perc_s, heartbeat(v), t)
    cue(T_HIT2, "second, smaller hit (the botch): low tom + Eb/A tritone bells + organ Eb (Phrygian II)")
    place(perc_s, tom(55.0, vel=0.85, dur=1.0), T_HIT2)
    place(perc_s, kick(0.7), T_HIT2)
    place(fx_s, bell(hz("Eb3"), 6.0, vel=0.55, t60=5.0), T_HIT2)
    place(fx_s, bell(hz("A3"), 6.0, vel=0.3, t60=4.0), T_HIT2)
    organ_chord(organ_s, T_HIT2, "Eb", 1.6, reg="doom", vel=0.3, att=0.01, rel=0.4)

    # ---------------- Shot 07 (76-86): choir-like swell, crescendo to ~84, settle
    cue(76.0, "choir swell: Dm > Bb > Gm > A (oo -> ah), crescendo to 84; soft bell D4")
    place(fx_s, bell(hz("D4"), 6.0, vel=0.3, t60=5.0), 76.0)
    swell = [("Dm", 76.0, 2.0, 0.45, (0.0, 0.3)), ("Bb", 78.0, 2.0, 0.6, (0.3, 0.55)),
             ("Gm", 80.0, 2.0, 0.8, (0.55, 0.8)), ("A", 82.0, 2.0, 1.0, (0.8, 1.0))]
    for ch, t, d, v, m in swell:
        choir_chord(pads_s, t, ch, d, vel=0.32 * v, att=0.9, rel=0.9, morph=m)
        organ_chord(organ_s, t, ch, d, reg="warm", vel=0.14 * v, att=0.4, rel=0.5)
        place(bass_s, drone(hz(SUB[ch]), d, vel=0.3, att=0.5, rel=0.5), t)
    cue(84.0, "swell resolves to Dm, decrescendo; low tom")
    choir_chord(pads_s, 84.0, "Dm", 2.6, vel=0.3, att=0.5, rel=1.5, vowels=("ah", "oo"), morph=(0.0, 1.0))
    organ_chord(organ_s, 84.0, "Dm", 2.3, reg="warm", vel=0.14, att=0.2, rel=0.8)
    place(bass_s, drone(hz("D1"), 2.0, vel=0.3, att=0.3, rel=0.8), 84.0)
    place(perc_s, tom(55.0, vel=0.6, dur=1.0), 84.0)

    # ---------------- Shot 08 (86-98): pulse back, tighter (100 bpm, 5 bars)
    D0, DBAR = 86.0, 2.4
    DBEAT = 0.6
    cue(86.0, "pulse back, tighter: 100 bpm, kick on every beat, 16th hats, organ stabs on the offbeats")
    chords_d = ["Dm", "Dm", "Bb", "Gm", "A"]
    for k, ch in enumerate(chords_d):
        t0 = D0 + k * DBAR
        nxt = chords_d[k + 1] if k + 1 < len(chords_d) else "Dm"
        bass_bar(bass_s, t0, DBEAT, ch, nxt, vel=0.85, gate=0.5, octave_on=(3, 6))
        for b in range(4):
            place(perc_s, kick(0.8), t0 + b * DBEAT)
        for j in range(16):
            place(perc_s, hat(0.2 if j % 2 == 0 else 0.12), t0 + j * DBEAT / 4)
        for b in (1, 3):
            place(perc_s, tom(73.0, vel=0.4), t0 + b * DBEAT)
        # organ: low pedal + stabs on the "and" of 2 and 4
        place(organ_s, organ(hz(ROOT[ch]), DBAR, reg="doom", vel=0.26, att=0.05, rel=0.1), t0)
        for b in (1.5, 3.5):
            organ_chord(organ_s, t0 + b * DBEAT, ch, 0.17, reg="bright", vel=0.24, att=0.005, rel=0.08)
        pad_chord(pads_s, t0, ch, DBAR, vel=0.32, att=0.3, rel=0.6, cutoff=(800, 1800))
    choir_chord(pads_s, 86.0, "Dm", 11.5, vel=0.14, att=1.5, rel=1.0, vowels=("oo", "oo"), morph=(0, 0))
    for j in range(4):  # fill into the theme
        place(perc_s, tom(98.0 if j % 2 else 73.0, vel=0.5 + 0.12 * j, pan=0.3 - 0.2 * j), 96.8 + j * DBEAT / 2)

    # ---------------- Shot 09 (98-112): full theme, fade from 108
    cue(98.0, "FULL THEME: organ melody (D F G# A | F E | C# | D) + choir + bass + drums + bells doubling")
    band = {k: np.zeros((N, 2)) for k in S}
    T0 = 98.0
    chords_t = ["Dm", "Dm", "Bb", "A", "Dm"]
    for k, ch in enumerate(chords_t):
        t0 = T0 + k * DBAR
        nxt = chords_t[k + 1] if k + 1 < len(chords_t) else "Dm"
        if k < 4:
            bass_bar(band["bass"], t0, DBEAT, ch, nxt, vel=0.85, gate=0.8)
            for b in range(4):
                place(band["perc"], kick(0.75), t0 + b * DBEAT)
            for j in range(8):
                place(band["perc"], hat(0.22 if j % 2 == 0 else 0.14), t0 + j * DBEAT / 2)
            for b in (1, 3):
                place(band["perc"], tom(73.0, vel=0.5), t0 + b * DBEAT)
            organ_chord(band["organ"], t0, ch, DBAR, reg="full", vel=0.3, att=0.05, rel=0.15)
            choir_chord(band["pads"], t0, ch, DBAR, vel=0.36, att=0.3, rel=0.8, vowels=("ah", "ah"), morph=(0, 0))
            pad_chord(band["pads"], t0, ch, DBAR, vel=0.25, att=0.3, rel=0.8, cutoff=(1200, 2500))
        else:  # final Dm, held into the fade
            bass_bar(band["bass"], t0, DBEAT, ch, None, vel=0.75, gate=0.8)
            for b in range(4):
                place(band["perc"], kick(0.7), t0 + b * DBEAT)
            organ_chord(band["organ"], t0, ch, 5.0, reg="full", vel=0.3, att=0.05, rel=1.5)
            choir_chord(band["pads"], t0, ch, 4.0, vel=0.36, att=0.3, rel=2.0, vowels=("ah", "oo"), morph=(0, 1))
            pad_chord(band["pads"], t0, ch, 4.0, vel=0.25, att=0.3, rel=2.0, cutoff=(1800, 600))
    for j in range(4):
        place(band["perc"], tom(98.0 if j % 2 else 73.0, vel=0.55 + 0.12 * j, pan=0.3 - 0.2 * j), 106.4 + j * DBEAT / 2)
    melody = [("D4", 98.0, 1.2), ("F4", 99.2, 1.2), ("G#4", 100.4, 0.6), ("A4", 101.0, 1.8),
              ("F4", 102.8, 1.2), ("E4", 104.0, 1.2), ("C#4", 105.2, 2.4), ("D4", 107.6, 4.5)]
    for nn, t, d in melody:
        place(band["organ"], organ(hz(nn), d, reg="full", vel=0.5, att=0.03, rel=0.35 if d < 4 else 1.5), t)
        place(band["organ"], organ(hz(nn) * 2, d, reg="bright", vel=0.25, att=0.03, rel=0.35 if d < 4 else 1.5), t)
        place(fx_s, bell(hz(nn) * 2, 4.0, vel=0.28, t60=3.5), t)
    # fade from 108: band parts out by 110.5 (drums/bass) and 113 (organ/choir/pads)
    cue(108.0, "theme starts fading (drums and bass out by 110.5, organ/choir by 113)")
    tt = taxis(N)
    fade_fast = np.interp(tt, [0, 108.0, 110.5, DUR], [1, 1, 0, 0])[:, None]
    fade_slow = np.interp(tt, [0, 108.0, 113.0, DUR], [1, 1, 0, 0])[:, None]
    for k in band:
        S[k] += band[k] * (fade_fast if k in ("bass", "perc") else fade_slow)

    # ---------------- Shot 10 (112-120): bells echo the motif, last bell 113.0, drone out
    cue(109.4, "bells echo the motif: D5 F5 G#5 A5")
    for nn, t in (("D5", 109.4), ("F5", 110.0), ("G#5", 110.6), ("A5", 111.2)):
        place(fx_s, bell(hz(nn), 7.0, vel=0.42, t60=6.0), t)
    cue(T_LAST_BELL, "last bell D4 (long)")
    place(fx_s, bell(hz("D4"), 7.0, vel=0.7, t60=7.0), T_LAST_BELL)
    place(bass_s, drone(hz("D1"), 7.0, vel=0.3, att=2.0, rel=5.0), 107.6)
    place(pads_s, pad(["D2", "A2", "D3"], 7.0, vel=0.25, att=3.0, rel=5.0, cutoff=(500, 200)), 107.6)
    cue(DUR, "silence")
    return S


# ----------------------------------------------------------------------------- mastering
def gate_mask() -> np.ndarray:
    """Hard silence 68.5-69.5 (50 ms ramps) and a clean end before 120.0."""
    m = np.ones(N)
    a, b = sec(T_SILENCE[0] - 0.05), sec(T_SILENCE[0])
    m[a:b] = np.linspace(1, 0, b - a)
    c, d = sec(T_SILENCE[1]), sec(T_SILENCE[1] + 0.05)
    m[b:c] = 0.0
    m[c:d] = np.linspace(0, 1, d - c)
    e0, e1 = sec(119.0), sec(119.6)
    m[e0:e1] = np.linspace(1, 0, e1 - e0)
    m[e1:] = 0.0
    return m


def mono_low(x: np.ndarray, fc: float = 150.0) -> np.ndarray:
    low = signal.sosfiltfilt(butter_sos(2, fc, "low"), x, axis=0)
    return (x - low) + low.mean(axis=1, keepdims=True)


def true_peak_db(x: np.ndarray) -> float:
    up = signal.resample_poly(x, 4, 1, axis=0)
    return to_db(float(np.max(np.abs(up))))


def limiter(x: np.ndarray, thresh_db: float = -1.5, look_ms: float = 20.0) -> np.ndarray:
    """Transparent brickwall: per-sample required gain, min-filtered over the lookahead window and
    smoothed with a Hann window of the same width (which keeps gain <= required everywhere)."""
    T = db(thresh_db)
    peak = np.max(np.abs(x), axis=1)
    g = np.minimum(1.0, T / np.maximum(peak, 1e-9))
    L = sec(look_ms / 1000.0)
    gmin = ndimage.minimum_filter1d(g, size=2 * L + 1, mode="nearest")
    w = np.hanning(2 * L + 1)
    w /= w.sum()
    gs = signal.fftconvolve(gmin, w, mode="same")
    gs = np.minimum(gs, g)  # numerical safety
    print(f"  limiter: max gain reduction {-to_db(float(gs.min())):.1f} dB, "
          f"{np.mean(gs < db(-1.0)) * 1000:.1f} ms/s with > 1 dB reduction")
    return x * gs[:, None]


def master(stems: dict[str, np.ndarray], target_lufs: float = -14.0, tp_limit: float = -1.0):
    import pyloudnorm as pyln

    meter = pyln.Meter(SR)
    mix = sum(stems.values())
    lufs = meter.integrated_loudness(mix)
    gain = db(target_lufs - lufs)
    print(f"pre-master: {lufs:.2f} LUFS, peak {to_db(float(np.max(np.abs(mix)))):.2f} dBFS, gain {to_db(gain):+.2f} dB")
    stems = {k: v * gain for k, v in stems.items()}
    mix = sum(stems.values())
    thr = -1.4
    out = mix
    for it in range(5):
        out = limiter(mix, thr)
        l2 = meter.integrated_loudness(out)
        tp = true_peak_db(out)
        print(f"  limiter pass {it}: thr {thr:.2f} dB -> {l2:.2f} LUFS, true peak {tp:.2f} dBTP")
        ok_tp = tp <= tp_limit
        ok_l = abs(l2 - target_lufs) <= 0.3
        if ok_tp and ok_l:
            break
        if not ok_l:
            g2 = db(target_lufs - l2)
            mix = mix * g2
            stems = {k: v * g2 for k, v in stems.items()}
        if not ok_tp:
            thr -= (tp - tp_limit) + 0.1
    return out, stems, {"integrated_lufs": round(float(meter.integrated_loudness(out)), 2),
                        "true_peak_dbtp": round(true_peak_db(out), 2),
                        "sample_peak_dbfs": round(to_db(float(np.max(np.abs(out)))), 2),
                        "limiter_threshold_db": round(thr, 2)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/trailer/music")
    args = ap.parse_args()
    out = Path(args.out)
    (out / "score_stems").mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    stems = compose()
    print(f"composed in {time.time() - t0:.1f} s")

    ir = make_ir(4.0)
    gate = gate_mask()
    gated = (T_SILENCE[0] - 0.05, T_SILENCE[1])
    # per-stem high-pass (keep the low end to the bass stem) and reverb
    settings = {  # hp Hz, wet, wet-hp Hz
        "organ": (100.0, 0.45, 140.0), "bass": (None, 0.08, 220.0), "perc": (35.0, 0.3, 160.0),
        "pads": (120.0, 0.4, 150.0), "fx": (110.0, 0.55, 140.0),
    }
    for k, (fc, wet, whp) in settings.items():
        x = stems[k]
        if fc:
            x = hp(x, fc, 2)
        x = reverb(x, ir, wet, hp_wet=whp, gate=gated)
        x = mono_low(x) * gate[:, None]
        stems[k] = x
        print(f"stem {k}: peak {to_db(float(np.max(np.abs(x)))):.1f} dBFS, rms {to_db(float(np.sqrt(np.mean(x ** 2)))):.1f} dB")
    print(f"processed in {time.time() - t0:.1f} s")

    mixed, stems, stats = master(stems)
    assert len(mixed) == N
    sf.write(out / "score.wav", mixed, SR, subtype="PCM_24")
    for k, v in stems.items():
        sf.write(out / "score_stems" / f"{k}.wav", v, SR, subtype="FLOAT")

    cues = {}
    for t, text in sorted(CUES):
        key = f"{t:07.3f}"
        cues[key] = f"{cues[key]}; {text}" if key in cues else text
    json.dump({
        "title": "ShadowRealms AI trailer score",
        "duration_s": DUR, "sample_rate": SR, "key": "D minor (harmonic-minor / Phrygian colour, G# tritone in the motif)",
        "tempo": {"heartbeat_bpm": 50.5, "toms_bpm": 51.4, "pulse_bpm": round(60 / (27.0 / 44), 1), "tight_pulse_bpm": 100},
        "motif": "D F G# A - F (organ 17.6 s and 50.8 s, bells 109.4-113.0)",
        "master": stats, "seed": SEED,
        "cues": cues,
    }, open(out / "cues.json", "w"), indent=2)
    print(json.dumps(stats))
    print(f"done in {time.time() - t0:.1f} s -> {out}")


if __name__ == "__main__":
    main()
