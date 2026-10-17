# Roadmap: the chronicle so far

Started 2026-10-17. One release per phase; a phase goes live only when it is finished and tested, the rest stays on its branch. The voice work is in [ROADMAP_VOICE.md](ROADMAP_VOICE.md).

What it is: the chat of a chronicle, written up as a story so far, the way recmeets writes the minutes of a meeting. Chapters per room and night, each written by the local model with every event pointing back to the messages it came from; then one digest of the whole chronicle (the story so far, open threads, cast, places, timeline, a Storyteller-only part). The Storyteller and staff read it in Chronicle settings, update it, edit it and export it as Markdown or PDF. Players get a "Previously on…" recap built only from what they could read.

How each phase runs: build in its own git worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file updated → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 0 | Measure | synthetic chronicles · Krikri timed on a chapter · results read by eye | — | not started |
| 1 | Chapters and the digest | tables and the chronicler role · chaptering, prompts, checks, join · jobs · routes · settings panel · Markdown export | 0.24 | not started |
| 2 | PDF, edit, languages | PDF in two looks · Storyteller edits a copy · the other language on request · chronicle language · session-end marks | 0.25 | not started |
| 3 | Previously on… | recap route · recap sheet on the play page · jump to the message · read-out | 0.26 | not started |
| 4 | Ops | nightly update · caps · admin health | 0.27 | not started |

## Decisions (2026-10-17, confirmed by Lef)

Lef's answers to the 28 questions (local file `to-lef/chronicle/QUESTIONS.md`). Where he picked something other than the default, it says so.

- **Who:** the Storyteller, site admins and helpers read and export. Players only get "Previously on…" in the app, with no export.
- **When:** on for every chronicle, but nothing runs until someone presses Update. Nothing is written below 8 story messages. The first run goes back to the beginning, at most 40 chapters per run, and the next Update carries on.
- **Chapters:** one room and one night (no gap over 6 hours), with rooms mixed in time order on the timeline. **Also (Lef): the Storyteller can mark where a session ends**, and a mark always starts a new chapter.
- **Language:** a `campaigns.language` asked at creation (default: the creator's app language); older chronicles use the language most of their messages are in. The other language comes from a Translate button and is saved.
- **What goes in:**
  - The OOC lobby stays out, unless the export option "with table talk" is used.
  - The writer sees every roll; botches and criticals are always listed under their night.
  - The Storyteller's version adds a short "what the players didn't see".
  - Player names never appear in the player version, and only in the cast list (in brackets) in the Storyteller's.
  - The AI is called "Storyteller".
  - Backgrounds are not given to the writer.
- **Running it:**
  - Limits: one job per chronicle, one Update every 5 minutes, "Rewrite everything" once an hour.
  - Server defaults first, with per-chronicle settings and an optional nightly run (off by default) in the ops phase.
  - The model: English from the LM Studio model, Greek from Krikri.
  - Cloud writers only if an admin picks one on purpose, with a warning.
  - Reading aloud is possible but off by default.
  - Hand edits go in one Markdown copy.
- **Minutes for the Storyteller (Lef):** besides the digest, the Storyteller can get the full-detail minutes (πρακτικά) for a date range (a from/to picker) or for the whole chronicle, to recall what he may have forgotten.
- **PDF (Lef): both looks, chosen when exporting.**
  - The character sheet's look: frame and sigil, black and white.
  - The horror look of the print PDFs made for Serkan: stained paper, burnt edges, blood and thorns. The paper is a raster image and the text stays vector.
- **Footer (Lef):** "Written by ShadowRealms AI" with a link to the app's page on lefteros.com, in the export's language (`/apps/shadowrealms-ai/` or `/en/apps/shadowrealms-ai/`). There is no model name, server or version in the file. File names are `<chronicle name> — so far.md|pdf`. The Storyteller's export cites message numbers; the player version shows dates only.
- **Storage:** no history; each update replaces the digest, and hand edits are kept apart. **When a chronicle is deleted (Lef): a full-detail Markdown copy of its minutes is written first**, recmeets' minutes format, and kept on the server where only site admins can reach it. Chapters, digests and jobs are then deleted with the chronicle.
- **The AI Storyteller's memory:** the chapters don't feed the Storyteller's prompt in this feature (later).

Earlier technical decisions:

- Same shape as recmeets' minutes: one structured JSON per chapter and one for the digest; Markdown and PDF are both rendered from it; the model's text is never read as markup. Every event cites message ids; uncited or unknown ids are dropped; the cast comes from the database, the model can only comment on names it was given. The chat is data, not instructions.
- A chapter is one room and one night: a run of messages with no gap over 6 hours. A night that doesn't fit the model's context is split and joined (map-reduce), never cut silently. The OOC lobby stays out unless the export asks for table talk.
- Two views. The player view is built from exactly what a player can read (no hidden rolls, no closed rooms). The Storyteller view adds a short "what the players did not see" per night and a Storyteller-only part in the export. Players never get the Storyteller view, and never get the export in this feature.
- Incremental: a hash per chapter, only changed or new chapters are rewritten, then the digest is joined again. Nothing runs per message; the Storyteller presses Update (and later a nightly run at a quiet hour).
- Everything long is a job: create, poll, cancel. One job per chronicle at a time, job state in the database (two gunicorn workers), one chapter call at a time, and a short wait after any Storyteller reply so play comes first on the GPU.
- Language: written in the chronicle's language (Krikri for Greek, the loaded model for English, a new `chronicler` role in Admin → AI system). The other language is a translation of the finished digest, made on request and cached. Greek is checked by its share of Greek letters, as recmeets does; one retry with the reason, then translate as a fallback.
- Edits never touch the generated text: the Storyteller edits a copy; exports use the copy and say so; a newer digest asks "keep my edit or start from the new one".
- PDF: two looks (the sheet's, black and white; the horror print look), Cinzel and EB Garamond, Greek works; footer "Written by ShadowRealms AI" with the link to the app's page on lefteros.com, no model name, no host, no version in the file.
- Schema changes go through `ensure_*` functions in `backend/database.py` and the same DDL in `init_postgresql_schema.sql`, like every other column.
- Nothing in the public repo names a host, a player or a tool.

## Review findings (2026-10-17, two independent reviews of the plan)

Build rules that come out of the reviews. These are not product choices. Product choices still open are in round 2 of the questions; the release order may change with that answer.

- **Two writer roles, one per language:** `chronicler_el` (Krikri) and `chronicler_en` (the loaded model), split like the Storyteller roles. They never fall through to the small Ollama model. They are added to `ROLES` and to the admin AI panel, EN + EL.
- **Never cut a night silently:** `generate_for_role` shrinks prompts that overflow (`ai_roles.py`). For the writer an overflow is a failure, so the night is split smaller and run again (`trimmed > 0` or a `shrink=False` option).
- **Live play first:** `last_generation_meta()` only works inside a request, so it can't tell a job thread that the Storyteller is busy. A small cross-process marker (a row written around each Storyteller generation) lets the job wait for a quiet moment. Phase 0 measures whether LM Studio queues a Storyteller reply behind a chapter call, and the VRAM headroom with Whisper and TTS loaded.
- **One chapter per night:** one summary per night for everyone, plus `st_notes` from a second, short call that only gets the rows players can't see. That means hidden dice and closed rooms; there are no whispers in the app. The player digest has no Storyteller keys at all, and a test checks it.
- **Visibility is checked when it's read:** a chapter's hash includes the room's open/active state. "Previously on…" and every read check `fetch_readable_location_ids` again rather than trusting stored rows. A test checks that no username appears in player-view lines.
- **Chapters that no longer exist are removed:** after each run, chapter rows whose key isn't in the freshly computed set are deleted. That covers session marks, moved 6-hour boundaries and deleted messages. Citations of deleted messages show as "(message removed)".
- **The chapter cutter takes session marks from the start:** the column and the cutter's parameter arrive in phase 1, even if the menu control comes later.
- **`campaigns.language` arrives in phase 1** (nullable; when it's empty, the language most messages are in). Asking for it at creation can come later.
- **Partial runs say so:** "40 of 63 nights; Update continues". The unwritten nights aren't marked up to date.
- **Botches and criticals are always listed:** after the model's events are tidied, any botch or critical not already cited is added from the dice row's fixed sentence.
- **Table talk is always stored:** lobby lines and in-room OOC go into the chapter's `ooc` list, which the story prompt never sees. Exports show it only "with table talk".
- **The summary of the whole chronicle is updated in steps too:** a digest per era of about 10 chapters, hashed like a chapter, then one final join over at most 8 era digests. Otherwise a 60-night chronicle redoes about 15 join calls on every Update at 8k context.
- **Minutes are a render, not a second pipeline:** minutes for the whole chronicle, the last N nights or a date range are the stored chapter records rendered as Markdown in a minutes layout. There are no extra model calls, and the file says which nights it covers. A date range uses the Storyteller's timezone, and a night counts by its first message.
- **The archive on delete makes no model calls:** inside `delete_campaign`, before the SQL delete, it writes `data/chronicle_archive/<id>-<slug>-<time>/` with the minutes rendered from stored chapters plus the raw Storyteller-view transcript. It adds an index row in `chronicle_archives` and admin-only routes to list and download, with the path taken from the row and never from the request. It goes in docs/SECURITY_MODEL.md, because the archive holds hidden rolls.
- **Jobs are claimed safely:** two gunicorn workers claim with `SELECT … FOR UPDATE SKIP LOCKED`, then the per-chronicle lock. The nightly run is on the first worker only.
- **The horror look in the app:** no browser engine in the backend. The stained-paper image is made once (with a fixed seed) by Serkan's builder and committed per paper size; reportlab draws it as the page background, the frame, thorns and blood as vector paths (the sheet code already draws SVG paths), and the text as vector. One test print before release.
- **The footer link to lefteros.com** is the one host named in exported files, at the user's request. Docs and tests still name no host.

## Phase 0 — Measure

- [ ] 0.1 Three synthetic chronicles (Greek, English, mixed; 1, 10 and 60 nights; hidden rolls and a closed room) as a pytest fixture generator. Status: not started.
- [ ] 0.2 Krikri at the loaded 8k context on one 4000-token chapter prompt: seconds, tokens per second, how often the JSON is usable, how often the Greek check passes; the same for the English model. Sets the chapter budget. Status: not started; no such measurement exists yet.
- [ ] 0.3 The digest of the live chronicles read by eye with Lef in both languages: does it get the gist, does it invent. Status: not started.

## Phase 1 — Chapters and the digest, Markdown (0.24)

- [ ] 1.1 Tables `chronicle_chapters`, `chronicle_digests`, `chronicle_jobs` through `ensure_chronicle_tables`; the `chronicler` AI role with its row in Admin → AI system and the table in AI_SYSTEMS.md. Status: not started.
- [ ] 1.2 Pure core `services/chronicle_digest.py`: lines from message rows for the player and Storyteller views, chaptering by room and night, token budget and splitting at a message, chapter and join and digest prompts with the schema in the prompt, parse and checks (ids, names, empty, language share, mixed scripts) with the retry reason, hashes, the fixed words in EL and EN, Markdown. pytest on the synthetic chronicles with a fake model. Status: not started.
- [ ] 1.3 Jobs `services/chronicle_jobs.py`: a worker thread per process, an advisory lock per chronicle, progress "chapter 3 of 7", cancel between calls, the wait after a Storyteller reply, only stale chapters rewritten. Status: not started.
- [ ] 1.4 Routes under `/api/campaigns/<id>/chronicle`: the digest, jobs (create, poll, cancel), chapters, `chronicle.md`, and the minutes (`minutes.md?from=&to=`, full detail per night, a date range or the whole chronicle). Permission tests: outsider 404, player 403 on Update and exports, helper and Storyteller allowed, hidden rolls and closed rooms never in the player view. Status: not started.
- [ ] 1.5 Panel "The chronicle so far" in Chronicle settings: status line, Update with progress and Cancel, Export Markdown, Minutes with a from/to date picker or "whole chronicle", the digest read-only, Storyteller-only section behind a toggle; 44 px buttons, works on a phone. EN + EL. jest for the panel states. Status: not started.
- [ ] 1.6 Release 0.24: `docs/CHRONICLE.md`, FEATURES, CHANGELOG, this file. Status: not started.

## Phase 2 — PDF, edit, languages (0.25)

- [ ] 2.1 The sheet's frame, sigil, section rule, footer and fonts lifted into `services/pdf_look.py` (sheet tests unchanged); `services/chronicle_pdf.py` with two looks, `look=sheet|horror`. The horror look follows the print PDFs made for Serkan: a stained paper background at about 250 dpi as an image, then a vector frame, thorned corners and blood, with the text stamped on top. `chronicle.pdf` route; Export PDF with a look choice; Greek checked in the file; A4 and Letter; footer with the lefteros.com link. Status: not started.
- [ ] 2.2 Edit: the Storyteller's Markdown copy, saved with `PUT`, used by the exports and marked in the footer; the notice when a newer digest exists. Status: not started.
- [ ] 2.3 The other language on request: a translate job through the translator role with the chronicle's names protected, cached as its own row, a language switch in the panel and `lang=` on exports. Status: not started.
- [ ] 2.4 `campaigns.language` asked at creation (default: the creator's UI language) and in Chronicle settings; the digest's default language. Status: not started (Lef: yes).
- [ ] 2.4b Session-end marks: the Storyteller marks "session ended here" on a message (the message menu, Storyteller only); a mark always starts a new chapter, and the 6-hour gap still applies. Status: not started.
- [ ] 2.5 Release 0.25. Status: not started.

## Phase 3 — Previously on… (0.26)

- [ ] 3.1 `GET …/chronicle/recap`: the player view's last nights for one room since the character's last read, plus the story so far in short; 404 for rooms the viewer can't read. Status: not started.
- [ ] 3.2 Recap sheet on the play page (a bottom sheet on phones) with a jump from a night to its first message in the room. Status: not started.
- [ ] 3.3 Read the recap aloud through Listen as its own kind, off by default. Status: not started.
- [ ] 3.4 Release 0.26. Status: not started.

## Phase 4 — Ops (0.27)

- [ ] 4.1 Nightly update at a quiet hour for chronicles with new messages, one at a time, skipped while the Storyteller is answering; a per-chronicle switch, off by default. Status: not started.
- [ ] 4.2 Caps: chapters per job, seconds per job, one job per chronicle, old job rows pruned. Deleting a chronicle first writes its full-detail minutes as Markdown to a server folder only site admins can reach (Admin → archived chronicles, download), then removes its chapters, digests and jobs. Tested. Status: not started.
- [ ] 4.3 Chronicler block in Admin → AI system: jobs today, seconds per chapter, failures, last error. Status: not started.
- [ ] 4.4 Release 0.27. Status: not started.

## Log

- 2026-10-17 — Plan written from recmeets' minutes pipeline and the current code; questions for Lef listed in the plan. Nothing built yet.
- 2026-10-17 — Plan reviewed twice; build rules above; round 2 of questions (17) for Lef.
- 2026-10-17 — Lef answered the 28 questions: defaults, plus session-end marks, both PDF looks, the lefteros.com link in the footer, minutes kept when a chronicle is deleted, and minutes for a date range. Decisions above updated.

## Left for later

- Chapters feeding the Storyteller's prompt instead of the trimmed room history: the tables are shaped for it, not done here.
- "What my character knows": a digest per character. Not planned.
- A per-section editor, digest history, portraits in the PDF, a cloud writer by default: not planned.
