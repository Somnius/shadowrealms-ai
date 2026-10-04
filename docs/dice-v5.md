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
| `/ai roll`, `/ai roll-hidden`, `/ai rouse` | `backend/services/ai_slash_commands.py` |
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
- **Willpower reroll**: after the roll, the roller may reroll **up to 3 normal dice**, once. Hunger dice can't be rerolled. The app doesn't mark the Willpower damage on the sheet.
- **Rouse check**: roll one die. On **6+**, Hunger doesn't change; otherwise Hunger goes up by 1, to a maximum of 5. A failed Rouse at Hunger 5 sets `at_max_hunger`, meaning the ST should call for a hunger frenzy test.
- **Room leniency** (`/ai dice-diff`): no die shows 1, and with 2+ dice at least one die is ≥ the floor. Bestial failures therefore can't happen. Reroll dice are 2–10.

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

Response: `{roll_id, rules_edition: "v5", roll_result, chat_message}`, with `roll_result`:

| Field | Meaning |
|-------|---------|
| `results` | all dice (normal then Hunger) |
| `normal_dice`, `hunger_dice` | the two groups |
| `difficulty`, `successes`, `margin`, `critical_pairs` | |
| `outcome` | `"win"` or `"fail"` |
| `is_critical`, `is_messy_critical`, `is_bestial_failure`, `is_total_failure` | |
| `is_botch` | always `false` |
| `leniency_floor`, `roll_id`, `can_reroll` | `can_reroll` is true when there are normal dice |

The roll is stored in `dice_rolls`. `difficulty` holds the successes needed, `is_critical` holds the V5 critical, and the `modifiers` JSON holds `rules_edition`, `hunger`, `normal_dice`, `hunger_dice` and `rerolled`.

### `POST /api/campaigns/:id/roll/:roll_id/reroll`

```json
{ "indices": [0, 2] }
```

`indices` are positions in `normal_dice` (0-based, 1–3 of them, no repeats). Only the user who made the roll can reroll it, and only once: a second try returns **409**. Only V5 `manual` rolls can be rerolled. The stored row is updated, and the response has the same shape as a roll, plus `rerolled: true`, `rerolled_indices` and `rerolled_from`.

### `POST /api/campaigns/:id/rouse`

```json
{ "character_id": 12, "location_id": 4 }
{ "hunger": 3, "location_id": 4 }
```

With `character_id` (it must be the caller's own character, or any character in the campaign for a site admin), Hunger is read from the sheet and the new value is written back to `wod_meta.hunger`; a `hunger` in the body is ignored. Without one (for example a storyteller rousing for an NPC, or a player not speaking as their character), the optional `hunger` (an integer 0–5, default 0; booleans and fractions are refused with **400**) is the Hunger before the check, and nothing is saved. Response: `{die, success, hunger_before, hunger_after, at_max_hunger, roll_id, chat_message}`. The check is also logged in `dice_rolls` with `roll_type = 'rouse'`.

### Contested and AI rolls

`POST /roll/contested` in a V5 campaign rolls both sides (optional `attacker_hunger` and `defender_hunger`, 0–5). The attacker is the acting character and wins ties (core p. 123): the attacker wins when its successes are **≥** the defender's, so there is never a `"tie"` winner in V5 (0 vs 0 also goes to the attacker, margin 0). Each side's flags then come from the contest, not from a difficulty: the winning side is `outcome: "win"`, `is_critical` only when it has a pair of 10s, `is_messy_critical` when one of those 10s is a Hunger die; the losing side is `outcome: "fail"`, never critical, and `is_bestial_failure` when any of its Hunger dice shows a 1. Each side also gets `contest_won`, `opponent_successes` and `margin` (successes − opponent's). The stored rows keep `difficulty = 0`, `is_critical` from the contest, and these flags plus `winner` in `modifiers`. `POST /roll/ai` maps the AI's classic target number to successes needed as `max(1, min(5, TN − 4))`, so TN 6 becomes 2, and rolls with Hunger 0.

Calling `reroll` or `rouse` in a classic campaign returns **400**.

Input types are checked on every dice route and bad ones get **400**, not 500: the body must be a JSON object; integer fields refuse booleans and fractions (`"3"` and `3.0` are accepted); `pool_expression`, `action_description` and `description` must be strings; `specialty` / `willpower` must be JSON booleans (the string `"false"` is refused); reroll `indices` must be JSON integers (no booleans, floats or strings).

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
