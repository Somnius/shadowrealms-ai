#!/usr/bin/env python3
"""Rows (generate_data.py / seeds JSONL) -> tokenized Laya items (runs in the
training container, which has laya installed). Every row gives two items: the
OOC `noul` question and the intent `choice` question.

usage: prep_items.py <model_dir> <out.pt> <rows.jsonl>... [--eval] [--ic-share 0.4]

Training (default): choice options are shuffled per item (insurance against
position bias) and in-character rows are repeated for the OOC question until
they are --ic-share of its items. --eval: canonical option order, no balancing.
"""
import json, os, random, sys
import torch
from transformers import AutoTokenizer
from laya.agent import _fix_tokenizer_config
from laya.common import build_sequence, render_options, QTYPES

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from question import OOC_QUESTION, INTENT_QUESTION, INTENTS, state_of

args = [a for a in sys.argv[1:]]
evaluation = "--eval" in args
ic_share = float(args[args.index("--ic-share") + 1]) if "--ic-share" in args else 0.4
pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--ic-share")]
model_dir, out_path, files = pos[0], pos[1], pos[2:]

_fix_tokenizer_config(model_dir)
tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))
cfg = json.load(open(os.path.join(model_dir, "rl_agent_config.json")))
rows = [json.loads(l) for f in files for l in open(f, encoding="utf-8") if l.strip()]
rng = random.Random(20261004)

POS, NEG = 0.97, 0.03          # noul soft target
GOLD = 0.92                    # choice soft target: 0.92 gold, the rest spread
k_choice = len(INTENTS)


def meta(r, question):
    return {"id": r.get("id"), "lang": r["lang"], "greeklish": bool(r.get("greeklish")), "text": r["text"],
            "question": question, "source": r.get("source", "")}


items = []
for r in rows:
    state = state_of(r["text"])
    # (a) OOC noul: options are always [false, true]
    seq, markers = build_sequence(tok, state, OOC_QUESTION, cfg["max_len"], cfg["head_max_len"])
    assert len(markers) == 2
    ic = bool(r["in_character"])
    items.append({"ids": seq, "markers": markers, "qtype": QTYPES["noul"],
                  "target": [NEG, POS] if ic else [POS, NEG], "label": int(ic), "meta": meta(r, "ooc")})
    # (b) intent choice
    order = list(range(k_choice))
    if not evaluation:
        rng.shuffle(order)
    seq, markers = build_sequence(tok, state, INTENT_QUESTION, cfg["max_len"], cfg["head_max_len"], option_order=order)
    assert len(markers) == k_choice, (len(markers), r["text"])
    gold = INTENTS.index(r["intent"])
    target = [GOLD if o == gold else (1 - GOLD) / (k_choice - 1) for o in order]
    items.append({"ids": seq, "markers": markers, "qtype": QTYPES["choice"], "target": target,
                  "label": order.index(gold), "order": order, "meta": meta(r, "intent")})

if not evaluation:
    noul = [it for it in items if it["qtype"] == QTYPES["noul"]]
    ic_items = [it for it in noul if it["label"] == 1]
    n_ic, n = len(ic_items), len(noul)
    # repeat IC items until IC is `ic_share` of the OOC question's items
    want = int(ic_share * (n - n_ic) / (1 - ic_share)) - n_ic
    if want > 0 and ic_items:
        extra = [ic_items[i % n_ic] for i in range(want)]
        items += extra
        print(f"OOC question: {n_ic} IC / {n - n_ic} OOC; repeated {want} IC items")
    rng.shuffle(items)

torch.save(items, out_path)
lens = sorted(len(it["ids"]) for it in items)
print(f"{len(items)} items from {len(rows)} rows -> {out_path} | tokens mean {sum(lens)/len(lens):.0f}, max {lens[-1]}")
