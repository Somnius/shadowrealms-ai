# Labelling chat and evaluating Laya

Laya is the classifier behind the OOC monitor (is this message written in character?) and intent
routing (`dice`, `combat`, `rules_question`, `roleplay`, `general`). This is how to check it
against real chat. Results so far: [EVALUATION.md](EVALUATION.md).

## Admin tab

Admin panel → **Laya** (`/admin/laya`).

1. **Label queue.** Player chat only: no Storyteller replies, no dice rows, no system rows.
   Filter by unlabelled / labelled / stale, chronicle and language (detected from the text).
   For each message pick **in / out of character** and an **intent**, then save.
   Keys: `I` / `O`, `1`-`5` for the intent, `Enter` to save, `J` / `K` to move. Click a message
   first; keys only work in the list, not in fields, links or buttons.
   "Stale" means the text changed after it was labelled; stale labels are left out of evaluations
   until relabelled.
2. **Progress** shows how many messages are labelled and the label balance. Aim for at least 30
   per label (and per language) before reading the numbers as rates.
3. **Run evaluation.** Runs Laya on every labelled message, the same way the OOC monitor does
   (in character = P(IC) >= `OOC_VIOLATION_THRESHOLD`, default 0.8), in the background. The
   report has accuracy with a 95% interval, precision / recall / F1 and n per label, confusion
   matrices, a per-language line and the misclassified messages. Labels under 30 examples, or a
   set under 100, are flagged "sample too small". Earlier runs stay in the list.
   A label with no human examples at all isn't counted in "too small"; its precision / recall /
   F1 show as "–" (undefined), not 0.
   A run still "running" after max(30 min, 1 s per label) is treated as crashed and marked failed.

Stored reports keep message ids, not text; the text is looked up when a report is opened, so a
deleted message drops out of old reports too.

## CLI

Inside the backend container (cwd `/app`):

```
python scripts/laya_eval.py                    # labels from the DB, print the report (read-only session)
python scripts/laya_eval.py --save             # also store it; it shows up in the admin tab
python scripts/laya_eval.py --json             # report as JSON
python scripts/laya_eval.py --labels l.jsonl   # labels from a file instead of the DB
python scripts/laya_eval.py --no-text          # leave out the message excerpts
```

From the host: `docker compose exec backend python scripts/laya_eval.py`.

A label file has one JSON object per line:
`{"message_id": 231, "in_character": true, "intent": "roleplay"}`.
Ids that are missing or aren't player chat are counted and skipped.

## API

All admin-only, under `/api/admin/laya`: `GET messages`, `PUT` / `DELETE labels/<message_id>`,
`POST evaluate` (202, one run at a time, 409 if one is running), `GET report[?id=]`.
Tables: `laya_labels` (one row per message, deleted with the message) and `laya_eval_reports`.
