# Roadmap: after the chronicle (0.29–0.30)

Started 2026-10-18. One release per phase, same rules as [ROADMAP_CHRONICLE.md](ROADMAP_CHRONICLE.md): build in a worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 1 | The Storyteller reads the chronicle | memory block in the Storyteller prompt · per-chronicle switch · `/ai context` shows it | 0.29 | built on `feat/st-memory`, waiting for review |
| 2 | Small AI pieces | AI death description · slash commands served by the backend · chronicle language default check | 0.30 | not started |
| — | Schedar samples | two sample files for Lef to listen to | — | not started |

## Decisions (2026-10-18, Lef: full auto)

- **The Storyteller's memory is the Storyteller view.** It is the Storyteller: it already sees hidden rolls and closed rooms in its history. The prompt is never shown to players (`/ai context` is admin-only), and the block says it is private memory, never to be quoted. Noted in SECURITY_MODEL.md.
- **What goes in:** the story so far in short, the open threads, the last three nights of this room (skipping what the room history already has), one line per other room's last night, and the Storyteller-only paragraphs. At most a quarter of the prompt budget and never more than 1,500 tokens; history gets the rest.
- **On for every chronicle,** with a switch in Chronicle settings → The chronicle so far. Nothing in the chapters means nothing added. Never a model call and never a wait on the hot path.
- **Death description:** one call to the chronicler role in the chronicle's language from the story so far and the character's last nights; the three canned sentences stay as the fallback on any failure or timeout, EN and EL.
- **Slash commands:** one list in the backend, with EN and EL text; the browser fetches it once per session and keeps today's list as a fallback.
- **Chronicle language at creation** was already done in 0.25; only the server-side default is checked.

## Phase 1 — The Storyteller reads the chronicle (0.29)

- [x] 1.1 `services/chronicle_memory.py`: the block from the stored digest and chapters, by priority, cut to the budget, cached 60 s. Status: built. Read in the chronicle's own language only; using the cached translation when the reply language differs is left out (the reply language is only resolved later, in `llm_service`).
- [x] 1.2 `_storyteller_reply` adds the block after the campaign context when the chronicle's `memory` setting is on; `/ai context` shows it. Status: built.
- [x] 1.3 The switch in Chronicle settings, EN + EL; docs (CHRONICLE.md, AI_SYSTEMS.md, SECURITY_MODEL.md). Status: built.
- [ ] 1.4 Tests: block contents and cuts, empty when nothing is written, off switch, cache; one reply measured on the test chronicle after the build. Status: unit tests done; the live measurement is not done yet.

## Phase 2 — Small AI pieces (0.30)

- [ ] 2.1 AI death description in `admin.py` kill, canned fallback EN + EL, `generated` flag in the response. Status: not started.
- [ ] 2.2 `GET /api/ai/slash/commands`, one list for `/ai help` and the composer, EN + EL; the browser's list stays as the fallback. Status: not started.
- [ ] 2.3 Creating a chronicle without a language takes the creator's app language on the server too. Status: not started (check first; may already be so).

## Schedar samples

- [ ] S.1 A script in the speech service writes a Greek and an English line in the Schedar voice to the local to-lef voice folder for Lef to listen to; then ROADMAP_VOICE 8.4. Status: not started.

## Later (not planned in a release)

- [ ] A live nightly run on a test chronicle, watched once at the quiet hour.
- [ ] Site screenshots from a test chronicle (chronicle so far, Previously on…).
- [ ] The voice-showcase trailer (0.16–0.22).

## Log

- 2026-10-18 — plan written.
- 2026-10-18 — phase 1 built on `feat/st-memory` (not reviewed, not merged, not released).
