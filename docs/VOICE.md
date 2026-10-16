# Voice

Voice in the chat comes in phases (see [ROADMAP_VOICE.md](ROADMAP_VOICE.md)). Release 0.16 has the first one: **listening with your phone's own voices**. Server voices, speaking and the language override follow.

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
