# Laya on real chat: evaluation

First run: 2026-10-04, on the live instance's chat. Re-run it whenever games have produced more
chat (see [HOWTO.md](HOWTO.md)); this file is a snapshot, the admin "Laya" tab has the latest.

## What was measured

- **Model:** `laya-shadowrealms-chat` (laya.json sha256 `97070eefe2d3`, model.onnx 343,204,364 bytes),
  run the way the OOC monitor runs it (`LayaProvider.classify`, in character = P(IC) >= 0.8).
- **Messages:** every player chat message in the database: `role = 'user'`, not a system row, not a
  dice row. That is **8 messages** out of 35 rows (the rest: 12 dice roll / rouse rows, 11 dice
  animation markers, 4 Storyteller replies). 2 chronicles, 7 English and 1 Greek, 6 in IC rooms
  and 2 in the OOC lobby.
- **Labels:** **provisional, made by Claude (the AI assistant) on 2026-10-04, not by a human
  admin.** They were never written to the live DB (it has no label table yet); they were passed to
  the CLI as a file. A human should check them in the admin tab once this ships.

| message | language | label (in character / intent) | Laya: P(IC), intent (score) |
|---|---|---|---|
| 231 | en | in / roleplay | 0.965, roleplay (0.89) |
| 233 | en | in / roleplay | 0.966, roleplay (0.89) |
| 239 | en | in / roleplay | 0.966, roleplay (0.89) |
| 248 | en | in / roleplay | 0.966, roleplay (0.89) |
| 249 | en | out / roleplay | 0.034, **general** (0.88) |
| 250 | en | out / rules_question | 0.034, **dice** (0.54) |
| 251 | el | in / roleplay | 0.966, roleplay (0.89) |
| 256 | en | in / roleplay | 0.966, roleplay (0.89) |

## Results

**The sample is far too small to give rates.** 8 messages, 6 in character and 2 out, 7 of them one
intent. Every label is under the tool's threshold of 30 examples, and the set is under 100.

- **In character (the OOC monitor's question):** 8 of 8 right. 95% Wilson interval 0.68-1.00, so
  all this says is "probably not worse than about 2 in 3". No false positives (the expensive
  error: 3 warnings mean a 24 h campaign ban), but with only 2 out-of-character messages that
  means little.
- **Intent:** 6 of 8 (0.75, interval 0.41-0.93). The 2 misses:
  - #250, a rules question about Willpower rerolls and Hunger dice, went to `dice` with a low
    score (0.54). The router only uses Laya's intent at score >= 0.6, so in practice this one
    would have fallen back to the keyword rules.
  - #249, the player greeting the table and saying where their character will go first, went to
    `general`. Labelling grey zone: the intent wording counts "the player plans a scene" as
    `roleplay`, but the message is half greeting. Labelled `general`, Laya would be right.
- Scores sit at the saturated values the model README describes (P(IC) ~0.034 / ~0.966, top
  intent ~0.89), so they say little about confidence on individual messages.
- `dice`, `combat` and `general` have no labelled examples at all; their precision/recall are
  undefined, not zero.

## Limits

- 8 messages from 2 test chronicles, mostly written to try the app, not from real play.
- One labeller, and that labeller is an AI. Labels are provisional.
- 1 Greek message, no Greeklish.
- Nothing here is comparable with the model card's numbers (289 held-out hand-written messages,
  `ml/laya/README.md`), which remain the better estimate until real games add a few hundred
  labelled messages.

The same report, reproduced with:

```
python scripts/laya_eval.py --labels labels.jsonl   # in the backend container, read-only
```
