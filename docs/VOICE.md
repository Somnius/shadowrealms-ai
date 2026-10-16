# Voice

## Speech service (server side)

The `speech` container turns text into audio (TTS) and voice clips into text (transcription). Only the backend talks to it. It is a small FastAPI app in `speech/`.

### How it runs

- Host network like the backend, but it listens on `127.0.0.1:5055` only. It is never exposed through nginx.
- Every call needs the header `X-Speech-Secret: <SPEECH_SECRET>` (set in `.env`). With no secret set, every call is refused.
- It is opt-in: `docker compose --profile voice up -d speech`. A plain `docker compose up -d` does not start it.
- Limits: 8 CPUs (`cpus: 8`), the server runs under `nice -n 10`, ffmpeg uses 2 threads, Pocket TTS 1 thread.
- Models are mounted read-only from `data/voice/models` and are never downloaded at run time (`HF_HUB_OFFLINE=1`). Audio goes to `data/voice/cache` (`tts/` for spoken lines, `clips/` for transcoded clips).
- Image base: `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04` (about 2.9 GB to download), CPU-only torch for Pocket TTS, faster-whisper on the GPU.

### Engines and voices

| lang / accent | female | male | neutral (unset gender, OOC) | narrator |
|---|---|---|---|---|
| en-US | Piper lessac | Piper ryan | Piper lessac | Piper ryan |
| en-GB | Piper jenny | Piper alan | Piper cori | Piper alan |
| el | Pocket TTS athina | Pocket TTS kostas | Pocket TTS eleni | Pocket TTS spyros |

If Pocket TTS fails to load, Greek falls back to Piper rapunzelina. Choices come from the Phase 0 measurements (Greek Piper voices were too hard to understand to be the default). Licences are listed by `GET /voices`; ryan is non-commercial, Pocket TTS Greek is CC BY 4.0 (needs attribution).

Before speaking, text is cleaned: markdown removed, links dropped, and for Greek, numbers become words and `?` becomes `;`. Long text is split into parts of at most 1,200 characters.

### Endpoints

| call | what it does |
|---|---|
| `GET /health` | Whisper loaded or not, free VRAM, queue depths, Pocket TTS state |
| `GET /voices` | the catalog with licences and which role each voice is the default for |
| `POST /tts` | JSON `{text, lang, voice?, gender?, accent?, role?}` → a job. If the line is already cached the job comes back `done` at once |
| `GET /tts/<job>` | job status: `queued` (with `position`), `running`, `done` (with `key`), `failed` (with `error`) |
| `GET /audio/<key>?fmt=ogg\|m4a` | the spoken line, Ogg/Opus or an AAC copy for phones that cannot play Opus |
| `POST /stt` | multipart `file` + `lang` (`el` or `en`) → a job; the clip is checked and transcoded before it is queued |
| `GET /stt/<job>` | job status; `done` has `text`, `duration` and `clip` |
| `GET /clips/<clip>?fmt=ogg\|m4a` | the stored clip (the AAC copy is made on first request) |
| `DELETE /clips/<clip>` | removes a clip and its copy |

Errors come back as `{"error": code}`: `gpu_busy` and `queue_full` with HTTP 503, the rest (`too_large`, `too_long`, `bad_format`, `unsupported_lang`, `unknown_voice`, …) with 400.

TTS audio is cached by a hash of the engine version, voice, bitrate and cleaned text, so two listeners asking for the same line make one file.

### Clips

- Up to 8 MB and 3 minutes. The upload is checked with `ffprobe` before anything decodes it: one audio stream, no video, a known container and codec. Browser WebM often has no duration in its header; then the clip is cut at 3 minutes during the transcode and checked again.
- Stored as Ogg/Opus, mono, 16 kbps, `-application voip` (about 115 KB a minute). Phase 0 found no accuracy loss at 16 kbps.
- The raw upload is deleted as soon as the transcode finishes, whatever happens.

### Transcription and the GPU

- faster-whisper `large-v3-turbo`, `int8_float16`, on CUDA, with voice activity filtering. One transcription at a time; at most 8 waiting (`queue_full` after that). TTS has its own queue and never waits for transcription.
- Whisper loads on the first clip and unloads after 10 idle minutes (`VOICE_STT_IDLE_SECONDS`).
- Before loading it checks free VRAM with `nvidia-smi`. Below `VOICE_STT_VRAM_MB` (default 2150: the measured 1.6 GB plus headroom) the job fails with `gpu_busy`; the app then suggests the phone's own dictation. It never unloads anyone else's model.

### Settings (`.env`)

`SPEECH_SECRET`, `SPEECH_PORT` (5055), `VOICE_STT_VRAM_MB` (2150), `VOICE_STT_IDLE_SECONDS` (600). Others with defaults in `speech/app/config.py`: text limit 5,000 characters, clip limits, bitrates (clips 16k, TTS 24k), queue sizes.

### Tests

`python -m pytest speech/tests` covers text cleaning, Greek numbers, splitting, cache keys, limits and the voice mapping (including neutral). They need no models.
