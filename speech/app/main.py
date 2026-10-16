"""ShadowRealms speech service: TTS (Piper, Pocket TTS Greek) and STT (faster-whisper) as jobs.

Bound to 127.0.0.1; every call needs the X-Speech-Secret header (SPEECH_SECRET).
"""
import hmac
import logging
import os
import shutil
import tempfile
import threading
import time
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import audio, catalog, config, textprep
from .cachekeys import tts_key
from .engines import PiperEngine, PocketEngine, WhisperEngine, gpu_free_mb
from .jobs import Lane
from .limits import Refused, check_lang, check_probe, check_size, check_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("speech")

TTS_DIR = os.path.join(config.CACHE_DIR, "tts")
CLIP_DIR = os.path.join(config.CACHE_DIR, "clips")
TMP_DIR = os.path.join(config.CACHE_DIR, "tmp")

piper, pocket, whisper = PiperEngine(), PocketEngine(), WhisperEngine()


def _tts_paths(key):
    return os.path.join(TTS_DIR, key[:2], key + ".ogg"), os.path.join(TTS_DIR, key[:2], key + ".m4a")


def run_tts(p):
    ogg, m4a = _tts_paths(p["key"])
    if not os.path.exists(ogg):
        os.makedirs(os.path.dirname(ogg), exist_ok=True)
        engine = piper if catalog.VOICES[p["voice"]]["engine"] == "piper" else pocket
        with tempfile.TemporaryDirectory(dir=TMP_DIR) as td:
            wavs = []
            for i, part in enumerate(textprep.split_parts(p["text"], config.TEXT_PART_CHARS)):
                w = os.path.join(td, f"{i:03d}.wav")
                engine.synth(p["voice"], part, w)
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
    return dict(key=p["key"], duration=round(audio.duration(ogg), 2))


def run_stt(p):
    text, dur = whisper.transcribe(p["ogg"], p["lang"])
    return dict(text=text, duration=round(dur, 2), clip=p["clip"])


tts_lane = Lane("tts", config.TTS_QUEUE_MAX, run_tts)
stt_lane = Lane("stt", config.STT_QUEUE_MAX, run_stt)

app = FastAPI(title="speech", docs_url=None, redoc_url=None, openapi_url=None)


def auth(x_speech_secret: str = Header(default="")):
    if not config.SECRET or not hmac.compare_digest(x_speech_secret.encode(), config.SECRET.encode()):
        raise HTTPException(status_code=401, detail="unauthorised")


@app.exception_handler(Refused)
def _refused(_req, e: Refused):
    status = 503 if e.code in ("gpu_busy", "queue_full") else 400
    return JSONResponse({"error": e.code, "detail": e.detail}, status_code=status)


def _idle_loop():
    while True:
        time.sleep(30)
        whisper.unload_if_idle()


@app.on_event("startup")
def _startup():
    for d in (TTS_DIR, CLIP_DIR, TMP_DIR):
        os.makedirs(d, exist_ok=True)
    for f in os.listdir(TMP_DIR):  # leftovers from a crash
        shutil.rmtree(os.path.join(TMP_DIR, f), ignore_errors=True)
    tts_lane.start()
    stt_lane.start()
    threading.Thread(target=_idle_loop, daemon=True).start()
    threading.Thread(target=pocket.ok, daemon=True).start()  # warm Greek TTS in the background


@app.get("/health", dependencies=[Depends(auth)])
def health():
    return dict(ok=True, stt=dict(loaded=whisper.loaded, last_load_seconds=whisper.load_seconds,
                                  queue=stt_lane.depth(), vram_free_mb=gpu_free_mb(),
                                  vram_needed_mb=config.STT_VRAM_MB, idle_unload_s=config.STT_IDLE_SECONDS),
                tts=dict(queue=tts_lane.depth(), pocket_loaded=pocket._model is not None,
                         pocket_error=pocket.error))


@app.get("/voices", dependencies=[Depends(auth)])
def voices():
    return dict(voices=[dict(v, available=(piper.available(v["id"]) if v["engine"] == "piper"
                                            else pocket.error is None))
                        for v in catalog.listing()],
                defaults={f"{l}-{a}": t for (l, a), t in catalog.DEFAULTS.items()})


class TTSReq(BaseModel):
    text: str
    lang: str
    voice: str | None = None
    gender: str | None = None
    accent: str | None = None
    role: str | None = None


@app.post("/tts", dependencies=[Depends(auth)])
def tts(req: TTSReq):
    check_text(req.text, config.TEXT_MAX_CHARS)
    try:
        vid = catalog.resolve(req.lang, req.voice, req.gender, req.accent, req.role,
                              pocket_ok=pocket.error is None)
    except ValueError as e:
        raise Refused(str(e))
    text = textprep.normalise(req.text, req.lang)
    check_text(text, config.TEXT_MAX_CHARS * 2)
    engine = catalog.VOICES[vid]["engine"]
    key = tts_key(engine, vid, text, config.TTS_BITRATE)
    meta = dict(voice=vid, key=key)
    if os.path.exists(_tts_paths(key)[0]):
        return tts_lane.add_done(dict(meta, cached=True))
    return tts_lane.submit(dict(voice=vid, key=key, text=text), dict(meta, cached=False))


@app.get("/tts/{job_id}", dependencies=[Depends(auth)])
def tts_status(job_id: str):
    job = tts_lane.get(job_id)
    if not job:
        raise HTTPException(404)
    return job


@app.get("/audio/{key}", dependencies=[Depends(auth)])
def tts_audio(key: str, fmt: str = "ogg"):
    if not key.isalnum() or fmt not in ("ogg", "m4a"):
        raise HTTPException(404)
    ogg, m4a = _tts_paths(key)
    path = ogg if fmt == "ogg" else m4a
    if not os.path.exists(ogg) or not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/ogg" if fmt == "ogg" else "audio/mp4")


@app.delete("/audio/{key}", dependencies=[Depends(auth)])
def tts_audio_delete(key: str):
    """The backend removes a spoken line when its message is deleted (and no other message uses it)."""
    if not key.isalnum():
        raise HTTPException(404)
    for p in _tts_paths(key):
        if os.path.exists(p):
            os.remove(p)
    return {"ok": True}


@app.post("/stt", dependencies=[Depends(auth)])
def stt(file: UploadFile = File(...), lang: str = Form(...)):
    check_lang(lang)
    if stt_lane.q.full():
        raise Refused("queue_full")
    clip = uuid.uuid4().hex
    raw = os.path.join(TMP_DIR, clip + ".upload")
    try:
        n = 0
        with open(raw, "wb") as f:
            while chunk := file.file.read(1 << 16):
                n += len(chunk)
                if n > config.CLIP_MAX_BYTES:
                    raise Refused("too_large", f"max {config.CLIP_MAX_BYTES} bytes")
                f.write(chunk)
        check_size(n, config.CLIP_MAX_BYTES)
        dur = check_probe(audio.probe(raw), config.CLIP_MAX_SECONDS)
        ogg = os.path.join(CLIP_DIR, clip + ".ogg")
        audio.to_opus(raw, ogg, config.CLIP_BITRATE, max_seconds=config.CLIP_MAX_SECONDS)
        if dur is None:
            real = audio.duration(ogg)
            if real > config.CLIP_MAX_SECONDS + 0.5:
                os.remove(ogg)
                raise Refused("too_long", f"max {config.CLIP_MAX_SECONDS} s")
    finally:
        if os.path.exists(raw):
            os.remove(raw)
    return stt_lane.submit(dict(ogg=ogg, lang=lang, clip=clip), dict(clip=clip))


@app.get("/stt/{job_id}", dependencies=[Depends(auth)])
def stt_status(job_id: str):
    job = stt_lane.get(job_id)
    if not job:
        raise HTTPException(404)
    return job


@app.get("/clips/{clip}", dependencies=[Depends(auth)])
def clip_audio(clip: str, fmt: str = "ogg"):
    if not clip.isalnum() or fmt not in ("ogg", "m4a"):
        raise HTTPException(404)
    ogg = os.path.join(CLIP_DIR, clip + ".ogg")
    if not os.path.exists(ogg):
        raise HTTPException(404)
    if fmt == "m4a":
        m4a = ogg[:-4] + ".m4a"
        if not os.path.exists(m4a):  # AAC copy made on first request, kept beside the Ogg
            audio.to_m4a(ogg, m4a + ".tmp")
            os.replace(m4a + ".tmp", m4a)
        return FileResponse(m4a, media_type="audio/mp4")
    return FileResponse(ogg, media_type="audio/ogg")


@app.delete("/clips/{clip}", dependencies=[Depends(auth)])
def clip_delete(clip: str):
    if not clip.isalnum():
        raise HTTPException(404)
    for ext in (".ogg", ".m4a"):
        p = os.path.join(CLIP_DIR, clip + ext)
        if os.path.exists(p):
            os.remove(p)
    return {"ok": True}
