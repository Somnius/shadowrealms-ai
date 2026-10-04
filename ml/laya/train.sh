#!/usr/bin/env bash
# Items -> training -> dev-set pick -> test report -> ONNX package, all in the
# shadowrealms-laya-train image (see Dockerfile). Data lives in data/laya/ (gitignored).
#
#   ml/laya/train.sh [run_name]          # default run1; EPOCHS=3 by default
#
# Needs data/laya/base-multilingual (laya-multilingual: encoder/, tokenizer/,
# model.safetensors, rl_agent_config.json) and data/laya/dataset/{train,dev,test}.jsonl
# from generate_data.py finalize. CPU is capped (--cpus, nice) per the machine's 80% rule.
# The GPU needs ~8 GB free: unload LM Studio models first (`lms unload --all`).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RUN="${1:-run1}"
EPOCHS="${EPOCHS:-3}"
IMG=shadowrealms-laya-train
W=/ft/w; S=/ft/s
dock() { docker run --rm --cpus "${CPUS:-16}" --shm-size 2g --user "$(id -u):$(id -g)" -e HOME=/tmp -e USER=laya "$@"; }
gpu=(--device nvidia.com/gpu=all)
vols=(-v "$REPO/data/laya:$W" -v "$REPO/ml/laya:$S" -e PYTHONDONTWRITEBYTECODE=1 -e HF_HUB_OFFLINE=1)

docker image inspect "$IMG" >/dev/null 2>&1 || docker build -t "$IMG" "$REPO/ml/laya"

echo "== items"
dock "${vols[@]}" "$IMG" nice -n 10 python $S/prep_items.py $W/base-multilingual $W/train.pt $W/dataset/train.jsonl
dock "${vols[@]}" "$IMG" nice -n 10 python $S/prep_items.py $W/base-multilingual $W/dev.pt $W/dataset/dev.jsonl --eval
dock "${vols[@]}" "$IMG" nice -n 10 python $S/prep_items.py $W/base-multilingual $W/test.pt \
  $W/dataset/test.jsonl --eval   # test.jsonl = held-out seeds + seeds/extra_test.jsonl

echo "== train ($EPOCHS epochs)"
start=$(date +%s)
dock "${gpu[@]}" "${vols[@]}" -e EPOCHS="$EPOCHS" -e FREEZE_EMBEDDINGS="${FREEZE_EMBEDDINGS:-1}" -e MICRO_BATCH="${MICRO_BATCH:-4}" -e GRAD_ACCUM="${GRAD_ACCUM:-8}" -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$IMG" \
  nice -n 10 torchrun --standalone --nproc_per_node=1 $S/train.py $W/base-multilingual $W/$RUN $W/train.pt \
  2>&1 | tee "$REPO/data/laya/$RUN.log"
echo "training took $(( $(date +%s) - start )) s" | tee -a "$REPO/data/laya/$RUN.log"

echo "== dev set, every epoch"
for e in $(seq 1 "$EPOCHS"); do
  dock "${gpu[@]}" "${vols[@]}" "$IMG" nice -n 10 python $S/evaluate.py torch $W/$RUN/epoch-$e $W/dev.pt \
    --out $W/$RUN/dev-epoch-$e.json > "$REPO/data/laya/$RUN/dev-epoch-$e.txt"
  echo "epoch $e: $(grep -A3 '=== all' "$REPO/data/laya/$RUN/dev-epoch-$e.txt" | tr '\n' ' ')"
done
# pick: the epoch with the best mean of OOC macro-F1 and intent macro-F1 on dev (BEST=n overrides)
BEST="${BEST:-$(python3 - "$REPO/data/laya/$RUN" "$EPOCHS" <<'PY'
import json, sys
d, n = sys.argv[1], int(sys.argv[2])
def score(e):
    r = json.load(open(f"{d}/dev-epoch-{e}.json"))["report"]["all"]
    o = r["ooc"]
    return (o["in_character_class"]["f1"] + o["out_of_character_class"]["f1"]) / 2 + r["intent"]["macro_f1"]
print(max(range(1, n + 1), key=score))
PY
)}"
echo "== best epoch on dev: $BEST"

echo "== test set (held-out seeds + extra hand-written), torch"
dock "${gpu[@]}" "${vols[@]}" "$IMG" nice -n 10 python $S/evaluate.py torch $W/$RUN/epoch-$BEST $W/test.pt \
  --out $W/$RUN/test-epoch-$BEST.json | tee "$REPO/data/laya/$RUN/test-epoch-$BEST.txt"

echo "== package -> data/laya/model"
rm -rf "$REPO/data/laya/model.new"
dock "${vols[@]}" "$IMG" nice -n 10 python $S/package.py $W/$RUN/epoch-$BEST $W/model.new
dock "${vols[@]}" "$IMG" nice -n 10 python $S/check_parity.py $W/model.new $W/$RUN/epoch-$BEST
rm -rf "$REPO/data/laya/model" && mv "$REPO/data/laya/model.new" "$REPO/data/laya/model"

echo "== test set, packaged ONNX model on CPU"
CPUS=4 dock "${vols[@]}" "$IMG" nice -n 10 python $S/evaluate.py onnx $W/model \
  $W/dataset/test.jsonl --out $W/$RUN/test-onnx.json | tee "$REPO/data/laya/$RUN/test-onnx.txt"
