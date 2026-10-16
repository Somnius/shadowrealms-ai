"""Transcript check, step 1 (docs/VOICE.md, voice phase 6): which words Whisper probably misheard.

Laya-words (somniusx/recmeets-laya-words: convaiinnovations' Laya, Apache 2.0, fine-tuned by
RecMeets on Whisper's own mistakes in Greek and English, ONNX int8) answers one yes/no question
per word: "is the word marked ⟦ ⟧ a recognition mistake?". The input is built exactly as RecMeets
builds it (src/laya.rs, a port of laya.common.build_sequence):
[CLS] noul question: <instructions> [SEP] [MASK] false: … [MASK] true: … [SEP] <state> [SEP],
answer read at the two [MASK]s, divided by the fitted temperature in laya.json.

Only Whisper's unsure words are asked (one ~0.1-0.2 s pass each on LAYA_THREADS (4) CPU threads), the least sure
first, within a time budget; a missing model or a slow machine just means fewer (or no) flags.
"""
import json
import logging
import os
import threading
import time

from . import config

log = logging.getLogger("speech.check")

NOUL = 2          # Laya's qtype for yes/no questions
OPTION_TOKENS = 48
UNSURE = 0.985    # Whisper word probability below which a word is asked about
MAX_ASKED = 12
MIN_LETTERS = 3   # short function words (ο, τη, the) are not asked about
FLAG = 0.5        # Laya's chance of a mistake above which a word is flagged
PUNCT = ".,;:!?«»\"'()·;…-"
LANG_NAMES = {"el": "Greek", "en": "English"}


WINDOW = 10      # words each side of the asked word, as RecMeets' training data (±10)


def mark(words, i):
    """The words around word i (±WINDOW) with word i marked ⟦ ⟧, punctuation outside the marks,
    as RecMeets' mark()."""
    lo = max(0, i - WINDOW)
    toks = list(words[lo:i + WINDOW + 1])
    w = toks[i - lo]
    core = w.strip(PUNCT) or w
    toks[i - lo] = w.replace(core, f"⟦{core}⟧", 1)
    return " ".join(toks)


def state(words, i, prob, lang):
    """What Laya reads for one word (RecMeets' laya::state; no dictionary here: "can't tell")."""
    name = LANG_NAMES.get(lang)
    dictionary = f"the {name}" if name else "the"
    conf = "unknown" if prob is None else f"{prob:.2f}"
    core = words[i].strip(PUNCT) or words[i]
    return (f"Sentence: {mark(words, i)}\nWord: {core}\nEngine confidence: {conf}\n"
            f"In {dictionary} dictionary: can't tell")


def build(encode, m, text):
    """(ids, markers) exactly as laya.common.build_sequence for this checkpoint's question.
    encode(text) -> list of token ids without special tokens."""
    def clean(s):
        return s.replace(m["mask_token"], " ")
    head = encode("noul question: " + clean(m["instructions"]))
    opts = [[m["mask"]] + encode(" " + clean(o))[:OPTION_TOKENS]
            for o in ("false: " + m["criteria_false"], "true: " + m["criteria_true"])]
    budget = m["head_max_len"] - sum(len(o) for o in opts)
    if budget < 16:
        per = max(4, (m["head_max_len"] - 16) // len(opts))
        opts = [o[:per] for o in opts]
        budget = m["head_max_len"] - sum(len(o) for o in opts)
    ids = [m["cls"]] + head[: max(8, budget)] + [m["sep"]]
    markers = []
    for o in opts:
        markers.append(len(ids))
        ids.extend(o)
    ids.append(m["sep"])
    room = max(0, m["max_len"] - len(ids) - 1)
    ids += encode(clean(text))[:room] + [m["sep"]]
    ids = ids[: m["max_len"]]
    return ids, [p for p in markers if p < m["max_len"]]


def candidates(words, probs):
    """Indexes of the words to ask about: unsure ones, least sure first, at most MAX_ASKED."""
    idx = [i for i, p in enumerate(probs)
           if p is not None and p < UNSURE and len(words[i].strip(PUNCT)) >= MIN_LETTERS]
    return sorted(idx, key=lambda i: probs[i])[:MAX_ASKED]


class LayaWords:
    def __init__(self, model_dir=None):
        self.dir = model_dir or os.path.join(config.MODELS_DIR, "laya-words")
        self._sess = self._tok = self.meta = None
        self.error = None
        self._lock = threading.Lock()

    def present(self):
        return all(os.path.exists(os.path.join(self.dir, f)) for f in ("model.onnx", "tokenizer.json", "laya.json"))

    def ok(self):
        with self._lock:
            if self._sess is None and self.error is None:
                try:
                    import onnxruntime as ort
                    from tokenizers import Tokenizer
                    self.meta = json.load(open(os.path.join(self.dir, "laya.json"), encoding="utf-8"))
                    self._tok = Tokenizer.from_file(os.path.join(self.dir, "tokenizer.json"))
                    self._tok.no_truncation()
                    self._tok.no_padding()
                    so = ort.SessionOptions()
                    so.intra_op_num_threads = config.LAYA_THREADS
                    so.inter_op_num_threads = 1
                    self._sess = ort.InferenceSession(os.path.join(self.dir, "model.onnx"), so,
                                                      providers=["CPUExecutionProvider"])
                    log.info("laya-words loaded (%d threads)", config.LAYA_THREADS)
                except Exception as e:  # missing or broken model: no flags, transcripts unchanged
                    self.error = repr(e)
                    log.warning("laya-words not available: %s", self.error)
            return self._sess is not None

    def _encode(self, text):
        return self._tok.encode(text, add_special_tokens=False).ids

    def judge(self, text):
        """Chance that the marked word in this state is a recognition mistake."""
        import numpy as np
        ids, markers = build(self._encode, self.meta, text)
        logits = self._sess.run(["logits"], {
            "input_ids": np.asarray([ids], dtype=np.int64),
            "attention_mask": np.ones((1, len(ids)), dtype=np.int64),
            "marker_pos": np.asarray([markers], dtype=np.int64),
            "marker_mask": np.ones((1, len(markers)), dtype=bool),
            "qtype": np.asarray([NOUL], dtype=np.int64),
        })[0][0, :2].astype(np.float64) / self.meta["temperature"]
        e = np.exp(logits - logits.max())
        return float(e[1] / e.sum())

    def score(self, words, probs, lang, budget_s=None):
        """[{i, word, p_whisper, p_laya}] for the words asked about, within budget_s seconds."""
        if not words or not self.ok():
            return []
        budget = config.LAYA_BUDGET_S if budget_s is None else budget_s
        t0, out = time.perf_counter(), []
        for i in candidates(words, probs):
            if time.perf_counter() - t0 > budget:
                break
            try:
                p = self.judge(state(words, i, probs[i], lang))
            except Exception:
                log.exception("laya-words failed")
                break
            out.append(dict(i=i, word=words[i], p_whisper=round(probs[i], 3), p_laya=round(p, 3)))
        return sorted(out, key=lambda s: s["i"])
