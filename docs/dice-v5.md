# Vampire: The Masquerade 5th Edition (V5) dice in ShadowRealms AI

**Document version:** 0.9

This document explains how the app rolls dice in campaigns with `rules_edition = v5`. Classic (Revised) campaigns are covered in [dice-old-wod.md](dice-old-wod.md).

V5 is only available for `game_system = vampire`. It's chosen when the campaign is created (`POST /api/campaigns` with `"rules_edition": "v5"`) and can't be changed afterwards.

## Where it is implemented

| Area | Location |
|------|----------|
| V5 rules (pure, rng injectable) | `backend/services/v5_dice.py`: `resolve_v5`, `roll_v5`, `willpower_reroll`, `resolve_rouse` / `rouse_check`, `parse_v5_roll_expression` |
| API wrapper and chat text | `backend/services/dice_service.py`: `roll_v5_pool`, `format_v5_roll_for_chat` |
| Routes | `backend/routes/dice.py`: `manual_roll`, `willpower_reroll`, `rouse_check_route`, `contested_roll`, `ai_roll` |
| Posting rolls to chat (marker + result line) | `backend/services/dice_chat.py`, `backend/services/dice_markers.py` |
| `/ai roll`, `/ai roll-hidden`, `/ai rouse`, `/ai explain` | `backend/services/ai_slash_commands.py` |
| Roll explanations (`/ai explain`) | `backend/services/roll_explainer.py` |
| Unit tests | `backend/tests/unit/test_v5_dice.py` |

## Rules as the app applies them

- **Pool**: roll that many d10 (1–50). `min(hunger, pool)` of them are **Hunger dice**; the rest are normal dice.
- **Success**: any die showing **6–10**. There's **no botch**, and **1s cancel nothing**.
- **Pairs of 10s**: each pair of 10s, counting normal and Hunger dice together, adds **2 extra successes**, so a pair is worth 4. Three 10s are 5 successes, four 10s are 8.
- **Difficulty**: the number of successes needed, **0–10**, default **1**. The roll **wins** when successes ≥ difficulty. The margin is successes − difficulty.
- **App ruling**: 0 successes is a **total failure** and never wins, even at difficulty 0. Difficulty 0 just means "count successes".
- **Critical win**: at least one pair of 10s, and the roll wins.
- **Messy critical**: a critical where at least one of the 10s is on a Hunger die.
- **Bestial failure**: the roll fails and any Hunger die shows a 1.
- **Willpower reroll**: after the roll, the roller may reroll **up to 3 normal dice**, once. Hunger dice can't be rerolled. It costs **1 Willpower**: when the roll has a character, the server marks **1 Superficial Willpower damage** on the sheet (`wod_meta.willpower`, not halved), in the same transaction as the reroll. If every box is already filled, one Superficial box turns Aggravated instead (core p. 126). **App ruling:** a track full of Aggravated damage has nothing left to spend, so the reroll is refused. Rolls without a character (NPC / storyteller) cost nothing.
- **Rouse check**: roll one die. On **6+**, Hunger doesn't change; otherwise Hunger goes up by 1, to a maximum of 5. A failed Rouse at Hunger 5 sets `at_max_hunger`, meaning the ST should call for a hunger frenzy test.
- **Room leniency**: see below. V5 rooms don't use the Classic floor.

## API

### `POST /api/campaigns/:id/roll`

```json
{ "pool_size": 6, "difficulty": 3, "hunger": 2,
  "character_id": 12, "location_id": 4, "action_description": "Persuade the Prince" }
```

- `pool_expression` (`"4+2"`) can replace `pool_size`.
- `hunger` (0–5) is optional. When it's left out and `character_id` is given, the character's `wod_meta.hunger` is used, otherwise 0.
- If `hunger` is sent with a `character_id` and differs from the sheet, the roll uses the sent value and says so: `roll_result` gets `hunger_override`, `sheet_hunger` and `hunger_note` ("Hunger override: 3 (sheet 1)"), the same note is added to `chat_message`, and `modifiers` stores `hunger_override` and `sheet_hunger`.
- `specialty` and `willpower` are ignored in V5. Willpower is the reroll below.

Optional `speak_as` (`"character"`, `"player"` or `"staff"`) and `hidden` (boolean) control how the roll is posted to chat (see "Posting to chat" below).

Response: `{roll_id, rules_edition: "v5", roll_result, chat_message, server_posted, message_ids, messages}`, with `roll_result`:

| Field | Meaning |
|-------|---------|
| `results` | all dice (normal then Hunger) |
| `normal_dice`, `hunger_dice` | the two groups |
| `difficulty`, `successes`, `margin`, `critical_pairs` | |
| `outcome` | `"win"` or `"fail"` |
| `is_critical`, `is_messy_critical`, `is_bestial_failure`, `is_total_failure` | |
| `is_botch` | always `false` |
| `v5_leniency`, `roll_id`, `can_reroll` | the room's switches used for this roll (or `null`); `can_reroll` is true when there are normal dice |

The roll is stored in `dice_rolls`. `difficulty` holds the successes needed, `is_critical` holds the V5 critical, and the `modifiers` JSON holds `rules_edition`, `hunger`, `normal_dice`, `hunger_dice` and `rerolled` (plus `posted: {hidden, speak_as}` when it was posted to a room).

### `POST /api/campaigns/:id/roll/:roll_id/reroll`

```json
{ "indices": [0, 2], "location_id": 4 }
```

`indices` are positions in `normal_dice` (0-based, 1–3 of them, no repeats). Only the user who made the roll can reroll it, and only once: a second try returns **409**. Only V5 `manual` rolls can be rerolled. The stored row is updated, and the response has the same shape as a roll, plus `rerolled: true`, `rerolled_indices` and `rerolled_from`. With `location_id` (it must be the room of the original roll, else **400**) the reroll is posted to chat like a roll; `speak_as` and `hidden` default to what the original roll was posted with.

Willpower cost (`v5_dice.spend_willpower`): when the roll has a `character_id`, the character's track is read from `wod_meta.willpower` `{max, superficial, aggravated}`. If the sheet has no usable track, `max` is Composure + Resolve with no damage, and the new track is saved to `wod_meta.willpower`. The response adds `willpower_spent` (bool), `willpower_before` and `willpower_after` (the tracks, or `null` without a character), and `roll_result.willpower_cost` (`"superficial"`, or `"aggravated"` when a full track turned a box). The chat line says `· Willpower −1`. Errors: **409** `No Willpower left…` when the track is full of Aggravated damage (the body also has `willpower`), and **409** when the character has neither a Willpower track nor Composure and Resolve. Nothing is changed in either case.

### `POST /api/campaigns/:id/rouse`

```json
{ "character_id": 12, "location_id": 4 }
{ "hunger": 3, "location_id": 4, "speak_as": "player" }
```

With `character_id` (it must be the caller's own character, or any character in the campaign for a site admin), Hunger is read from the sheet and the new value is written back to `wod_meta.hunger`; a `hunger` in the body is ignored. Without one (for example a storyteller rousing for an NPC, or a player not speaking as their character), the optional `hunger` (an integer 0–5, default 0; booleans and fractions are refused with **400**) is the Hunger before the check, and nothing is saved. Response: `{die, success, hunger_before, hunger_after, at_max_hunger, roll_id, chat_message, server_posted, message_ids, messages}`. The check is also logged in `dice_rolls` with `roll_type = 'rouse'`, and its line is posted to the room (always; `location_id` is required here). `speak_as` defaults to `character` with a `character_id`, else `player`.

### Posting to chat

Since v0.9 phase 2 the dice API posts its own results. When `/roll`, `/roll/:id/reroll` or `/rouse` gets a `location_id`, the server saves, in the same transaction as the `dice_rolls` row (`backend/services/dice_chat.py`):

1. the animation marker (not for Rouse checks): role `assistant`, `message_type` `system`, `ai_message_kind` `dice_animation:<animation_id>` (`dice_animation_hidden:` with `hidden: true`), content = the marker JSON built by `backend/services/dice_markers.py` (same fields as `frontend/src/dice/diceMarker.js`, plus `roll_id` and `roll_kind` `manual` / `reroll`; `duration_ms` 3000, `started_at_ms` = server time);
2. the result line: role `user`, `message_type` `action`, attributed to the roller, `speaker_mode` from `speak_as` (`staff` only for admins, helpers and the campaign's storyteller, else **403**; `character` uses `character_id` or the playing character, and falls back to `player` without one), `ai_message_kind` `dice_roll[_hidden]:<animation_id>`, or `dice_rouse:<roll_id>` for a Rouse check.

Before rolling, the room must be active and in the campaign (**400**), open or the caller allowed into closed rooms (**403** `location_closed`), and the caller not banned in the campaign (**403**). The response then has `server_posted: true`, `message_ids` (marker first, then the line) and `messages` (the saved rows in the `GET /campaigns/:id/locations/:lid` shape), so the client appends them instead of posting anything. Without `location_id` nothing is posted (`server_posted: false`, `message_ids: []`).

`POST /campaigns/:id/locations/:lid` refuses any `ai_message_kind` starting with `dice_animation`, `dice_roll` or `dice_rouse` from everyone except site admins (**403**), so players can't post fake dice cards. Admin-posted markers (the admin-only `/ai roll` flow) are checked against the marker key whitelist and their timing is clamped: `duration_ms` at most 8000, `started_at_ms` within ±60 s of the server clock. Hidden rolls keep their visibility rules: `dice_*_hidden` rows are returned only to admins, helpers and the campaign's storyteller.

### Contested and AI rolls

`POST /roll/contested` in a V5 campaign rolls both sides (optional `attacker_hunger` and `defender_hunger`, 0–5). The attacker is the acting character and wins ties (core p. 123): the attacker wins when its successes are **≥** the defender's, so there is never a `"tie"` winner in V5 (0 vs 0 also goes to the attacker, margin 0). Each side's flags then come from the contest, not from a difficulty: the winning side is `outcome: "win"`, `is_critical` only when it has a pair of 10s, `is_messy_critical` when one of those 10s is a Hunger die; the losing side is `outcome: "fail"`, never critical, and `is_bestial_failure` when any of its Hunger dice shows a 1. Each side also gets `contest_won`, `opponent_successes` and `margin` (successes − opponent's). The stored rows keep `difficulty = 0`, `is_critical` from the contest, and these flags plus `winner` in `modifiers`. `POST /roll/ai` maps the AI's classic target number to successes needed as `max(1, min(5, TN − 4))`, so TN 6 becomes 2, and rolls with Hunger 0.

Calling `reroll` or `rouse` in a classic campaign returns **400**.

Input types are checked on every dice route and bad ones get **400**, not 500: the body must be a JSON object; integer fields refuse booleans and fractions (`"3"` and `3.0` are accepted); `pool_expression`, `action_description` and `description` must be strings; `specialty` / `willpower` must be JSON booleans (the string `"false"` is refused); reroll `indices` must be JSON integers (no booleans, floats or strings).

## Pools from the character sheet (Storyteller roll requests)

The AI Storyteller doesn't count dice itself. It asks for a roll with a tag such as `[[roll: Dexterity + Stealth, difficulty 3]]`, and `/api/ai/chat` computes the pool from the requesting player's sheet:

- **Pool** = Attribute + Skill, or Attribute + Discipline (`wod_meta.disciplines[].level`), or Attribute + Attribute. Two or more traits need an Attribute among them. One trait alone is allowed (a Willpower or Humanity roll).
- **Specialty**: +1 die when the tag names a specialty the sheet has for that Skill (`skills.specialties[{skill, name}]`, predator specialty included). Only one per roll.
- **Hunger dice** = current `wod_meta.hunger`, at most the pool size (Hunger 2 on a 1-die pool → 1 Hunger die). They're part of the pool, not extra dice.
- **Impairment** −2: a full Health track (`wod_meta.health`, superficial + aggravated ≥ max) on Physical pools, a full Willpower track on Social and Mental pools (the Skill's group decides, else the Attribute's), more Stains than free Humanity boxes on every pool. The pool never drops below 1 die.
- **Tracker rolls**: Willpower uses the undamaged boxes (max − superficial − aggravated), Humanity uses the rating (it is not a tracker pool in V5, p. 118; Stains only matter for Remorse), and neither gets Hunger dice.
- **Difficulty** from the tag, clamped to 1–10; none given → none filled in.

The reply is saved with a canonical tag, e.g. `[[roll: Dexterity + Stealth | 4 dice | 2 hunger | difficulty 3]]`, and the response carries the same data as `roll_requests`. In the chat the requester gets a **Roll** chip that opens the roll dialog pre-filled (pool, difficulty, reason); Hunger in the dialog still follows the sheet, so a Rouse check made in between is respected. Other players see the chip as text.

Code: `backend/services/dice_pools.py` (pools and tags), `backend/routes/ai.py` (`resolve_roll_tags`, prompt block), `frontend/src/features/dice/rollRequests.js` and `RollRequestChips.jsx` (chips, dialog pre-fill), tests in `backend/tests/unit/test_dice_pools.py` and `frontend/src/features/dice/__tests__/rollRequests.test.jsx`. The AI side is described in [AI_SYSTEMS.md](AI_SYSTEMS.md) → "Dice pools from the character sheet".

## Room leniency (`/ai dice-diff` in a V5 chronicle)

A V5 room can have three switches, stored in `locations.dice_leniency_v5` (JSON, `NULL` = all off). The Classic floor (`dice_leniency_floor`) is ignored in V5 rooms.

- **no_bestial**: Hunger dice never show 1, so a roll can't be a bestial failure.
- **no_messy**: Hunger dice never show 10, so no messy critical from Hunger tens. Normal 10s still make criticals.
- **min_successes** (0–3): at least that many dice show 6+, never more than the pool. After the roll, only the missing number of failing dice is re-drawn, each to a random 6–10 (a Hunger die 6–9 with no_messy). Normal dice are picked first, at random among the failing ones; Hunger dice only when no failing normal die is left. A Hunger 1 can therefore still be there, so min_successes alone doesn't stop bestial failures.

Every die stays uniformly random over the faces it may show. Normal dice keep their 1s (they don't matter in V5). The switches apply to Roll dice in the sidebar and `/ai roll`. **Willpower rerolls** are plain d10s (they only touch normal dice, and min_successes is for the first roll). **Rouse checks** are always one plain d10 against 6. Contested and AI rolls don't use room leniency (as before).

Commands (campaign owner or site admin, from inside the room): `/ai dice-diff` shows the switches, `/ai dice-diff no-bestial on|off`, `/ai dice-diff no-messy on|off`, `/ai dice-diff successes <0-3>`, `/ai dice-diff restore` (clears all, the Classic floor too). A number (`/ai dice-diff 7`) is refused in a V5 room with a hint. Site admins can set the same in **Room dice rules**, or with `PUT /api/campaigns/:id/locations/:loc/dice-leniency` and `{"dice_leniency_v5": {"no_bestial": true, "no_messy": false, "min_successes": 1}}` (missing keys are off, `null` clears; anything else, or a `dice_leniency_floor`, is a **400**).

The roll's chat line and `/ai roll` output say which switches were on.

## Explaining a roll (`/ai explain`)

Any member of the chronicle can reply to a dice card with `/ai explain` (also `/ai explain this roll`, or `/ai εξήγησε` in Greek). Without a reply it explains the newest roll in the room that the requester can see; hidden rolls only for admins, helpers and the chronicle's owner, as in the chat. The answer is posted as a Storyteller line in the room:

- the dice, with the Hunger dice set apart, the pool and the difficulty;
- the counting step by step: 6+ is a success (core pp. 118–121), each pair of 10s adds 2 (pp. 120–121), successes against difficulty and the margin (p. 121);
- the result and what it means in play: win, critical win, messy critical (p. 207), failure (win at a cost, p. 121), total failure (p. 122), bestial failure (p. 207: the Beast acts, typically a Compulsion, pp. 208–211);
- a Willpower reroll (p. 122) shows the first roll, which dice changed and the cost; room leniency and a Hunger override are named.

The numbers come from the stored roll (`dice_rolls` and the card's marker) and are re-counted with `resolve_v5`. If the re-count disagrees with what was stored, the answer says so. A Rouse check is explained too. After that, when an LLM is up, the Storyteller adds 2–3 sentences in the requester's language (Greek for `/ai εξήγησε`, a Greek line or a Greek UI) with the rule books searched as a dice question. The line is dropped if it brings a number the roll doesn't have; without an LLM only the breakdown is posted. `/ai respond` is a latency check, not the Storyteller, and says so.

When a player replies to any message and asks the Storyteller (a normal line or `/chat`), the quoted message goes into the Storyteller's prompt: its author, kind and text, or for a dice card the same roll summary (`backend/services/reply_context.py`).

## `/ai roll` syntax (V5 campaigns)

`pool[@difficulty][h<hunger>]`:

| Input | Pool | Difficulty | Hunger |
|-------|------|------------|--------|
| `6` | 6 | 1 | 0 |
| `6@3` | 6 | 3 | 0 |
| `6h2` | 6 | 1 | 2 |
| `6@3h2` | 6 | 3 | 2 |
| `4+2@2 h1` | 6 | 2 | 1 |

`h2@3` (Hunger first) is accepted too. `/ai rouse [hunger]` makes a Rouse check that doesn't touch any sheet. Both are admin only, like every `/ai` roll command. In a classic campaign, `/ai roll` uses the classic syntax and `/ai rouse` is refused.

The printed rulebook and the Storyteller have the final word at the table.
