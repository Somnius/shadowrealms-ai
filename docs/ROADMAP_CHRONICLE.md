# Roadmap: the chronicle so far

Started 2026-10-17. One release per phase; a phase goes live only when it is finished and tested, the rest stays on its branch. The voice work is in [ROADMAP_VOICE.md](ROADMAP_VOICE.md).

What it is: the chat of a chronicle, written up as a story so far, the way recmeets writes the minutes of a meeting. Chapters per room and night, each written by the local model with every event pointing back to the messages it came from; then one digest of the whole chronicle (the story so far, open threads, cast, places, timeline, a Storyteller-only part). The Storyteller and staff read it in Chronicle settings, update it, edit it and export it as Markdown or PDF. Players get a "Previously on…" recap built only from what they could read.

How each phase runs: build in its own git worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file updated → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Status |
|---|---|---|---|---|
| 0 | Measure | synthetic chronicles · a chapter timed on Krikri · does LM Studio queue a Storyteller reply behind a chapter call · VRAM headroom with Whisper and TTS · the live chronicle read by eye with Lef | — | done 17 Oct (Lef read the results and agreed; Krikri at 32k) |
| 1 | Summary, minutes, archive | chronicler roles · busy marker · chapters (gap, session-mark ids, cleanup) · era digests · jobs · routes · panel · Markdown export · minutes for the whole chronicle or the last N nights · archive on delete (stored minutes + raw transcript) · `campaigns.language` column | 0.24 | done: released 0.24.0 (17 Oct) |
| 2 | Sheet-look PDF, edits, languages | PDF in the sheet's look · Storyteller's edit copy · translation on request · chronicle language asked at creation | 0.25 | done: released 0.25.0 (17 Oct) |
| 3 | Horror look, date ranges, session marks | horror PDF (committed paper image + reportlab, A4 and Letter, one test print) · minutes for a date range · "session ended here" from the message menu, shown to players | 0.26 | done: released 0.26.0 (17 Oct) |
| 4 | Previously on… | recap card after 12 h away and a button · jump to the message · read-out | 0.27 | done: released 0.27.0 (17 Oct) |
| 5 | Ops | nightly run (quiet window) · per-chronicle settings · caps · admin health · admin archive page | 0.28 | built on `chronicle/p5` (17 Oct); review next |

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

## Round 2 decisions (2026-10-17, Lef)

- **Archive on delete:**
  - If it can't be written, the delete stops with an error and the chronicle stays.
  - It always holds two files: the minutes from the nights already written, and the full raw transcript of every room with hidden rolls marked. The top says what's covered.
  - It's kept until an admin deletes it.
  - **Downloads: site admins, plus the Storyteller who deleted it, for 30 days (Lef).**
- **GPU:** the writer runs only after 10 minutes with no new message in that chronicle. An Update pressed during play queues and says "waiting for a quiet moment".
- **Minutes for a date range:**
  - The range is the real date, in the Storyteller's timezone, and a night counts by its first message.
  - Unwritten nights are reported, not written.
  - The file is always the generated record; hand edits apply only to the whole story.
- **Helpers:** they read and export but don't edit, and they see only the chronicles they can already open.
- **OOC said in a story room** counts as table talk, so it shows only "with table talk".
- **Session-end marks** show to players as a thin "— end of session —" line.
- **"Previously on…"** appears as a card when a player opens a room after 12 hours or more away, and from a button.
- **The horror look** is rebuilt in reportlab with a committed paper image. Sizes are A4 and Letter, with one test print by Lef.
- **Phase 0** may read "The Echoing Basement" with the local model only; Lef reads the result by eye.
- **Five releases, 0.24 to 0.28,** as in the table above.

## Review findings (2026-10-17, two independent reviews of the plan)

Build rules that come out of the reviews. These are not product choices; Lef's choices are in the two decision sections above.

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
- **Live progress (Lef: tell the viewer it takes time, and show live data from LM Studio):**
  - **The source:** `POST /v1/chat/completions` with `stream: true` and `stream_options.include_usage: true`. LM Studio sends one chunk per token, then a final `usage` chunk; this was checked on this LM Studio. `LMStudioProvider.generate` gets an `on_token` callback (`ai_providers.py` hard-codes `stream: False` today), used only by the writer roles. The Storyteller stays non-streaming.
  - **Progress:** the job thread keeps it in memory and writes it to `chronicle_jobs` at most every 1.5 s, plus at each night and at the end:
    - the night and the number of nights
    - tokens for this night and in total
    - tokens per second over the last 2 s
    - elapsed time, time left, and the phase (waiting / writing / era digests / joining)
  - **The browser:** it polls `GET …/chronicle/jobs/<id>` every 1.5 s (5 s while waiting), reusing the recorder's job-polling pattern; no SSE, because the room stream carries players' traffic.
  - **Up front:** the page says how long it will take: nights to write × the median seconds per night of the last 10 jobs (6 s before there are any), plus the era digests and the join, and it warns when the run stops at 40 nights. During the run the estimate is refined after each night, and it never jumps up.
  - **The card:** "Night 3 of 12", a progress bar (a new `ProgressBar` in the design system), "1,240 tokens · 104 tok/s" ("Reading the night…" before the first token), elapsed and time left, "Waiting for a quiet moment" with a spinner, and Cancel. 44 px, EN + EL.
  - **Cancel** closes the stream, so LM Studio stops generating; this is checked once with `lms log stream`. Each call has a timeout between chunks. A job whose row hasn't been updated for 60 s is marked stale and picked up again on the next claim.
  - **Context before each night:** the night's prompt, its `max_tokens` and the Storyteller's context must fit in the loaded context, or the night is split smaller. On "Context size has been exceeded" it waits 30 s and retries once with the night split.
- **Krikri at 32,768 context (phase 0):** it fits with Whisper loaded (13.4 GB of 16 GB). The quick start and the docs load it like that.
- **Instructions in the chronicle's language,** with a rule against clans, titles and relationships that aren't in the lines. The summary is a list of 2–4 explained paragraphs in the enforced format, and the title is in the chronicle's language.
- **The footer link to lefteros.com** is the one host named in exported files, at the user's request. Docs and tests still name no host.

## Phase 0 — Measure

- [ ] 0.1 Three synthetic chronicles (Greek, English, mixed; 1, 10 and 60 nights; hidden rolls, a closed room, in-room OOC, a session mark) as a pytest fixture generator. Status: moved into 1.2, where the tests that use them are written.
- [x] 0.2 Krikri on real nights of 2,100–4,000 tokens: 4–7 s each at about 100 tokens a second, valid JSON every time, ids real (numbers with the enforced schema). **The instructions must be in Greek:** English instructions gave 0–13% Greek, Greek ones 94–100%. One invention ("Ventrue Prince"), so the prompt needs a rule against clans and titles that aren't in the lines. Status: done 17 Oct.
- [x] 0.3 There are 4 parallel slots, so there's no queueing: a Storyteller reply during a chapter isn't slower. **But the slots share the context:** at 8k, a 4k chapter plus a 5.7k Storyteller prompt both fail with "context exceeded". At 16k both succeed, for +1 GB. GPU memory: 8.9 GB at 8k, 10.0 GB at 16k, 11.3 GB with Whisper too (of 16 GB). Status: done 17 Oct.
- [x] 0.4 "The Echoing Basement" summarised by the local model only and read by eye with Lef. Status: done 17 Oct; Lef is happy with the detailed summaries (`to-lef/chronicle/PHASE0_RESULTS.md`).

## Phase 1 — Summary, minutes, archive (0.24)

- [x] 1.1 Schema through `ensure_*` and `init_postgresql_schema.sql`:
  - tables `chronicle_chapters`, `chronicle_digests`, `chronicle_jobs`, `chronicle_archives`
  - `campaigns.language` (nullable)
  - `messages.session_end` (or a marks table)
  - roles `chronicler_el` and `chronicler_en`, in `ROLES`, the admin AI panel and AI_SYSTEMS.md
  - the cross-process "Storyteller busy" marker

  Status: done 17 Oct: the four tables plus `chronicle_session_marks` (a marks table, not a column) and `ai_busy_marks` (the busy marker, bumped around every Storyteller generation in `SmartModelRouter`); one DDL list in `database.py` reused for SQLite; CI's schema diff checked locally against PostgreSQL 16 (no change after `migrate_db()`, twice).
- [x] 1.2 Pure core `services/chronicle_digest.py`:
  - lines per view
  - the cutter: room, a 6-hour gap and session-mark ids
  - token budget and splitting; overflow is a failure, never a shrink
  - prompts with the schema
  - parse and checks: ids, names, language share, mixed scripts
  - botch and critical injection
  - table talk stored as `ooc`
  - `st_notes` from hidden rows only
  - hashes that include the room state
  - era digests
  - fixed words in EL and EN
  - Markdown for the story and the minutes

  pytest on the synthetic chronicles with a fake model. Status: done 17 Oct; after review a session mark cuts every room at its time, the hash counts only the names a night mentions, the retry carries the model's answer, nights are numbered by what players see. 21 tests on synthetic chronicles (Greek, English, mixed; 1, 10, 60 nights; hidden roll, closed room, in-room OOC, session mark). A night that doesn't fit is written in parts and the parts are merged without another model call.
- [x] 1.3 Jobs `services/chronicle_jobs.py`:
  - claim with `FOR UPDATE SKIP LOCKED` plus a per-chronicle lock
  - the quiet window (10 minutes with no message)
  - progress, partial runs reported ("40 of 63 nights"), cancel
  - stale chapters only; orphan chapter rows deleted

  Status: done 17 Oct; after review the claim skips chronicles that aren't quiet (one waiting chronicle no longer blocks the others), `finish_reason: length` halves the night at once, a night still in the wrong language is translated (flagged only if that fails), cancelled and failed jobs don't count against the 5 minutes, errors are short codes, and the estimate counts only the eras that change. Before that: streaming with `on_token` in `LMStudioProvider`, progress every 1.5 s, ETA from past jobs (6 s a night before any), stale jobs reclaimed after 60 s, overflow → wait 30 s → halves; claim and advisory lock checked against PostgreSQL by hand. 15 tests with a fake model.
- [x] 1.4 Routes under `/api/campaigns/<id>/chronicle`:
  - the digest, jobs, chapters
  - `chronicle.md` (story, optional table talk)
  - `minutes.md` for the whole chronicle or the last N nights, as a render of stored chapters

  Permission tests: outsider 404; player 403 on Update and exports; helper read and export only when they can open the chronicle; no username and no Storyteller keys in player data; rooms checked again at read time. Status: done 17 Oct: also `…/chronicle/estimate`. Lef: helpers read and export only; Update and Rewrite everything are for the Storyteller and admins; 503 `no_worker` without PostgreSQL; the player view lists no NPC that no visible night names and no closed room. 8 route tests.
- [x] 1.5 Archive on delete:
  - inside `delete_campaign` before the SQL delete, write the stored minutes plus the raw Storyteller-view transcript (hidden rolls marked, header saying what's covered) to `data/chronicle_archive/`
  - an index row in `chronicle_archives`
  - if the write fails, the delete stops
  - download routes: site admins always, the deleting Storyteller for 30 days; the path comes from the row
  - noted in SECURITY_MODEL.md

  Status: done 17 Oct: `services/chronicle_archive.py`, written before any cleanup in `delete_campaign` and removed again if the delete then fails; routes `/api/chronicle-archives` (filtered in SQL). Lef: the chronicle's Storyteller downloads for 30 days whoever pressed delete.
- [x] 1.6 Panel "The chronicle so far" in Chronicle settings: the time estimate before starting (Start / Cancel), the live progress card (night x of y, bar, tokens and tok/s from the LM Studio stream, elapsed and time left, waiting state, Cancel), the status line for partial runs, Export story / minutes, the digest read-only, the Storyteller part behind a toggle. A new `ProgressBar` component. 44 px buttons, EN + EL, jest. Status: done 17 Oct: `ChronicleSoFarPanel.jsx`, `ProgressBar`; after review Rewrite everything has its button, helpers see no Update, the quiet minutes come from the server, queued jobs poll every 1.5 s, the "not fully in Greek" flag shows on a night. 10 jest tests.
- [x] 1.7 Release 0.24: `docs/CHRONICLE.md`, FEATURES, CHANGELOG, this file. Status: done 17 Oct: CHRONICLE.md, FEATURES, CHANGELOG, AI_SYSTEMS, SECURITY_MODEL, version 0.24.0.

## Phase 2 — Sheet-look PDF, edits, languages (0.25)

- [x] 2.1 The sheet's frame, sigil, rule, footer and fonts lifted into `services/pdf_look.py` (sheet tests unchanged); `chronicle.pdf` in the sheet look; footer with the lefteros.com link in the file's language; Greek checked; A4 and Letter. Status: done 17 Oct: `services/chronicle_pdf.py` draws the PDF from the same Markdown as the `.md` (headings, paragraphs, lists, bold, italic only; no links from the text), `chronicle.pdf` and `minutes.pdf` with the `.md` permissions, the Storyteller part after a page break, footer with page numbers and the one link, producer "ShadowRealms AI". Greek checked by extracting the text with pypdf (added to CI's unit job). After review: tags close in order with a plain-text fallback, EB Garamond Bold (chronicle PDF only; a test checks the sheet stays byte-identical), long headings ellipsized. The sheet's `section` and `footer` still draw through `SheetCanvas.text`, so the sheet tests are unchanged and pass.
- [x] 2.2 The Storyteller's edit copy (Storyteller and admins only), used by the exports and marked in the footer; a notice when a newer digest exists. Status: done 17 Oct: `GET/PUT/DELETE …/chronicle/edit`, kept across rewrites (`edited_from_hash` tells a newer digest), Keep my edit / Start from the new one. Built so: the player view and the minutes never use the edit; the edit is for the chronicle's own language only; with an edit the table talk option doesn't apply.
- [x] 2.3 Translation on request through the translator role with the names protected, cached; a language switch and `lang=` on exports. Status: done 17 Oct: a `translate` job in the same queue (quiet window, progress per text, Cancel between texts), every text through `translation.translate` with `chronicle_names`, cached as a `chronicle_digests` row marked `translated_from` with a source hash (the panel says when it's behind). After review: ProviderError per text is counted and skipped (job `partial`, untranslated count shown), texts over 2,000 characters split at sentence ends, 15 s per call, `edited_in_target` instead of overwriting an edit, own rate window. Tested with a fake translator; not yet run against a real model.
- [x] 2.4 Chronicle language asked at creation and in Chronicle settings. Status: done 17 Oct: create and update validate `el`/`en` (empty clears it); the settings page has a Chronicle language panel with "most messages decide".
- [ ] 2.5 Release 0.25. Status: docs, changelog and the version bump done on the branch 17 Oct; review, merge and release next.

## Phase 3 — Horror look, date ranges, session marks (0.26)

- [x] 3.1 Horror look: the paper image made once from Serkan's builder (fixed seed) and committed per paper size; reportlab draws the paper, then the frame, thorns and blood as paths, then the text as vector. `look=horror` on exports. One test print by Lef. Status: built 17 Oct: `backend/assets/pdf/paper-a4.jpg` and `paper-letter.jpg` (seed 26, 250 dpi, about 320 KB, README beside them), `services/pdf_horror.py` (frame, thorned corners, splatters, drips from the builder's geometry, a fixed seed per page), ink and blood-red headings in `chronicle_pdf.py`; Look: Sheet / Horror in the panel. Greek checked by extraction, the paper embedded once, text inside the margins (tests). The sheet look is the default and unchanged. After Lef saw the samples ("less background"): the paper made much lighter and calmer (README), the JPEG's bytes go into the PDF unchanged (no ASCII85, +25 % before), and the footer link reads `lefteros.com/apps/shadowrealms-ai` in every PDF and Markdown export. Lef's test print still to do.
- [x] 3.2 Minutes for a date range: a from/to picker in the Storyteller's timezone, nights counted by their first message, unwritten nights reported. Status: done 17 Oct: `from`, `to`, `tz` on `minutes.md|pdf` (default the user's display timezone, then UTC; a range wins over `last`), nights keep their whole-chronicle numbers, unwritten nights in the range counted at the top; From/To pickers in the panel (sending the display timezone or the device's). Tests with Athens time and nights across midnight. After review: every date in a ranged file is in its timezone, one date alone is open-ended, the count of nights to write comes from the changed nights in the range (no double count after a mark), stored nights whose cut is gone are left out, only the range's nights are hashed, and untranslated nights are counted in the other language.
- [x] 3.3 "Session ended here" in the message menu (Storyteller only); players see a thin "— end of session —" line; the cutter already honours it. Status: done 17 Oct: `GET/POST …/chronicle/session-marks`, `DELETE …/session-marks/<id>` (marking: Storyteller and site admins; reading: members, players only in rooms they can read); the chat loads the marks in one small request per chronicle; the line is a timeline row after the marked message. A mark makes the nights it cuts stale (test). No schema change. After review: players never get a hidden roll's id (the mark moves to the last message they can see), a mark on a row the viewer can't see still shows its line, DELETE of a missing mark is 404, and the message toolbar is 44 px on touch screens.
- [ ] 3.4 Release 0.26. Status: docs, changelog and the version bump done on the branch 17 Oct; review, Lef's test print, merge and release next.

## Phase 4 — Previously on… (0.27)

- [x] 4.1 `GET …/chronicle/recap`: the player view's last nights for one room since the character's last visit, plus the story so far in short; rooms checked at read time; 404 for rooms the viewer can't read. Status: done 17 Oct: every member, the stored player view only, no model call; the room checked with `fetch_readable_location_ids` (404), the nights and digest with what players can read now; at most 5 nights, the digest's tldr or about 600 characters of the story so far; the viewer's language when a translation is saved. "Last there" is a new `chronicle_room_visits` row per user and room (`POST …/recap/visit` on opening the room and every 10 minutes in it; `away_since` moves after 12 hours): `location_reads` is per character and moves as messages are read, so it can't tell where an absence began. `recent=1` for the button (the room's last 3 nights). A night’s jump target is its first message players can see. 7 tests.
- [x] 4.2 The recap card when a room is opened after 12 hours or more away (closable), plus a button; a bottom sheet on phones; jump from a night to its first message. Status: done 17 Oct: `PreviouslyOn.jsx` and `previouslyOn.js` in the play page; a scroll button in the room header; closing remembered per room and absence in the browser; Jump to the start pages older history with the reply-quote jump; 44 px, EN + EL. Jest tests.
- [x] 4.3 Read aloud through Listen, off by default. Status: done 17 Oct: Read it on the card, `listen.readRecap` through the same queue as Read this (Listen off too, the user's voice settings); server voices through `POST …/recap/tts`, the text made on the server from the same recap in the narrator's voice. Tests for both paths.
- [ ] 4.4 Release 0.27. Status: docs (CHRONICLE, FEATURES, CHANGELOG), this file and the version bump done on the branch 17 Oct; review, merge and release next.

## Phase 5 — Ops (0.28)

- [x] 5.1 A nightly run at a quiet hour for chronicles with new messages, one at a time, on the first worker only; a per-chronicle switch, off by default. Status: done 17 Oct: `services/chronicle_nightly.py`, started from `main.start_background_jobs` (the first gunicorn worker); `CHRONICLE_NIGHTLY_AT` (05:00), queued for up to 3 hours after it; ordinary Update jobs with no `requested_by`, so the queue, quiet window, busy marker and limits apply; the next one only when the last has ended; "new messages" means since the last finished Update (a partial one counts as unfinished). Tests for switch off, no new messages, one at a time, the limits.
- [x] 5.2 Per-chronicle settings (gap, table talk, nightly, model) and caps (chapters and seconds per job, old jobs pruned). Status: done 17 Oct: `campaigns.chronicle_settings` (`services/chronicle_settings.py`), `GET/PUT …/chronicle/settings` for the Storyteller and site admins; the gap feeds the cutter, jobs, ranged minutes and the archive, and a new gap leaves only the nights it cuts differently stale; table talk is the exports' default; the model is one of the AI panel's listed models (cloud only by a site admin), tried before the role's chain. Caps `CHRONICLE_MAX_NIGHTS_PER_JOB` (40), `CHRONICLE_MAX_SECONDS_PER_JOB` (3600, stops after the night that passes it), `CHRONICLE_JOB_KEEP_DAYS` (90, pruned daily by the nightly thread).
- [x] 5.3 Admin: writer health (jobs, seconds per chapter, failures, last error) and the archive list page. Status: done 17 Oct: `GET /api/chronicle-health` and Chronicle writer next to Voice health; Admin → Archives (name, Storyteller, deleted at and by, size, nights covered, both downloads). The routes already let a Storyteller list their own for 30 days, so they also get `/archives` from the account menu (shown only when they have one). 44 px, EN + EL, jest tests.
- [ ] 5.4 Release 0.28. Status: docs (CHRONICLE, FEATURES, AI_SYSTEMS, CHANGELOG), this file, env vars and the version bump done on the branch 17 Oct; review, merge and release next.

## Log

- 2026-10-17 — Phase 5 built on `chronicle/p5`: per-chronicle settings (gap, table talk, nightly, writer model), the nightly run on the first worker, caps from the environment and pruning of old jobs, writer health in Admin → AI system, the archives page, docs and version 0.28.0. Backend and frontend tests green with fake models. Review next.
- 2026-10-17 — **0.27.0 released**, tested on the live chronicle.

- 2026-10-17 — Two reviews of phase 4 fixed: recap audio indexed with its chronicle and room (`voice_audio.campaign_id`, `location_id`), playable only by members who can read that room and deleted with the chronicle; a translation behind the story is not used; Jump to the start waits for a page in flight; no visit heartbeat in hidden tabs, a visit when the tab is visible again; Read it stops quietly with 409 `recap_changed`, and a speech error is a clean 500; a token refresh no longer re-opens the card; two tabs on a first visit don't collide; on phones a jump hides the sheet without closing it.
- 2026-10-17 — Phase 4 built on `chronicle/p4`: `…/chronicle/recap` and `…/recap/visit` for every member from the stored player view, `chronicle_room_visits` for "last there", the Previously on… card (bottom sheet on phones, header button, jump to a night's first message), Read it through the voice queue with phone or server voices, docs and version 0.27.0. Backend and frontend tests green. Review next.
- 2026-10-17 — **0.26.0 released.**
  - Two reviews fixed, including a session mark revealing a hidden roll's message number to players.
  - Lef's changes: a lighter horror paper, the short footer link, and Colour / Print exports.
  - Lef printed the samples and approved them.
  - Tested on the live chronicle: the export looks, date ranges in Athens time, and session marks splitting and rejoining a night.

- 2026-10-17 — Colour or print on the chronicle PDFs (Lef): `color=colour|print` for both looks, default by look (horror colour, sheet print, the sheet unchanged byte for byte); horror in print on white with the art in black and greys; the sheet in colour with red headings, rules and sigil; a third choice in the panel. Samples `horror-el-a4-story-print.pdf` and `sheet-el-a4-story-colour.pdf`.
- 2026-10-17 — Two reviews of phase 3 fixed and Lef's sample notes applied: a much lighter paper, the short footer link (`lefteros.com/apps/shadowrealms-ai`) in every export, hidden-roll marks kept from players, ranged minutes in the user's timezone with a single count of changed nights, cheaper ranged exports, the paper JPEG passed through unchanged, 44 px message toolbar on phones, open-ended dates, 404 for a missing mark, untranslated nights reported.
- 2026-10-17 — Phase 3 built on `chronicle/p3`: the horror look (committed paper images, vector frame and blood, `look=horror`), minutes for a date range in the Storyteller's timezone, "Session ended here" in the message menu with the end-of-session line, docs and version 0.26.0. Backend and frontend tests green with fake models. Review and Lef's test print next.
- 2026-10-17 — **0.25.0 released.**
  - Two reviews were fixed: the PDF crash on crossed bold/italic in an edit, translations lost on one timeout, long paragraphs cut, partial translations hidden.
  - Real bold in the PDF.
  - Translation was tested on the live chronicle with Krikri and made robust (sentence fallback, titles in sentence case, rolls kept as written, half-translations rejected).

- 2026-10-17 — Two reviews of phase 2 fixed: crossed bold/italic no longer breaks the PDF (tags close in order, plain-text fallback); EB Garamond Bold for the chronicle PDF (sheet output byte-identical); long headings cut with an ellipsis; translation keeps going past timeouts (job `partial`, "n texts still in …"), splits long texts at sentence ends, 15 s per call, Cancel before each call and retry; the name-protection retry keeps names hidden; translations don't hold Update back; Translate refuses to drop an edit in the target language (`edited_in_target`); cancel is Storyteller/admin only; 44 px selects.
- 2026-10-17 — Phase 2 built on `chronicle/p2`: sheet-look PDF (A4 and Letter), the Storyteller's edit copy, translation on request, the chronicle language at creation and in settings, docs and version 0.25.0. Backend and frontend tests green with fake models. Review next.
- 2026-10-17 — **0.24.0 released.**
  - Two reviews fixed, then a polish round after the first real run: Greek dice lines, no repeated citations, Greek titles.
  - A last fix: each night only gets the names its lines use (prompt version 2), after the model placed a night in a room where it never happened.
  - Tested on the live chronicle: the estimate matched the run, the progress was live, Cancel stopped the GPU within 2 s, and the player view had no leaks.

- 2026-10-17 — Polish after the first real run (branch `chronicle/p1-polish`): rolls as a sentence in the chronicle's language, no message numbers inside texts, room-name titles asked again, NPC and room spellings in the prompt.
- 2026-10-17 — Two reviews of phase 1 fixed and Lef's answers applied (helpers read and export only; the Storyteller downloads archives for 30 days; wrong-language nights translated; closed rooms kept; a session mark cuts every room).
- 2026-10-17 — Phase 1 built on `chronicle/p1`: schema, roles, busy marker, digest core, jobs with live progress, routes, archive on delete, panel, docs. Backend and frontend tests green; one chapter checked against Krikri. Review next.
- 2026-10-17 — Plan written from recmeets' minutes pipeline and the current code; questions for Lef listed in the plan. Nothing built yet.
- 2026-10-17 — Live progress designed from what LM Studio actually returns (stream with usage); Krikri at 32k recommended (12.1 GB, 13.4 GB with Whisper; 64k does not fit).
- 2026-10-17 — Phase 0 measured on the live chronicle (results: Greek instructions needed, shared context at 8k fails under load, 16k works with headroom).
- 2026-10-17 — Lef answered round 2: defaults, plus 30-day archive downloads for the deleting Storyteller; five releases 0.24–0.28. Plan final.
- 2026-10-17 — Plan reviewed twice; build rules above; round 2 of questions (17) for Lef.
- 2026-10-17 — Lef answered the 28 questions: defaults, plus session-end marks, both PDF looks, the lefteros.com link in the footer, minutes kept when a chronicle is deleted, and minutes for a date range. Decisions above updated.

## Left for later

- Chapters feeding the Storyteller's prompt instead of the trimmed room history: the tables are shaped for it, not done here.
- "What my character knows": a digest per character. Not planned.
- A per-section editor, digest history, portraits in the PDF, a cloud writer by default: not planned.
