# Roadmap: voice (listen, speak, language override)

Started 2026-10-16 23:05, target: every phase done before 07:00 on 2026-10-17. One release per phase; at 07:00 only finished, tested phases are live, the rest stays on its branch. The 0.10 work is in [ROADMAP_v0.10.md](ROADMAP_v0.10.md).

How each phase runs: build in its own git worktree → tests and CI green → one independent review → fixes → merge to `main` → docs and this file updated → release. Builds run niced and never above 80 % of the machine.

## Status

| # | Phase | Parts | Version | Time box | Status |
|---|---|---|---|---|---|
| 0 | Measure | voices listened to · Whisper on the GPU timed and its real VRAM read · phone test page | — | until 00:00 | done except 0.5 (phones) |
| 1 | Listen with the phone's own voices | CSP and glyphs · player voice settings · chronicle read-out defaults · Listen toggle and queue · read-out rules | 0.16 | until 02:00 | built on voice/p1-listen, waiting for review |
| 2 | Server voices | speech container · gender on the sheet · TTS jobs and cache · voice catalog and narrator voices · server mode in the app | 0.17 | until 03:45 | not started |
| 3 | Speaking | clip upload · transcription jobs and the GPU policy · recorder with the timer · review and text steps · mic marker and replay · phone dictation | 0.18 | until 06:00 | not started |
| 4 | Language override | translator · ahead-of-time translation · captions with "show original" · speak in one language, write in the other | 0.19 | until 06:45 | not started |
| 5 | Ops and polish | health panel · cache and disk caps · per-character voice · device checklist | 0.20 | after the deadline | not started |

## Decisions (2026-10-16)

- Voice is for the whole site, no public/private split; non-commercial voices are fine; the phone's own speech recognition and voices are allowed as a choice, labelled as leaving the phone.
- Clips: up to 3 minutes; the timer pulses every 5 seconds, changes colour after 1 and 2 minutes and goes bright blood red near the end; the player listens back (seek, 0.75–2× speed) before transcribing, then checks the text; nothing is ever sent without a tap. Clips are kept as Ogg/Opus for the chronicle's lifetime, everyone in the room can replay them, deleted with their message or the chronicle.
- Gender on the sheet: Female / Male / Neutral; unset is spoken neutral and the sheet reminds you. NPC lines are not spoken yet; `npcs.gender` exists for later. Narrator voices per language (EN US, EN UK, Greek) and read-out defaults (Storyteller, IC, OOC, dice) are asked at chronicle creation; every player can opt out in Profile → Voice, and sets listening speed and volume there. "Hear in" defaults to "as written".
- Voice messages are IC, quote or OOC through the existing "Speaking as" picker and reply bar; no new control.
- No daily quotas: per-minute limits, one transcription at a time, a queue, and a disk cap. Bandwidth is not the limit; GPU time, the CPU cap and abuse are.
- GPU: Whisper loads on the first clip, stays while clips come, unloads after 10 idle minutes; it checks free VRAM before loading and refuses cleanly (phone dictation takes over) instead of fighting the language models or the image tool.
- Translation (Krikri, local) runs right after a message is saved for the players who need it, never while someone waits for audio. "Show original" is always there.
- Everything long is a job (create, poll, fetch); only the clip upload is a big request. Audio from blobs needs `media-src` in the CSP.
- Schema changes go through `ensure_*` functions in `backend/database.py` like every other column.

## Phase 0 — Measure

- [x] 0.1 Piper voices (EN US, EN UK, Greek): seconds per sentence, listened to, Greek intelligibility scored by transcribing it back. Status: done 23:17. Piper EN go (alan, jenny, cori); Piper EL no-go as the main voice (WER 24–27 %).
- [x] 0.2 Pocket TTS Greek (the only local Greek male voice found): same test. Status: done 23:17. Pocket TTS Greek go (kostas, spyros, eleni, athina), about 0.28× real time on one thread.
- [x] 0.3 Whisper large-v3-turbo on the GPU in the CUDA image: seconds for 10 s / 60 s / 180 s clips, cold start, real VRAM read from `nvidia-smi` during a clip, name prompt on/off, Parakeet A/B. Status: done 23:17. faster-whisper large-v3-turbo int8_float16 on the GPU go: +1.6 GB VRAM, about 30× real time.
- [x] 0.4 Opus bitrate (64/48/32) against transcription accuracy; 20 chat lines translated each way, timed. Status: done 23:17. Clips as Opus 16 kbps mono (about 115 KB a minute); Krikri translation go with a game-term glossary. Models in data/voice/models (2.5 GB).
- [ ] 0.5 Phone test page (recording formats, voices, home-screen mic, silent switch, 2× playback, Opus playback, phone recognition) on an iPhone and an Android phone. Status: still needs Lef's phones.

## Phase 1 — Listen with the phone's own voices (0.16)

- [x] 1.1 `media-src 'self' blob:` in nginx; nine new glyphs (mic, mic-off, ear, play, pause, stop, skip, waveform, tongue). Status: done 23:10. Glyph test added; blob playback on live nginx is checked at release.
- [x] 1.2 Player voice settings column, `GET/PUT /api/voice/settings`, Profile → Voice panel (source, accent, speed, volume, opt-outs). Status: done 23:17. Profile → Voice panel (Phone voices / Off, accent, speed, volume, per-kind opt-outs); pytest + jest.
- [x] 1.3 Chronicle voice settings column, route, "Voice" block in Create chronicle and Chronicle settings (read-out defaults). Status: done 23:17. Voice block in Create chronicle and Chronicle settings; creator/admin only, effective rule tested.
- [x] 1.4 Listen toggle in the room header, audio unlock on tap, speech queue (order, skip own, cap 20, pause in background, tap to resume), speaking bar, "read the last 3?" on open. Status: done 23:17. Ear in the room header, speaking bar (44 px), queue with cap 20 / missed / pause on hidden / tap to resume, catch-up of 3; jest for the queue. Not yet tried on real phones.
- [x] 1.5 Read-out rules (Storyteller / IC / OOC / dice from chronicle defaults and player overrides), dice read as one sentence, system lines skipped. Status: done 23:17. Storyteller / IC / OOC / dice / actions rules, dice as one sentence, system lines skipped; jest table.
- [x] 1.6 Release 0.16: `docs/VOICE.md`, FEATURES, CHANGELOG. Status: done 23:19. VOICE.md, FEATURES, CHANGELOG, version 0.16.0. Backend 1256 passed, frontend 929 passed, lint clean. Waiting for review, merge, tag and phone check.

## Phase 2 — Server voices (0.17)

- [x] 2.1 `speech` container (CUDA base, ffmpeg, Piper, Pocket TTS, faster-whisper installed), host network, GPU checked with `nvidia-smi` inside, 8 CPUs, job queue with STT / TTS / translate lanes, `/health`. Status: done on `voice/speech-service` (STT and TTS lanes; the translate lane comes with 4.1). Opt-in compose profile `voice`, 127.0.0.1:5055, shared secret. Checked once on the host GPU: EN line 0.23 s warm, EL (Pocket) 0.81 s warm, 170 s Greek clip transcribed in 3.5 s.
- [x] 2.2 Gender on the character sheet (Forge and sheet select), returned with messages. Status: done 23:35. `characters.gender` + `npcs.gender`; V5 and Classic forges, the sheet's "Voice" line (owner sets it, also on a locked sheet; reminder when unset), PDF line on V5 and V5 ghoul sheets (the Classic identity block is full: no line there). Not added to the message JSON: the backend picks the voice, the app does not need it. Ghoul forges have no field; set it on the sheet.
- [x] 2.3 TTS jobs, audio route and cache; the same visibility check as reading messages (404 for missing and forbidden alike); audio removed when a message is deleted. Status: done 23:35. `visible_message()` in messages.py, `voice_audio` index, `DELETE /audio/<key>` on the service; pytest (404 both ways, one file for two listeners, delete). Chronicle delete does not clean the cache yet (Phase 5).
- [x] 2.4 Voice catalog, previews, narrator voice per language in chronicle creation and settings, neutral voice per language, attributions in About. Status: done 23:35. EN-US / EN-UK / Greek narrator with "Hear it"; neutral voice per language from the catalog. The app has no About page: licences and the Pocket TTS CC BY 4.0 credit are in VOICE.md and `GET /voices`. Not synthesised against the live service here (no container started); every catalog id is checked at deploy.
- [x] 2.5 Server mode in the app: job → audio → play, prefetch, fallback to the phone's voice when the server is busy. Status: done 23:35. One `<audio playsinline>` per room, Ogg or m4a by `canPlayType`, speed and volume, next line prefetched, fallback with a notice at most once a minute; jest. Not yet tried on real phones (iOS audio unlock on the ear tap is untested).
- [x] 2.6 Release 0.17: docs (VOICE.md, AI_SYSTEMS.md section on the speech container and VRAM policy), CHANGELOG. Status: done 23:40. Waiting for review, merge, deploy (`--profile voice`, `SPEECH_SECRET` in .env) and phone check.

## Phase 3 — Speaking (0.18)

- [x] 3.1 Clip upload: nginx 8 MB on the clips route, clips table, probe before decode, transcode to Ogg/Opus, temp files cleaned; a 6 MB test clip through the public address to learn the front proxy's limits. Status: done 23:50. `POST /api/voice/clips` → speech `/stt` (probe, Ogg/Opus 16 kbps, raw deleted), `voice_clips` table, nginx 8 MB on that route; pytest for member/room/type/size/disk cap. The 6 MB clip through the public address still needs Lef.
- [x] 3.2 Transcription jobs with the GPU policy (lazy load, idle unload, VRAM gate, one at a time, queue depth, CPU fallback for short clips), silence guards. Status: done 23:50. Backend `GET /api/voice/stt/jobs/<id>` (owner only, transcript stored on the clip); `gpu_busy` sends the player to phone dictation or typing. No CPU fallback (left for later: phone dictation covers it). Not run against the live GPU here.
- [x] 3.3 Recorder step 1: mic button in the composer, permission path, timer with the pulse colours, auto-stop at the chronicle's limit (3 min). Status: done 23:50. Sheet replaces the box, mic-off + Settings hint when blocked, pause + Tap to resume in the background; jest for the colour schedule and the flow. Not tried on phones.
- [x] 3.4 Review and text steps: seek slider, speeds, upload with progress, job position, editable transcript, Speaking as and reply kept, send is a separate tap. Status: done 23:50. One rate button 0.75→2×, upload only on Transcribe, queue position, fillers stripped, Back/Discard/Send row, sent through the normal send (same OOC checks as typed; not tested separately). jest flow test.
- [x] 3.5 Mic marker on voice-sent messages (everyone sees it), clip replay chip, AAC copy for phones that cannot play Opus, disk cap. Status: done 23:50. 14-px mic with a spoken name, one-line chip with separate play and seek, one `<audio playsinline>`, m4a copy by `canPlayType`, `VOICE_CLIPS_MAX_GB`; clips deleted with the message and the chronicle. jest + pytest.
- [x] 3.6 Phone dictation as a choice (text only unless the phone can record at the same time), privacy note. Status: done 23:50. Profile → Voice choice with the Apple/Google note, chronicle switch, text only (no parallel recording), also offered when the GPU is busy. Not tried on phones.
- [x] 3.7 Release 0.18: docs, CHANGELOG, security model paragraph on uploads. Status: done 23:55. Waiting for review, merge, deploy (nginx reload for the clip route) and phone check.

## Phase 4 — Language override (0.19)

- [x] 4.1 Translator role, translations table, translate lane, prompt checked on 20 lines each way. Status: done 00:05. `translator` role (Krikri, no Ollama fallback), `message_translations`, one background worker in the backend (not a lane in the speech service: it is an LM Studio call, not audio), few-shot prompt + glossary file. Phase 0 lines + game lines read: meaning and game terms kept; Greek names sometimes transliterated (Ελένη → Eleni). pytest with a fake LM Studio.
- [x] 4.2 Translate right after a message is saved for the players who need it; message language stored when known. Status: done 00:05. Members' hear-in languages cached 60 s (cleared when someone saves voice settings); `messages.lang`/`orig_lang`. pytest: a hear-in-Greek member gets a row in one job, one call per (message, language), no job when nobody needs it.
- [x] 4.3 Hearing in the chosen language, captions under messages with "show original" (typed messages too). Status: done 00:05. `waiting_translation` then the original after ~9 s; captions with EL/EN chip and 44-px swap button; phone voices use the translation when ready. jest for the swap, pytest for 404/waiting. Not tried on phones.
- [x] 4.4 Speak in one language, write in the other: the text step shows both; the original stays as the caption. Status: done 00:05. STT poll translates when done; `POST /api/voice/translate` for phone dictation and "Translate again"; original row so the speaker hears his own words. Round-trip pytest.
- [x] 4.5 Release 0.19: docs, CHANGELOG. Status: done 00:05. Waiting for review, merge, deploy (Krikri must stay loaded in LM Studio) and phone check.

## Phase 5 — Ops and polish (0.20)

- [ ] 5.1 Admin health: queue depths, VRAM, minutes per player today, clip disk use, in the monitoring panel. Status: not started.
- [ ] 5.2 TTS cache LRU, clip folder removed with the chronicle, orphan sweep. Status: not started.
- [ ] 5.3 Per-character voice pick; desktop Space push-to-talk. Status: not started.
- [ ] 5.4 Device checklist in VOICE.md and a load check (4 listeners + one narration under 3 s to first audio). Status: not started.
- [ ] 5.5 Release 0.20. Status: not started.

## Log

- 23:05 — Plan revised with the answers; this file created. Nothing built yet.
- 23:55 — Phase 3 (speaking) built on `voice/p3-speak`, release 0.18.0 pending review.
- 00:05 — Phase 4 (language override) built on `voice/p4-translate` (p3 merged in), release 0.19.0 pending review.

## Left for later

- Cloud voices: a slot in the catalog, not built.
- Pitch-shifted voices: not doing it, they sound bad; a missing voice falls back to the neutral one or the phone's.
- Daily quotas: not needed for now; the health panel shows minutes per player so one can be added in minutes if it ever is.
