# ShadowRealms AI: system specification

Version of the system described: 0.31.0. This document says what the system is and what it must do. It is a reference for contributors and for checking a change against. It is not a changelog (see [docs/CHANGELOG.md](docs/CHANGELOG.md)) and not a plan (see the `docs/ROADMAP_*.md` files). Where a detail lives in another document, this one links to it instead of repeating it.

## 1. Purpose and scope

ShadowRealms AI is a self-hosted web application for running World of Darkness chronicles with an AI Storyteller. A group signs in, joins a chronicle, plays in chat rooms with their characters, rolls dice on the server, and a local language model narrates and answers as the Storyteller. The written chat is turned into a story night by night, can be read aloud with server or phone voices, and works in English and Greek throughout.

In scope:

- Chronicles in two rules editions: Classic (oWoD Revised: Vampire, Werewolf, Mage) and V5 (Vampire: The Masquerade 5th edition).
- Chat rooms with live updates, in-character and out-of-character play, dice, and an AI Storyteller.
- Character creation (the Forge), locked sheets, downtime and saved-point requests, ghouls, PDF sheets.
- "The chronicle so far": the chat written up as a story, exports, recaps, the Storyteller's memory.
- Voice: listening, speaking, translation, optional cloud voices.
- Moderation: OOC monitoring, bans, play suspension, kill and revive.
- Administration: users, invites, AI models and keys, health, archives.

Out of scope is listed in section 14.

## 2. Users and roles

`users.role` is one of `admin`, `helper`, `player`. On top of the site role, a user may be a chronicle's Storyteller (its creator, `campaigns.created_by`) and a member of chronicles (`campaign_players`).

| Role | Can |
|---|---|
| Site admin (`admin`) | Everything below, plus the admin panel: users, bans, password resets, invites, downtime requests, moderation log, login audit and unlocks, AI roles and cloud keys, embeddings, classifier, voice and writer health, archives, Laya labelling, kill and revive of characters. May open any chronicle for support. May post any `role: assistant` message and `dice_*` message kinds. Only an admin may set a cloud model as a chronicle's writer. `/ai` commands other than `/ai explain` are admin only. |
| Helper (`helper`) | Reads and edits any character sheet and its `wod_meta`, sees hidden rolls and closed rooms, adds members and sets playing characters in any chronicle, reads and exports the chronicle so far of chronicles they are a member of. Not an admin: every `/api/admin/*` route refuses a helper (`require_admin` checks `role == 'admin'`). Deletes only their own messages. |
| Storyteller (chronicle creator) | Chronicle settings (listing, enrolment, creation rules, allowed books, voice defaults, chronicle language and chronicle-so-far settings), members and playing characters, closed rooms, hidden rolls, room dice rules, deletes any message in the chronicle, reads and writes the chronicle so far, edit copy, session marks, archives of their own deleted chronicles for 30 days. |
| Player (`player`) | Joins listed chronicles, creates characters in the Forge, plays in open rooms with their playing character, rolls dice, uses `/roll`, `/me`, `/chat` and `/ai explain`, asks for downtime and saved-point spends, sets their own voice settings, deletes their own messages, sees "Previously on…". |

"Staff" in this document means site admins and helpers. "Chronicle staff" means staff plus the chronicle's Storyteller.

Registration needs an invite code (`admin` or `player` type, with a use count) from `backend/invites.json` or Admin → Invite codes. See [docs/FEATURES.md](docs/FEATURES.md#invite-code-system).

## 3. Core concepts

- **Chronicle** (table `campaigns`; "campaign" in the API). Has a `game_system` (vampire, werewolf, mage, custom), a `rules_edition` (`classic` or `v5`, fixed at creation; `v5` only with `vampire`), a language (`el`, `en` or empty), listing and enrolment flags, `max_players`, and JSON settings for character creation, voice and the chronicle so far.
- **Room / location** (table `locations`). A chat room inside a chronicle. `type = 'ooc'` is the OOC lobby, created with every chronicle and never deletable. Rooms can be closed (`is_open = false`) and carry per-room dice rules.
- **Member** (`campaign_players`). One row per user and chronicle, with the user's **playing character** for that chronicle (`active_character_id`).
- **Character** (`characters`). Belongs to a user, usually to one chronicle (`campaign_id` may be NULL for a sheet not yet in a chronicle, and is always NULL for a ghoul). Copies the chronicle's `rules_edition`. The sheet lives in `attributes`, `skills`, `merits_flaws`, `background` and `wod_meta` (JSON). A sheet locks after creation (`sheet_locked`). Flags: `is_npc`, `play_suspended`, `is_active`.
- **Editions.** Classic follows the Revised core rules; V5 follows the 5th edition corebook. Each edition has its own dice engine, Forge, sheet, PDF layout, prompt brief and rule-book collection. Rules as implemented: [docs/rules/CLASSIC_REVISED.md](docs/rules/CLASSIC_REVISED.md), [docs/rules/V5.md](docs/rules/V5.md).
- **Dice.** Rolls are made and posted by the server. Classic: d10 pools against a difficulty, 1s cancel, botches, specialties, Willpower. V5: Hunger dice, pairs of 10s, messy criticals, bestial and total failures, Willpower rerolls, Rouse checks. See [docs/dice-old-wod.md](docs/dice-old-wod.md), [docs/dice-v5.md](docs/dice-v5.md).
- **AI Storyteller.** A local language model (through LM Studio, Ollama as fallback) that answers in-character messages with a prompt built from the chronicle, the character, the room history, memory and rule books. It asks for rolls with tags the server resolves from the sheet. See [docs/AI_SYSTEMS.md](docs/AI_SYSTEMS.md).
- **The chronicle so far.** The chat written up as a story, one room and one night at a time, by a local model, with a player view and a Storyteller view, exports, a recap card and a private memory block for the Storyteller. See [docs/CHRONICLE.md](docs/CHRONICLE.md).
- **Voice.** Listen (phone or server voices), speak (recorded clips transcribed on the server), read along, translation of lines into each player's language, and opt-in cloud voices. See [docs/VOICE.md](docs/VOICE.md).
- **Forge.** Character creation per edition, with catalogs, a guided mode, a server-side check and per-chronicle creation rules. See [docs/CHARACTER_SHEET_BLOCKS.md](docs/CHARACTER_SHEET_BLOCKS.md).
- **Downtime and saved points.** Changes to a locked sheet go through downtime requests resolved by an admin; unspent V5 Advantage dots and the free specialty are spent through spend requests approved by the Storyteller, staff, or a deterministic rule check.
- **Moderation.** OOC monitoring with warnings and per-chronicle bans, site bans, play suspension, and admin kill and revive of characters with an AI-written or fixed death text.

## 4. Functional requirements

Each statement is meant to be checkable against the running system.

### 4.1 Accounts and sessions

- Registration requires a username, email, a password that passes the policy, and a valid invite code; the code's use is claimed atomically.
- Login answers the same 401 for an unknown username and a wrong password; lockouts follow the rules in [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) and expire by themselves.
- An access token lasts 30 minutes; the browser refreshes it through `POST /api/auth/refresh` with the HttpOnly refresh cookie, with rotation and reuse detection.
- Logout revokes the access token and the refresh chain; "Sign out everywhere" ends every session; changing the password ends all other sessions.
- A password or role change, deactivation or ban invalidates every token of that user (`token_version`).
- Every user has an interface language (`ui_language`, `en` or `el`), a display timezone, an OOC portrait, an atmosphere setting and voice settings.

### 4.2 Chronicles and membership

- A chronicle is created with a name, game system, rules edition, language, and optional creation, voice and dice settings. The rules edition cannot change afterwards (409).
- Every chronicle gets an OOC lobby at creation. The lobby cannot be deleted.
- A Storyteller can list a chronicle and open it to players, with a maximum number of players; listed chronicles appear in the hall for others to join.
- A user who leaves a chronicle keeps their characters and gets `restrict_self_join_new_chronicles`; self-join to another chronicle then needs chronicle staff until an admin clears the flag, unless a sheet for that chronicle already exists.
- A player binds a playing character once per chronicle; switching to another character in the same chronicle needs chronicle staff.
- By default a player may hold one locked character across chronicles; an admin can grant `allow_multi_campaign_play`.
- Chronicle staff add members by username and set a member's playing character.
- Deleting a chronicle first writes an archive (minutes and full transcript) and fails without deleting if the archive cannot be written.
- Details: [docs/CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md](docs/CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md).

### 4.3 Rooms and chat

- Members read and post in open rooms of their chronicle; non-members get 403 for rooms, messages, events and dice.
- Closed rooms are readable only by chronicle staff; closed rooms never show in unread counts or live events for anyone else.
- A message has a role (`user` or `assistant`), a type (chat, action, system, ooc), a speaker mode (character, player, staff) and optional `reply_to_id` to a visible message in the same room.
- Only chronicle staff can post with the staff voice; only site admins can post `role: assistant` text outside a one-time grant issued by the AI endpoints, and only site admins can post `dice_*` message kinds.
- Players delete their own messages; the Storyteller and site admins delete any message; nobody but them deletes dice rows or AI Storyteller lines. Helpers follow the player rule. There is no message editing.
- A room opens with the newest 150 messages and loads older ones in pages of up to 100.
- Live updates arrive over server-sent events with a single-use 60-second ticket; the client falls back to polling.
- Slash commands: `/roll`, `/me`, `/chat` for everyone; `/ai explain` for every member; every other `/ai` command for site admins only. The command list is served by `GET /api/ai/slash/commands` in English and Greek.
- The composer offers "Speaking as": the playing character, the player out of character, or (chronicle staff) the Storyteller voice.

### 4.4 Dice

- Every dice card in chat comes from a server roll stored in `dice_rolls`; the marker and the result line are saved in the same transaction as the roll.
- Classic rolls: pool 1–50, difficulty 2–10 (default 6), 1s cancel successes, a botch only when nothing succeeded and a 1 showed, specialty rerolls 10s (rerolled 1s cancel only in Mage), Willpower adds one uncancellable success, degrees: 4 exceptional, 5+ phenomenal.
- V5 rolls: pool 1–50, Hunger dice = min(hunger, pool), success on 6+, each pair of 10s adds 2, difficulty 0–10 (default 1), critical, messy critical, bestial failure, total failure. A Willpower reroll of up to 3 normal dice, once, costs one Superficial Willpower on the sheet. A Rouse check raises Hunger on 1–5 and writes it to the sheet when a character is named.
- Contested rolls: classic ties are ties; V5 ties go to the attacker.
- Room dice rules: a Classic room may have a leniency floor (2–10); a V5 room may have `no_bestial`, `no_messy` and `min_successes` switches. Set by the chronicle owner or an admin.
- Hidden rolls are stored and shown only to chronicle staff.
- When the Storyteller asks for a roll with a `[[roll: …]]` tag, the server resolves the pool from the requester's sheet (specialty, Hunger, impairment, untrained rules) and the requester gets a Roll chip that pre-fills the dice dialog.
- `/ai explain` re-counts a stored roll with the pure rules engine and posts the breakdown; a disagreement with the stored result is reported.
- Bad input types on dice routes answer 400, never 500.

### 4.5 Characters and the Forge

- A character is created in the Forge for a chronicle's edition. Classic uses the Revised budgets (7/5/3, 13/9/5, virtues, freebies); V5 follows the corebook's order with clans, predator types, Disciplines, Advantages, Flaws, loresheets and supplement books picked from a catalog with descriptions in English and Greek.
- V5 creation is checked on the server; the Storyteller can override the check. Creation rules and allowed books are set per chronicle in `creation_settings`.
- A guided mode suggests a clan and predator type and fills Attributes and Skills from a few questions.
- A sheet locks after creation. Later changes go through downtime requests (text requests reviewed by an admin, status pending, approved or rejected, with a reason on rejection) or, for saved V5 points, spend requests.
- Spend requests are approved by the chronicle's creator or staff, or by a deterministic rule check when the chronicle's `st_mode` is `ai`; a spend that fails the check stays pending for a person. Approvals can be reversed.
- Staff can edit any sheet and its `wod_meta`; owners can change their portrait, voice gender and voice pick on a locked sheet.
- A sheet without a chronicle can be brought into a chronicle of the same edition and game line; moving between chronicles is not supported.
- Ghouls are made from a vampire's sheet, have no chronicle of their own, follow their domitor, are never playing characters, and are known to the Storyteller prompt.
- Every sheet exports to PDF (fillable and print versions, A4 or Letter) for the owner, the chronicle's Storyteller and staff; others get 404.
- Each player may hold one playing character per chronicle; the sheet view shows Hunger, Willpower and Humanity trackers.

### 4.6 AI Storyteller

- In an in-character room, a player's message produces one Storyteller reply from the configured role for the message's language (`storyteller_en` or `storyteller_el`); the reply is in the player's language.
- The prompt is token-budgeted: fixed parts (instructions, chronicle, chronicle memory, character and ghouls, room, NPCs), then rule-book and memory sections, then room history. Context overflow is retried with a trimmed prompt on the same model.
- Rule-book search uses the chronicle's edition and game line and is gated by the message's intent from the classifier; fiction chunks are never used.
- A reply gets 45 seconds per model and 55 seconds in total before falling back; when every model fails the API answers 503 with a fixed text and no grant.
- `POST /api/ai/chat` returns `ai_meta` saying which provider and model answered.
- In the OOC lobby, the AI never narrates: a message classed as in character gets a short fixed moderator note; otherwise no reply.
- The Storyteller's reply text is saved by the browser through a one-time grant tied to the user, chronicle, room and exact text, valid 30 minutes.

### 4.7 The chronicle so far

- Update and Rewrite everything are for the Storyteller and site admins; helpers who are members read and export; players get 403; outsiders 404.
- A night is one room and one run of messages with no gap over the chronicle's night gap (default 6 hours, 2–24) or a session-end mark. Nights are numbered by what players can see.
- The story of a night is written from what players could read; hidden rolls go to Storyteller notes; closed rooms are written whole but shown only in the Storyteller view. Table talk is kept apart and exported only on request.
- The model's answer is JSON checked for ids, names, language and alphabet; failures are retried once, then translated, then flagged. Botches and criticals are always listed.
- One job per chronicle; Update at most every 5 minutes, Rewrite once an hour; the writer waits for 10 quiet minutes and never runs while a Storyteller reply is being written. A night is never cut: it is split when it does not fit.
- Exports: story and minutes as Markdown and PDF (sheet or horror look, colour or print, A4 or Letter, date ranges in the Storyteller's timezone, `lang=` for the cached translation).
- The Storyteller and site admins keep an edit copy of the story; minutes and the player view never use it.
- Session-end marks are set and removed by the Storyteller and site admins; everyone sees the end-of-session line.
- "Previously on…" shows every member a room's recent nights and the story so far in short after 12 hours away, built only from the player view, with no model call.
- The Storyteller's memory block (story so far, open threads, recent nights, Storyteller-only notes) goes into every Storyteller reply, at most a quarter of the budget and 1,500 tokens, with a per-chronicle switch; no model call, no wait.
- An optional nightly run updates chronicles with new messages at a quiet hour.
- Writer model per chronicle: one of the models the admin panel lists; a cloud writer only by a site admin, with a warning that the chat leaves the server.

### 4.8 Voice

- Listen reads new messages aloud with the phone's voices or server voices; a player never hears their own lines; the chronicle sets what is read by default and each player overrides it, with speed and volume.
- Server voices: the narrator voice per chronicle and language; a character's voice by gender or an explicit pick; a neutral voice for OOC. If the server is busy or off, the phone's voice reads the line.
- Read along: lines are spoken sentence by sentence, the message being read is highlighted, "Read this" and "Read from here" on any message, a catch-up choice when Listen turns on.
- Speak: a clip of up to the chronicle's limit (default 3 minutes) is recorded on the phone, sent only on Transcribe, transcribed on the server GPU, checked, edited and sent through the normal send path. Phone dictation is an alternative when the chronicle allows it.
- Clips are kept as Opus for the chronicle's lifetime, playable by whoever may read the message, deleted with the message or the chronicle, and the Storyteller can delete all of a chronicle's clips.
- Language override: lines are translated ahead of time into each listener's hear-in language, shown with "Show original"; a player can speak one language and send the other, keeping their words as the original.
- Cloud voices (Gemini) are off unless a site admin turns them on, and then only for chronicles that opt in; any error falls back to the local voice.
- TTS audio and clips are reachable only by users who may read the message they belong to.

### 4.9 Moderation and safety

- In the OOC lobby, a message classed as in character (P ≥ 0.8) is a violation: two warnings, then a 24-hour ban from that chronicle on the third within 7 days. Staff, the Storyteller and staff-voice posts are exempt. With no classifier, nothing is flagged.
- Site admins ban and unban users (temporary or permanent), reset passwords, deactivate accounts, and suspend a character's play with a player-visible message.
- Site admins kill a character (soft, sacrifice or horrible) with a death text written by the chronicler role in the chronicle's language from the player view of the chronicle, or a fixed sentence on any failure; killing a fallen character is a 409. Revive is admin only; the kill row stays. Both go to the moderation log.
- The death text is shown to the same people who may see the sheet: the owner, the chronicle's Storyteller, and staff.
- Admin actions are written to `user_moderation_log`; login events to `auth_events`.

### 4.10 Administration

- Admin panel sections: users, all chronicles, invite codes, downtime requests, moderation log, logins and lockouts, Laya labels and evaluation, AI system (roles, cloud keys, embeddings, classifier, cloud voices, voice and writer health), characters (kill, revive, deaths log), archives.
- AI role settings are stored in `app_settings`; cloud keys are stored encrypted and never returned in clear.
- Re-embedding of vector collections runs at start and on demand, one run at a time.

## 5. Visibility and privacy rules

What players never see:

- Hidden rolls (`dice_*_hidden` rows), returned only to chronicle staff; a quoted hidden roll reaches the Storyteller prompt only as "a hidden dice roll".
- Closed rooms, their messages, their unread counts and their live events.
- The Storyteller view of the chronicle so far: Storyteller-only paragraphs, `st_notes`, nights in closed rooms, the edit copy, usernames in the cast list, message ids in the player view.
- The Storyteller's system prompt and memory block (`/ai context` is admin only and is never saved to the room).
- Other players' sheets, PDFs and death texts (owner, Storyteller and staff only).
- Chronicle exports, archives and the writer's settings (helpers get only the table-talk default).
- Cloud API keys in any form other than "set" and a masked tail.

Other rules:

- Lines given to the chronicle writer never carry usernames.
- The Storyteller prompt is marked as private memory never to be quoted; player text and quoted messages are fenced as data, not instructions.
- A chronicle's chat leaves the server only when a site admin sets a cloud writer or a cloud Storyteller role, or when cloud voices are on and the chronicle opted in; the panels say so.
- Archives of deleted chronicles stay on the server, unreadable through nginx, until an admin deletes them.
- Rule-book text is readable only through the Storyteller's short quotes; the rule-book API is admin only.

## 6. AI system

- Every model call goes through one router that picks an **AI role** and a provider. Roles: `storyteller_en`, `storyteller_el`, `utility`, `classifier`, `chronicler_en`, `chronicler_el`, `translator`. Each is set in Admin → AI system.
- Providers: LM Studio (default, local), Ollama (local), and optional Anthropic and OpenAI with admin-entered keys; the classifier can also use Typesafe Jev with its own key. Nothing uses a cloud provider until a key is saved, tested and a role is pointed at it.
- Fallback chain: cloud → the role's local model → LM Studio's loaded model → Ollama → LM Studio. The chronicler, translator and classifier roles never fall back to Ollama. A model LM Studio cannot load is skipped for 5 minutes.
- Language routing: Greek letters ≥ 30% → Greek; clearly English → English; otherwise the user's interface language, then English. Greek replies are checked for stray scripts.
- Embeddings: `text-embedding-bge-m3` through LM Studio for every ChromaDB collection (memory and rule books); collections record their embedder and are re-embedded when it changes.
- Classifier: Laya (a fine-tuned mmBERT on ONNX Runtime, CPU) by default, Jev with a key, or an LLM prompt; returns in-character probability and intent (`dice`, `combat`, `rules_question`, `roleplay`, `general`). Fails open.
- Voices run in the `speech` container: Piper and Pocket TTS for speech, faster-whisper on the GPU for transcription, Laya-words for the transcript check. Gemini cloud voices are opt-in per site and per chronicle and never required.
- The "AI Storyteller" approval of saved points is a deterministic rule check, not a model call.
- Nothing in the system requires a cloud service. Local models are the default everywhere.

Details and measured numbers: [docs/AI_SYSTEMS.md](docs/AI_SYSTEMS.md), [docs/TECH_STACK.md](docs/TECH_STACK.md).

## 7. Languages

- The interface is complete in English and Greek (i18next), chosen per account; a switch remounts the app and keeps the session.
- The Storyteller answers in the language the player wrote; Greek defaults to `llama-krikri-8b-instruct`.
- The chronicle so far is written in the chronicle's language and can be translated whole into the other.
- Voice: Greek text gets a Greek voice, English an English one; dice outcomes are read in the listener's language; Greek names are sounded out by English voices.
- Game terms (trait names, Disciplines, clans, Hunger) stay in English in both languages; the translator keeps them and the chronicle's names untouched.
- Slash commands, catalog descriptions, PDF reference pages and fixed death texts exist in both languages.
- Known gap: the `/ai help` body and `/ai` permission replies are English only (see [docs/ROADMAP_NEXT.md](docs/ROADMAP_NEXT.md)).

## 8. Non-functional requirements

- **Self-hosted.** Docker Compose on Linux; LM Studio and Ollama on the host; an NVIDIA GPU is strongly recommended. Stories, sheets, clips and archives stay on the operator's machine unless an admin turns on a cloud option.
- **Mobile-first.** Every screen works on a phone; the design token `--sr-tap` is 44 px and message toolbar buttons, recorder controls, chips and "Show original" are 44 px targets. Reduced motion is honoured.
- **Security.** Only nginx is reachable from the network; gunicorn binds to localhost; a strict Content-Security-Policy; rate limits per route; audit log; log-injection escaping; 16 MB request limit (8 MB for clips). See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).
- **Performance limits.** A Storyteller reply: 45 s per model, 55 s total. Chronicle writer: 40 nights and 3600 s per job, one job per chronicle. SSE: 20 streams per gunicorn worker, 4 per user. Speech: 8 CPUs, one transcription at a time, 8 waiting, Whisper unloads after 10 idle minutes. Caches: TTS 5 GB, clips 20 GB.
- **Integrity.** Dice results, markers and chat lines for rolls are server-made; clients cannot post them.
- **Data retention.** Login audit rows older than 180 days are pruned; finished chronicle job rows after 90 days; unsent clips after 24 hours; archives until an admin deletes them.
- **Fail open, fail safe.** No classifier means nothing is flagged; no speech service means phone voices; no model means a fixed 503 text, never an echoed or invented reply.
- **Quality gates.** CI runs ruff, pytest, a schema and migration check, Jest, ESLint with no warnings, and the frontend build; CodeQL and Dependabot are on.

## 9. Architecture overview

Services in `docker-compose.yml`:

| Service | What | Reachable |
|---|---|---|
| `nginx` | serves the built frontend, proxies `/api`, CSP | ports 80 and 443 (host network) |
| `backend` | Flask 3.1 on gunicorn (2 workers × 48 threads), Python 3.12 | 127.0.0.1:5000 only (host network) |
| `postgresql` | PostgreSQL 16, schema from `backend/init_postgresql_schema.sql` plus startup `ensure_*` migrations | 127.0.0.1:5432 |
| `redis` | Redis 7: rate limits, lockouts, SSE tickets, classifier cache | 127.0.0.1:6379 |
| `chromadb` | ChromaDB 1.5.9: memory and rule-book collections | 127.0.0.1:8000 |
| `monitoring` | GPU and container stats | 127.0.0.1:8001 |
| `speech` (profile `voice`) | FastAPI: TTS, transcription, transcript check, Gemini client | 127.0.0.1:5055, shared secret |
| `frontend` (profile `dev`) | Vite dev server, development only | 127.0.0.1:3000 |

On the host: LM Studio (chat models and embeddings, port 1234) and Ollama (utility model, port 11434). Data lives under `./data` (logs, vector store, voice models and cache, chronicle archives, Laya model) and in the `postgresql_data` and `redis_data` volumes.

Frontend: React 18, Vite, react-router 7, i18next, motion, an own SVG design system (`frontend/src/design`). Routes in `frontend/src/app/App.jsx`: `/login`, `/showcase`, `/showcase/design`, and behind sign-in `/chronicles` (hall), `/chronicles/new`, `/chronicles/:id` (settings), `/c/:id/:locationId` (play), `/archives`, `/profile`, `/profile/characters/new`, `/profile/:section`, `/admin/*` (admins).

Background work in the backend: the chronicle writer thread, the nightly scheduler, translation and TTS queues, re-embedding, clip and cache clean-up. They start in the first gunicorn worker after fork.

## 10. API surface overview

All under `/api`, JSON, JWT bearer auth unless noted. Rate limits per route are in [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md).

| Group | Prefix | Main routes |
|---|---|---|
| Auth | `/auth` | register, login, refresh (cookie), logout, logout-all, change-password, profile |
| Users | `/users` | me (profile, language), list and get, admin edits, stats |
| Chronicles | `/campaigns` | create, list, discover, join, get/update/delete, stats, detach, members, my-playing-character, players/:id/playing-character, world, search, context, interaction |
| Rooms | `/campaigns/:id/locations`, `/locations/:id` | list, create, get, update, delete, suggest, batch, enter, leave, dice-leniency |
| Messages | `/campaigns/:id/locations/:lid` | get (paged), post, read-state; `DELETE /messages/:id` |
| Events | `/campaigns/:id/events` | ticket, SSE stream, unread, roster |
| Dice | `/campaigns/:id/roll`, `/rouse`, `/rolls` | roll, reroll, rouse, contested, ai, history, templates |
| Characters | `/characters` | list, create, get, update, delete, sheet.pdf, assign, creation-override, downtime-requests |
| Spend requests | `/characters/:id/spend-requests`, `/campaigns/:id/spend-requests` | create, list, resolve |
| Rules catalog | `/rules/v5` | catalog, guided |
| AI | `/ai` | health, status, llm/status, llm/test, chat, slash, slash/commands, world-building, memory/:campaign |
| Chronicle so far | `/campaigns/:id/chronicle` | get, chapters, estimate, jobs, exports (.md/.pdf, minutes), edit, settings, session-marks, recap (visit, get, tts); `/chronicle-health`, `/chronicle-archives` |
| Voice | `/voice`, `/campaigns/:id/voice-*` | settings, voices, tts jobs and audio, preview, clips and stt jobs, translations, translate, health, cloud-settings |
| Rule books (admin) | `/rule-books` | status, delete |
| Admin | `/admin` | users (edit, reset-password, ban, unban, debug, memberships), characters (list, kill, revive, convert-to-npc, play-status), character-deaths, moderation-log, invites, downtime-requests, campaigns, ai-settings, ai-providers (+test), classifier/test, embeddings (+reembed), lm-studio/models, auth/unlock, auth-events, laya (labels, evaluate, report) |

Error bodies are JSON with a stable `code`; 429 carries `retry_after`; 500 never leaks exception text.

## 11. Data model overview

Main tables in `backend/init_postgresql_schema.sql` (PostgreSQL):

| Area | Tables |
|---|---|
| Accounts | `users` (role, bans, grants, `ui_language`, `token_version`, `voice_settings`), `auth_refresh_tokens`, `auth_revoked_tokens`, `auth_events` |
| Chronicles | `campaigns`, `campaign_players`, `campaign_bans`, `campaign_activity`, `campaign_location_activity` |
| Rooms | `locations`, `location_connections`, `location_reads`, `location_deletion_log`, `character_locations` |
| Characters | `characters`, `character_downtime_requests`, `character_spend_requests`, `character_moderation`, `npcs`, `npc_messages`, `relationships` |
| Chat | `messages`, `message_translations` |
| Dice | `dice_rolls`, `dice_roll_templates` |
| AI | `ai_interactions`, `ai_memory`, `ai_reply_grants`, `ai_busy_marks`, `app_settings`, `laya_labels`, `laya_eval_reports`, `ooc_violations` |
| Chronicle so far | `chronicle_chapters`, `chronicle_digests`, `chronicle_jobs`, `chronicle_archives`, `chronicle_session_marks`, `chronicle_room_visits` |
| Voice | `voice_audio`, `voice_clips` |
| Moderation | `user_moderation_log` |
| Legacy | `combat_encounters`, `combat_participants` |

Vector collections in ChromaDB: campaign, character, world, session and message memory, and `rule_books_v5`, `rule_books_classic`, `rule_books_chronicle`.

Files on disk: `data/chronicle_archive/`, `data/voice/cache`, `data/voice/models`, `data/laya/model`, `data/vector_db`, `backend/invites.json`.

## 12. Invariants worth testing

- A chronicle's `rules_edition` never changes after creation; a character's edition equals its chronicle's.
- Every chronicle has exactly one OOC lobby that cannot be deleted.
- No `dice_*` message row exists without a `dice_rolls` row behind it, and none was posted by a non-admin client.
- A non-member gets 403 on every chronicle route; a non-staff member never receives a hidden roll or a closed room.
- The player view of the chronicle so far contains no `st_*` field, no username, no message id, no closed room.
- A cloud writer or cloud role is set only by a site admin.
- Only an admin revive brings back a fallen character; `PUT is_active: true` on a fallen character is a 409.
- Plain-text cloud keys never appear in an API response or a log.

## 13. Glossary

- **Chronicle / campaign**: one game, its rooms, members and characters. "Campaign" in the API and database, "chronicle" in the interface.
- **Storyteller**: the chronicle's creator (human), or the AI Storyteller when it narrates.
- **Staff**: site admins and helpers. **Chronicle staff**: staff plus the chronicle's Storyteller.
- **Room / location**: a chat room inside a chronicle. **OOC lobby**: the out-of-character room.
- **IC / OOC**: in character / out of character.
- **Playing character**: the character a member plays in a chronicle.
- **Classic**: the oWoD Revised rules. **V5**: Vampire: The Masquerade 5th edition.
- **Hunger, Rouse check, messy critical, bestial failure**: V5 dice terms.
- **Botch, specialty, difficulty**: Classic dice terms.
- **Forge**: the character creation flow.
- **Downtime request**: a text request to change a locked sheet. **Spend request**: spending saved V5 points.
- **Ghoul / retainer**: a mortal bound to a vampire, with its own sheet under the domitor.
- **The chronicle so far**: the written story of the chat; **night**: one room and one session of it; **era**: a digest of about 10 nights.
- **Session mark**: a message marked as the end of a session.
- **Previously on…**: the recap card after 12 hours away.
- **Hidden roll**: a roll stored but shown only to chronicle staff.
- **Laya**: the local chat classifier. **Laya-words**: the transcript-check model. **Krikri**: `llama-krikri-8b-instruct`, the Greek model.
- **Role (AI)**: a named job (Storyteller EN/EL, chronicler, translator, classifier, utility) mapped to a provider and model.
- **Grant**: a one-time permission for the browser to save an AI reply as the Storyteller.

## 14. Out of scope

- Other game lines than Vampire, Werewolf and Mage (Classic) and Vampire (V5); a `custom` system uses the shared Storyteller dice without a line.
- Rulebook text in the repository; books are the operator's own and are imported outside the app.
- Editing of messages.
- Moving a character between chronicles.
- NPC lines in rooms from the `npcs` table (NPCs that speak in rooms are characters flagged `is_npc`).
- Public registration without an invite code.
- A hosted or multi-tenant service; one instance serves one group.
- Running without PostgreSQL in production (the SQLite path lacks the moderation tables).

## 15. Related documents

- [README.md](README.md): what it is, quick start, models and hardware.
- [docs/FEATURES.md](docs/FEATURES.md): feature notes by release.
- [docs/TECH_STACK.md](docs/TECH_STACK.md): versions, models, how Laya was trained.
- [docs/AI_SYSTEMS.md](docs/AI_SYSTEMS.md): providers, roles, prompts, RAG, classifier, OOC monitor.
- [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md): sessions, limits, proxy trust, who reads what.
- [docs/CHRONICLE.md](docs/CHRONICLE.md): the chronicle so far.
- [docs/VOICE.md](docs/VOICE.md): listening, speaking, translation, the speech service.
- [docs/CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md](docs/CAMPAIGN_MEMBERSHIP_AND_PLAYING_CHARACTER.md): membership rules.
- [docs/dice-old-wod.md](docs/dice-old-wod.md), [docs/dice-v5.md](docs/dice-v5.md): dice as implemented.
- [docs/CHARACTER_SHEET_BLOCKS.md](docs/CHARACTER_SHEET_BLOCKS.md): sheet data and the Forge.
- [docs/rules/CLASSIC_REVISED.md](docs/rules/CLASSIC_REVISED.md), [docs/rules/V5.md](docs/rules/V5.md): rules as implemented.
- [docs/CHANGELOG.md](docs/CHANGELOG.md), [docs/ROADMAP_NEXT.md](docs/ROADMAP_NEXT.md): history and open items.
