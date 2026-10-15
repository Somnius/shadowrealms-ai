#!/usr/bin/env python3
"""Binding cue times of the trailer score, in one place.

compose.py (the score), analyze.py (its measurement), placeholders.py (the stand-in beeps) and
edit.py (the cut: duration, flashes, data folder) all import this file, so music, measurement
and edit cannot drift apart. No dependencies: plain Python.

A preset is one trailer version. "v1" is the 120 s trailer of 2026-10-04 (trailer-v0.10.0);
rendering it must give the same score as then. "v2" is the 150 s trailer (CUES_v2.md).

    python3 tools/trailer/music/cues.py [v2]                      # print the preset
    python3 tools/trailer/music/cues.py --check tools/trailer/timeline_v2.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Cues:
    name: str
    data_dir: str                   # outputs (gitignored) for this trailer version, relative to the repo root
    dur: float                      # total length (s); the music is zero from end_gate[1]

    # The opening (0-27 s: drone, heartbeat 2.0, bell 6.0, organ 15.0, Bb chord on the create click
    # 24.5) is the same in every preset and lives in compose.py.
    toms: float                                     # low toms start
    toms_beats: int                                 # beats from `toms` to `toms_end` (forge if set, else pulse)
    toms_vel: tuple[float, float]                   # tom velocity ramp over the section
    toms_prog: tuple[tuple[str, float], ...]        # organ/pad/drone chords under the toms; the last ends at toms_end
    soft_bell: float | None                         # a soft bell D4 (v2: the Guided suggestion panel)
    forge: float | None                             # v2: doubled toms + low choir + motif restated, to `pulse`
    forge_prog: tuple[tuple[str, float], ...]       # chords under the forge section

    pulse: float                                    # darkwave pulse enters; bars to the hit, the last bar is the climb
    pulse_chords: tuple[str, ...]                   # one chord per bar; len = bars; the last one is the climb (A)
    hit: float                                      # THE HIT: the V5 dice result frame (riser from hit-8)
    silence: tuple[float, float]                    # digital zero (50 ms ramps around it)
    heartbeats: tuple[tuple[float, float], ...]     # (t, vel) between the silence and the choir swell
    card_organ: float | None                        # v2: a warm organ D4 as the "Roll explained" card appears
    hit2: float                                     # the smaller second hit (the Classic botch)
    choir: float                                    # choir swell Dm > Bb > Gm > A over 8 s, resolves at choir+8
    tight: float                                    # tight pulse, 100 bpm, 5 bars of 2.4 s
    page_bell: float | None                         # v2: bell D4 as the exported PDF page appears
    pre_theme: float | None                         # v2: a riser bar (free time) from here into the theme
    theme: float                                    # FULL THEME downbeat; fade from theme+10
    theme_hit: bool                                 # v2: kick + tom + bell D3 on the theme downbeat (climax 2)
    last_bell: float                                # last bell D4 (organ/choir are out by here)
    end_gate: tuple[float, float]                   # ramp to zero between these; zero after

    # analyze.py: band table sections, spectrogram labels, level checks around these times
    sections: tuple[tuple[float, float, str], ...]
    labels: tuple[tuple[float, str], ...]
    level_checks: tuple[float, ...]
    # placeholders.py beeps on every mark; CUES_*.md lists them
    marks: tuple[float, ...]

    @property
    def toms_end(self) -> float:
        return self.forge if self.forge is not None else self.pulse

    @property
    def pulse_bar(self) -> float:
        """Bar length of the darkwave pulse: the bars land the downbeat of the last+1 bar on the hit."""
        return (self.hit - self.pulse) / len(self.pulse_chords)

    @property
    def flash_times(self) -> tuple[float, ...]:
        """Where the edit may put a flash: the two hits and the theme downbeat."""
        return (self.hit, self.hit2, self.theme)

    def as_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d.update(toms_end=self.toms_end, pulse_bar=self.pulse_bar)
        return d


V1 = Cues(
    name="v1", data_dir="data/trailer", dur=120.0,
    toms=27.0, toms_beats=12, toms_vel=(0.6, 0.85),
    toms_prog=(("Dm", 27.0), ("Bb", 30.5), ("Gm", 34.0), ("A", 37.5)),
    soft_bell=None, forge=None, forge_prog=(),
    pulse=41.0, pulse_chords=("Dm", "Dm", "Bb", "Bb", "Dm", "Dm", "Gm", "A", "Dm", "Bb", "A"),
    hit=68.0, silence=(68.5, 69.5),
    heartbeats=((70.0, 0.7), (71.2, 0.7), (72.4, 0.75), (74.2, 0.5), (75.4, 0.35)),
    card_organ=None, hit2=73.0, choir=76.0, tight=86.0, page_bell=None, pre_theme=None,
    theme=98.0, theme_hit=False, last_bell=113.0, end_gate=(119.0, 119.6),
    sections=((0, 15, "intro"), (15, 27, "organ"), (27, 41, "toms"), (41, 60, "pulse"), (60, 68, "riser"),
              (69.5, 76, "tension"), (76, 86, "choir"), (86, 98, "tight pulse"), (98, 108, "theme"), (108, 120, "outro")),
    labels=((2, "hb"), (6, "bell"), (15, "organ"), (24.5, "create"), (27, "toms"), (41, "pulse"), (60, "riser"),
            (68, "HIT"), (73, "botch"), (76, "choir"), (86, "tight"), (98, "theme"), (108, "fade"), (113, "bell")),
    level_checks=(73.0, 113.0, 15.0, 24.5, 41.0, 76.0, 98.0),
    marks=(2.0, 6.0, 15.0, 24.5, 27.0, 41.0, 60.0, 73.0, 76.0, 86.0, 98.0, 112.0, 113.0),
)

V2 = Cues(
    name="v2", data_dir="data/trailer-v2", dur=150.0,
    toms=27.0, toms_beats=17, toms_vel=(0.6, 0.75),
    toms_prog=(("Dm", 27.0), ("Bb", 31.0), ("Gm", 35.0), ("A", 39.0), ("Dm", 43.0)),
    soft_bell=44.6, forge=47.0, forge_prog=(("Dm", 47.0), ("Bb", 50.5), ("Gm", 54.0), ("A", 57.5)),
    pulse=61.0, pulse_chords=("Dm", "Dm", "Bb", "Bb", "Dm", "Gm", "A", "Dm", "Bb", "A"),
    hit=85.0, silence=(85.5, 86.5),
    heartbeats=((87.0, 0.7), (88.2, 0.7), (89.4, 0.65), (90.6, 0.6), (91.8, 0.55), (93.0, 0.5), (94.2, 0.42), (95.4, 0.35),
                (97.0, 0.6), (98.2, 0.75), (100.2, 0.5), (101.4, 0.35)),
    card_organ=88.0, hit2=99.0, choir=102.0, tight=112.0, page_bell=123.4, pre_theme=124.0,
    theme=128.0, theme_hit=True, last_bell=143.0, end_gate=(149.0, 149.6),
    sections=((0, 15, "intro"), (15, 27, "organ"), (27, 47, "toms"), (47, 61, "forge"), (61, 77, "pulse"), (77, 85, "riser"),
              (86.5, 96, "tension"), (96, 102, "botch"), (102, 112, "choir"), (112, 124, "tight pulse"), (124, 128, "pdf riser"),
              (128, 138, "theme"), (138, 150, "outro")),
    labels=((2, "hb"), (6, "bell"), (15, "organ"), (24.5, "create"), (27, "toms"), (47, "forge"), (61, "pulse"), (77, "riser"),
            (85, "HIT"), (99, "botch"), (102, "choir"), (112, "tight"), (124, "riser"), (128, "THEME"), (138, "fade"), (143, "bell")),
    level_checks=(99.0, 128.0, 143.0, 15.0, 24.5, 27.0, 47.0, 61.0, 102.0, 112.0, 123.4, 124.0),
    marks=(2.0, 6.0, 15.0, 24.5, 27.0, 35.0, 47.0, 61.0, 77.0, 99.0, 102.0, 112.0, 121.6, 123.4, 128.0, 142.0, 143.0),
)

PRESETS: dict[str, Cues] = {"v1": V1, "v2": V2}
DEFAULT = "v2"


def by_duration(seconds: float, tol: float = 0.01) -> Cues | None:
    for c in PRESETS.values():
        if abs(c.dur - seconds) <= tol:
            return c
    return None


def check_timeline(path: str) -> list[str]:
    """The edit's timeline against its preset: duration, data folder, flash times. -> problems."""
    tl = json.load(open(path))
    name = tl.get("music_preset")
    if not name:
        return [f"{path}: no 'music_preset'"]
    c = PRESETS[name]
    bad = []
    if abs(float(tl["duration"]) - c.dur) > 1e-6:
        bad.append(f"duration {tl['duration']} != preset {c.name} {c.dur}")
    if tl.get("data_dir", "data/trailer") != c.data_dir:
        bad.append(f"data_dir {tl.get('data_dir')!r} != preset {c.data_dir!r}")
    for fl in tl.get("flashes", []):
        if not any(abs(float(fl["at"]) - t) < 1e-6 for t in c.flash_times):
            bad.append(f"flash at {fl['at']} is not a hit of preset {c.name} {c.flash_times}")
    last = tl["shots"][-1]
    if abs(float(last["end"]) - c.dur) > 1e-6:
        bad.append(f"last shot ends at {last['end']}, preset {c.dur}")
    return bad


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--check"]:
        problems = check_timeline(args[1])
        print("\n".join(problems) if problems else f"{args[1]}: consistent with its music preset")
        sys.exit(1 if problems else 0)
    c = PRESETS[args[0] if args else DEFAULT]
    for k, v in c.as_dict().items():
        print(f"{k:14s} {v}")
