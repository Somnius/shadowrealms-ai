"""Model owners. Only this module loads models; each engine is used by one worker thread."""
import gc
import logging
import os
import subprocess
import threading
import time
import wave

from . import config
from .catalog import VOICES
from .limits import Refused

log = logging.getLogger("speech.engines")
POCKET_REPO = "myned-ai/pocket-tts-greek"


class PiperEngine:
    def __init__(self):
        self._voices = {}

    def available(self, vid):
        return os.path.exists(os.path.join(config.MODELS_DIR, "piper", vid + ".onnx"))

    def synth(self, vid, text, wav_path):
        from piper import PiperVoice
        if vid not in self._voices:
            self._voices[vid] = PiperVoice.load(os.path.join(config.MODELS_DIR, "piper", vid + ".onnx"))
        with wave.open(wav_path, "wb") as wf:
            self._voices[vid].synthesize_wav(text, wf)


class PocketEngine:
    """Pocket TTS Greek on the CPU, one thread (the library sets it on import)."""

    def __init__(self):
        self._model = None
        self._states = {}
        self.error = None

    def ok(self):
        if self._model is None and self.error is None:
            try:
                from pocket_tts import TTSModel
                self._model = TTSModel.load_model(config=f"hf://{POCKET_REPO}/greek.yaml")
            except Exception as e:  # model missing or broken: Greek falls back to Piper
                self.error = repr(e)
                log.exception("pocket tts failed to load")
        return self._model is not None

    def synth(self, vid, text, wav_path):
        import scipy.io.wavfile as wf
        name = vid.split("-", 1)[1]
        if name not in self._states:
            self._states[name] = self._model.get_state_for_audio_prompt(
                f"hf://{POCKET_REPO}/voices/{name}.wav")
        audio = self._model.generate_audio(self._states[name], text)
        audio = audio.numpy() if hasattr(audio, "numpy") else audio
        wf.write(wav_path, self._model.sample_rate, audio)


def gpu_free_mb():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return None


class WhisperEngine:
    """Lazy load, idle unload, free-VRAM gate before every load."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self.last_used = 0.0
        self.load_seconds = None

    @property
    def loaded(self):
        return self._model is not None

    def _load(self):
        free = gpu_free_mb()
        if free is None or free < config.STT_VRAM_MB:
            raise Refused("gpu_busy", f"free VRAM {free} MB, need {config.STT_VRAM_MB} MB")
        from faster_whisper import WhisperModel
        t0 = time.perf_counter()
        self._model = WhisperModel(config.STT_MODEL, device="cuda", compute_type=config.STT_COMPUTE,
                                   cpu_threads=4, local_files_only=True,
                                   download_root=os.path.join(config.MODELS_DIR, "faster-whisper"))
        self.load_seconds = time.perf_counter() - t0
        log.info("whisper loaded in %.1fs", self.load_seconds)

    def transcribe(self, path, lang, prompt=None):
        """(text, duration, words): words are (word, probability) as Whisper wrote them.
        prompt: the chronicle's names and a short glossary (initial_prompt), only a bias."""
        with self._lock:
            if self._model is None:
                self._load()
            self.last_used = time.time()
            segs, info = self._model.transcribe(
                path, language=lang, beam_size=5, vad_filter=True,
                condition_on_previous_text=False, no_speech_threshold=0.6,
                initial_prompt=prompt or None, word_timestamps=True)
            kept = [s for s in segs if s.no_speech_prob < 0.8]
            text = " ".join(s.text.strip() for s in kept).strip()
            words = [(w.word.strip(), float(w.probability)) for s in kept for w in (s.words or []) if w.word.strip()]
            self.last_used = time.time()
            return text, info.duration, words

    def unload_if_idle(self):
        with self._lock:
            if self._model is not None and time.time() - self.last_used > config.STT_IDLE_SECONDS:
                self._model = None
                gc.collect()
                log.info("whisper unloaded after idle")
                return True
        return False


def voice_ready(vid, piper, pocket):
    meta = VOICES[vid]
    return piper.available(vid) if meta["engine"] == "piper" else pocket.ok()
