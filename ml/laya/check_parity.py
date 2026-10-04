#!/usr/bin/env python3
"""infer.py's token sequences == laya.common.build_sequence's, for every seed
message (run in the training container). usage: check_parity.py <model_dir> <run_dir>"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from transformers import AutoTokenizer
from laya.agent import _fix_tokenizer_config
from laya.common import build_sequence
from question import OOC_QUESTION, INTENT_QUESTION, state_of
from infer import LayaClassifier

model_dir, run = sys.argv[1], sys.argv[2]
_fix_tokenizer_config(run)
tok = AutoTokenizer.from_pretrained(os.path.join(run, "tokenizer"))
cfg = json.load(open(os.path.join(run, "rl_agent_config.json")))
clf = LayaClassifier(model_dir)
texts = [json.loads(l)["text"] for f in sorted(glob.glob(os.path.join(HERE, "seeds", "*.jsonl"))) for l in open(f, encoding="utf-8")]
texts += ["<mask> weird [MASK] «quotes» — ünïcode 🎲 " * 3, "x" * 5000]
bad = 0
for t in texts:
    for name, q in (("ooc", OOC_QUESTION), ("intent", INTENT_QUESTION)):
        ref = build_sequence(tok, state_of(t), q, cfg["max_len"], cfg["head_max_len"])
        if clf.sequence(name, t) != (ref[0], ref[1]):
            bad += 1
            print("MISMATCH", name, repr(t[:80]))
print(f"{len(texts)} texts x 2 questions, {bad} mismatches")
sys.exit(1 if bad else 0)
