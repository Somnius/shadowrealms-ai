# Old World of Darkness (Storyteller) dice in ShadowRealms AI

**Document version:** 0.7.13 (aligned with app release; update when dice or admin `/ai roll` behavior changes.)

This document summarizes how **classic / Revised Storyteller**–style **d10 pools** are used in the app, where to find the implementation, and how it relates to published rules. It is not a full replacement for the rulebooks.

## Where it is implemented

| Area | Location |
|------|-----------|
| Player **Roll dice** UI (sidebar) | `frontend/src/SimpleApp.js` — modal posts to `POST /api/campaigns/:id/roll` |
| Roll API + access control | `backend/routes/dice.py` — `manual_roll` |
| Core resolution (pool loop) | `backend/services/dice_service.py` — `roll_d10_pool` |
| `/ai roll` (admin-only) expression parser | `backend/services/wod_dice.py` — `parse_roll_expression`, `roll_storyteller_pool` |

Administrative **`/ai`** commands (including `/ai roll` with `pool@diff` text syntax) are **restricted to site users with `role = admin`** in `POST /api/ai/slash` (`backend/routes/ai.py`). All campaign members may use the **Roll dice** button if they have campaign access.

## Core mechanics (Storyteller d10)

The **Storyteller System** used in **Vampire: The Masquerade**, **Werewolf: The Apocalypse**, **Mage: The Ascension**, etc. (often called **old WoD** or **oWoD**) typically uses:

1. **Dice pool** — Roll a number of **d10** determined by traits (Attribute + Ability, etc.). The UI accepts a total pool or a sum expression (`5`, `4+3`, `7-1`).
2. **Difficulty (target number)** — Usually **6–10** on a per-roll basis. Each die that shows **greater than or equal to** the difficulty counts as **one success** (before cancellations).
3. **1s** — On a **1**, the die does not succeed; in **Revised** rules, **1s cancel successes** (each 1 removes one success from the pool’s total). Net successes are typically floored at zero for display.
4. **Botch** — Definitions differ between **original** and **Revised** Storyteller. The **Revised** simplification is often stated as: a **botch** occurs when there are **no successes after applying 1s**, and the roll included **at least one 1**. The **original** edition could treat botches when **more 1s than successes** appeared (a stricter reading).  

   Community references: [Storyteller System (Fandom)](https://whitewolf.fandom.com/wiki/Storyteller_System), [Botch (Fandom)](https://whitewolf.fandom.com/wiki/Botch), [RPG.SE — botch / automatic successes](https://rpg.stackexchange.com/questions/84150/how-do-automatic-successes-in-old-world-of-darkness-deal-with-fails-and-botches).

5. **Specialty** — With an applicable **specialty**, **10** may count as **two successes** (and in some editions, **10s** “explode” — reroll; that optional rule is **not** fully modeled here unless added later). The sidebar and API expose a **Specialty** checkbox that maps to `dice_service.roll_d10_pool(..., specialty=True)`.

6. **“Five successes” style exceptional results** — The service flags **5+ net successes** as a **critical** highlight for chat formatting; table interpretation is always up to the Storyteller.

## Defaults in the UI

- **Difficulty** defaults to **6** (a common baseline in many oWoD examples; your table may prefer 7 or higher for hard tasks).
- **Pool** is entered as a **number or sum**; the server caps pools at **50** dice per roll.

## Botch display and narration

How a **botch** should read in chat (aces, dramatic text, house rules) is intentionally left flexible; the code returns structured flags (`is_botch`, `successes`, raw `results`) and a short **chat message** string. Tables can override presentation in the UI or downstream tooling in a later iteration.

## Related reading (external)

- [Storyteller System — Fandom Wiki](https://whitewolf.fandom.com/wiki/Storyteller_System)  
- [Success — Fandom Wiki](https://whitewolf.fandom.com/wiki/Success)  
- [Botch — Fandom Wiki](https://whitewolf.fandom.com/wiki/Botch)  
- [Storytelling System — Wikipedia](https://en.wikipedia.org/wiki/Storytelling_System) (successor **nWoD / Chronicles of Darkness** — different from classic oWoD in several places)

Always defer to your **printed rulebook** and **Storyteller** for the final word at the table.
