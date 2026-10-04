# Trailer timing sheet (the contract between recording, music and edit)

Plan and captions: `docs/video/TRAILER_PLAN.md`. Total length **120.0 s**, 1920×1080, 60 fps.

| Shot | Start | End | Scene | Music at this point |
|---|---|---|---|---|
| 01 | 0.0 | 8.0 | Intro: fog, sigil draws, title | Low drone in, one heartbeat at 2.0, a bell at 6.0 |
| 02 | 8.0 | 15.0 | Login | Heartbeat continues (~50 bpm), pad swells |
| 03 | 15.0 | 27.0 | New chronicle (Classic vs V5, game lines, create) | Organ chord on 15.0, second chord on the "create" click ~24.5 |
| 04 | 27.0 | 41.0 | Character forge (sped up) | Low toms start at 27.0 |
| 05 | 41.0 | 60.0 | Play: Storyteller reply with roll chip, second player quotes | Darkwave pulse enters at 41.0 (low synth bass under the organ, ~100 bpm), builds |
| 06 | 60.0 | 76.0 | Dice: V5 messy critical / bestial failure, then a Classic botch | Riser 60–68, **big hit at 68.0** (the V5 result appears), silence 68.5–69.5, second smaller hit at 73.0 (the botch) |
| 07 | 76.0 | 86.0 | Two languages | Choir-like swell 76–84 |
| 08 | 86.0 | 98.0 | Moderation (Laya) and admin | Pulse back, tighter |
| 09 | 98.0 | 112.0 | Theme showcase | Full theme (everything), starts fading at 108 |
| 10 | 112.0 | 120.0 | Outro: sigil, "Enter the night", GitHub link, own-domain line | Last bell at 113.0, drone out to silence at 120.0 |

Folders (all under `data/trailer/`, gitignored):

- `clips/en/shotNN.mp4`, `clips/el/shotNN.mp4`: raw recordings per shot, 1920×1080, 60 fps, no audio, a little longer than the slot (the edit trims).
- `music/score.wav` (48 kHz stereo, 120.0 s) and `music/score_stems/` if useful.
- `cards/en/`, `cards/el/`: caption and title overlays (transparent PNG or ProRes 4444 / VP9 alpha).
- `out/`: renders.

Scripts live in `tools/trailer/`. Nothing in `data/trailer/` goes into git.

Fonts: Cinzel is capitals-only and has no Greek, so **Greek text never uses Cinzel**: Alegreya (titles) and EB Garamond (body) for Greek, the same swap the app does.
