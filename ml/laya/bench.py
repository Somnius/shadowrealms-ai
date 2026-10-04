#!/usr/bin/env python3
"""Load time, RAM and per-message latency of infer.py on the CPU.
usage: bench.py <model_dir> [threads]   (e.g. in the training image with --cpus 4)"""
import json, os, resource, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024


model_dir = sys.argv[1]
threads = int(sys.argv[2]) if len(sys.argv) > 2 else 4
base = rss_mb()
t0 = time.perf_counter()
from infer import LayaClassifier  # noqa: E402
clf = LayaClassifier(model_dir, threads=threads)
load_s = time.perf_counter() - t0
after_load = rss_mb()
here = os.path.dirname(os.path.abspath(__file__))
texts = [json.loads(l)["text"] for f in ("seeds_en.jsonl", "seeds_el.jsonl")
         for l in open(os.path.join(here, "seeds", f), encoding="utf-8")][:200]
for t in texts[:5]:
    clf.classify(t)  # warm-up
lat = []
for t in texts:
    s = time.perf_counter()
    clf.classify(t)
    lat.append((time.perf_counter() - s) * 1000)
lat.sort()
print(json.dumps({
    "threads": threads, "messages": len(lat), "load_s": round(load_s, 2),
    "rss_mb_before": round(base), "rss_mb_after_load": round(after_load), "rss_mb_peak": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
    "ms_per_message_mean": round(statistics.mean(lat), 1), "p50": round(lat[len(lat) // 2], 1),
    "p95": round(lat[int(len(lat) * 0.95)], 1), "max": round(lat[-1], 1)}, indent=1))
