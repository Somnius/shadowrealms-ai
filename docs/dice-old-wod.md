# Old World of Darkness (Storyteller) dice in ShadowRealms AI

**Document version:** 0.9 (classic rules corrected to the Revised core text; campaigns now have a `rules_edition`, see below.)

This document explains how the app rolls **classic / Revised Storyteller** **d10 pools** and where the code lives. It does not replace the rulebooks. For Vampire 5th Edition campaigns, see [dice-v5.md](dice-v5.md).

## Rules edition

Every campaign has `rules_edition`: `classic` (the default, and what every campaign created before v0.9 is) or `v5`. It's picked when the campaign is created and can't be changed later (`PUT /api/campaigns/:id` with a different value returns **409**). `v5` is only allowed for `game_system = vampire`. Characters copy the campaign's edition when they're created. Everything below applies to `classic` campaigns.

## Where it is implemented

| Area | Location |
|------|-----------|
| Classic rules (the one implementation) | `backend/services/wod_dice.py`: `resolve_classic` (pure, explicit dice), `roll_classic`, expression parsing |
| API wrapper | `backend/services/dice_service.py`: `roll_d10_pool` delegates to `wod_dice.roll_classic` |
| Roll API + access control | `backend/routes/dice.py`: `manual_roll`, `contested_roll`, `ai_roll` |
| `/ai roll` and `/ai roll-hidden` (admin only) | `backend/services/ai_slash_commands.py` |
| Player **Roll dice** UI (sidebar) | `frontend/src/SimpleApp.js` (posts to `POST /api/campaigns/:id/roll`) |
| Chat rows for dice | `backend/routes/messages.py`: `ai_message_kind` values `dice_animation`, `dice_roll`, `dice_animation_hidden`, `dice_roll_hidden` |
| Unit tests | `backend/tests/unit/test_wod_dice.py` |

Administrative `/ai` commands are restricted to site admins in `POST /api/ai/slash` (`backend/routes/ai.py`). Hidden sidebar rolls are available to admin, helper or the campaign owner. All campaign members (and site admins) can use **Roll dice**.

## Core mechanics (Vampire: The Masquerade Revised)

1. **Dice pool**: roll that many d10 (Attribute + Ability, etc.). The API accepts a number or a sum expression (`5`, `4+3`, `7-1`). Pools are capped at **50**.
2. **Difficulty**: a target number from **2 to 10**, default **6**. Each die showing **≥ difficulty** is one success. A 10 is always a success.
3. **1s cancel successes**: each 1 removes one success. Net successes never go below 0.
4. **Botch**: only when **no die succeeded** (before cancelling) **and at least one 1** showed. If successes were rolled but 1s cancelled them all, that's a plain **failure**, not a botch. Book example (Revised p. 192): 9, 1, 1, 8, 1 at difficulty 8 is a failure.
5. **Specialty**: each natural **10** counts as a success **and is rerolled**. A 10 on the reroll is rerolled again, with no limit (the code stops after 100 rerolls as a safety cap). Rerolled dice only **add** successes. **App ruling** (the book is silent): a 1 on a specialty reroll cancels nothing. 1s from the original pool cancel successes from the pool and from rerolls alike.
6. **Willpower**: declared before the roll (`willpower: true`). Adds **1 automatic success** that 1s can't cancel. A Willpower roll therefore never botches and always has at least 1 net success. The app doesn't deduct the Willpower point from the sheet.
7. **Exceptional success**: **5+ net successes**. The API field is `is_exceptional`. `is_critical` is kept for older clients and means the same thing for classic rolls. The chat text says "Exceptional success", not "critical".

## API

`POST /api/campaigns/:id/roll`

```json
{ "pool_size": 6, "difficulty": 7, "specialty": true, "willpower": false,
  "character_id": 12, "location_id": 3, "action_description": "Sneak past the guard" }
```

`pool_expression` (e.g. `"4+3"`) can replace `pool_size`. With `location_id` the server also posts the roll to that room itself (animation marker + result line, attributed to the roller with the `speak_as` voice, `hidden: true` for a hidden roll) and the response adds `server_posted: true`, `message_ids` and `messages`; clients no longer post dice rows themselves, and the messages API refuses `dice_*` kinds from non-admins. Details in `dice-v5.md` → "Posting to chat" (same for both editions). The response is `{roll_id, rules_edition: "classic", roll_result, chat_message, server_posted, message_ids[, messages]}`, where `roll_result` holds:

- `results`: the original dice
- `specialty_rerolls`: the extra dice rolled for 10s
- `successes`: net successes
- `raw_successes` and `ones_count`
- `is_botch`, `is_exceptional` and `is_critical` (same as `is_exceptional`)
- `willpower`, `specialty`, `difficulty`, `leniency_floor` and `message`

`POST /api/campaigns/:id/roll/contested` takes `attacker_pool` and `defender_pool` (1–50 each) and `difficulty`. Each side is rolled with the rules above. A botch loses automatically; otherwise the side with more successes wins. Equal successes are a tie in classic (V5 differs: the acting character wins ties, see `dice-v5.md`). `specialty` and `willpower` on `POST /roll` must be JSON booleans and integer fields refuse booleans and fractions; bad types get **400**.

## Room leniency (`/ai dice-diff`)

A room can have a leniency floor (2–10). Its dice never show 1, and with 2+ dice at least one die is ≥ the floor, so botches can't happen. Specialty rerolls are plain d10s.

## `/ai roll` syntax (classic campaigns)

`5`, `4+3`, `6-1`, `5@8` (pool@difficulty), `6 tn 7`, `6 diff 7`. The default difficulty is 6.

## Related reading (external)

- [Storyteller System (Fandom wiki)](https://whitewolf.fandom.com/wiki/Storyteller_System)
- [Botch (Fandom wiki)](https://whitewolf.fandom.com/wiki/Botch)

The printed rulebook and the Storyteller have the final word at the table.
