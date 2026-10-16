"""In-memory jobs with one worker thread per lane (stt, tts). Results live on disk in the cache."""
import queue
import threading
import time
import uuid

from . import config
from .limits import Refused


class Lane:
    def __init__(self, name, maxsize, handler):
        self.name, self.handler = name, handler
        self.q = queue.Queue(maxsize=maxsize)
        self.jobs = {}
        self.order = []  # ids waiting, for queue position
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._run, name=f"lane-{name}", daemon=True)

    def start(self):
        self.thread.start()

    def submit(self, payload, job=None):
        jid = uuid.uuid4().hex
        job = dict(job or {}, id=jid, lane=self.name, status="queued", created=time.time())
        with self.lock:
            try:
                self.q.put_nowait((jid, payload))
            except queue.Full:
                raise Refused("queue_full")
            self.jobs[jid] = job
            self.order.append(jid)
        return job

    def add_done(self, job):
        jid = uuid.uuid4().hex
        job = dict(job, id=jid, lane=self.name, status="done", created=time.time())
        with self.lock:
            self.jobs[jid] = job
        return job

    def get(self, jid):
        with self.lock:
            job = self.jobs.get(jid)
            if not job:
                return None
            out = dict(job)
            if out["status"] == "queued" and jid in self.order:
                out["position"] = self.order.index(jid)
            return out

    def depth(self):
        return self.q.qsize()

    def _run(self):
        while True:
            jid, payload = self.q.get()
            with self.lock:
                if jid in self.order:
                    self.order.remove(jid)
                self.jobs[jid]["status"] = "running"
            t0 = time.perf_counter()
            try:
                result = self.handler(payload)
                upd = dict(status="done", **result)
            except Refused as e:
                upd = dict(status="failed", error=e.code, detail=e.detail)
            except Exception as e:  # never kill the lane
                upd = dict(status="failed", error="internal", detail=repr(e)[:300])
            upd["seconds"] = round(time.perf_counter() - t0, 3)
            with self.lock:
                self.jobs[jid].update(upd)
            self._prune()

    def _prune(self):
        cut = time.time() - config.JOB_KEEP_SECONDS
        with self.lock:
            for k in [k for k, j in self.jobs.items() if j["created"] < cut and j["status"] in ("done", "failed")]:
                del self.jobs[k]
