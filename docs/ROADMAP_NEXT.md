# Roadmap: after the chronicle (0.29–0.31)

Started 2026-10-18. One release per phase, same rules as [ROADMAP_CHRONICLE.md](ROADMAP_CHRONICLE.md): build in a worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 1 | The Storyteller reads the chronicle | memory block in the Storyteller prompt · per-chronicle switch · `/ai context` shows it | 0.29 | released 0.29.0 (2026-10-18) |
| 2 | Small AI pieces | AI death description · slash commands served by the backend · chronicle language default check | 0.30 | released 0.30.0 (2026-10-18) |
| 3 | Kill page and death text | Admin → Characters (kill, revive, deaths log) · fallen on the profile card and sheet · stricter death prompt and script check | 0.31 | built, waiting for review |
| — | Schedar samples | two sample files for Lef to listen to | — | done, Lef OK 19 Oct |

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

## Phase 3 — Kill page and death text (0.31)

- [x] 3.1 Admin → Characters (`pages/admin/CharactersPanel.jsx`, `GET /api/admin/characters`): every player character with owner, chronicle, edition and alive/fallen, search and a status filter, cards in one column on phones. Kill: soft / sacrifice / horrible with a line each, a warning that it retires the character for good, a "writing" state while the model works (up to 25 s), then the text and whether the AI wrote it or the fixed sentence was used. Kill on a fallen character is a 409 now, before any model call; a missing character a 404. Status: built.
- [x] 3.2 Deaths log in the same tab (`GET /api/admin/character-deaths`): who killed or revived whom, when, the type and the text. Kill and revive also write a row to the general moderation log (`character_kill`, `character_revive`). Status: built.
- [x] 3.3 Players see it: `death` (type, text, date) on `GET /api/characters/` and `/api/characters/<id>`, same permission as the sheet (owner, the chronicle's Storyteller, admins and helpers; other players at the table don't get the sheet). Shown on the profile card and at the top of the sheet. Fallen comes from the latest kill/revive row (`services/character_death.py`), not from `is_active`. Status: built.
- [x] 3.4 Death text: the prompt now says to use only facts from the material (no invented names, clans, titles, places, sects or lore) and, in Greek, Greek letters only except names the material spells in Latin. Post-check: wrong language, a word mixing scripts, or a Latin word the material doesn't have gives the fixed sentence. Status: built; not tried against the live model yet.
- [x] 3.5 Revive: `POST /api/admin/characters/<id>/revive` sets `is_active` true and logs a `revive` row; the kill row stays. Only an admin revive brings a fallen character back (a staff `PUT is_active` on a fallen character is a 409). Status: built.
- [x] 3.6 Review (Grok) fixes: a kill that finished while the model wrote now wins (the row is locked and checked again after the model call; the later one gets 409); `PUT is_active: true` on a fallen character is refused for admins too; names (character, clan, cast, places) no longer count against the language check, and in Greek only Latin words from those names pass; the Characters list ignores a stale reload. Not changed: on SQLite, kill, revive and the deaths log fail because the SQLite `init_db` has neither `character_moderation` nor `user_moderation_log` (the ban and moderation log routes fail there the same way); the app runs on PostgreSQL. Status: built.
- [ ] 3.7 Review, then a look on a phone (390 px) in the browser, then a live kill and revive on a test character.

## Schedar samples

- [x] S.1 A Greek and an English line in the Schedar voice, written by the speech service to the local to-lef voice folder (`gemini-samples/gemini-Schedar_el.ogg`, `gemini-Schedar_en.ogg`). Status: done 18 Oct; Lef listened 19 Oct: OK; ROADMAP_VOICE 8.4 ticked.

## Later (not planned in a release)

- [ ] A live nightly run on a test chronicle, watched once at the quiet hour.
- [ ] Site screenshots from a test chronicle (chronicle so far, Previously on…).
- [ ] The voice-showcase trailer (0.16–0.22).
- [x] An admin page that calls kill and shows the death text: phase 3.
- [ ] `/ai help` and the permission replies in Greek.
- [x] A death-description prompt rule against clans and details that aren't in the chapters: phase 3.

## Log

- 2026-10-18 — plan written.
- 2026-10-18 — phase 1 built on `feat/st-memory` (not reviewed, not merged, not released).
- 2026-10-18 — phase 2 built on `feat/death-slash` (not reviewed, not merged, not released).
- 2026-10-18 — both reviewed (Grok), fixed, merged; 0.29.0 and 0.30.0 released; Schedar samples made.
- 2026-10-19 — phase 3 built on `feat/kill-page` (not reviewed, not merged, not released).
