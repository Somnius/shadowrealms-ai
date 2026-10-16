# Voice

Voice in the chat comes in phases (see [ROADMAP_VOICE.md](ROADMAP_VOICE.md)). Release 0.16 has the first one: **listening with your phone's own voices**; 0.17 adds **server voices** (a voice per character by gender, a narrator chosen per chronicle). Speaking and the language override follow.

## Listening (0.16)

- In a room, tap the **ear** in the header. New messages are read aloud as they arrive; the ear turns gold while it is on. On a phone this first tap is what allows speech at all.
- When you turn it on, a bar above the message box asks "Read the last 3 messages?". After that it shows who is speaking and how many messages wait, with pause, skip and stop.
- Your own messages are never read to you. System lines are skipped. A dice result is read as one sentence with the roller's name.
- At most 20 messages wait; if more arrive, the oldest are dropped and the bar says how many you missed.
- If you switch to another app or lock the phone, reading pauses. When you come back, tap play to go on (phones stop speech in the background).
- The voices are your phone's or browser's own (`speechSynthesis`). Nothing is sent anywhere. Greek text is read with a Greek voice when the device has one, English with an American or British voice as you choose.

## What is read

The Storyteller sets the defaults for the chronicle when creating it (and later in Chronicle settings → Voice): Storyteller, in character, out of character and dice results, all on unless changed.

Each player can override any of them in **Profile → Voice** (as the chronicle sets it / always / never), and actions too. There you also pick Phone voices or Off, the English accent, the speed (0.75–2×) and the volume.

## API

| Route | Who | What |
|---|---|---|
| `GET/PUT /api/voice/settings` | signed in | your own settings (`tts_source`, `en_accent`, `rate`, `volume`, `overrides`, …); an unknown key or bad value is a 400 |
| `GET /api/campaigns/<id>/voice-settings` | members, creator, admins | `{settings, can_edit, effective}`; `effective` is what is read for you |
| `PUT /api/campaigns/<id>/voice-settings` | creator, site admins | `{defaults: {storyteller, ic, ooc, dice}}` and the later keys |

Stored as JSON text in `users.voice_settings` and `campaigns.voice_settings` (`ensure_users_voice_settings_column`, `ensure_campaigns_voice_settings_column`); the rules are in `backend/services/voice_settings.py`. The CSP allows `media-src 'self' blob:` for the audio of the next phases.

## Server voices (0.17)

- In **Profile → Voice** pick **Server voices**. Listen (the ear) then plays each line made on this site's server instead of the phone's voice. The English accent (American / British), speed (0.75–2×) and volume apply as before.
- **Who sounds like what.** The Storyteller (AI, or the chronicle's Storyteller speaking as staff), actions and dice results use the chronicle's narrator voice. A player character speaks with the voice of its gender (Female / Male / Neutral); not set uses the neutral voice. Out-of-character lines use the neutral voice. Greek text gets a Greek voice, English text an English one in your accent.
- **Voice gender** is set in the Forge (Concept step in V5, next to Concept in Classic) and on the character sheet ("Voice"), where only the owner can change it, also on a locked sheet: it is not a rule. Unset shows a reminder to the owner. The PDF has a "Voice" line (V5 and V5 ghoul sheets).
- **Narrator voice**: in Create chronicle and Chronicle settings → Voice, one choice each for English (American), English (British) and Greek, with "Hear it". Left on Default, the catalog's narrator for that language is used. If the speech service is not running, the block says so and the default is kept.
- **Playback**: one `<audio playsinline>` per room. The app asks for Ogg/Opus where the browser can play it and for the AAC (m4a) copy otherwise (iOS Safari). While a line plays, the next one in the queue is already being made and fetched. If the server is busy or off, or the audio will not play, that line is read with the phone's voice and a notice says so (at most once a minute).
- Text sent to the speaker: markdown and emoji removed, an in-character or OOC line starts with the speaker's name, a dice result is its first line as one sentence with the roller's name, at most 600 characters (the service then cleans per language, see below).

### Server voices API

| Route | Who | What |
|---|---|---|
| `GET /api/voice/voices` | signed in | `{available, voices, defaults}`; `available: false` (200) when the speech service is off |
| `POST /api/voice/tts/jobs` `{message_id}` | whoever may read the message | `{job_id, state, key?, position?}`; `state` is `done` at once when the line is cached. 404 for a missing message and for one the viewer may not read (same checks as reading the room: chronicle access, closed rooms, hidden rolls); 400 `not_spoken` for markers and system lines; 503 when the service is busy or off |
| `GET /api/voice/tts/jobs/<job_id>` | signed in | `{state, position?, key?, error?}`; a service that went away reads as `failed` / `speech_unavailable` |
| `GET /api/voice/audio/<key>?fmt=ogg\|m4a` | whoever may read a message with that audio | the audio, `Cache-Control: private, max-age=86400`; 404 otherwise |
| `POST /api/voice/tts/preview` `{voice_id, lang}` | signed in | a fixed sample sentence in that voice (a job, as above) |
| `PUT /api/characters/<id>` `{gender}` | owner, staff | `female`, `male`, `neutral` or `null`; allowed on a locked sheet |

Rate limits: 60 jobs a minute (1,500 an hour), 240 status polls, 120 audio fetches, 10 previews a minute per user.

Stored: `characters.gender` and `npcs.gender` (`ensure_characters_gender_column`; `npcs.gender` is not used for voices yet: NPC lines are not in `messages`, so Listen does not read them), the chronicle's `narrator_voice_en` (American), `narrator_voice_en_gb` and `narrator_voice_el` in `campaigns.voice_settings`, and `voice_audio (message_id, audio_key, voice_id)` (`ensure_voice_audio_table`): which message used which cached file (NULL for previews). Deleting a message deletes its rows and asks the service to delete each file no other message still uses (`DELETE /audio/<key>`). The backend reaches the service at `127.0.0.1:${SPEECH_PORT}` with `SPEECH_SECRET` (both in the backend's compose environment).

## Speaking (0.18)

- **Record.** The mic in the message box opens the recorder in place of the box (the reply bar stays above it, Speaking as sits in its header: in character, out of character, or a quote by replying). The timer is 28 px with tabular digits; the 44-px mic ring is gold, then `--sr-warn-400` from 1:00, `--sr-blood-500` from 2:00 and `--sr-blood-300` from 2:45. It pulses every 5 s (every second in the last 15 s) by a class toggle; with reduced motion it only changes colour. At the chronicle's limit (3:00 by default) it stops by itself and goes to review. If the app goes to the background the recording pauses and shows "Tap to resume".
- **Review.** Play it back on the phone, seek (44-px touch box), one speed button stepping 0.75 → 1 → 1.25 → 1.5 → 1.75 → 2×, Record again, Discard, Transcribe. **Nothing leaves the phone until Transcribe.** Formats: WebM/Opus (Android, desktop) or MP4/AAC (iOS), whichever `MediaRecorder` offers.
- **Text.** Transcribe sends the clip (`POST /api/voice/clips`), the speech service keeps it as Ogg/Opus 16 kbps and transcribes it (Whisper on the GPU); the app polls and shows the place in the queue. The text (hesitations like "um", "εε" removed) is editable. Back / Discard / Send are one 44-px row; **Send is always a separate tap** and goes through the normal send: OOC warnings and the ban, the Storyteller's reply, reply-to, all exactly as typed text. If the GPU is busy (`gpu_busy`) or the service is down, the text step says so and offers the phone's dictation; the recording is still sent with the line.
- **Phone dictation** (Profile → Voice → "Voice messages are written by: My phone's dictation", if the chronicle allows it): the phone's own recogniser (`SpeechRecognition`, audio goes to Apple or Google) writes while you speak; no recording is kept, so the line gets the mic marker and no replay chip.
- **Marker and replay.** A line sent by voice has a 14-px mic after the speaker's name (and at the start of later rows of the same speaker), with a spoken name ("Sent by voice" / "Dictated on the phone"); everyone sees it. A recorded line has a one-line chip under it: play/pause, time, and a separate seek bar. One `<audio playsinline>` per room, so one clip plays at a time; Ogg/Opus where the browser plays it, the AAC copy (made on first request) on iOS.
- **Microphone blocked**: the mic button becomes `mic-off`; tapping it says to allow the microphone in the phone's Settings.
- **Chronicle settings → Voice**: longest recording (30 s to 3 min) and whether players may use phone dictation.
- **Kept** for the chronicle's lifetime; deleted with the message, and all of a chronicle's clips with the chronicle. A recording that was transcribed but never sent is removed after 24 hours (0.20).

### Speaking API

| Route | Who | What |
|---|---|---|
| `POST /api/voice/clips` (multipart `audio`, `campaign_id`, `location_id`, `lang` el/en) | chronicle members | ≤ 8 MB (nginx `client_max_body_size 8m` on this route only; Flask checks too); sent to the speech service `/stt`, which probes, transcodes and queues it. `{clip_id, job_id, state, position?}`; 404 not a member / not a room of the chronicle, 400 bad type or language, 413 too large, 507 `clips_disk_full`, 503 when the service is down or the queue is full |
| `GET /api/voice/stt/jobs/<job_id>` | the clip's owner | `{state, position?, text?, duration_ms?, error?}`; the raw transcript is stored on the clip |
| `GET /api/voice/clips/<clip_id>/audio?fmt=ogg\|m4a` | whoever may read the message; an unsent clip only its owner | the audio; 404 otherwise |
| `POST /api/campaigns/<cid>/locations/<lid>` + `clip_id`, `source` | the clip's owner, same room, not sent before | `source` `voice` or `phone-voice`; the message JSON carries `source`, `clip_id`, `clip_ms` |

Rate limits per user: 6 clips a minute (60 an hour), 120 job polls and 120 replays a minute. Disk cap: `VOICE_CLIPS_MAX_GB` (default 20, counted from the stored durations). Stored: `voice_clips (clip_id, campaign_id, location_id, user_id, message_id, duration_ms, lang, transcript_raw, created_at)` and `messages.source`, `messages.clip_id`, `messages.clip_ms`.

Not tried on real phones yet (step 0.5): iOS home-screen mic access, which format each phone records, 2× review playback on older iOS, and Opus replay on the iPhone.

## Ops and polish (0.20)

- **Your character's own voice.** On the character sheet («χαρτί του χαρακτήρα») the owner can pick one voice from the server's list (e.g. `el-kostas`) under "Specific voice". It reads that character's in-character lines («Εντός ρόλου») in its language instead of the voice chosen by gender; lines in the other language keep the gender voice; out-of-character lines («Εκτός ρόλου») keep the neutral voice. "Automatic (by gender)" clears it. The pick is checked against the speech service's catalog (`characters.voice_override`; 503 `speech_unavailable` if the service is down when you save).
- **Push-to-talk on a computer.** In a room, hold Space to record and let go to stop and review. It does nothing while you are typing in a box, with a modifier key held, or when the microphone is blocked.
- **Admin → AI system → Voice**: whether the speech service runs, Whisper loaded or idle, both queues, free GPU memory against what transcription needs, recordings on disk against the cap, the spoken-line cache against its cap, and minutes recorded per player today (UTC). `GET /api/voice/health`, site admins only (403 for everyone else).
- **Clean-up.** The spoken-line cache is capped at `VOICE_TTS_CACHE_GB` (default 5): the least recently played lines are removed first, checked at start and after every 20 new lines. Recordings transcribed but never sent are removed after 24 hours (rows and files), at backend start and then daily. Deleting a chronicle deletes all its recordings (since 0.18).

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
| `DELETE /audio/<key>` | removes a spoken line (the backend calls it when the last message using it is deleted) |
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

`SPEECH_SECRET`, `SPEECH_PORT` (5055), `VOICE_STT_VRAM_MB` (2150), `VOICE_STT_IDLE_SECONDS` (600), `VOICE_TTS_CACHE_GB` (5). Backend: `VOICE_CLIPS_MAX_GB` (20). Others with defaults in `speech/app/config.py`: text limit 5,000 characters, clip limits, bitrates (clips 16k, TTS 24k), queue sizes.

### Tests

`python -m pytest speech/tests` covers text cleaning, Greek numbers, splitting, cache keys, limits, the voice mapping (including neutral) and the TTS cache eviction with a tiny cap. They need no models.

## Device checklist

Fill in on the real phones after each voice release (✓ works, ✗ fails, note what happened). Results are left blank until someone runs it.

| Check | iPhone, Safari tab | iPhone, home-screen app | Android, Chrome |
|---|---|---|---|
| Listen with phone voices: first line plays after the ear tap | | | |
| Listen with server voices: Greek and English lines play | | | |
| Silent / mute switch on: does Listen still play? | | | |
| App in the background: Listen pauses, "Tap to resume" on return | | | |
| Screen locked during a narration | | | |
| Record 20 s, review at 2×, Transcribe, Send | | | |
| Record to the 3-minute auto-stop | | | |
| Recording when the app goes to the background (pauses or stops) | | | |
| Microphone denied: mic-off button and the Settings hint | | | |
| Microphone allowed again after denying | | | |
| Replay a recorded line (Ogg or the AAC copy) | | | |
| Phone dictation (Greek and English) | | | |
| GPU busy: the text step offers phone dictation | | | |
| Character's specific voice heard on its lines | | | |

Desktop (one browser is enough): Space push-to-talk starts and stops; Space while typing in the message box types a space.

Load check (server): 4 listeners in one room and one Storyteller narration, cold cache: first audio in under 3 s, CPU under the 80% cap. Result: 
