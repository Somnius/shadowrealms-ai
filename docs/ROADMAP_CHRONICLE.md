# Roadmap: the chronicle so far

Started 2026-10-17. One release per phase; a phase goes live only when it is finished and tested, the rest stays on its branch. The voice work is in [ROADMAP_VOICE.md](ROADMAP_VOICE.md).

What it is: the chat of a chronicle, written up as a story so far, the way recmeets writes the minutes of a meeting. Chapters per room and night, each written by the local model with every event pointing back to the messages it came from; then one digest of the whole chronicle (the story so far, open threads, cast, places, timeline, a Storyteller-only part). The Storyteller and staff read it in Chronicle settings, update it, edit it and export it as Markdown or PDF. Players get a "Previously on…" recap built only from what they could read.

How each phase runs: build in its own git worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file updated → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 0 | Measure | synthetic chronicles · Krikri timed on a chapter · results read by eye | — | not started |
| 1 | Chapters and the digest | tables and the chronicler role · chaptering, prompts, checks, join · jobs · routes · settings panel · Markdown export | 0.24 | not started |
| 2 | PDF, edit, languages | PDF in the sheet's look · Storyteller edits a copy · the other language on request · chronicle language | 0.25 | not started |
| 3 | Previously on… | recap route · recap sheet on the play page · jump to the message · read-out | 0.26 | not started |
| 4 | Ops | nightly update · caps · admin health | 0.27 | not started |

## Decisions (2026-10-17, proposed; Lef to confirm)

- Same shape as recmeets' minutes: one structured JSON per chapter and one for the digest; Markdown and PDF are both rendered from it; the model's text is never read as markup. Every event cites message ids; uncited or unknown ids are dropped; the cast comes from the database, the model can only comment on names it was given. The chat is data, not instructions.
- A chapter is one room and one night: a run of messages with no gap over 6 hours. A night that doesn't fit the model's context is split and joined (map-reduce), never cut silently. The OOC lobby stays out unless the export asks for table talk.
- Two views. The player view is built from exactly what a player can read (no hidden rolls, no closed rooms). The Storyteller view adds a short "what the players did not see" per night and a Storyteller-only part in the export. Players never get the Storyteller view, and never get the export in this feature.
- Incremental: a hash per chapter, only changed or new chapters are rewritten, then the digest is joined again. Nothing runs per message; the Storyteller presses Update (and later a nightly run at a quiet hour).
- Everything long is a job: create, poll, cancel. One job per chronicle at a time, job state in the database (two gunicorn workers), one chapter call at a time, and a short wait after any Storyteller reply so play comes first on the GPU.
- Language: written in the chronicle's language (Krikri for Greek, the loaded model for English, a new `chronicler` role in Admin → AI system). The other language is a translation of the finished digest, made on request and cached. Greek is checked by its share of Greek letters, as recmeets does; one retry with the reason, then translate as a fallback.
- Edits never touch the generated text: the Storyteller edits a copy; exports use the copy and say so; a newer digest asks "keep my edit or start from the new one".
- PDF: black and white, Cinzel and EB Garamond, the sheet's frame and sigil, Greek works; footer "Written by ShadowRealms AI", no model name, no host, no version in the file.
- Schema changes go through `ensure_*` functions in `backend/database.py` and the same DDL in `init_postgresql_schema.sql`, like every other column.
- Nothing in the public repo names a host, a player or a tool.

## Phase 0 — Measure

- [ ] 0.1 Three synthetic chronicles (Greek, English, mixed; 1, 10 and 60 nights; hidden rolls and a closed room) as a pytest fixture generator. Status: not started.
- [ ] 0.2 Krikri at the loaded 8k context on one 4000-token chapter prompt: seconds, tokens per second, how often the JSON is usable, how often the Greek check passes; the same for the English model. Sets the chapter budget. Status: not started; no such measurement exists yet.
- [ ] 0.3 The digest of the live chronicles read by eye with Lef in both languages: does it get the gist, does it invent. Status: not started.

## Phase 1 — Chapters and the digest, Markdown (0.24)

- [ ] 1.1 Tables `chronicle_chapters`, `chronicle_digests`, `chronicle_jobs` through `ensure_chronicle_tables`; the `chronicler` AI role with its row in Admin → AI system and the table in AI_SYSTEMS.md. Status: not started.
- [ ] 1.2 Pure core `services/chronicle_digest.py`: lines from message rows for the player and Storyteller views, chaptering by room and night, token budget and splitting at a message, chapter and join and digest prompts with the schema in the prompt, parse and checks (ids, names, empty, language share, mixed scripts) with the retry reason, hashes, the fixed words in EL and EN, Markdown. pytest on the synthetic chronicles with a fake model. Status: not started.
- [ ] 1.3 Jobs `services/chronicle_jobs.py`: a worker thread per process, an advisory lock per chronicle, progress "chapter 3 of 7", cancel between calls, the wait after a Storyteller reply, only stale chapters rewritten. Status: not started.
- [ ] 1.4 Routes under `/api/campaigns/<id>/chronicle`: the digest, jobs (create, poll, cancel), chapters, `chronicle.md`. Permission tests: outsider 404, player 403 on Update and exports, helper and Storyteller allowed, hidden rolls and closed rooms never in the player view. Status: not started.
- [ ] 1.5 Panel "The chronicle so far" in Chronicle settings: status line, Update with progress and Cancel, Export Markdown, the digest read-only, Storyteller-only section behind a toggle; 44 px buttons, works on a phone. EN + EL. jest for the panel states. Status: not started.
- [ ] 1.6 Release 0.24: `docs/CHRONICLE.md`, FEATURES, CHANGELOG, this file. Status: not started.

## Phase 2 — PDF, edit, languages (0.25)

- [ ] 2.1 The sheet's frame, sigil, section rule, footer and fonts lifted into `services/pdf_look.py` (sheet tests unchanged); `services/chronicle_pdf.py`; `chronicle.pdf` route; Export PDF button; Greek checked in the file; A4 and Letter. Status: not started.
- [ ] 2.2 Edit: the Storyteller's Markdown copy, saved with `PUT`, used by the exports and marked in the footer; the notice when a newer digest exists. Status: not started.
- [ ] 2.3 The other language on request: a translate job through the translator role with the chronicle's names protected, cached as its own row, a language switch in the panel and `lang=` on exports. Status: not started.
- [ ] 2.4 `campaigns.language` asked at creation (default: the creator's UI language) and in Chronicle settings; the digest's default language. Status: not started; needs Lef's yes.
- [ ] 2.5 Release 0.25. Status: not started.

## Phase 3 — Previously on… (0.26)

- [ ] 3.1 `GET …/chronicle/recap`: the player view's last nights for one room since the character's last read, plus the story so far in short; 404 for rooms the viewer can't read. Status: not started.
- [ ] 3.2 Recap sheet on the play page (a bottom sheet on phones) with a jump from a night to its first message in the room. Status: not started.
- [ ] 3.3 Read the recap aloud through Listen as its own kind, off by default. Status: not started.
- [ ] 3.4 Release 0.26. Status: not started.

## Phase 4 — Ops (0.27)

- [ ] 4.1 Nightly update at a quiet hour for chronicles with new messages, one at a time, skipped while the Storyteller is answering; a per-chronicle switch, off by default. Status: not started.
- [ ] 4.2 Caps: chapters per job, seconds per job, one job per chronicle, old job rows pruned; delete of a chronicle removes its chapters, digests and jobs (tested). Status: not started.
- [ ] 4.3 Chronicler block in Admin → AI system: jobs today, seconds per chapter, failures, last error. Status: not started.
- [ ] 4.4 Release 0.27. Status: not started.

## Log

- 2026-10-17 — Plan written from recmeets' minutes pipeline and the current code; questions for Lef listed in the plan. Nothing built yet.

## Left for later

- Chapters feeding the Storyteller's prompt instead of the trimmed room history: the tables are shaped for it, not done here.
- "What my character knows": a digest per character. Not planned.
- Session breaks set by the Storyteller by hand, a per-section editor, digest history, portraits in the PDF, a cloud writer by default: not planned.
