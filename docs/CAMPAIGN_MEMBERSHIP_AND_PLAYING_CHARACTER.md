# Chronicle membership: detach, join restrictions, and per-campaign playing character

**Last updated:** 2026-10-05 (unreleased: characters without a chronicle)  

This document describes data fields, API routes, and UI behavior for leaving a chronicle without deleting sheets, self-join rules after a voluntary leave, and which character is “live” for in-character play per chronicle.

## Purpose

- **Detach (leave chronicle):** Remove the user’s row from `campaign_players` for that campaign. Character rows stay in the database.
- **Join restriction:** After a detach, the account gets `users.restrict_self_join_new_chronicles = true`. While set, **self-join** to a **different** listed chronicle is blocked unless a matching **character sheet already exists** for that campaign (rejoin path). Storytellers or site staff can add the user via membership APIs; site admins can clear the flag on the user record.
- **Per-campaign playing character:** `campaign_players.active_character_id` stores which PC is used for that chronicle. IC chat and AI context resolve the effective PC via `effective_playing_character_id()` in `backend/services/playing_character.py`: the membership field, else the player's only active PC in that chronicle, else the legacy global `users.active_character_id` if it belongs to that chronicle. There is no global "active character" in the v0.9 interface; the global field is kept only so older data keeps working.
- **Switching PCs inside one chronicle:** Players may set their playing character the **first** time (or when unchanged). Changing to **another** PC in the **same** chronicle requires the chronicle **creator**, or site **admin** / **helper**.
- **Another chronicle:** Binding and switches are evaluated **per campaign**; activity in chronicle B is not blocked by chronicle A’s binding.
- **Characters without a chronicle:** `characters.campaign_id` may be `NULL` (e.g. a sheet imported for a new player who isn't in a chronicle yet). The owner and admins/helpers see it in `GET /api/characters/` and `GET /api/characters/<id>` with `campaign_id: null` and no `campaign_name`; the character's own `rules_edition` column (and `wod_meta.edition` on V5 sheets) gives its edition. It can't be played, and downtime requests for it are refused (`400`, `character_has_no_chronicle`) until it is brought into a chronicle. It doesn't count as "a locked character in another chronicle" for the one-locked-character rule.

## Schema (PostgreSQL)

| Location | Column | Meaning |
|----------|--------|--------|
| `users` | `restrict_self_join_new_chronicles` | After voluntary detach; gates discover/join to new chronicles. |
| `campaign_players` | `active_character_id` | Optional FK to `characters.id`: live PC for this membership. |

Migrations run at app startup via `database.migrate_db()` (`ensure_*` helpers).

## HTTP API (authenticated)

| Method | Path | Who | Notes |
|--------|------|-----|--------|
| `POST` | `/api/campaigns/<id>/detach` | Member; or storyteller/staff with body | Body optional: `{"user_id": <n>}` to remove another member (creator/admin/helper). Sets restrict flag on the **removed** user; clears global `active_character_id` if it pointed at a PC in that campaign. |
| `POST` | `/api/campaigns/<id>/join` | Player | If `restrict_self_join_new_chronicles` and no active character row for this `campaign_id`, **403** with `error_code: join_requires_storyteller_approval`. |
| `PUT` | `/api/campaigns/<id>/my-playing-character` | Member | JSON `{"character_id": <n>}`. First bind allowed; change to a different PC in the same chronicle → **403** (`playing_character_switch_requires_storyteller`). |
| `PUT` | `/api/campaigns/<id>/players/<user_id>/playing-character` | Creator or admin/helper | JSON `{"character_id": <n> \| null}`. |
| `POST` | `/api/campaigns/<id>/members` | Creator or admin/helper | JSON `{"user_id": <n>}` or `{"username": "<name>"}` (case-insensitive) — insert `campaign_players`. The username is only looked up after the permission check. |
| `POST` | `/api/characters/<id>/assign` | Character owner; admin/helper | JSON `{"campaign_id": <n>}`. Brings a character **without a chronicle** into one. The owner must be the chronicle's creator or in `campaign_players`, and the chronicle active (else **404**). Refused with **400** when the character already has a chronicle (`character_already_in_chronicle`; moving between chronicles isn't supported), the game line differs (`game_line_mismatch`) or the rules edition differs (`rules_edition_mismatch`: a V5 sheet only goes into a V5 chronicle, classic into classic); **409** when the name is taken in that chronicle or the owner is a player without `allow_multi_campaign_play` who already has an active locked character in another chronicle (`single_locked_pc_conflict`). Not the owner → **403**. On success it sets `campaign_id` and, like creating a character there, `campaign_players.active_character_id` if the owner has none in that chronicle. Default per-user rate limit. |
| `GET` | `/api/campaigns/` | Member | Each campaign may include `my_playing_character_id` when joined with the membership row. |
| `PUT` | `/api/users/me` | Self | Legacy: setting the global `active_character_id` enforces the same switch rules for that character’s campaign and syncs `campaign_players.active_character_id` when allowed. The v0.9 frontend doesn't use it. |
| `PUT` | `/api/admin/users/<id>` | Admin | May set `restrict_self_join_new_chronicles` to clear or set the flag. |

Site-wide campaign membership override remains: `POST /api/admin/users/<user_id>/campaigns/<campaign_id>/membership` (admin only).

## Frontend (v0.9)

- **Chronicle settings page** (`/chronicles/:id`, `frontend/src/features/chronicle/ChronicleSettingsPage.jsx`): shows your playing character for that chronicle and has **Leave chronicle** (detach; the dialog explains that the sheet is kept and that joining a different chronicle later needs approval). The **Members** panel lets the creator or staff add a member by **username** and set a player's playing character.
- **Play view** (`/c/:id/:locationId`): the character you play is the chronicle's playing character (`my_playing_character_id` from `GET /api/campaigns/`), or your only active character there. The composer's **Speaking as** menu switches between that character (in character), yourself (out of character) and, for staff, the Storyteller voice. It changes the voice of a message, not the playing character.
- **Chat messages:** members delete their own messages; the chronicle's creator (Storyteller) and site admins delete any message, including dice rolls and Storyteller (AI) lines, which players can't delete. Helpers follow the player rule here. See [FEATURES.md](FEATURES.md#chat-message-actions-and-older-history).
- **Profile → Characters** (`frontend/src/features/profile/ProfilePage.jsx`, `BringIntoChronicle.jsx`): a character without a chronicle shows a **No chronicle yet** badge, keeps the sheet and portrait actions, and has **Bring into a chronicle**, which lists only your chronicles with the same rules edition and game line and calls the assign endpoint. The Downtime tab lists only characters that are in a chronicle.
- **Play view, no character yet:** the "Your character" card offers your characters without a chronicle that fit this chronicle ("Bring … here") next to **Create character**. The chronicle hall cards only offer **Create character**.
- Open **enrollment** (listed / accepting / max players) remains **creator or admin** only.

## Tests

- `tests/test_campaign_membership.py` — PostgreSQL integration: detach → blocked join to unrelated chronicle; storyteller sets playing character after player switch blocked.

- `backend/tests/unit/test_unassigned_characters.py` — list/get of characters without a chronicle and the assign rules (SQLite, no server).
- `frontend/src/features/profile/__tests__/unassignedCharacters.test.jsx` — badge, bring-in dialog, play panel offer.

## Related documentation

- [SECURITY_AND_TESTING.md](SECURITY_AND_TESTING.md) — security and feature test harness.
- [DATABASE_TEST_DATA_CLEANUP.md](DATABASE_TEST_DATA_CLEANUP.md) — removing integration-test rows (`sec_*`, `@test.local`, etc.).
