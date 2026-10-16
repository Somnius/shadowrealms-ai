# ShadowRealms AI trailer

Two trailers so far, both in English and Greek, both made with the scripts in `tools/trailer/`:

- **v2** (2026-10-16, app v0.14.0, 2:30): https://github.com/Somnius/shadowrealms-ai/releases/tag/trailer-v0.14.0
- **v1** (2026-10-04, app v0.10.0, 2:00): https://github.com/Somnius/shadowrealms-ai/releases/tag/trailer-v0.10.0

## Trailer v2 (v0.14.0)

Status: **done** (2026-10-16). 150 s, 1920×1080, 60 fps, H.264, English and Greek renders. The timing contract is `tools/trailer/CUES_v2.md`, the cut `tools/trailer/timeline_v2.json`, the recordings `tools/trailer/record_v2.mjs`, the score `tools/trailer/music/` (preset `v2`).

### What's in it

| Time | Scene | Source |
|---|---|---|
| 0:00 | Intro: the login page's sigil draws, the wordmark | v1 footage |
| 0:08 | Sign-in, the hall opens | v1 |
| 0:15 | New chronicle: Classic or V5 | v1 |
| 0:27 | The Storyteller sets the chronicle's character creation rules: allowed clans (Hecata in, Caitiff and Thin-blood out), neonates only, a house rule | new |
| 0:35 | Guided mode: a new player answers the eight questions, the guide suggests Hecata · Grim Reaper | new |
| 0:47 | The forge with the guide's prefill: the clan card, the Oblivion power list and its description with book and page, the Summon Spirit ceremony, the predator preview, Backgrounds from the catalog, then the finished sheet | new |
| 1:01 | Play: the Storyteller answers and asks for Dexterity + Stealth with 4 Hunger | new |
| 1:17 | The roll from the chip: a **bestial failure** on the big hit (1:25.000) | new |
| 1:26 | `/ai explain` on the dice card: the counting and the result, page by page | new, same take |
| 1:36 | A Classic **botch** on the second hit (1:39.000) | new |
| 1:42 | English and Greek in the same chronicle | v1 |
| 1:52 | Laya flags an in-character line in the OOC room; admin pages | v1 |
| 2:01 | Export PDF: the real exported sheet, page 1 and the Reference page | new |
| 2:07 | The theme showcase: the switch to Full atmosphere lands on the theme's downbeat (2:08.000), glyphs, clan sigils, Subtle, Off, the dice editions | new |
| 2:22 | Outro: Enter the night, run it on your own server, the GitHub link | v1 card |

Captions: 13, English and Greek, game terms in English in both; Greek is set in Alegreya / EB Garamond, never Cinzel.

### How it was made

The same way as v1 (below): a separate demo copy of the stack with its own database (project `srdemo`, loopback ports only), headless Chromium driven over the DevTools protocol at 1920×1080, frames captured with their compositor timestamps and turned into 60 fps, an original score generated from code, ffmpeg for the edit.

- The demo stack ran the v0.14.0 backend and frontend, with the v1 accounts, chronicles and characters plus a fourth player, `kalliroi`, who made her Hecata *Kalliroi Daskalaki* (Grim Reaper, Oblivion, an undertaker who talks to the dead) on camera: Guided mode, then the forge, then the sheet, in one take.
- Real results only. The Storyteller lines come from Llama-Krikri running locally; the dice are server rolls, rolled until the wanted result landed. V5 bestial failure: English on take 5, then again on take 2 of a retake (the script that opens the `/ai explain` card failed on the first one), Greek on take 4. Classic botch: English take 2, Greek take 3. The Storyteller's roll chip came on its first reply in both languages. Every take is logged by the recorder.
- The hits are frame-exact: the first frame showing "Result" is pinned to 1:25.000 and 1:39.000, the first frame of the Full switch to 2:08.000 (checked frame by frame on the review sheets), and `check_hits.py` measured the hits in the rendered audio at 85.000, 99.000 and 128.000 s.
- The forge, Guided and explain shots are zoomed in (static crops) so their text can be read. The PDF shot is the file the app downloaded, rendered page by page at 300 dpi.
- Score: 150 s, the v1 instruments and motif with new cue times, −14 LUFS integrated, true peak below −1 dBTP.

### Tools

```sh
# demo stack for one language (from a worktree: DEMO_ROOT=<main checkout>), then the recordings
DEMO_ROOT=<main checkout> TRAILER_DATA=data/trailer-v2 RESYNC=1 tools/trailer/reset_demo.sh en
TRAILER_DATA=data/trailer-v2 taskset -c 0-15 nice -n 10 node tools/trailer/record_v2.mjs en
# reused v1 clips, cut and render, then measure the hits
python3 tools/trailer/reuse_v1.py --timeline tools/trailer/timeline_v2.json --from <main checkout>/data/trailer
taskset -c 0-15 nice -n 10 python3 tools/trailer/edit.py --timeline tools/trailer/timeline_v2.json --lang both --final
uv run --with numpy --with scipy --with soundfile python3 tools/trailer/check_hits.py data/trailer-v2/out/trailer_en_1080p60.mp4
# remove the demo stack and its data
DEMO_ROOT=<main checkout> TRAILER_DATA=data/trailer-v2 tools/trailer/demo-down.sh --purge
```

## Trailer v1 (v0.10.0)

Status: **done** (2026-10-04). Published at https://github.com/Somnius/shadowrealms-ai/releases/tag/trailer-v0.10.0 (English and Greek). The scripts are in `tools/trailer/` (`CUES.md`, `timeline.json`, `edit.py`, `record.mjs`, `music/compose.py`).

### What was decided (2026-10-04)

| | |
|---|---|
| Kind | One trailer, about **2 minutes** |
| Editions | **Classic and V5** both shown |
| Versions | **Two renders:** English (English UI, English captions) and Greek (Greek UI, Greek captions, Greek chat with the Greek Storyteller) |
| Music | **An original score composed for the trailer** (no copyrighted or stock music) |
| Narration | Captions only, no voice |
| Format | **1920×1080, 60 fps, H.264 MP4**, for YouTube and the README |
| Style | Sigil intro, title card, URL outro; fog, film grain, vignette, blood-red accents, Cinzel captions |
| Where it's recorded | **A separate demo copy of the stack** with its own database; the live site and its data aren't touched |

### Shot list (English version; the Greek one follows the same cuts)

Times are targets; the edit will move them by a second or two to sit on the music.

| # | Time | Scene | What's on screen | Caption (EN) | Caption (EL) | Music |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:08 | Intro | Black, fog rolls in, the sigil draws itself (the login page's SigilReveal), title "ShadowRealms AI" | — | — | Low drone, a single heartbeat, a bell |
| 2 | 0:08–0:15 | Login | The sign-in page, a username typed, the sigil pulses, the hall opens | *Your chronicles. Your Storyteller. Your machine.* | *Τα χρονικά σου. Ο Αφηγητής σου. Στο δικό σου μηχάνημα.* | Heartbeat continues, pad swells |
| 3 | 0:15–0:27 | New chronicle | "New chronicle": Classic vs V5 picked first, then the game lines (Vampire, Werewolf, Mage / V5 Vampire); a V5 chronicle is created | *Classic or V5. Chosen per chronicle.* | *Classic ή V5. Ξεχωριστά για κάθε χρονικό.* | Organ chord on the click |
| 4 | 0:27–0:41 | Character forge | The V5 forge sped up: clan, Predator type, attribute and skill spreads, disciplines; the finished sheet with Hunger and Willpower | *Forge your character by the book.* | *Φτιάξε τον χαρακτήρα σου όπως ορίζουν οι κανόνες.* | Rhythm starts (low toms) |
| 5 | 0:41–1:00 | Play | A Discord-style room: a player writes in character, the AI Storyteller answers and asks for a roll (the roll chip "Dexterity + Stealth"); a second player replies with a quote | *An AI Storyteller that remembers, and calls for the right roll.* | *Ένας Αφηγητής AI που θυμάται και ζητά τη σωστή ζαριά.* | Builds |
| 6 | 1:00–1:16 | Dice | The roll chip opens the dice dialog; V5 roll with Hunger dice ends in a **messy critical** or **bestial failure** (blood effect); quick cut to a **Classic botch** | *Hunger. Messy criticals. Botches.* | *Hunger. Messy criticals. Botches.* | Big hit on the result, then silence for a beat |
| 7 | 1:16–1:26 | Two languages | The same room in Greek: a Greek line, the Storyteller answers in Greek (EN version: a short split shot) | *Speaks English and Greek.* | *Μιλά Ελληνικά και Αγγλικά.* | Choir-like swell |
| 8 | 1:26–1:38 | Keeping the table safe | OOC room: Laya flags an in-character line, the warning; admin "Logins & lockouts" and the AI roles page for a second each | *Moderated by Laya, a classifier trained for this table.* | *Με επίβλεψη από το Laya, έναν ταξινομητή εκπαιδευμένο γι' αυτό το τραπέζι.* | Pulse |
| 9 | 1:38–1:52 | The look | The theme showcase: glyphs and clan sigils, fog, candle glow, atmosphere Full/Subtle/Off | *Gothic down to the last glyph.* | *Γοτθικό ως την τελευταία λεπτομέρεια.* | Full theme, then fades |
| 10 | 1:52–2:00 | Outro | Sigil on black with fog; "Self-hosted · Open source · MIT"; github.com/Somnius/shadowrealms-ai | *Enter the night.* / *Run it on your own server, under your own domain.* | *Πέρνα στη νύχτα.* / *Στήσ' το στον δικό σου server, στο δικό σου domain.* | Last bell, drone out |

Game terms stay in English in the Greek captions (Hunger, messy critical, botch), the same rule the app's Greek UI follows.

### Demo data (in the separate stack only)

All made up for the trailer:

- Accounts: `nyx` (Storyteller and admin), players `ianthe` and `stavros`.
- V5 chronicle **"Thessaloniki Requiem"**: rooms *Elysium: The Rotunda*, *Ladadika After Midnight*, *The Cisterns*, and the out-of-character room.
- Classic chronicle **"Mistra in Ashes"** (Vampire, Revised): rooms *The Despot's Palace*, *Pantanassa Crypt*, and the out-of-character room.
- Characters:
  - **Ianthe Kallergi**, V5 Toreador, a gallery owner who never sleeps (the forge scene builds her).
  - **Stavros Morou**, V5 Nosferatu, an information broker under the city (the second player in the chat).
  - **Brother Anselm**, Classic Tremere, a scholar-monk of Mistra (the botch shot).
- Some earlier chat so the rooms don't look empty.

### How it gets made

1. **Demo stack.** A second Docker Compose project with its own PostgreSQL, Redis, ChromaDB, backend and nginx on other localhost ports (e.g. 127.0.0.1:8180), the same LM Studio and Ollama. The demo data is created through the app's API. Deleted afterwards.
2. **Recording.** A script drives Chromium at exactly 1920×1080 (no desktop, no notifications) and captures frames over the DevTools protocol; typing and clicks are scripted, so every take is the same. Frames are turned into constant 60 fps with ffmpeg.
3. **Real results, no fakes.** Storyteller replies come from the real models (Llama-Krikri). Dice are rolled by the server as always; for the messy critical, bestial failure and botch shots I roll as many takes as it takes and keep the ones that land. No code is changed to force a result.
4. **Captions and cards.** Rendered as HTML with the app's own fonts and colours (Cinzel, EB Garamond), then laid over the footage.
5. **Music.** An original ~2-minute dark ambient score made here from code: organ-like drones, low string pads, heartbeat, bells, choir-like swells, and hits timed to the cuts. Mixed to a normal online loudness (−14 LUFS). Good atmosphere, not a film orchestra.
6. **Edit and render.** ffmpeg: cuts, cross-fades, speed-ups for the forge, grain and vignette, fades. GPU encoding (NVENC) for drafts, a final x264 render. Machine limits as always: under 80% CPU, capped containers.
7. **Review.** You get both drafts to watch; changes, then the final.

### Where it goes

- Both MP4s attached to a GitHub release (direct download and playable in the browser) and linked from the README's "Demo video" section, plus a poster frame image in the README.
- YouTube: you upload it (I have no access to your channel); I'll prepare the title, description and chapters text in both languages.
- The scripts that build it (demo stack, recording, music, edit) go in the repo, so it can be re-made for later versions. The rendered files stay out of git.

### Things to confirm before go

1. **Captions:** the wording above, English and Greek. Change anything you like.
2. ~~Demo names~~: decided, made up (see Demo data).
3. ~~URL on the end card~~: decided, only the GitHub link, plus a line that it runs on your own server and domain.
4. ~~Music mood~~: decided, both: it opens slow and heavy (doom organ, heartbeat) and a darkwave pulse (low synth bass under the organ) comes in from the play scene on.
5. **GPU:** the AI scenes need LM Studio with Krikri loaded; if ComfyUI is busy at the time, the replies are slower (that part is cut down in the edit anyway).
