# Chronicle membership: detach, join restrictions, and per-campaign playing character

**Last updated:** 2026-04-04  

This document describes data fields, API routes, and UI behavior for leaving a chronicle without deleting sheets, self-join rules after a voluntary leave, and which character is “live” for in-character play per chronicle.

## Purpose

- **Detach (leave chronicle):** Remove the user’s row from `campaign_players` for that campaign. Character rows stay in the database.
- **Join restriction:** After a detach, the account gets `users.restrict_self_join_new_chronicles = true`. While set, **self-join** to a **different** listed chronicle is blocked unless a matching **character sheet already exists** for that campaign (rejoin path). Storytellers or site staff can add the user via membership APIs; site admins can clear the flag on the user record.
- **Per-campaign playing character:** `campaign_players.active_character_id` stores which PC is used for that chronicle. IC chat and AI context resolve the effective PC via `effective_playing_character_id()` (membership field, then single-PC fallback, then legacy global `users.active_character_id` for migration).
- **Switching PCs inside one chronicle:** Players may set their playing character the **first** time (or when unchanged). Changing to **another** PC in the **same** chronicle requires the chronicle **creator**, or site **admin** / **helper**.
- **Another chronicle:** Binding and switches are evaluated **per campaign**; activity in chronicle B is not blocked by chronicle A’s binding.

## Schema (PostgreSQL / SQLite)

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
| `POST` | `/api/campaigns/<id>/members` | Creator or admin/helper | JSON `{"user_id": <n>}` — insert `campaign_players`. |
| `GET` | `/api/campaigns/` | Member | Each campaign may include `my_playing_character_id` when joined with the membership row. |
| `PUT` | `/api/users/me` | Self | Setting `active_character_id` enforces the same switch rules for that character’s campaign and syncs `campaign_players.active_character_id` when allowed. |
| `PUT` | `/api/admin/users/<id>` | Admin | May set `restrict_self_join_new_chronicles` to clear or set the flag. |

Site-wide campaign membership override remains: `POST /api/admin/users/<user_id>/campaigns/<campaign_id>/membership` (admin only).

## Frontend (SPA)

- **Campaign details:** “Chronicle membership” — **Leave chronicle** (detach). Shows `my_playing_character_id` when present.
- **Player profile:** Warning when `restrict_self_join_new_chronicles` is true.
- **Storyteller / admin / helper:** Add member by numeric user ID; set a player’s playing character (user ID + character ID). Open **enrollment** (listed / accepting / max players) remains **creator or admin** only.

## Tests

- `tests/test_campaign_membership.py` — PostgreSQL integration: detach → blocked join to unrelated chronicle; storyteller sets playing character after player switch blocked.

## Related documentation

- [SECURITY_AND_TESTING.md](SECURITY_AND_TESTING.md) — security and feature test harness.
- [DATABASE_TEST_DATA_CLEANUP.md](DATABASE_TEST_DATA_CLEANUP.md) — removing integration-test rows (`sec_*`, `@test.local`, etc.).
