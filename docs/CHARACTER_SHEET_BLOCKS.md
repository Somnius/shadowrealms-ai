# Character sheet blocks

Internal map of the character forge's **UI blocks** to **storage**, for both rules editions. A chronicle uses one edition (`campaigns.rules_edition`: `classic` or `v5`); a character copies it at creation (`characters.rules_edition`). Section order follows common multi-page sheet layouts (Identity, Attributes, Abilities, Advantages, Story); use sample PDFs under `books/oWoD/` for visual hierarchy only.

The rules themselves (dot budgets, costs, page references) live in [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md) and [rules/V5.md](rules/V5.md), with the numbers in `docs/rules/classic.json` and `docs/rules/v5.json` (copied to `frontend/src/rules/`).

## Classic (Revised): Vampire, Werewolf, Mage

Code: `frontend/src/components/CharacterCreationWizard.js`, rules in `frontend/src/characterSheet/validation.js`. Section ids: `SHEET_SECTION_IDS` in `characterSheet/constants.js`.

| Block id | Sheet region | Primary storage |
|----------|--------------|-----------------|
| `identity` | Chronicle, name, concept | `campaign_id`, `name`, `concept` (also in `wod_meta.concept`) |
| `template` | Clan / Breed, Auspice, Tribe / Tradition | `wod_meta` |
| `nature` | Nature and Demeanor | `wod_meta.nature`, `wod_meta.demeanor` |
| `attributes` | Physical / Social / Mental (9 Attributes) | `attributes` JSON |
| `abilities` | Talents / Skills / Knowledges | `skills` JSON (+ optional `skills.custom`) |
| `advantages` | Line-specific | `wod_meta` |
| `story` | Background, merits and flaws | `background`, `merits_flaws` JSON |
| `freebies` | Freebie point summary | derived from the other blocks (not stored separately) |

The wizard stores **final** ratings. Dots beyond the creation budgets count as freebie dots.

**Budgets (all three lines):**

- **Attributes:** every Attribute starts with 1 free dot; **7 / 5 / 3** dots are added on top (category totals 10 / 8 / 6 before freebies). Nosferatu have Appearance 0, which can't be raised.
- **Abilities:** **13 / 9 / 5** added dots, no Ability above 3 before freebies.
- **Freebies:** 15 points, plus up to 7 more from Flaws. Attributes and Abilities can be raised with freebies on every line; Merits cost their points.

### Vampire (`vampire`)

- **template:** clan, generation
- **advantages:** Disciplines (3 dots), Backgrounds (5 dots), Virtues (1 free dot each + 7 = 10 in total), Humanity = Conscience + Self-Control, Willpower = Courage
- **freebies:** Disciplines, Backgrounds, Virtues, Humanity and Willpower can also be bought with freebies. Freebie Virtue dots are kept apart from the creation Virtues, so Humanity and Willpower are worked out from the creation Virtues only.

### Werewolf (`werewolf`)

- **template:** breed, auspice, tribe
- **advantages:** Rage and Gnosis (numbers, set with the Storyteller), gifts as free text (`wod_meta`)

### Mage (`mage`)

- **template:** tradition; Arete is fixed at 1 at creation
- **advantages:** the nine Spheres, exactly 6 dots at creation

### Custom fields

- **Abilities:** optional `skills.custom.talents|skills|knowledges`: `[{ key, label, dots }]` for Storyteller-approved extra rows; their dots count toward the Ability budgets.
- **Merits/flaws:** `merits_flaws.entries`: `[{ name, points, note? }]`, plus an optional `notes` string; the legacy `{ notes: string }` still loads.

## V5: Vampire only

Code: `frontend/src/components/characterCreation/V5CharacterCreationWizard.js`, rules in `frontend/src/characterSheet/v5/validation.js` (`buildV5Payload`). Section ids: `V5_SECTION_IDS` in `characterSheet/v5/constants.js`.

| Block | Contents | Primary storage |
|-------|----------|-----------------|
| `identity` | Chronicle, name, concept, sire, ambition, desire, age bracket, generation | `name`, `campaign_id`, `wod_meta` |
| `clan` | Clan (incl. Caitiff and Thin-blood) | `wod_meta.clan` |
| `attributes` | 9 Attributes, spread 4 / 3 / 3 / 3 / 2 / 2 / 2 / 2 / 1 | `attributes` JSON |
| `skills` | Skill distribution (Jack of all trades, Balanced, Specialist) and specialties | `skills` JSON (`physical` / `social` / `mental`, `specialties`, `distribution`) |
| `disciplines` | Two clan Disciplines at 2 and 1 dots, one power per dot | `wod_meta.disciplines` |
| `rituals` | With Blood Sorcery 1+: one Level 1 ritual chosen at creation (optional) | `wod_meta.rituals` (`[{name, level, source}]`, at most 10, `level` required 1-5, `source` is `'creation'` for the free one or `'xp'` when bought with starting experience) |
| `predator` | Predator type and its specialty, Discipline dot, advantages and flaws | `wod_meta.predator_type` (+ entries in advantages and flaws) |
| `advantages` | 7 dots of Merits and Backgrounds, at least 2 dots of Flaws (Thin-blood: their own merits and flaws) | `wod_meta.advantages`, `wod_meta.flaws`, mirrored into `merits_flaws.entries` |
| `experience` | Neonates (15 XP) and ancillae (35 XP), optional: buy Attribute, Skill and Discipline dots one at a time, new specialties and rituals (level up to Blood Sorcery); unspent XP allowed, no overspending | XP dots folded into `attributes`, `skills` (XP specialties have `source: 'xp'`), `wod_meta.disciplines` and `wod_meta.rituals` (`source: 'xp'`); the ledger in `wod_meta.experience` (below) |
| `humanity` | Convictions and Touchstones, chronicle tenets; Humanity 7 (8 with the fledgling option) | `wod_meta.touchstones`, `wod_meta.humanity` |
| `story` | Background text | `background` |

Derived values are stored in `wod_meta` too: `edition: "v5"`, `hunger`, `blood_potency`, `health` and `willpower` (each `{ max, superficial, aggravated }`), `stains`.

`wod_meta.experience` (only when the age gives XP):

```json
{
  "total": 15, "spent": 13, "unspent": 2,
  "log": [
    { "kind": "attribute", "trait": "resolve", "what": "Resolve", "from": 1, "to": 2, "cost": 10 },
    { "kind": "specialty", "trait": "Stocks", "skill": "finance", "what": "Finance specialty: Stocks", "from": 0, "to": 1, "cost": 3 }
  ]
}
```

`kind` is `attribute` / `skill` (`trait` = storage key), `discipline` (`trait` = name), `specialty` (`skill` + `trait` = name, from 0 to 1) or `ritual` (`trait` = name, from 0 to the ritual level). One log entry per dot, in the order bought; `cost` is the new rating × the multiplier from V5.md §4 (XP costs). Backend bounds (`character_sheet_v5.py`): `total`, `spent`, `unspent` required ints, `spent ≤ total`, `unspent = total − spent`, at most 200 log entries, `from`/`to` 0-5 with `to > from`, `cost` 0-100, and the log may not cost more than `spent`. The read-only sheet shows "+N XP" next to XP-bought dots and "(XP)" after XP specialties.

## Out of scope

Chat, dice, chronicle administration and rule books (RAG) are not part of this block map.
