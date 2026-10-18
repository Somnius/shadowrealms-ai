# Roadmap: after the chronicle (0.29–0.30)

Started 2026-10-18. One release per phase, same rules as [ROADMAP_CHRONICLE.md](ROADMAP_CHRONICLE.md): build in a worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 1 | The Storyteller reads the chronicle | memory block in the Storyteller prompt · per-chronicle switch · `/ai context` shows it | 0.29 | released 0.29.0 (2026-10-18) |
| 2 | Small AI pieces | AI death description · slash commands served by the backend · chronicle language default check | 0.30 | released 0.30.0 (2026-10-18) |
| — | Schedar samples | two sample files for Lef to listen to | — | samples made, waiting for Lef's ear |

## Decisions (2026-10-18, Lef: full auto)

- **The Storyteller's memory is the Storyteller view.** It is the Storyteller: it already sees hidden rolls and closed rooms in its history. The prompt is never shown to players (`/ai context` is admin-only), and the block says it is private memory, never to be quoted. Noted in SECURITY_MODEL.md.
- **What goes in:** the story so far in short, the open threads, the last three nights of this room (skipping what the room history already has), one line per other room's last night, and the Storyteller-only paragraphs. At most a quarter of the prompt budget and never more than 1,500 tokens; history gets the rest.
- **On for every chronicle,** with a switch in Chronicle settings → The chronicle so far. Nothing in the chapters means nothing added. Never a model call and never a wait on the hot path.
- **Death description:** one call to the chronicler role in the chronicle's language from the story so far and the character's last nights; the three canned sentences stay as the fallback on any failure or timeout, EN and EL.
- **Slash commands:** one list in the backend, with EN and EL text; the browser fetches it once per session and keeps today's list as a fallback.
- **Chronicle language at creation** was already done in 0.25; only the server-side default is checked.

## Phase 1 — The Storyteller reads the chronicle (0.29)

- [x] 1.1 `services/chronicle_memory.py`: the block from the stored digest and chapters, by priority, cut to the budget, cached 60 s. Status: built. A stored translation of the digest is used when the reply language differs; never a new one.
- [x] 1.2 `_storyteller_reply` adds the block after the campaign context when the chronicle's `memory` setting is on; `/ai context` shows it. Status: built.
- [x] 1.3 The switch in Chronicle settings, EN + EL; docs (CHRONICLE.md, AI_SYSTEMS.md, SECURITY_MODEL.md). Status: built.
- [x] 1.4 Tests: block contents and cuts, empty when nothing is written, off switch, cache. Status: done. Review (Grok) found four real bugs, all fixed: `/ai context` was saved to the room, the off switch and a language change didn't reach the other worker, a stored translation was ignored, a short line could push out a night. Live on the test chronicle: `/ai context` shows the Greek block to the admin only; a full Storyteller reply with the block was not measured.

## Phase 2 — Small AI pieces (0.30)

- [x] 2.1 AI death description in `admin.py` kill, canned fallback EN + EL, `generated` flag in the response. Status: released in 0.30. Tried live on the test chronicle's character (read only, nobody killed): Greek text in 1–1.5 s for soft and horrible. The model invents a bit (Tremere details) and once wrote a Latin T in a Greek word. No page in the new frontend calls `killCharacter` (`utils/api.js`), so there is no admin UI for it today: UI debt. After review: player view only in the prompt, whole-word name match, the model call holds no database connection, and kill sets `is_active` false.
- [x] 2.2 `GET /api/ai/slash/commands`, one list for the composer and the `/ai` hints, EN + EL; the browser's list stays as the fallback. Status: released in 0.30; live list has 16 commands for an admin, 401 without a login. The long `/ai help` text is still written by hand (it has per-edition detail); a test checks it names every verb. Later: the `/ai help` body and the permission replies in the caller's language (they are English only; the composer list is EN + EL).
- [x] 2.3 Chronicle language at creation. Already done before this phase (the creation form sends the language, the chronicle settings page edits it). Residual check: the API stored NULL when the language was left out; it now takes the creator's app language (`users.ui_language`). Status: released in 0.30.

## Schedar samples

- [x] S.1 A Greek and an English line in the Schedar voice, written by the speech service to the local to-lef voice folder (`gemini-samples/gemini-Schedar_el.ogg`, `gemini-Schedar_en.ogg`). Status: done 18 Oct; ROADMAP_VOICE 8.4 waits for Lef to listen.

## Later (not planned in a release)

- [ ] A live nightly run on a test chronicle, watched once at the quiet hour.
- [ ] Site screenshots from a test chronicle (chronicle so far, Previously on…).
- [ ] The voice-showcase trailer (0.16–0.22).
- [ ] An admin page that calls kill and shows the death text (the new frontend has none).
- [ ] `/ai help` and the permission replies in Greek.
- [ ] A death-description prompt rule against clans and details that aren't in the chapters.

## Log

- 2026-10-18 — plan written.
- 2026-10-18 — phase 1 built on `feat/st-memory` (not reviewed, not merged, not released).
- 2026-10-18 — phase 2 built on `feat/death-slash` (not reviewed, not merged, not released).
- 2026-10-18 — both reviewed (Grok), fixed, merged; 0.29.0 and 0.30.0 released; Schedar samples made.
