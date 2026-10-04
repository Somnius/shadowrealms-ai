#!/usr/bin/env python3
"""Accuracy / precision / recall / F1 per class and language, confusion
matrices, OOC AUROC and threshold table, for a Laya checkpoint.

  torch (training container, GPU or CPU):
    evaluate.py torch <run_dir> <items.pt> [--out report.json]
        items.pt from `prep_items.py <base> items.pt rows.jsonl --eval`
  onnx (anything with onnxruntime + tokenizers; the packaged model):
    evaluate.py onnx <model_dir> <rows.jsonl>... [--out report.json]

Languages are reported as en, el (Greek letters) and greeklish (el rows in
Latin letters), plus all.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from question import INTENTS  # noqa: E402


# ---------------------------------------------------------------- predictions
def predict_torch(run_dir, items_path):
    import torch
    from safetensors.torch import load_file
    from transformers import AutoTokenizer
    from laya.common import build_model
    from train import collate_train_batch
    cfg = json.load(open(os.path.join(run_dir, "rl_agent_config.json")))
    tok = AutoTokenizer.from_pretrained(os.path.join(run_dir, "tokenizer"))
    model = build_model(cfg, encoder_dir=os.path.join(run_dir, "encoder"))
    model.load_state_dict(load_file(os.path.join(run_dir, "model.safetensors")), strict=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(dev).eval()
    temps = cfg.get("temperature", [1.0, 1.0, 1.0])
    items = torch.load(items_path, weights_only=False)
    by_row = {}
    with torch.no_grad():
        for i in range(0, len(items), 32):
            chunk = items[i:i + 32]
            b = collate_train_batch(chunk, tok.pad_token_id)
            with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                logits, _ = model(b["input_ids"].to(dev), b["attention_mask"].to(dev), b["marker_pos"].to(dev),
                                  b["marker_mask"].to(dev), b["qtype"].to(dev))
            logits = logits.float().cpu()
            for r, it in enumerate(chunk):
                k = len(it["markers"])
                p = torch.softmax(logits[r, :k] / temps[it["qtype"]], -1).tolist()
                m = it["meta"]
                row = by_row.setdefault(m["id"] or m["text"], {"lang": m["lang"], "greeklish": m["greeklish"],
                                                               "text": m["text"]})
                if m["question"] == "ooc":
                    row["p_ic"], row["gold_ic"] = p[1], bool(it["label"])
                else:
                    order = it.get("order", list(range(k)))
                    probs = [0.0] * k
                    for j, o in enumerate(order):
                        probs[o] = p[j]
                    row["intent_probs"] = probs
                    row["gold_intent"] = INTENTS[order[it["label"]]]
    return list(by_row.values())


def predict_onnx(model_dir, files):
    from infer import LayaClassifier
    clf = LayaClassifier(model_dir)
    out = []
    for f in files:
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            res = clf.classify(r["text"])
            out.append({"lang": r["lang"], "greeklish": bool(r.get("greeklish")), "text": r["text"],
                        "p_ic": res["ooc_violation"]["score"], "gold_ic": bool(r["in_character"]),
                        "intent_probs": [res["intent"]["probs"][k] for k in INTENTS], "gold_intent": r["intent"]})
    return out


# -------------------------------------------------------------------- metrics
def auroc(scores, labels):
    import bisect
    pos = [s for s, l in zip(scores, labels) if l]
    neg = sorted(s for s, l in zip(scores, labels) if not l)
    if not pos or not neg:
        return None
    tot = 0.0
    for p in pos:
        lo, hi = bisect.bisect_left(neg, p), bisect.bisect_right(neg, p)
        tot += lo + 0.5 * (hi - lo)
    return round(tot / (len(pos) * len(neg)), 4)


def prf(gold, pred, cls):
    tp = sum(g == cls and p == cls for g, p in zip(gold, pred))
    fp = sum(g != cls and p == cls for g, p in zip(gold, pred))
    fn = sum(g == cls and p != cls for g, p in zip(gold, pred))
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    return {"precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3), "support": tp + fn}


def report(rows):
    groups = {"all": rows, "en": [r for r in rows if r["lang"] == "en"],
              "el": [r for r in rows if r["lang"] == "el" and not r["greeklish"]],
              "greeklish": [r for r in rows if r["greeklish"]]}
    out = {}
    for name, rs in groups.items():
        if not rs:
            continue
        g_ic = [r["gold_ic"] for r in rs]
        p_ic = [r["p_ic"] for r in rs]
        pred_ic = [p >= 0.5 for p in p_ic]
        ooc = {"n": len(rs), "in_character": sum(g_ic), "accuracy": round(sum(a == b for a, b in zip(g_ic, pred_ic)) / len(rs), 3),
               "in_character_class": prf(g_ic, pred_ic, True), "out_of_character_class": prf(g_ic, pred_ic, False),
               "auroc": auroc(p_ic, g_ic), "thresholds": {}}
        for t in (0.5, 0.7, 0.8, 0.9):
            pr = [p >= t for p in p_ic]
            fp = sum(p and not g for p, g in zip(pr, g_ic))
            ooc["thresholds"][str(t)] = {"flagged": sum(pr), "false_positives": fp,
                                         "fp_rate_on_ooc": round(fp / max(1, len(rs) - sum(g_ic)), 3),
                                         "recall_ic": prf(g_ic, pr, True)["recall"]}
        g_in = [r["gold_intent"] for r in rs]
        p_in = [INTENTS[max(range(len(INTENTS)), key=lambda i: r["intent_probs"][i])] for r in rs]
        per = {c: prf(g_in, p_in, c) for c in INTENTS}
        present = [c for c in INTENTS if per[c]["support"]]
        conf = {g: {p: sum(a == g and b == p for a, b in zip(g_in, p_in)) for p in INTENTS} for g in INTENTS}
        out[name] = {"ooc": ooc, "intent": {
            "n": len(rs), "accuracy": round(sum(a == b for a, b in zip(g_in, p_in)) / len(rs), 3),
            "macro_f1": round(sum(per[c]["f1"] for c in present) / len(present), 3),
            "per_class": per, "confusion_gold_rows_pred_cols": conf}}
    return out


def print_report(rep):
    for name, r in rep.items():
        o, i = r["ooc"], r["intent"]
        print(f"\n=== {name}: {o['n']} messages ({o['in_character']} in character)")
        print(f"OOC/IC  acc {o['accuracy']:.3f}  AUROC {o['auroc']}  IC P/R/F1 "
              f"{o['in_character_class']['precision']:.3f}/{o['in_character_class']['recall']:.3f}/{o['in_character_class']['f1']:.3f}"
              f"  OOC F1 {o['out_of_character_class']['f1']:.3f}")
        for t, v in o["thresholds"].items():
            print(f"   P(IC)>={t}: flagged {v['flagged']}, false positives {v['false_positives']} "
                  f"(fp rate {v['fp_rate_on_ooc']}), IC recall {v['recall_ic']}")
        print(f"intent  acc {i['accuracy']:.3f}  macro-F1 {i['macro_f1']:.3f}")
        for c, v in i["per_class"].items():
            print(f"   {c:15s} P {v['precision']:.3f} R {v['recall']:.3f} F1 {v['f1']:.3f} n={v['support']}")
        print("   confusion (rows gold, cols pred): " + " ".join(f"{c[:5]:>6s}" for c in INTENTS))
        for g in INTENTS:
            print(f"   {g:15s}" + " " * 19 + " ".join(f"{i['confusion_gold_rows_pred_cols'][g][p]:6d}" for p in INTENTS))


def main():
    a = sys.argv[1:]
    out = a[a.index("--out") + 1] if "--out" in a else None
    a = [x for i, x in enumerate(a) if x != "--out" and (i == 0 or a[i - 1] != "--out")]
    rows = predict_torch(a[1], a[2]) if a[0] == "torch" else predict_onnx(a[1], a[2:])
    rep = report(rows)
    print_report(rep)
    if out:
        json.dump({"report": rep, "predictions": rows}, open(out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
