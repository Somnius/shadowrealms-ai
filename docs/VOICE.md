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

## Language override (0.19)

- **Hear in** (Profile → Voice → "Read and hear messages in": As written / English / Ελληνικά; default as written, each player opts in). Lines in the other language are translated **ahead of time**: right after a message is saved, the server checks which languages the chronicle's members hear in (their settings, cached 60 s) and queues a translation job on one background worker. Nothing is translated inside an audio request.
- **On screen** (typed lines too): the body shows your language; the other text sits under it as a 13-px italic caption (`--sr-text-2`, two lines with "more") with an **EL** / **EN** text chip, and a 44-px **Show original** button (`--sr-arcane-300`) swaps body and caption for that row (not saved). A line that is still being translated shows as written and swaps when its translation arrives (the room asks every 3 s while some are pending).
- **Listening**: server voices speak the translation in the voice of that language; while it is not ready the server answers `waiting_translation` and the app asks again (6 times, 1.5 s apart), then reads the original. Phone voices read the translation if it is there by the time the line's turn comes, else the original.
- **Write in** (Profile → Voice → "Voice messages are sent in": The language I speak / English / Ελληνικά): speak Greek and send English, or the other way round. The recorder's text step shows both: your words (editable) and the line that will be sent, labelled "English (sent)" (editable too; "Translate again" after you change your words). Phone dictation gets the same through `POST /api/voice/translate`. Your words are kept with the message: everyone, the Storyteller included, sees them as the caption with "Show original" ("Show your original" on your own lines), and when you hear in your language you hear your own words, not a translation back.
- **Translator**: the `translator` AI role (Admin → AI; default LM Studio `llama-krikri-8b-instruct`, temperature 0; falls back to LM Studio's loaded model, never to the small Ollama model). Names never reach the model: proper names (the chronicle's characters, NPCs and locations, plus capitalised words that read as names) become ⟦1⟧, ⟦2⟧… placeholders it copies, with a man/woman hint for the Greek article, and go back in exactly as written (if a placeholder gets lost the line is translated once more without them). The prompt keeps dice, *actions* and markdown, asks for the exact meaning, and carries a few examples (one is "misses by a hair" → «αστοχεί παρά τρίχα», which it once reversed) plus the lines of the game-term glossary (`backend/services/translation_glossary.txt`: Wits, Disciplines, clan names, Hunger… stay in English; Storyteller ↔ Αφηγητής) that appear in the line. Answers with notes or far longer than the line are dropped (no caption rather than a wrong one).
- Checked on the 20 phase 0 lines plus a few game lines (0.1–0.5 s a line on this GPU): meaning kept, glossary terms kept, Greek attribute names (Οξύνοια, Επίγνωση) come back as Wits, Awareness. Names now come through as written in all 28 test lines (before: Ελένη → Eleni, Μάρκος → Marcus, Eleni → Ελένη); lowercase "hunger" in narration stays Hunger; «η αίμα» and wrong articles before names are fixed after the model. A name that opens a sentence and is not in the chronicle is only caught by its grammar ("Eleni whispers", "Eleni,").

### Language override API

| Route | Who | What |
|---|---|---|
| `GET /api/voice/translations?campaign_id&location_id&ids=1,2&lang=el` | whoever may read the room | `{translations: {id: {lang: {text, kind}}}, pending: [ids]}`: the rows in `lang` and every `original`; a missing one is queued and listed as pending. At most 60 ids; dice, slash and system lines are skipped |
| `POST /api/voice/tts/jobs {message_id, original?}` | as before | in the listener's hear-in language; `{state: 'waiting_translation'}` while the translation is made; `original: true` reads the line as written |
| `GET /api/voice/stt/jobs/<id>` | the clip's owner | with a write-in language: `translated: {lang, text}` (or `translate_failed`) once done |
| `POST /api/voice/translate {text, from, to}` | signed in | one line for the recorder's text step; 503 `translation_failed` |
| `POST /api/campaigns/<cid>/locations/<lid>` + `original: {text, lang}` | the player, voice lines | the sent line is the translation; the original is stored as the `original` row |

Rate limits per user: translations 60 a minute, translate 20 a minute (200 an hour), TTS jobs 90 a minute. Stored: `message_translations (message_id, lang, text, kind 'ai'|'original', model, created_at)`, deleted with the message; `messages.lang` (language of the text, guessed from the letters) and `messages.orig_lang`.

## Ops and polish (0.20)

- **Your character's own voice.** On the character sheet («χαρτί του χαρακτήρα») the owner can pick one voice from the server's list (e.g. `el-kostas`) under "Specific voice". It reads that character's in-character lines («Εντός ρόλου») in its language instead of the voice chosen by gender; lines in the other language keep the gender voice; out-of-character lines («Εκτός ρόλου») keep the neutral voice. "Automatic (by gender)" clears it. The pick is checked against the speech service's catalog (`characters.voice_override`; 503 `speech_unavailable` if the service is down when you save).
- **Push-to-talk on a computer.** In a room, hold Space to record and let go to stop and review. It works only with focus on the page or the message list (not on a link, a button or an open dialog), so Space still scrolls and presses things elsewhere. It does nothing while you are typing in a box, with a modifier key held, or when the microphone is blocked.
- **Admin → AI system → Voice**: whether the speech service runs, Whisper loaded or idle, both queues, free GPU memory against what transcription needs, recordings on disk against the cap, the spoken-line cache against its cap, and minutes recorded per player today (UTC). `GET /api/voice/health`, site admins only (403 for everyone else).
- **Clean-up.** The spoken-line cache is capped at `VOICE_TTS_CACHE_GB` (default 5): the least recently played lines are removed first, checked at start and after every 20 new lines. Recordings transcribed but never sent are removed after 24 hours (rows and files), at backend start and then daily. Deleting a chronicle deletes all its recordings (since 0.18).

## Transcript check (0.21)

When you tap Transcribe, the text is checked before you see it. Nothing is ever held up: if a step is missing, down or slow, you get Whisper's text unchanged.

1. **Hint.** Whisper gets the chronicle's character, NPC and location names and a short World of Darkness glossary as its `initial_prompt` (≤ 400 characters). It only nudges spellings.
2. **Flags.** In the speech service, Laya-words scores Whisper's unsure words (word probability < 0.985, 3+ letters; least sure first, up to 12, within 2 s; about 0.12 s a word on 4 CPU threads): "is the word marked ⟦ ⟧ a recognition mistake?", asked with the 10 words each side. The input is built exactly as RecMeets builds it (laya.common.build_sequence).
3. **Fix.** The backend sends Krikri (`TRANSCRIPT_CHECK_MODEL`, default LM Studio `llama-krikri-8b-instruct`, temperature 0, one call of at most 3.5 s, 4.5 s in all; asked once per clip, on the first poll after Whisper is done, then stored) the whole line with only the flagged spans marked (Laya ≥ 0.7; a neighbour Whisper was under 0.7 sure of joins the span, so «βλυχ άρα» is one span) and the names. It may join split words and writes slang and swearing as spoken. A fix that does not sound like the span (a synonym), a rewrite, or an accent-only change is dropped.
4. **Show.** Under the text, each fixed word is a 44-px chip ("heard: βλυχ άρα"); a tap puts Whisper's words back in the text, another tap re-applies the fix. The text stays editable.

`GET /api/voice/stt/jobs/<id>` adds `checked` (segments `[{t}, {t, raw}]`) and `text_raw` when something was fixed; `text` is then the checked text (and what a write-in translation uses). Stored: `voice_clips.transcript_raw` (Whisper, always) and `voice_clips.transcript_checked` (JSON segments, `[]` when nothing changed). `VOICE_TRANSCRIPT_CHECK=0` turns it off. The speech service's `/stt` takes `prompt` and `check=1` and returns `words`, `probs`, `suspects [{i, word, p_whisper, p_laya}]` and `check_ms`; `/health` has `check`.

**Model.** `data/voice/models/laya-words/` (`model.onnx`, `tokenizer.json`, `laya.json`; 378 MB) from [somniusx/recmeets-laya-words](https://huggingface.co/somniusx/recmeets-laya-words) at revision `8ae611d196aef03143b926a86bca67268d6b92b9` (SHA-256 of model.onnx `73e49fbc…a566`). Without it, the check is skipped. Laya is by [convaiinnovations](https://huggingface.co/convaiinnovations) (Apache 2.0); the fine-tune on Whisper's own mistakes in Greek and English is somniusx/recmeets-laya-words (Apache 2.0), from RecMeets.

**Measured** (2026-10-17, phase 0 samples and synthetic lines spoken by Pocket TTS kostas; Krikri 0.1–0.5 s; Laya 0.15–1.1 s a line):

| Clip | Whisper | After the check |
|---|---|---|
| synthetic text: Whisper's split as Lef saw it | Ο Νίκος του λέει είσαι μεγάλη βλυχ άρα ρε μαλάκα. | … μεγάλη **βλαχάρα** ρε μαλάκα. |
| synthetic text, same split | Άντε ρε βλυχ άρα, πάλι χάθηκες στο Elysium; | unchanged (Krikri offered «βρε άρη», dropped as not alike) |
| Pocket «Άντε ρε βλαχάρα, πάλι χάθηκες στο Elysium;» | no hint: Άντερε Βλαχάρα … Ελίσιουμ; with the hint: Άντερευλαχάρα, … Elysium. | unchanged (Laya 0.69, under 0.7) |
| Pocket «… είσαι μεγάλη βλαχάρα, φίλε μου.» | right | unchanged |
| Pocket «Γαμώτο, ο Πρίγκιπας μας έστησε, ρε μαλάκα.» | Αγαμώτο, … έστεισε, ρε Μαλάκα. | unchanged (Laya 0.13 and 0.23: not flagged) |
| Pocket athina 07 | … πυρώνεται … | unchanged (Laya 0.25) |
| Piper ryan 07 «Blood is a debt …» | Elud is a debt … | unchanged (Krikri offered Elysium, then Eld; dropped) |
| Pocket 03, Piper ryan 01 (right) | right; Laya flagged σιγανά, candles | unchanged (before the guards Krikri made σιγά-σιγά, ψιθυριστά, candle) |

So: it does what it should on a split word in a clear sentence, it does not damage right text in these cases, and it misses most mistakes Whisper was sure of (Laya scores them low). Real recordings from players are the next test.

## Read along (0.22)

- **Chunks.** What a line says (`spokenParts` in `frontend/src/features/voice/readout.js`, `spoken_parts` in `backend/services/voice_tts.py`; keep them in step) is a list of `{text, lang}` chunks: the text split at sentence ends (. ! ? ; · … and the Greek ;, closing quotes and brackets kept with their sentence), sentences under 60 characters joined, none over 220 (cut at a comma, else a space). A whole message may be up to 4000 characters. Each chunk is its own TTS job (`POST /api/voice/tts/jobs {message_id, chunk, lang}` → `{…job, chunk, chunks, text}`, 400 `no_such_chunk` past the end) and its own cached file, indexed in `voice_audio` like before. The app plays chunk N while N+1 and N+2 are made; if a chunk fails the rest goes to the phone voice. When chunk 0 falls back to the original (translation not ready) the rest of the line is asked as the original too.
- **Rolls in your language.** The listener's language is the hear-in language when set, else the app's language (sent as `lang`). A Storyteller line's `[[roll: …]]` tags become their label in the prose and, after it, one sentence per roll in the listener's language ("Roll: Wits plus Awareness, 5 dice, difficulty 6." / «Ρίψη: Wits συν Awareness, 5 ζάρια, δυσκολία 6.»). A dice line is read from its marker row: who, what, dice, successes and the outcome (critical win, messy critical, bestial failure, total failure, botch, success, failure / κρίσιμη επιτυχία, κρίσιμη επιτυχία με Πείνα, κτηνώδης αποτυχία, ολική αποτυχία, καταστροφική αποτυχία, επιτυχία, αποτυχία). Each chunk is spoken by the voice of its own language, so English text never goes to the Greek voice. Trait names stay English (game terms).
- **Highlight and follow.** The message being read gets `sr-msg--reading` (accent bar and a light tint from the theme; no transition with reduced motion). Exact sentence wrapping inside the rendered Markdown was left out: the sentence being said is shown in the speaking bar instead. Follow scrolls the message into view at each chunk; a wheel, finger scroll or scroll key in the list pauses it, "Follow" in the bar resumes.
- **Message menu.** "Read this" and "Read from here" (this and every later readable message of the room, in order) in the … menu and on long-press. A long-press that selected text, or a finger that moves, does not open the menu. With Listen off they play and stop ("Stop reading" in the bar).
- **Catch-up.** Turning Listen on asks "Read earlier messages?": Last 3 / Last 10 / From where I stopped / None. The choice is kept in `localStorage` (`sr_voice_catchup`) and shown first next time; "From where I stopped" reads the readable messages after the last one finished in that room (`sr_voice_last_read:<campaign>:<room>`).
- **NPC voices.** NPC lines in rooms are characters marked as NPCs; they speak with their sheet's gender like any character. The `npcs` table (with `gender` since 0.17) has no lines in rooms (`npc_messages` is AI context) and no editing screen.
- **Delete all recordings.** Chronicle settings → Voice → "Delete all recordings" (creator or admin, with a confirm): `DELETE /api/campaigns/<id>/voice-clips` deletes every clip row and file of the chronicle and clears `messages.clip_id`; the text and the mic mark stay. Answers `{deleted}`.
- **Roll-line captions.** Storyteller lines with roll chips get the caption and "Show original" like other lines; the translator gets the text with the tags replaced by their labels, and the chips always come from the original.

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
