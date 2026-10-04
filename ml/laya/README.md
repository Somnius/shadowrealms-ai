# Laya chat classifier (OOC monitor + intent routing)

## Integration interface (for backend/services/classifier.py)

- **Model files** (gitignored, ~378 MB): `data/laya/model/model.onnx` (343,204,364 B),
  `data/laya/model/tokenizer.json` (34 MB), `data/laya/model/laya.json` (questions, special ids,
  temperatures). Override the location with `LAYA_MODEL_DIR`.
- **Code:** `ml/laya/infer.py` (self-contained: copy it next to the service or import it).
- **pip deps:** `onnxruntime` (tested 1.30.0), `tokenizers` (tested 0.23.2; already pulled in by
  transformers/sentence-transformers), `numpy`. No torch.
- **API:**

  ```python
  from infer import LayaClassifier, classify
  clf = LayaClassifier(model_dir=None, threads=None, ooc_threshold=0.5)  # load once (1.4 s, ~590 MB RSS)
  clf.classify(text: str, questions=("ooc", "intent")) -> dict
  classify(text, questions=...)   # module-level singleton, model from $LAYA_MODEL_DIR or data/laya/model
  ```

  ```json
  {"ooc_violation": {"label": true, "score": 0.9652},
   "intent": {"label": "combat", "score": 0.8897,
              "probs": {"dice": 0.03, "combat": 0.89, "rules_question": 0.03, "roleplay": 0.03, "general": 0.02}}}
  ```

  - `ooc_violation.score` = P(message is written in character); `label` = score >= `ooc_threshold`.
    It is a violation only if the message was posted in an OOC room; the model doesn't know the room.
  - `intent.label` is one of `dice | combat | rules_question | roleplay | general`
    (`rules_question` has no `TaskType` member today: add one or map it to GENERAL).
  - `questions=("ooc",)` or `("intent",)` runs one pass only (half the latency) and omits the other key.
- **Latency (CPU, ONNX Runtime, batch 1, 200 seed messages):** 232 ms/message for both
  questions on 4 threads (p95 244 ms), 407 ms on 2 threads; one question is half that.
  Peak RSS 747 MB. `LAYA_THREADS` (default 4) sets intra-op threads. The session is
  thread-safe; serialize calls or run them in a worker if CPU is tight.
- **Scores saturate:** training used soft targets (0.97/0.03 for OOC, 0.92/0.02 for intent),
  so OOC scores sit near 0.03 or 0.965 and the top intent near 0.89 even when wrong.
  Thresholds above ~0.9 never fire; use 0.5 for OOC (no false positives on the test set at
  0.5..0.9) and treat intent `score` < ~0.6 as "unsure -> GENERAL".

## What

A small fine-tuned encoder that answers two questions about a chat message, in
English, Greek and Greeklish, in ~115 ms per question on 4 CPU threads:

- **OOC (a `noul` question):** is the message written *in character*? In an
  Out-Of-Character room, P(in character) high means a rule violation
  ("\*draws my fangs\*", "I lunge at the Prince"). Players talking as themselves
  (rules, dice, scheduling, "my character should...", quoting a character to joke
  about it) are fine.
- **Intent (a `choice` question):** `dice | combat | rules_question | roleplay | general`,
  to route the message to the right handler/model.

Both are one checkpoint. The exact question wording and the state format live in
`question.py`; training, evaluation and `infer.py` all use it.

## Why Laya

[Laya](https://github.com/NandhaKishorM/laya) (Apache 2.0) is an encoder
"decision model" that answers typed questions (`noul`, `choice`, `score`) about a
text. The base, `laya-multilingual` (mmBERT-base, 307M params, MIT), is near chance
zero-shot, but fine-tunes well. It is the same recipe as RecMeets'
`somniusx/recmeets-laya-words` (`~/dev/recmeets/scripts/laya/`,
`docs/research/laya-finetune.md`): RLCD policy gradient on proper-scoring rewards
plus soft cross-entropy, a held-out calibration slice, one fitted temperature per
question type, every epoch saved. It runs on the CPU via ONNX Runtime with no torch,
and replaces an LLM call (`ooc_monitor._detect_ic_content`) and a keyword router.

## Files

| file | what |
|---|---|
| `question.py` | the two questions and `state_of(text)` (shared by everything) |
| `seeds/seeds_en.jsonl`, `seeds/seeds_el.jsonl` | 332 EN + 331 EL hand-written messages (EL includes 60 Greeklish), each with `in_character`, `intent` and a fixed `split` (~50% train / 20% dev / 30% test, stratified) |
| `seeds/extra_test.jsonl` | 92 more hand-written test messages, fresh content (not translations of the seeds), many hard cases |
| `generate_data.py` | synthetic expansion with the local LLMs in LM Studio, a 2-of-3 label vote, dedupe, Greeklish transliteration |
| `prep_items.py` | rows -> tokenized Laya items (2 per message) |
| `train.py` | the RecMeets/Laya training loop; changes: model name, env-tunable batch, `FREEZE_EMBEDDINGS`, lower-memory optimizer/DDP settings |
| `evaluate.py` | per-class / per-language P/R/F1, confusion matrices, OOC AUROC and thresholds; on a torch run or the packaged ONNX model |
| `package.py` | ONNX export + 8-bit block packaging -> `model.onnx`, `tokenizer.json`, `laya.json` |
| `check_parity.py` | `infer.py`'s token sequences == Laya's `build_sequence` |
| `infer.py` | the runtime: `classify(text)` with onnxruntime + tokenizers on CPU |
| `bench.py` | load time, RAM, latency of `infer.py` |
| `train.sh` | items -> train -> pick epoch on dev -> test -> package -> ONNX test |
| `Dockerfile` | `shadowrealms-laya-train` = RecMeets' `recmeets-laya-train` + onnx/onnxruntime |

Data, checkpoints and the packaged model stay out of git, in `data/laya/`
(gitignored): `base-multilingual/`, `gen/` (raw generations and judge labels),
`dataset/{train,dev,test}.jsonl`, `run*/`, `model/`.

## Results (run2, epoch 3 picked on dev; packaged ONNX model on CPU)

Test set = held-out hand-written seeds (197) + the separate hand-written extra set (92):
289 messages, 78 in character. Never seen in training or generation prompts.

| group | n (IC) | OOC acc | IC precision / recall | OOC AUROC | intent acc | intent macro-F1 |
|---|---|---|---|---|---|---|
| all | 289 (78) | 0.986 | 1.000 / 0.949 | 0.996 | 0.872 | 0.873 |
| en | 145 (39) | 0.993 | 1.000 / 0.974 | 1.000 | 0.903 | 0.904 |
| el (Greek letters) | 121 (34) | 0.983 | 1.000 / 0.941 | 1.000 | 0.851 | 0.853 |
| greeklish | 23 (5) | 0.957 | 1.000 / 0.800 | 0.928 | 0.783 | 0.785 |
| held-out seeds only | 197 | 0.985 | 1.000 / 0.942 | | 0.853 | 0.852 |
| extra set only (fresh) | 92 | 0.989 | 1.000 / 0.962 | | 0.913 | 0.909 |
| zero-shot laya-multilingual, all | 289 | 0.702 | 0.420 / 0.269 | 0.684 | 0.488 | 0.488 |

Intent per class (all): dice F1 0.877, combat 0.780, rules_question 0.937, roleplay 0.879,
general 0.891. Confusion (rows gold, cols predicted: dice, combat, rules, roleplay, general):

```
dice            50   1   1   0   3
combat           6  46   2   1   3
rules_question   0   2  52   0   1
roleplay         0  11   0  51   2
general          3   0   1   0  53
```

- OOC: **0 false positives** among 211 out-of-character test messages at any threshold
  0.5-0.9. The 4 misses are in-character lines with no action markers: polite dialogue
  ("Good evening, Primogen. I trust the night finds you well.", same in Greek,
  "Ψιθυρίζω στη Σοφία: πρέπει να φύγουμε. Τώρα.") and one Greeklish attack.
- Intent: the main error is quiet Greek roleplay (walking, bowing, feeding) predicted as
  `combat` (7 of 29 Greek roleplay messages); and OOC combat bookkeeping
  ("I'm at Wounded, how many dice do I lose?") going to `dice` or `rules_question`,
  which is arguably a labelling grey zone.
- The ONNX package matches PyTorch: max |dP(IC)| 0.028, 0 OOC flips and 2 intent flips on 289.
- Training: 3 epochs, 1167 s on the RTX 4080 SUPER (~53 items/s), micro-batch 4 x grad-accum 8.
  Dev (132 messages) per epoch: OOC acc 0.962 / 0.970 / 0.970, intent macro-F1 0.878 / 0.872 / 0.878.

Full reports: `data/laya/run2/test-onnx.{txt,json}` (with every prediction),
`test-epoch-3.*` (torch), `test-zeroshot.json`, `dev-epoch-*.txt`.

## Dataset

10,103 training rows (synthetic 9,769 + 334 train-split seeds), 132 dev, 289 test.

| | dice | combat | rules_question | roleplay | general | in character / out |
|---|---|---|---|---|---|---|
| en | 709 | 910 | 917 | 1,378 | 929 | 1,639 / 3,204 |
| el (Greek letters) | 629 | 724 | 890 | 1,394 | 957 | 1,629 / 2,965 |
| greeklish | 88 | 108 | 122 | 211 | 137 | 239 / 427 |

For the OOC question, in-character items are repeated to 40% of its items (`prep_items.py --ic-share`);
choice options are shuffled per item. 21,096 training items, mean 134 tokens.

How it was made (`generate_data.py`, ~41 min of LLM time):

1. **Generate** 15 messages per call per bucket (dice, rules, general, combat IC/OOC, roleplay
   IC/OOC) with random length/style/names/topics and 6 train-split seeds as examples:
   English with `google/gemma-4-e2b` (5,780 rows, ~370 tok/s), Greek with
   `llama-krikri-8b-instruct` (5,847 rows, ~225 tok/s). `reasoning_effort: none`, JSON schema output.
2. **Judge** every row with *both* models (Krikri and Gemma), batches of 20, temperature 0.
   Krikri alone was unreliable on mechanical OOC messages (it called `/roll 6d10 difficulty 7`
   in character), so strict generator-judge agreement threw away correct hard cases.
   The rule used: **each label must win 2 of 3 votes** (the generator's intended label + 2 judges).
   Kept: en 4,855 / 5,780, el 4,472 / 5,847.
3. **Clean and dedupe:** strip chat-log speaker prefixes ("Anna: ..."), exact duplicates,
   bge-m3 near-duplicates (cosine >= 0.95: 116 dropped), and anything >= 0.92 to a dev/test seed (2).
4. **Greeklish:** 15% of the Greek synthetic rows are copied through a rule-based
   transliteration with casual variants (θ->8/th, ξ->3/ks, ω->w/o, ...), labels unchanged.

## Retrain

```bash
# 0. base model (Apache 2.0 / MIT), e.g. from RecMeets' workspace or HF:
cp -r ~/.cache/recmeets-dev/laya-ft/base-multilingual data/laya/
# 1. data (models must be loaded in LM Studio; check `lms ps` first, unload only what you loaded)
lms load google/gemma-4-e2b -y --parallel 4 -c 8192
python3 ml/laya/generate_data.py gen   --lang en --model google/gemma-4-e2b
python3 ml/laya/generate_data.py judge --lang en --model google/gemma-4-e2b
python3 ml/laya/generate_data.py judge --lang el --model google/gemma-4-e2b   # after el gen
lms unload google/gemma-4-e2b && lms load llama-krikri-8b-instruct -y --parallel 4 -c 8192
python3 ml/laya/generate_data.py gen   --lang el --model llama-krikri-8b-instruct
python3 ml/laya/generate_data.py judge --lang en --model llama-krikri-8b-instruct
python3 ml/laya/generate_data.py judge --lang el --model llama-krikri-8b-instruct
docker run --rm --cpus 8 --network host --user $(id -u):$(id -g) -e HOME=/tmp -e USER=laya \
  -e LAYA_DATA=/ft/w -v $PWD/data/laya:/ft/w -v $PWD/ml/laya:/ft/s shadowrealms-laya-train \
  python /ft/s/generate_data.py finalize          # needs text-embedding-bge-m3 in LM Studio
# 2. items, train, pick epoch on dev, test, package, parity, ONNX test
ml/laya/train.sh run3        # EPOCHS=3, FREEZE_EMBEDDINGS=1, MICRO_BATCH=4, GRAD_ACCUM=8 by default
```

`train.sh` writes `data/laya/<run>/` and replaces `data/laya/model/`. It needs ~3.6 GB of
free VRAM with the defaults (the card is shared with ComfyUI and LM Studio):
`FREEZE_EMBEDDINGS=1` keeps mmBERT's 256k-token embedding table (197M of 322M params)
fixed and in fp16; with more free VRAM, `FREEZE_EMBEDDINGS=0 MICRO_BATCH=8 GRAD_ACCUM=4`
is RecMeets' original setting (not tried here). CPU is capped with `--cpus 16` and `nice`.

## Packaging

`package.py`: Laya's 32-bit ONNX export (opset 18), then MatMul weights in ONNX Runtime's
8-bit block format (`MatMulNBits`, block 64, symmetric, accuracy_level 4) and the embedding
table in 8-bit per tensor: 1.29 GB -> 343 MB. Laya's default per-channel int8 quantizer
is deliberately not used (it broke RecMeets' fine-tune). `check_parity.py` checks that
`infer.py` builds the same token sequences as Laya's `build_sequence` (757 texts x 2
questions, 0 mismatches). The export runs one sequence per call (batch 1).

## Serving alternatives

`infer.py` (ONNX in-process) is the recommended route. `laya-serve` (same `POST /v1/systemone`
protocol as Jev) could serve the PyTorch checkpoint `data/laya/run2/epoch-3/` from a sidecar
via a small launcher with `Router(models={...: path})`; not set up or tested here.

## Limitations (read before trusting the numbers)

- **The test set is hand-written by the same author as the seeds, not real chat logs.**
  The held-out seeds share style with the train seeds, and many Greek seeds are translations
  of English ones (the train split of one language can contain the translation of a test
  message in the other). The fresh extra set (92) avoids that and scores similarly, but it
  is small. The real check is ~300-500 real, hand-labelled messages from campaign rooms;
  set the thresholds on those.
- Greeklish is thin: 23 test messages (5 in character), and the training Greeklish is mostly
  rule-based transliteration, not how people really type.
- Synthetic labels are noisy (spot checks found e.g. an OOC "ST told me..." labelled in
  character). Small models wrote and judged them; a 200-row human spot check was not done.
- No context: the state is the message alone. Short replies like "ok" or a bare line of
  dialogue are judged on their own; previous messages would help with bare dialogue,
  which is where the OOC misses are.
- Intent boundaries are fuzzy by design (OOC combat bookkeeping vs dice vs rules).
- Only one training run with the final data (run1 used seeds with a parsing bug and was
  discarded); no hyper-parameter search, and the embedding table was frozen for VRAM reasons.
- Synthetic data from Krikri falls under the Llama 3.1 licence terms for outputs; check
  clause 1.b.v before publishing the dataset or the model.
