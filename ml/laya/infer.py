"""ShadowRealms' Laya chat classifier on CPU: ONNX Runtime + tokenizers, no torch.

    from infer import LayaClassifier
    clf = LayaClassifier("data/laya/model")          # load once at startup
    clf.classify("*draws my fangs and lunges at the Prince*")
    -> {"ooc_violation": {"label": True, "score": 0.98},             # score = P(in character)
        "intent": {"label": "combat", "score": 0.91, "probs": {...}}}

`classify(text)` is the module-level shortcut (loads the model from
$LAYA_MODEL_DIR, default data/laya/model, on first use).

The token layout is a port of laya.common.build_sequence (laya 0.3.21):
[CLS] "<type> question: <instructions>" [SEP] [MASK] opt0 [MASK] opt1 ... [SEP] state [SEP],
the markers being the [MASK] positions. The exported graph runs one sequence
at a time (batch 1), so a message is two runs: the OOC question and the intent one.

pip deps: onnxruntime, tokenizers, numpy.
"""
import json, os, threading

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

_DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "laya", "model")


def _render_options(q):
    if q["t"] == "choice":
        return [f"{k}: {v}" if v not in (None, "") else str(k) for k, v in q["crit"].items()]
    if q["t"] == "noul":
        return [f"false: {q['crit']['false']}", f"true: {q['crit']['true']}"]
    raise ValueError(q["t"])


class LayaClassifier:
    def __init__(self, model_dir=None, threads=None, ooc_threshold=0.5):
        model_dir = model_dir or os.environ.get("LAYA_MODEL_DIR", _DEFAULT_DIR)
        self.cfg = json.load(open(os.path.join(model_dir, "laya.json"), encoding="utf-8"))
        self.tok = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
        self.tok.no_truncation()
        self.tok.no_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(threads or os.environ.get("LAYA_THREADS", "4"))
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(os.path.join(model_dir, "model.onnx"), so, providers=["CPUExecutionProvider"])
        self.ooc_threshold = ooc_threshold
        self.intents = self.cfg["intents"]
        # the question part of each sequence never changes: build it once
        self._heads = {name: self._head(q) for name, q in self.cfg["questions"].items()}

    def _enc(self, text, max_length=None):
        ids = self.tok.encode(text, add_special_tokens=False).ids
        return ids[:max_length] if max_length else ids

    def _head(self, q):
        c, mask_tok = self.cfg, self.cfg["mask_token"]
        opts = _render_options(q)
        head = self._enc("%s question: %s" % (q["t"], str(q["ins"]).replace(mask_tok, " ")))
        opt_ids = [[c["mask"]] + self._enc(" " + o.replace(mask_tok, " "), 48) for o in opts]
        budget = c["head_max_len"] - sum(len(o) for o in opt_ids)
        if budget < 16:
            per = max(4, (c["head_max_len"] - 16) // max(1, len(opt_ids)))
            opt_ids = [o[:per] for o in opt_ids]
            budget = c["head_max_len"] - sum(len(o) for o in opt_ids)
        ids = [c["cls"]] + head[: max(8, budget)] + [c["sep"]]
        markers = []
        for o in opt_ids:
            markers.append(len(ids))
            ids.extend(o)
        ids.append(c["sep"])
        return ids, markers

    def sequence(self, name, text):
        """(ids, markers) exactly as laya.common.build_sequence makes them."""
        c = self.cfg
        head, markers = self._heads[name]
        room = max(0, c["max_len"] - len(head) - 1)
        state = (c["state_prefix"] + text.strip()).replace(c["mask_token"], " ")
        ids = head + self._enc(state)[:room] + [c["sep"]]
        return ids[: c["max_len"]], [m for m in markers if m < c["max_len"]]

    def _probs(self, name, text):
        q = self.cfg["questions"][name]
        ids, markers = self.sequence(name, text)
        feeds = {
            "input_ids": np.asarray([ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            "marker_pos": np.asarray([markers], dtype=np.int64),
            "marker_mask": np.ones((1, len(markers)), dtype=bool),
            "qtype": np.asarray([self.cfg["qtypes"][q["t"]]], dtype=np.int64),
        }
        logits = self.sess.run(["logits"], feeds)[0][0, : len(markers)].astype(np.float64)
        z = logits / self.cfg["temperature"][q["t"]]
        e = np.exp(z - z.max())
        return e / e.sum()

    def classify(self, text, questions=("ooc", "intent")):
        """Both questions by default; questions=("ooc",) or ("intent",) runs only one
        (each is one ~115 ms pass on 4 threads)."""
        out = {}
        if "ooc" in questions:
            p_ooc = self._probs("ooc", text)          # [false, true]: true = in character
            score = float(p_ooc[1])
            out["ooc_violation"] = {"label": score >= self.ooc_threshold, "score": round(score, 4)}
        if "intent" in questions:
            p_int = self._probs("intent", text)
            top = int(p_int.argmax())
            out["intent"] = {"label": self.intents[top], "score": round(float(p_int[top]), 4),
                             "probs": {k: round(float(v), 4) for k, v in zip(self.intents, p_int)}}
        return out


_default = None
_default_lock = threading.Lock()


def classify(text, questions=("ooc", "intent")):
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                _default = LayaClassifier()
    return _default.classify(text, questions)


if __name__ == "__main__":
    import sys
    clf = LayaClassifier(sys.argv[1] if len(sys.argv) > 1 else None)
    for line in sys.stdin:
        if line.strip():
            print(json.dumps({"text": line.strip(), **clf.classify(line)}, ensure_ascii=False))
