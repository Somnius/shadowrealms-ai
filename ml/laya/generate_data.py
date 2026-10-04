#!/usr/bin/env python3
"""Synthetic training data for the ShadowRealms Laya classifier, from the local
LLMs in LM Studio (OpenAI API at http://localhost:1234/v1).

Every generated message is labelled again by a *different* model; rows where the
generator's intended labels and the judge's labels disagree are dropped. Exact and
near duplicates (bge-m3 cosine) are dropped too, and so is anything too close to a
held-out (dev/test) seed.

Steps (each resumable; outputs go to data/laya/gen/):
  gen      --lang en --model google/gemma-4-e2b [--minutes 30]
  judge    --lang en --model llama-krikri-8b-instruct
  finalize                       -> data/laya/dataset/{train,dev,test}.jsonl

The model named in `gen`/`judge` must already be loaded in LM Studio
(`lms load <id> -y --parallel 4`). Run it with `--network host` in the
training container (finalize needs numpy) or on any Python 3.10+ with numpy.
"""
import argparse, json, os, random, re, sys, threading, time, unicodedata, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from question import INTENTS  # noqa: E402

API = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.environ.get("LAYA_DATA", os.path.join(REPO, "data", "laya"))
GEN = os.path.join(DATA, "gen")

# bucket -> (intent, in_character, target rows per language, description)
BUCKETS = {
    "dice": ("dice", False, 700,
             "out-of-character messages about dice rolls: asking to roll or asking the Storyteller which roll to make, "
             "stating a dice pool (Attribute + Skill, e.g. Dex + Firearms), difficulty, number of successes, botches, "
             "rouse checks, hunger dice, messy criticals, bestial failures, willpower rerolls, dice-bot commands like "
             "'/roll 5d10 diff 6', or reporting a roll result. The player speaks as themselves."),
    "rules_question": ("rules_question", False, 700,
             "out-of-character questions about the game's rules, mechanics, Disciplines (Celerity, Dominate, Auspex, "
             "Obfuscate, Presence, Potence, Fortitude, Protean, Animalism, Blood Sorcery, Oblivion...), clans and banes, "
             "Humanity, Hunger, Blood Potency, generation, XP costs, merits/flaws, the character sheet, or setting lore "
             "(Camarilla, Anarchs, Sabbat, Traditions, Masquerade). V5 or V20 editions. The player asks as themselves."),
    "general": ("general", False, 800,
             "out-of-character chat that is NOT about dice, rules or combat: greetings, goodbyes, scheduling sessions, "
             "being late, tech/mic/discord problems, food breaks ('brb'), banter, one-word reactions ('lol', 'nice', '+1'), "
             "praising the Storyteller, real-life talk, and players laughing about or quoting something a character said "
             "earlier (they quote an in-character line but are clearly commenting on it as a player)."),
    "combat_ic": ("combat", True, 500,
             "in-character combat written as roleplay: the character attacks, punches, bites, shoots, stakes, grapples, "
             "dodges or flees a fight. Use first-person narration ('I lunge at the ghoul'), third-person narration of a "
             "named character ('Viktor smashes the lamp over his head'), or asterisk actions ('*draws fangs and leaps*'), "
             "sometimes with a line of dialogue. NO dice, numbers, pools or game mechanics."),
    "combat_ooc": ("combat", False, 350,
             "out-of-character combat talk during a fight: declaring an attack with its dice pool, initiative values and "
             "turn order, damage numbers, soak, health levels and wound penalties, whose turn it is, tactics discussed "
             "between players ('focus the Tzimisce', 'my character will flank'), complaining that the fight is long. "
             "The player speaks as themselves (game terms, 'my character', numbers)."),
    "roleplay_ic": ("roleplay", True, 900,
             "in-character roleplay that is not combat: the character's own dialogue (quoted or bare), actions in first "
             "or third person, asterisk actions, social scenes in Elysium, feeding, investigating, intrigue with the "
             "Prince, Primogen, Sheriff, Harpy, Anarchs, ghouls and mortals, brooding in the haven. A few messages may "
             "use words like 'rolls' or 'throws' in a non-dice sense (*rolls her eyes*, throws him a glance)."),
    "roleplay_ooc": ("roleplay", False, 300,
             "out-of-character talk about the story or a scene: the player says what their character will or should do, "
             "asks the Storyteller to describe or start a scene, asks for a flashback or downtime scene, or discusses how "
             "to play their character. Clearly the player speaking as themselves ('my character would...', "
             "'I want Elena to...', 'ST can you describe...')."),
}
LANG_NOTE = {
    "en": "in English, the way gamers type in a Discord chat",
    "el": "in Modern Greek, the way Greek gamers type in a Discord chat: casual, often lowercase, often keeping English "
          "game terms as they are (Dex + Brawl, Willpower, Celerity, Prince, ST, rouse check, botch). Use Greek letters.",
}
LENGTHS = ["very short (1 to 5 words)", "short (one sentence)", "short (one sentence)", "medium (one to three sentences)"]
STYLES = ["casual, a few typos", "proper punctuation", "with an emoji here and there", "all lowercase",
          "excited", "annoyed or tired", "dry and matter-of-fact", "mixed: vary the tone message to message"]
NAMES = ["Marcus", "Elena", "Viktor", "Sofia", "Anna", "Lucas", "Dmitri", "Mara", "Jonah", "Isabel", "Kostas", "Nikos",
         "Eleni", "Giorgos", "Katerina", "Lena", "Theo", "Raven", "Silas", "Ines", "Yannis", "Petra", "Malik", "Ada"]
TOPICS = ["Elysium", "the Prince", "the Sheriff", "a Nosferatu informant", "a Tremere chantry", "an Anarch bar",
          "a ghoul", "a hunter cell", "feeding in a nightclub", "a Sabbat pack", "the Masquerade", "a mortal relative",
          "a Toreador gallery", "a Malkavian prophecy", "the sewers", "a werewolf", "the docks", "a Brujah rant",
          "the haven", "a blood bond", "torpor", "a Ventrue boardroom", "a Lasombra", "a Tzimisce", "a Gangrel"]

GEN_SCHEMA = {"type": "json_schema", "json_schema": {"name": "messages", "strict": True, "schema": {
    "type": "object", "properties": {"messages": {"type": "array", "items": {"type": "string"}}},
    "required": ["messages"]}}}
JUDGE_SCHEMA = {"type": "json_schema", "json_schema": {"name": "labels", "strict": True, "schema": {
    "type": "object", "properties": {"labels": {"type": "array", "items": {
        "type": "object", "properties": {
            "n": {"type": "integer"},
            "in_character": {"type": "boolean"},
            "intent": {"type": "string", "enum": INTENTS}},
        "required": ["n", "in_character", "intent"]}}},
    "required": ["labels"]}}}

JUDGE_PROMPT = """You label chat messages from the Discord of a World of Darkness tabletop RPG (Vampire: The Masquerade). Messages may be English, Greek or Greeklish.

For each message decide:
1. in_character: true if the message is written IN CHARACTER (the character's own dialogue, actions or narration inside the story: "*draws fangs*", "I lunge at the Prince", "Elena whispers: leave now", "Good evening, Primogen."). false if it is OUT OF CHARACTER: the player talking as themselves about rules, dice, combat numbers, scheduling, plans for their character ("my character should..."), jokes, quoting a character to comment on it, or real life.
2. intent, exactly one of:
 - dice: a dice roll or check: asks to roll, gives a dice pool or difficulty, reports a roll result
 - combat: fighting: attacks, initiative, damage, soak, health levels, fleeing a fight (in or out of character)
 - rules_question: a question about the game's rules, mechanics, powers, lore or character stats
 - roleplay: the story: a character speaks or acts in a non-combat scene, or the player asks for or plans a scene
 - general: anything else: greetings, banter, scheduling, out-of-game talk

Return {"labels": [{"n": <message number>, "in_character": <bool>, "intent": <label>}, ...]} with one entry per message, in order.

Messages:
"""


def chat(model, messages, schema, temperature, max_tokens=2000, timeout=300):
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "response_format": schema, "reasoning_effort": "none"}
    req = urllib.request.Request(API + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    txt = d["choices"][0]["message"]["content"]
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip())
    return json.loads(txt), d.get("usage", {})


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def seeds(split=None):
    rows = []
    for f in ("seeds_en.jsonl", "seeds_el.jsonl", "extra_test.jsonl"):
        rows += load_jsonl(os.path.join(HERE, "seeds", f))
    return [r for r in rows if split is None or r["split"] == split]


def bucket_of(r):
    if r["intent"] in ("combat", "roleplay"):
        return f"{r['intent']}_{'ic' if r['in_character'] else 'ooc'}"
    return r["intent"]


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[\W_]+", " ", t).strip()


def cmd_gen(a):
    os.makedirs(GEN, exist_ok=True)
    out = os.path.join(GEN, f"{a.lang}.raw.jsonl")
    have = load_jsonl(out)
    count = {b: 0 for b in BUCKETS}
    for r in have:
        count[r["bucket"]] += 1
    train_seeds = [r for r in seeds("train") if r["lang"] == a.lang and not r["greeklish"]]
    by_bucket = {b: [r["text"] for r in train_seeds if bucket_of(r) == b] for b in BUCKETS}
    deadline = time.time() + a.minutes * 60
    lock = threading.Lock()
    rng = random.Random(hash((a.lang, len(have))) & 0xffff)
    tok_total = [0]

    def job(bucket):
        intent, ic, _, desc = BUCKETS[bucket]
        ex = rng.sample(by_bucket[bucket], min(6, len(by_bucket[bucket])))
        names = ", ".join(rng.sample(NAMES, 4))
        prompt = (f"Write {a.per_call} different chat messages that players might post in the Discord of a "
                  f"Vampire: The Masquerade tabletop game. Every message must be {desc}\n\n"
                  f"Language: {LANG_NOTE[a.lang]}.\nLength: {rng.choice(LENGTHS)}, but vary it a little.\n"
                  f"Style: {rng.choice(STYLES)}.\nCharacter names you may use: {names}. "
                  f"Topic ideas: {', '.join(rng.sample(TOPICS, 3))}.\n"
                  f"Make every message different in wording and content; do not copy the examples.\n\n"
                  "Examples of the kind of message wanted:\n" + "\n".join(f"- {e}" for e in ex) +
                  '\n\nReturn JSON: {"messages": ["...", ...]}')
        try:
            res, usage = chat(a.model, [{"role": "user", "content": prompt}], GEN_SCHEMA, a.temperature)
        except Exception as e:  # noqa: BLE001
            print("gen error:", bucket, repr(e)[:200], flush=True)
            return
        msgs = [m.strip() for m in res.get("messages", []) if isinstance(m, str) and 0 < len(m.strip()) <= 400]
        with lock:
            tok_total[0] += usage.get("completion_tokens", 0)
            with open(out, "a", encoding="utf-8") as f:
                for m in msgs:
                    f.write(json.dumps({"lang": a.lang, "text": m, "bucket": bucket, "intent": intent,
                                        "in_character": ic, "gen_model": a.model}, ensure_ascii=False) + "\n")
            count[bucket] += len(msgs)

    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as pool:
        while time.time() < deadline:
            todo = [b for b in BUCKETS if count[b] < BUCKETS[b][2] * a.over]
            if not todo:
                break
            # one round: a call per unfinished bucket, `workers` at a time
            list(pool.map(job, todo * max(1, a.workers // len(todo) or 1)))
            el = time.time() - t0
            print(f"[{el/60:5.1f} min] {sum(count.values())} rows, {tok_total[0]/max(el,1):.0f} tok/s  "
                  + " ".join(f"{b}={count[b]}" for b in BUCKETS), flush=True)
    print("done:", count)


def slug(model):
    return re.sub(r"[^\w.-]+", "_", model)


def cmd_judge(a):
    src = os.path.join(GEN, f"{a.lang}.raw.jsonl")
    out = os.path.join(GEN, f"{a.lang}.judged.{slug(a.model)}.jsonl")
    rows = load_jsonl(src)
    done = {(r["text"], r["bucket"]) for r in load_jsonl(out)}
    todo, seen = [], set()
    for r in rows:
        k = (r["text"], r["bucket"])
        if k in done or k in seen:
            continue
        seen.add(k)
        todo.append(r)
    random.Random(1).shuffle(todo)  # mix buckets so the judge isn't primed by a run of one class
    batches = [todo[i:i + a.per_call] for i in range(0, len(todo), a.per_call)]
    lock = threading.Lock()
    stats = {"rows": 0, "kept": 0, "bad_batches": 0}
    deadline = time.time() + a.minutes * 60

    def job(batch):
        if time.time() > deadline:
            return
        listing = "\n".join(f"{i+1}. {json.dumps(r['text'], ensure_ascii=False)}" for i, r in enumerate(batch))
        try:
            res, _ = chat(a.model, [{"role": "user", "content": JUDGE_PROMPT + listing}], JUDGE_SCHEMA, 0.0)
            labels = {int(l["n"]): l for l in res["labels"]}
        except Exception as e:  # noqa: BLE001
            print("judge error:", repr(e)[:200], flush=True)
            with lock:
                stats["bad_batches"] += 1
            return
        with lock, open(out, "a", encoding="utf-8") as f:
            for i, r in enumerate(batch):
                l = labels.get(i + 1)
                if not l or l.get("intent") not in INTENTS:
                    continue
                r = dict(r, judge_model=a.model, judge_ic=bool(l["in_character"]), judge_intent=l["intent"])
                r["verified"] = r["judge_ic"] == r["in_character"] and r["judge_intent"] == r["intent"]
                stats["rows"] += 1
                stats["kept"] += r["verified"]
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as pool:
        for i, _ in enumerate(pool.map(job, batches)):
            if i % 20 == 0:
                print(f"[{(time.time()-t0)/60:5.1f} min] batch {i}/{len(batches)} {stats}", flush=True)
    print("done:", stats)


# --- Greeklish: rule-based transliteration with casual variants -------------
_GL = {"ά": "a", "έ": "e", "ή": "h", "ί": "i", "ό": "o", "ύ": "y", "ώ": "w", "ϊ": "i", "ΐ": "i", "ϋ": "y", "ΰ": "y",
       "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "h", "θ": "8", "ι": "i", "κ": "k", "λ": "l",
       "μ": "m", "ν": "n", "ξ": "3", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y", "φ": "f",
       "χ": "x", "ψ": "ps", "ω": "w"}
_GL_VARIANTS = [{"8": "th", "3": "ks", "h": "i", "w": "o", "y": "i"},   # "phonetic" style
                {"8": "th", "3": "x", "y": "u"},
                {}]                                                   # "visual" style (8, 3, w)


def greeklish(text, rng):
    var = rng.choice(_GL_VARIANTS)
    out = []
    for ch in text:
        low = ch.lower()
        if low in _GL:
            t = _GL[low]
            t = var.get(t, t)
            out.append(t.capitalize() if ch != low and rng.random() < 0.5 else t)
        else:
            out.append(ch)
    s = "".join(out)
    return s.replace("«", '"').replace("»", '"').replace(";", "?")


def embed(texts, model="text-embedding-bge-m3", bs=64):
    import numpy as np
    vecs = []
    for i in range(0, len(texts), bs):
        req = urllib.request.Request(API + "/embeddings", data=json.dumps({"model": model, "input": texts[i:i + bs]}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
        vecs += [e["embedding"] for e in sorted(d["data"], key=lambda e: e["index"])]
    v = np.asarray(vecs, dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


_SPEAKER = re.compile(r"^(?:~\s*)?(?:[-•]\s*)?([A-ZΑ-ΩΆ-Ώ][\w'ά-ώ]{1,14}):\s+(?=\S)")


def clean(text):
    """Generated messages sometimes come as chat-log lines ("Anna: ...", "~...", "- ..."):
    in the app the text never carries the poster's name, so strip it."""
    t = text.strip().lstrip("~").strip()
    t = re.sub(r"^[-•]\s+", "", t)
    t = _SPEAKER.sub("", t)
    return t.lstrip("~").strip()


def vote(lang):
    """Each label of a generated row must win 2 of 3 votes: the generator's intended label
    and the two judges' (each judge is another model; Krikri alone was measured to call
    mechanical messages like '/roll 6d10 difficulty 7' in character)."""
    import glob
    judged = {}
    for f in sorted(glob.glob(os.path.join(GEN, f"{lang}.judged.*.jsonl"))):
        for r in load_jsonl(f):
            judged.setdefault((r["text"], r["bucket"]), []).append(r)
    n_judges = len(glob.glob(os.path.join(GEN, f"{lang}.judged.*.jsonl")))
    out = []
    for (text, bucket), js in judged.items():
        if len(js) < n_judges:
            continue  # a judge skipped it (bad batch): drop
        r = js[0]
        ic_votes = sum(j["judge_ic"] == r["in_character"] for j in js)
        in_votes = sum(j["judge_intent"] == r["intent"] for j in js)
        need = (len(js) + 1) // 2      # with the generator's vote: a majority of judges+1
        if ic_votes >= need and in_votes >= need:
            t = clean(text)
            if sum(ch.isalpha() for ch in t) >= 2:
                out.append(dict(r, text=t, judge_model="+".join(sorted(j["judge_model"] for j in js))))
    return out


def cmd_finalize(a):
    import numpy as np
    rng = random.Random(20261004)
    out_dir = os.path.join(DATA, "dataset")
    os.makedirs(out_dir, exist_ok=True)
    keep = []
    for lang in ("en", "el"):
        rows = vote(lang)
        print(lang, "rows kept by the vote:", len(rows))
        keep += rows
    # exact duplicates (normalised)
    seen, uniq = set(), []
    held = seeds("dev") + seeds("test")
    held_norm = {norm(r["text"]) for r in held}
    train_seed = seeds("train")
    for r in train_seed:
        seen.add(norm(r["text"]))
    for r in keep:
        n = norm(r["text"])
        if not n or n in seen or n in held_norm:
            continue
        seen.add(n)
        uniq.append(r)
    print("after exact dedupe:", len(uniq))
    # near duplicates with bge-m3: among themselves (>= a.near) and against held-out seeds (>= a.held)
    E = embed([r["text"] for r in uniq])
    H = embed([r["text"] for r in held])
    near_held = (E @ H.T).max(1) >= a.held
    order = list(range(len(uniq)))
    rng.shuffle(order)
    kept_idx, kept_vecs = [], np.zeros((0, E.shape[1]), dtype=np.float32)
    dropped_near = 0
    for i in order:
        if near_held[i]:
            continue
        if len(kept_idx) and float((kept_vecs @ E[i]).max()) >= a.near:
            dropped_near += 1
            continue
        kept_idx.append(i)
        kept_vecs = np.vstack([kept_vecs, E[i:i + 1]])
    print(f"near-dup dropped {dropped_near}, too close to dev/test {int(near_held.sum())}")
    syn = [uniq[i] for i in sorted(kept_idx)]
    # Greeklish: transliterate a share of the Greek rows (labels unchanged)
    gl = []
    for r in syn:
        if r["lang"] == "el" and rng.random() < a.greeklish:
            gl.append(dict(r, text=greeklish(r["text"], rng), greeklish=True, source=r.get("source", "") + "+greeklish"))
    for r in syn:
        r["greeklish"] = False
    train = []
    for i, r in enumerate(syn + gl):
        train.append({"id": f"syn-{r['lang']}-{i:05d}", "lang": r["lang"], "greeklish": r["greeklish"], "text": r["text"],
                      "in_character": r["in_character"], "intent": r["intent"], "split": "train",
                      "source": f"synthetic:{r['gen_model']}" + ("+greeklish" if r["greeklish"] else ""),
                      "judge": r["judge_model"]})
    train += train_seed
    rng.shuffle(train)

    def dump(name, rows):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        from collections import Counter
        c = Counter((r["lang"], r["intent"], "IC" if r["in_character"] else "OOC") for r in rows)
        print(f"{name}: {len(rows)}", dict(sorted(c.items())))
    dump("train.jsonl", train)
    dump("dev.jsonl", seeds("dev"))
    dump("test.jsonl", seeds("test"))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--lang", required=True, choices=["en", "el"])
    g.add_argument("--model", required=True)
    g.add_argument("--minutes", type=float, default=40)
    g.add_argument("--per-call", type=int, default=15)
    g.add_argument("--workers", type=int, default=4)
    g.add_argument("--temperature", type=float, default=1.0)
    g.add_argument("--over", type=float, default=1.35, help="generate this times the target (filtering drops some)")
    j = sub.add_parser("judge")
    j.add_argument("--lang", required=True, choices=["en", "el"])
    j.add_argument("--model", required=True)
    j.add_argument("--per-call", type=int, default=20)
    j.add_argument("--workers", type=int, default=4)
    j.add_argument("--minutes", type=float, default=40)
    f = sub.add_parser("finalize")
    f.add_argument("--near", type=float, default=0.95)
    f.add_argument("--held", type=float, default=0.92)
    f.add_argument("--greeklish", type=float, default=0.15)
    a = p.parse_args()
    {"gen": cmd_gen, "judge": cmd_judge, "finalize": cmd_finalize}[a.cmd](a)


if __name__ == "__main__":
    main()
