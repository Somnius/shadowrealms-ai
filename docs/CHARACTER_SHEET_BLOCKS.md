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

Code: `frontend/src/components/characterCreation/V5CharacterCreationWizard.js` (the shell) with one component per step in `components/characterCreation/v5/` and the state in `v5/useV5ForgeState.js`; rules in `frontend/src/characterSheet/v5/validation.js` (`buildV5Payload`). Section ids: `V5_SECTION_IDS` in `characterSheet/v5/constants.js`. The blocks follow the corebook's creation order (p. 136):

| Block | Contents | Primary storage |
|-------|----------|-----------------|
| `identity` | Chronicle, name, concept, ambition, desire | `name`, `campaign_id`, `wod_meta` |
| `clan` | Clan (incl. Caitiff and Thin-blood) and sire | `wod_meta.clan`, `wod_meta.sire` |
| `attributes` | 9 Attributes, spread 4 / 3 / 3 / 3 / 2 / 2 / 2 / 2 / 1 | `attributes` JSON |
| `skills` | Skill distribution (Jack of all trades, Balanced, Specialist) and specialties | `skills` JSON (`physical` / `social` / `mental`, `specialties`, `distribution`) |
| `disciplines` | Two clan Disciplines at 2 and 1 dots, one power per dot; with Blood Sorcery 1+ one Level 1 ritual (optional); a preview of a predator type | `wod_meta.disciplines`, `wod_meta.rituals` (`[{name, level, source}]`, at most 12 (`V5_RITUALS_MAX` / `RITUALS_MAX`, enough for an ancilla's free ritual + 11 bought), `level` required 1-5, `source` is `'creation'` for the free one or `'xp'` when bought with starting experience) |
| `predator` | Predator type and its specialty, Discipline dot, advantages and flaws (the flaws are extra) | `wod_meta.predator_type` (+ entries in advantages and flaws with `kind: 'predator'`) |
| `advantages` | 7 dots of Backgrounds, Merits and loresheets, at least 2 dots of Flaws of the player's own (Thin-blood: also 1-3 thin-blood Merits and as many thin-blood Flaws); from the catalog when it is installed (below) | `wod_meta.advantages`, `wod_meta.flaws` (rows below), `wod_meta.thin_blood_merits` / `thin_blood_flaws` (names), mirrored into `merits_flaws.entries` |
| `humanity` | Convictions and Touchstones, chronicle tenets; Humanity 7 (8 with the fledgling option, if the chronicle offers it) | `wod_meta.touchstones`, `wod_meta.humanity` |
| `age` | Age bracket and generation, Blood Potency | `wod_meta.age`, `wod_meta.generation`, `wod_meta.blood_potency` |
| `experience` | Neonates (15 XP) and ancillae (35 XP), optional: buy Attribute, Skill and Discipline dots one at a time, new specialties and rituals (level up to Blood Sorcery); unspent XP allowed, no overspending | XP dots folded into `attributes`, `skills` (XP specialties have `source: 'xp'`), `wod_meta.disciplines` and `wod_meta.rituals` (`source: 'xp'`); the ledger in `wod_meta.experience` (below) |
| `story` | Background text | `background` |

Guided mode (`components/characterCreation/V5ForgeEntry.jsx` and `v5/GuidedWizard.jsx`, scoring in `characterSheet/v5/guided.js`): before the blocks, the player can answer the scenario questions in `docs/rules/v5/guided/questions.json` (format in its README). The suggestion prefills `clan`, the predator type, `attributes` and `skills` (distribution and ratings) through `useV5ForgeState`'s `initial`, and sets the age to ancilla for an ancilla-only predator type. Nothing new is stored: the sheet is the same as one made in the full forge.

The chronicle's creation rules (`campaigns.creation_settings`, set by the Storyteller) limit the clans, predator types and ages offered, can cap the Flaws, turn off the Humanity 8 option and add house rules shown at the top. The sheet records the forge that made it: `wod_meta.forge = { version: 2, settings_v: 1 }`.

Advantage and Flaw rows (`wod_meta.advantages`, `wod_meta.flaws`):

```json
{ "id": "background:allies", "name": "Allies (police)", "dots": 2, "kind": "background", "note": "police" }
{ "id": "loresheet:the-bahari", "name": "The Bahari", "dots": 4, "kind": "loresheet", "levels": [1, 3] }
{ "name": "Hunted by a Lasombra", "dots": 2, "kind": "flaw", "custom": true }
{ "id": "flaw:suspect", "name": "Suspect", "dots": 1, "kind": "flaw", "source": "clan" }
{ "id": "flaw:prey-exclusion", "name": "Prey Exclusion (healthy mortals)", "dots": 1, "kind": "predator", "note": "healthy mortals" }
```

`kind` is `background`, `merit` or `loresheet` in advantages, `flaw` in flaws, and `predator` for the predator type's grants in either list (extra to the budget). With the V5 catalog (`docs/rules/v5/catalog/advantages.json`, `loresheets.json`, served by `GET /api/rules/v5/catalog`) the Advantages step offers Backgrounds, Merits, Flaws and loresheets as dropdowns, and a row stores the catalog `id`; `name` is the English catalog name with the note in brackets, `note` the note alone. The forge offers only what the clan may take at creation (Caitiff and thin-blood entries for those clans, `clans_only`, `cannot_buy_for`; no ghoul or coterie entries; Caitiff no Status), holds the dots to the printed rating (`{min, max}`, `max: null` meaning up to 5, or `{allowed}`; Allies goes to 6), takes a non-repeatable entry once (a repeatable one up to `max_instances`), checks a requirement that names a Background's dots ("Haven ••", counting a predator type's Background together with the dots bought on top of it) and the "ancilla or older" ones (Archaic, Living in the Past, core p. 180); other requirements are shown as a hint. Entries the book rules out together carry `excludes` in the catalog (thin-blood Dead Flesh / Lifelike, Mortal Frailty / Vampiric Resilience, Shunned by the Anarchs / Anarch Comrades, core p. 183) and are refused as a pair. A row whose `id` the catalog doesn't know is looked up by its name, else kept as a custom row; free-text rows typed before the catalog loaded move over the same way. `custom: true` marks a free-text row the catalog doesn't have, for the Storyteller to approve (1-5 dots, like every row without the catalog). A loresheet row lists the `levels` taken: each level is bought on its own and doesn't include the lower ones (core p. 190), so `dots` is their sum, and it counts toward the 7 Advantage dots; clan-restricted sheets are offered to that clan only. The clan's own Flaws (`creation.flaws` of the catalog clan: Caitiff start with Suspect •, core p. 107) are added with `source: "clan"` unless the player listed them already. The book doesn't say whether Suspect counts toward the 2 Flaw dots of the player's own; the app counts it (the forge says so and that the Storyteller may rule otherwise). A predator grant that stands for a whole group ("any Mythic Flaw", Osiris) asks which entry of the group, and the row keeps the group name in front with the chosen entry's id: `{ "id": "flaw:folkloric-bane", "name": "Mythic: Folkloric Bane", "kind": "predator" }`. Thin-blood Merits and Flaws are picked from the catalog but stored as names. Rows without an `id` (older sheets, or no catalog) keep working: the read-only sheet and the PDF Reference page find them by name (a trailing "(note)" ignored), and the sheet opens their description on click, loresheets with the levels taken.

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

`kind` is `attribute` / `skill` (`trait` = storage key), `discipline` (`trait` = name), `specialty` (`skill` + `trait` = name, from 0 to 1) or `ritual` (`trait` = name, from 0 to the ritual level). A first dot in Academics, Craft, Performance or Science also has `specialty` (its free specialty, which is added to `skills.specialties` without a `source`). One log entry per dot, in the order bought; `cost` is the new rating × the multiplier from V5.md §4 (XP costs). XP specialties must not repeat a specialty on the same skill (case-insensitive). Backend bounds (`character_sheet_v5.py`): `total`, `spent`, `unspent` required ints, `spent ≤ total`, `unspent = total − spent`, at most 200 log entries, each with a known `kind`, a `trait` (at most 120 characters), `skill` (a V5 skill key) on specialties, `from`/`to` 0-5 with `to > from`, `cost` 0-100, and `spent` equal to the sum of the log costs. `total` is not tied to the age grant (15 / 35): XP is also awarded in play (V5.md, 1 per session + 1 per story), so it is only capped at 10000. The read-only sheet shows "+N XP" next to XP-bought dots and "(XP)" after XP specialties.

## Out of scope

Chat, dice, chronicle administration and rule books (RAG) are not part of this block map.
