# Trailer v2 timing sheet (the contract between recording, music and edit)

Plan: `docs/video/TRAILER_PLAN.md` (v1) and the v2 plan it grew from. Total length **150.0 s**, 1920×1080, 60 fps,
English and Greek renders. The music's binding times are code: `music/cues.py` preset **`v2`** (compose.py renders
from it, analyze.py measures against it, placeholders.py beeps on it, edit.py checks `timeline_v2.json` against it).
v1 (120 s, `trailer-v0.10.0`) stays reproducible as preset `v1` with `CUES.md` / `timeline.json`.

| Shot | Start | End | Scene | Music at this point |
|---|---|---|---|---|
| 01 | 0.0 | 8.0 | Intro: fog, the login page's sigil draws, wordmark, subtitle (v1 clip reused) | unchanged: drone in, heartbeat 2.0, bell D4 6.0 |
| 02 | 8.0 | 15.0 | Login (v1 reused) | unchanged: heartbeat ~50 bpm, pad swell |
| 03 | 15.0 | 27.0 | New chronicle: Classic vs V5, game lines, create on the chord (v1 reused) | unchanged: organ Dm 15.0, motif 17.6, Bb chord on the create click 24.5 |
| 04 | 27.0 | 35.0 | Creation rules card (Forge v2 A): allowed clans with Hecata, starting age, a house rule | low toms start 27.0 (17 beats to 47.0, period 1.176 s), organ Dm 27.0 → Bb 31.0, soft heartbeat under |
| 05 | 35.0 | 47.0 | Guided mode (Forge v2 E): questions, the suggestion panel, Open the forge | organ Gm 35.0 → A 39.0 → Dm 43.0; toms continue; **soft bell D4 44.6** on the suggestion panel |
| 06 | 47.0 | 61.0 | Forge v2 (A + B): Hecata card, attributes/skills sped up, Disciplines with the predator preview and the ceremony, create, the sheet | toms double 47.0 (two-hand pattern), low choir "oo" Dm, organ motif restated 49.4–57.0 (warm), organ Dm 47 → Bb 50.5 → Gm 54 → A 57.5, 4-tom fill 59.8–61.0 |
| 07 | 61.0 | 77.0 | Play: Ianthe writes, "weaving…" 1.6 s, the reply with the roll chip readable ~4.7 s, Stavros quotes | darkwave pulse 61.0, **100 bpm** (bar 2.4 s), 10 bars to 85.0: Dm Dm Bb Bb Dm Gm A Dm Bb A; kick 1+3 for bars 1–4 then every beat, hats from bar 3, organ motif over bars 5–8 (70.6) |
| 08 | 77.0 | 85.5 | Dice, V5: the chip opens the dialog, roll, **bestial failure settles on 85.000** (blood flash 0.55) | riser 77.0–84.8, tom roll accelerating 81.0–84.5, organ A7 leslie 82.6 (bar 10, the climb), breath 84.6, **BIG HIT 85.0** |
| 09 | 85.5 | 96.0 | `/ai explain` in the same recording: "Roll explained" card on 88.0, static crop on the Result lines from 92.0 | **silence 85.5–86.5** (digital zero), drone creeps back 86.5, dark pad, heartbeats 87.0 … 95.4 (1.2 s apart, fading), warm organ D4 88.0 as the card appears |
| 10 | 96.0 | 102.0 | Classic botch (Pantanassa Crypt): **botch settles on 99.000** (flash 0.35) | heartbeats 97.0, 98.2; **second hit 99.0** (tom, kick, Eb/A tritone bells, organ Eb); heartbeats 100.2, 101.4; bells ring out to 102 |
| 11 | 102.0 | 112.0 | Two languages (v1 reused) | choir swell Dm 102 → Bb 104 → Gm 106 → A 108 (oo → ah), soft bell D4 102.0, resolves to Dm 110.0 with a low tom |
| 12 | 112.0 | 121.6 | Laya + admin (v1 reused, 2.4 s shorter) | tight pulse 100 bpm, 5 bars 112.0–124.0: Dm Dm Bb Gm A, kick every beat, 16th hats, organ stabs, low choir "oo" |
| 13 | 121.6 | 127.6 | PDF export: the click, then the real exported sheet on 123.4 (page 1 push-in, page 3 "Reference" from 125.6) | bar 5 (A) continues; **bell D4 123.4** as the white page appears; 124.0–128.0 riser bar (free time): short noise riser, bass pumps on A then climbs, organ A7 leslie from 125.0, tom fill 126.8 |
| 14 | 127.6 | 142.0 | The look (showcase re-recorded, Full first): hard cut to the hero on the 127.6 kick, **the atmosphere switch to Full lands on 128.000** (bone flash 0.18), glyphs, clan sigils (Hecata hover), Subtle, Off, Editions glimpse | **CLIMAX 2 128.0**: theme downbeat + kick + tom + bell D3 (no sub boom, no silence) → FULL THEME: melody D4 128.0, F4 129.2, G#4 130.4, A4 131.0, F4 132.8, E4 134.0, C#4 135.2, D4 137.6; chords Dm Dm Bb A Dm; fade from 138.0 (drums/bass out by 140.5, organ/choir by 143.0) |
| 15 | 142.0 | 150.0 | Outro: sigil + wordmark (v1 clip), "Enter the night.", own-server line, "Self-hosted · Open source · MIT", github.com/Somnius/shadowrealms-ai | bells echo the motif D5 139.4, F5 140.0, G#5 140.6, A5 141.2; **last bell D4 143.0**; drone + pad from 137.6; zero from 149.6; silence 150.0 |

Binding numbers (`music/cues.py` → `V2`): hit **85.0**, silence **85.5–86.5**, second hit **99.0**, theme downbeat **128.0**,
last bell **143.0**, end gate 149.0 → 149.6 → 0, length **150.0**. Marks the stand-in score beeps on:
2, 6, 15, 24.5, 27, 35, 47, 61, 77, 99, 102, 112, 121.6, 123.4, 128, 142, 143 (the loud beep is the 85.0 hit).

Acceptance for the score (`analyze.py`): integrated −14.0 ± 0.3 LUFS, true peak ≤ −1.0 dBTP, no clipped samples,
hit onset 85.000 ± 0.005, second hit 99.000 ± 0.005, theme downbeat 128.000 ± 0.005, silence max |x| = 0 in 85.5–86.5,
zero from 149.6. Same master as v1 (−14 LUFS, limiter threshold search).

Sync method (as v1): the recorder marks `result_at` (the dice overlay `.sr-diceov.is-settled`); the edit pins the
source frame to the hit time, a flash lands on the same frame, the caption appears only after the silence; the
`review_hits_*.png` sheets show the frames either side of 85.0, 99.0 and 128.0.

Captions: 13 (EN/EL in `timeline_v2.json`), ≤ 10 words, 0.5 s fades, bottom by default, top on chat shots. Game terms
stay English in the Greek captions; Greek text never uses Cinzel (Alegreya titles, EB Garamond body, as the app).

Folders (all under `data/trailer-v2/`, gitignored; v1's `data/trailer/` is not touched):

- `clips/en/`, `clips/el/`: `shotNN.mp4` recordings (the v1 reuses copied in by `reuse_v1.py`), `shots.json` with the marks.
- `music/score.wav` (48 kHz stereo, 150.0 s), `music/score_stems/`, `music/cues.json`, `music/analysis.json`, `music/spectrogram.png`.
- `cards/en/`, `cards/el/`: caption PNGs and the intro/outro cards (`cards.mjs`). `fonts/`: the OFL fonts (copied from v1).
- `placeholder/`: stand-in clips and score for dry runs (`placeholders.py`). `out/`: renders, posters, contact and review sheets.

How to run (repo root):

```sh
# score (capped container, ~2 min) and its measurement
docker run --rm --cpus 8 --cpuset-cpus 0-7 --user $(id -u):$(id -g) -e HOME=/tmp -v "$PWD":/w -w /w python:3.12-slim sh -c \
  "pip install -q --user -r tools/trailer/music/requirements.txt && \
   nice -n 10 python tools/trailer/music/compose.py --preset v2 && nice -n 10 python tools/trailer/music/analyze.py --preset v2"
# edit inputs and a dry run before any recording (real clips where they exist, placeholders elsewhere)
python3 tools/trailer/reuse_v1.py --timeline tools/trailer/timeline_v2.json
python3 tools/trailer/placeholders.py --timeline tools/trailer/timeline_v2.json
python3 tools/trailer/edit.py --timeline tools/trailer/timeline_v2.json --lang both --draft --fill-missing
```
