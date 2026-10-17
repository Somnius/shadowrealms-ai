"""Speaking a line into the TTS cache: local voices (tts lane) and cloud voices (cloud lane, 0.23).

Cloud lines run on their own lane so local lines never wait on Google. A cloud line has one total
deadline (config.GEMINI_TIMEOUT); when it fails or runs out, the whole line is spoken by its local
fallback voice. Local engines are used under one lock, whichever lane asks.
No FastAPI here, so the tests drive it with stub engines and converters.
"""
import logging
import os
import tempfile
import threading
import time

from . import audio, catalog, config, gemini, textprep
from .limits import Refused

log = logging.getLogger("speech.tts")


class Runner:
    def __init__(self, tts_dir, tmp_dir, pick_engine, stats, after_new=lambda: None):
        self.tts_dir, self.tmp_dir = tts_dir, tmp_dir
        self.pick_engine = pick_engine  # voice id -> engine with synth(voice, text, wav_path)
        self.stats, self.after_new = stats, after_new
        self.local_lock = threading.Lock()

    def paths(self, key):
        d = os.path.join(self.tts_dir, key[:2])
        return os.path.join(d, key + ".ogg"), os.path.join(d, key + ".m4a")

    def make(self, key, text, synth):
        """Speak `text` part by part with synth(part, wav_path), then store Opus + AAC under `key`.
        Nothing is written under `key` unless every part succeeded."""
        ogg, m4a = self.paths(key)
        os.makedirs(os.path.dirname(ogg), exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.tmp_dir) as td:
            wavs = []
            for i, part in enumerate(textprep.split_parts(text, config.TEXT_PART_CHARS)):
                w = os.path.join(td, f"{i:03d}.wav")
                synth(part, w)
                wavs.append(w)
            if len(wavs) == 1:
                src = wavs[0]
            else:
                lst = os.path.join(td, "list.txt")
                with open(lst, "w") as f:
                    f.writelines(f"file '{w}'\n" for w in wavs)
                src = os.path.join(td, "all.wav")
                audio._ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", src])
            tmp_ogg = os.path.join(td, "out.ogg")
            audio.to_opus(src, tmp_ogg, config.TTS_BITRATE)
            tmp_m4a = os.path.join(td, "out.m4a")
            audio.to_m4a(tmp_ogg, tmp_m4a)
            os.replace(tmp_m4a, m4a)
            os.replace(tmp_ogg, ogg)  # ogg last: its presence means the entry is complete
        self.after_new()

    def _done(self, key, voice, provider):
        return dict(key=key, voice=voice, provider=provider,
                    duration=round(audio.duration(self.paths(key)[0]), 2))

    def run_local(self, p):
        if p.get("voice") not in catalog.VOICES or not p.get("key"):
            raise Refused("unknown_voice", str(p.get("voice"))[:80])
        if not os.path.exists(self.paths(p["key"])[0]):
            with self.local_lock:
                engine = self.pick_engine(p["voice"])
                self.make(p["key"], p["text"], lambda part, w: engine.synth(p["voice"], part, w))
        return self._done(p["key"], p["voice"], "local")

    def run_cloud(self, p):
        fb, c = p.get("fallback") or {}, p["cloud"]
        if fb.get("voice") not in catalog.VOICES or not fb.get("key"):
            raise Refused("no_fallback", "a cloud line needs a local fallback voice")
        if os.path.exists(self.paths(p["key"])[0]):
            return self._done(p["key"], p["voice"], "gemini")
        deadline = time.monotonic() + config.GEMINI_TIMEOUT
        try:
            self.make(p["key"], p["text"], lambda part, w: gemini.synth_until(
                deadline, part, c["name"], c["model"], c["tier"], w))
            self.stats.success()
            return self._done(p["key"], p["voice"], "gemini")
        except Exception as e:  # any cloud failure: the whole line goes to the local voice
            code = e.code if isinstance(e, gemini.CloudError) else "internal"
            self.stats.error(code, c["model"], c["tier"])
            log.warning("cloud voice failed (%s, %s); local voice used for this line", code, c["model"])
        out = self.run_local(dict(fb, text=p["text"]))
        out["cloud_error"] = code
        return out
