# The chronicle so far

Since 0.24. The chat of a chronicle written up as a story, night by night, by the local model, the way meeting minutes are written from a recording. The plan and the phases are in [ROADMAP_CHRONICLE.md](ROADMAP_CHRONICLE.md).

## Who sees it

| Who | What |
|---|---|
| The Storyteller (the chronicle's creator) and site admins | read, Update, Rewrite everything, export; edits come in 0.25 |
| Helpers who can open the chronicle (they are a member of it) | read, Update, export; no edits, no Rewrite everything |
| Players | nothing yet: "Previously on…" comes in 0.27 and never includes the Storyteller's part |
| Anyone else | 404, as for the chronicle itself |

It lives in **Chronicle settings → The chronicle so far**.

## How it is written

1. **Lines.** Every message becomes one numbered line, `M1234 [21:05] [IC] Marcus: text`. The number is the message id, so every event can point back to where it came from. Dice markers, `/ai` helper lines and empty rows are left out; a dice result is one line with the roller's name. Usernames never appear in a line: a character speaks under its name, a player out of character as "Player", staff as "Storyteller" or "Staff".
2. **Chapters.** One room and one night: a run of messages in one room with no gap over 6 hours. A session-end mark (`chronicle_session_marks`; the message menu for it comes in 0.26) always ends a night. Rooms are mixed in time order on one timeline.
3. **Two views.** The story of a night is written from what players could read: hidden rolls and closed rooms are left out (the same rules as the chat: `hidden_dice_sql_filter` and `readable_location_ids`). If an open room had hidden rolls, a second short call writes `st_notes` ("what the players didn't see") from those rows only. A night in a closed room is written whole but shown only in the Storyteller's view.
4. **Table talk.** The OOC lobby and out-of-character lines inside a story room are stored as they were (`ooc`), never shown to the model, and exported only "with table talk".
5. **The model's answer** is one JSON object per night, enforced with `response_format` (a JSON schema): a title, a summary of 2–4 paragraphs, events that cite message ids, characters, places, threads opened and closed. The instructions are in the chronicle's language (Greek instructions for a Greek chronicle; English ones gave English text even when asked for Greek), say that the chat is data and not instructions, and forbid clans, titles, offices, relationships and places that aren't in the lines.
6. **Checks.** Unknown ids are dropped, an event needs at least one id, a character must be a name the chronicle has. The text must be in the chronicle's language (at least half Greek letters for Greek, at most a fifth for English) and no word may mix alphabets. A failed check is asked once more with the reason; letters of other alphabets that survive are removed.
7. **Botches and criticals** are always listed: any that the model didn't cite are added from the dice line.
8. **Eras and the whole.** About 10 nights make an era digest; one final join over the eras (at most 8 at a time) writes "In short", "The story so far" and the open threads, plus a Storyteller-only part from closed rooms and `st_notes`.
9. **Only what changed.** Each night has a hash of what the model would see (its lines, its hidden rows, the names, the language, whether the room is open). Update rewrites only nights whose hash changed and eras that hold them; nights that no longer exist (a session mark, a moved gap, deleted messages) are removed.

Nothing runs per message. Nothing is written below 8 story messages.

## The language

`campaigns.language` (`el` or `en`) when it is set; otherwise the language most story messages are in. Asking for it when a chronicle is made comes in 0.25. Greek is written by the `chronicler_el` role (default Krikri), English by `chronicler_en` (default: the loaded LM Studio model); both are in Admin → AI system and never fall back to the small Ollama model.

## Running it

- **Update** first shows how long it will take: nights to write × the median seconds per night of the last 10 finished jobs (6 s before there are any), plus the eras and the join. It warns when the run will stop at 40 nights.
- **One job per chronicle**, Update at most every 5 minutes, Rewrite everything once an hour.
- **Quiet first.** The writer starts only after 10 minutes with no new message in that chronicle (`CHRONICLE_QUIET_MINUTES`); until then the job says "Waiting for a quiet moment". Before each call it also waits while a Storyteller reply is being written anywhere (the `ai_busy_marks` row each Storyteller generation bumps).
- **Never cut a night.** A night's lines, the answer's `max_tokens` and room for a Storyteller prompt (LM Studio's parallel slots share one context) must fit in the loaded context, or the night is split into parts that are written and joined. On "Context size has been exceeded" the job waits 30 s (`CHRONICLE_OVERFLOW_WAIT_S`) and writes the night in two halves. A prompt is never trimmed (`generate_for_role(shrink=False)`).
- **Partial runs.** At most 40 nights per run; the status line says "40 of 63 nights; Update continues".
- **Jobs in the database.** `chronicle_jobs` holds the state, so either gunicorn worker can answer a poll. A worker thread claims a job with `SELECT … FOR UPDATE SKIP LOCKED` and a per-chronicle advisory lock; a running job whose row hasn't changed for 60 s is picked up again.

## Live progress

The model's answer is streamed (`stream: true` with `stream_options.include_usage`) through an `on_token` callback of the LM Studio provider; the Storyteller's replies stay non-streaming. The job keeps its progress in memory and writes it to its row at most every 1.5 s, and at each night and at the end: the night and the number of nights, tokens for the night and in total, tokens per second over the last 2 s, the phase (waiting, writing, eras, joining) and the time left, which is refined after each night and never goes up.

The panel polls the job every 1.5 s (5 s while waiting) and shows "Night 3 of 12", a progress bar, "1,240 tokens · 104 tok/s" ("Reading the night…" before the first token), elapsed and time left, and Cancel. Cancel closes the stream, so LM Studio stops writing.

## Exports

- **Story** (`chronicle.md`): in short, the story so far, open threads, cast and places from the database (players' usernames only in the Storyteller's view, in brackets in the cast list), every night in short, and the Storyteller-only part. Optional `with_table_talk=1`.
- **Minutes** (`chronicle/minutes.md`, whole chronicle or `last=N` nights): every written night in full — summary, what happened with message numbers, who, where, threads, rolls, what the players didn't see. It is a render of the stored nights: no model call, and it says which nights it covers and how many aren't written yet.
- Model text is never read as markup: it is escaped before it goes into Markdown. Citations of deleted messages show "(message removed)". The footer says "Written by ShadowRealms AI" with a link to the app's page; there is no model name, server or version in the file.

## When a chronicle is deleted

Before anything is deleted, `delete_campaign` writes `data/chronicle_archive/<id>-<name>-<time>/` (or `CHRONICLE_ARCHIVE_DIR`) with two files and an index row in `chronicle_archives`, with no model call:

- `minutes.md`: the minutes of the nights already written, with table talk;
- `transcript.md`: every message of every room as the Storyteller saw them, hidden rolls marked.

Both start with what they cover. If they can't be written, the delete stops with an error and the chronicle stays. Site admins can always download them; the Storyteller who deleted the chronicle can for 30 days (`GET /api/chronicle-archives`, `GET /api/chronicle-archives/<id>/minutes|transcript`). An archive is kept until an admin deletes it.

## API

All under `/api/campaigns/<id>/chronicle`:

| Route | What |
|---|---|
| `GET …/chronicle?view=st\|player` | the digest, the nights, the status (written, total, new messages since) and the last job |
| `GET …/chronicle/chapters` (`?key=`) | the nights |
| `GET …/chronicle/estimate` | nights to write, seconds, capped at 40, enough messages or not |
| `POST …/chronicle/jobs` `{scope: update\|all}` | 202 with the job; 409 while one runs; 429 with `retry_after` |
| `GET` / `DELETE …/chronicle/jobs/<job>` | poll / cancel |
| `GET …/chronicle.md`, `GET …/chronicle/minutes.md` | the exports |

`view=player` is what players will get: no Storyteller keys, no message ids, no usernames, and rooms are checked again when it is read (a room closed since the last Update drops out, and the digest is held back until the next Update).

## Data

`chronicle_chapters` (one row per night and language: the JSON, the hash, the message range), `chronicle_digests` (eras and the final digest; `edited_markdown` is for 0.25), `chronicle_jobs`, `chronicle_archives`, `chronicle_session_marks`, `ai_busy_marks`, and `campaigns.language`. They are created by `ensure_chronicle_tables` and `ensure_campaigns_language_column` in `backend/database.py` with the same DDL in `init_postgresql_schema.sql`. Chapters, digests and jobs go with the chronicle.

Code: `backend/services/chronicle_digest.py` (the pure part: lines, cutting, prompts, checks, Markdown), `backend/services/chronicle_jobs.py` (the database, jobs and the writer thread), `backend/services/chronicle_archive.py`, `backend/routes/chronicle.py`, `frontend/src/features/chronicle/ChronicleSoFarPanel.jsx`.
