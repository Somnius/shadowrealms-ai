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

### Ghoul (`vampire`, `wod_meta.sheet_kind = 'ghoul'`)

A Classic vampire's ghoul is a Classic `characters` row (`system_type 'vampire'`, `rules_edition 'classic'`, the domitor's edition), told apart by `wod_meta.sheet_kind = 'ghoul'` like a V5 ghoul and linked the same way (`wod_meta.ghoul.domitor.character_id`, `services/retainers.py`): **no chronicle of its own** (`campaign_id NULL`), owned by the domitor's owner, it goes where its domitor goes, the Storyteller of the domitor's chronicle may read it and its PDF. Rules: [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md) §7 (Ghouls: Fatal Addiction, which Revised p. 276 points to); numbers in `classic.json` `ghoul`.

Code: the forge `frontend/src/components/characterCreation/classicGhoul/` (`ClassicGhoulForge.jsx`, state in `useClassicGhoulForgeState.js`, `BloodPoolBoxes.jsx`), opened by "Add a ghoul retainer" on a Classic vampire's sheet or Profile card (`/profile/characters/new?ghoul_of=<id>`: the page picks the forge by the domitor's edition); rules and payload in `characterSheet/classicGhoul.js` (`validateClassicGhoulSheet`, `buildClassicGhoulPayload`, `rollStartingPool`, `disciplineCap`, `domitorBackgroundDots`); the read-only sheet `components/ClassicGhoulSheetView.js` (on top of the Classic Attributes / Abilities / Background / Merits blocks of `CharacterSheetModal`); the server bounds `backend/services/classic_ghoul.py`. Section ids are `SHEET_SECTION_IDS` plus `bond` (`CLASSIC_GHOUL_SECTION_IDS`).

| Block id | Sheet region | Primary storage |
|----------|--------------|-----------------|
| `identity` | Domitor (one of the user's Classic vampires), kind (vassal / independent), name, concept, duties, ghoul since, age, apparent age, Nature, Demeanor | `name`, `wod_meta.concept/nature/demeanor`, `wod_meta.ghoul` |
| `attributes` | 1 free dot each + **6 / 4 / 3** | `attributes` |
| `abilities` | **11 / 7 / 4**, none above 3 before freebies | `skills` (as the Classic wizard: three maps, `allocation`, optional `custom`) |
| `advantages` | Potence 1 (pinned) + one dot in one other Discipline (a vassal: the domitor's or Celerity / Fortitude; an independent: any; Protean / Thaumaturgy only from a Gangrel / Tremere domitor), none above the cap for the domitor's generation (13th–8th: 1); Backgrounds 5 (the Domitor Background pre-filled from the domitor's generation, editable; no Generation, Herd, Status); Virtues 1 free each + 7, Humanity = Conscience + Self-Control, Willpower = Courage; the **Blood Pool**: max 10, 1 per turn, the starting vitae a roll of 1d10 (an independent halves it, rounding up; a vassal may reroll a 1), editable 1–10 | `wod_meta.disciplines`, `wod_meta.backgrounds`, `wod_meta.virtues`, `wod_meta.humanity`, `wod_meta.willpower`, `wod_meta.blood_pool` |
| `bond` | Blood Bond in drinks (0–3; vassal 3, independent 0 by default), a note; when it last fed on the domitor's vitae and a feeding note; the "Overdosing?" line | `wod_meta.ghoul.bond`, `wod_meta.ghoul.feeding`, `wod_meta.ghoul.overdosing` |
| `story` | Background, Merits and Flaws (free-text rows, a hint on Fatal Addiction's recommended and barred ones) | `background`, `merits_flaws` |
| `freebies` | **21** points (+ up to 7 from Flaws, 28 at most); costs Discipline 10, Attribute 5, Ability 2, Virtue 2, Willpower 1, Humanity 1, Background 1 (`computeClassicFreebies` with `GHOUL_FREEBIE_RULES`) | derived |

```jsonc
"wod_meta": {
  "sheet_kind": "ghoul", "concept": "…", "nature": "…", "demeanor": "…",
  "ghoul": {
    "kind": "vassal",                    // vassal | independent | revenant (revenant: staff edits only, `family` text)
    "domitor": { "character_id": 21, "name": "…", "clan": "Ventrue", "generation": 12 },   // copied by the server
    "duties": "…", "ghouled_since": "…", "age": 51, "apparent_age": 38,
    "bond": { "stage": 3, "note": "…" },  // drinks of the domitor's vitae, 0-3 (the third binds)
    "feeding": { "last": "…", "note": "…" },
    "overdosing": "…"
  },
  "blood_pool": { "max": 10, "current": 6, "per_turn": 1 },   // an object; a Classic vampire's `blood_pool` is a number
  "disciplines": [ { "name": "Potence", "dots": 1 }, { "name": "Dominate", "dots": 1 } ],
  "backgrounds": [ { "name": "Domitor", "dots": 1 }, … ],
  "virtues": { "conscience": 3, "self_control": 3, "courage": 4 }, "humanity": 6, "willpower": 4,
  "creation": { "rules": "classic-ghoul-v1", "checked": "bounds", "at": "…" }   // server-written
}
```

A Classic ghoul has no `clan`, `generation`, `sire`, `edition: 'v5'` or V5 keys (`hunger`, `blood_potency`, `predator_type`, `advantages`, `flaws`). **The server checks bounds only** (`sanity_check_classic_ghoul`: ranges, Potence 1 or more, no Generation / Herd / Status Background, `blood_pool.max` 1–20 and `current` ≤ `max`, Bond 0–3), as Classic sheets have no creation check: the forge holds the budgets. A refusal is 400 `classic_ghoul_bounds` with `problems` (English lines). The same bounds hold on a staff `PUT`, which keeps the stored `creation` record. `creation_override` from the domitor's Storyteller or staff is accepted on `POST` (the same permission as for V5) and only recorded (`creation.override`); `POST /<id>/creation-override` answers `not_v5`. `GET` adds `domitor.generation` (a number) to a Classic ghoul, and every vampire's `retainers` rows carry `kind` and `rules_edition` (a Classic vampire gets the Retainers block too).

**PDF.** The Classic sheet with the 1997 ghoul sheet's page 1 (`_render_classic`, ghoul branch): header "Ghoul", identity row Domitor ("Name (Clan, 12th)") / Duties / Kind (fields `ghoul.domitor`, `ghoul.duties`, `ghoul.kind`); Potence on the first Discipline line (`disc1`); the Blood Pool as one row of 10 squares (`blood.r1`, a second row only above 10) with Per turn `1` and Max `10`; in the Health column "Blood Bond" (`bond`: "3/3 drinks · note") in place of Weakness and "Overdosing?" (`overdosing`). Page 2 prints its ages and "Ghouled" in Description and a Feeding box (`poss.feeding`) in place of Feeding Grounds. Footer "Name · Ghoul of Domitor · Chronicle". No Reference pages (Classic). A Classic vampire's PDF is unchanged.

## V5: Vampire

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

The chronicle's creation rules (`campaigns.creation_settings`, set by the Storyteller) limit the books the catalog entries come from (an entry printed in several books needs one of them), the clans, predator types and ages offered, can cap the Flaws, turn off the Humanity 8 option and add house rules shown at the top. The sheet records the forge that made it: `wod_meta.forge = { version: 2, settings_v: 1 }`.

Advantage and Flaw rows (`wod_meta.advantages`, `wod_meta.flaws`):

```json
{ "id": "background:allies", "name": "Allies (police)", "dots": 2, "kind": "background", "note": "police" }
{ "id": "loresheet:the-bahari", "name": "The Bahari", "dots": 4, "kind": "loresheet", "levels": [1, 3] }
{ "name": "Hunted by a Lasombra", "dots": 2, "kind": "flaw", "custom": true }
{ "id": "flaw:suspect", "name": "Suspect", "dots": 1, "kind": "flaw", "source": "clan" }
{ "id": "flaw:prey-exclusion", "name": "Prey Exclusion (healthy mortals)", "dots": 1, "kind": "predator", "note": "healthy mortals" }
```

`kind` is `background`, `merit` or `loresheet` in advantages, `flaw` in flaws, and `predator` for the predator type's grants in either list (extra to the budget). With the V5 catalog (`docs/rules/v5/catalog/advantages.json`, `loresheets.json`, served by `GET /api/rules/v5/catalog`) the Advantages step offers Backgrounds, Merits, Flaws and loresheets as dropdowns, and a row stores the catalog `id`; `name` is the English catalog name with the note in brackets, `note` the note alone. The forge offers only what the clan may take at creation (Caitiff and thin-blood entries for those clans, `clans_only`, `cannot_buy_for`; no ghoul or coterie entries; Caitiff no Status), holds the dots to the printed rating (`{min, max}`, `max: null` meaning up to 5, or `{allowed}`; Allies goes to 6), takes a non-repeatable entry once (a repeatable one up to `max_instances`; the predator type's rows count, so a Bagger isn't offered Iron Gullet again, but Enemies and Dark Secret are repeatable, so a player's own one sits beside the predator type's), checks a requirement that names a Background's dots ("Haven ••", counting a predator type's Background together with the dots bought on top of it) and the "ancilla or older" ones (Archaic, Living in the Past, core p. 180); other requirements are shown as a hint. Entries the book rules out together carry `excludes` in the catalog (thin-blood Dead Flesh / Lifelike, Mortal Frailty / Vampiric Resilience, Shunned by the Anarchs / Anarch Comrades, core p. 183) and are refused as a pair. A row whose `id` the catalog doesn't know is looked up by its name, else kept as a custom row; free-text rows typed before the catalog loaded move over the same way. `custom: true` marks a free-text row the catalog doesn't have, for the Storyteller to approve (1-5 dots, like every row without the catalog). A loresheet row lists the `levels` taken: each level is bought on its own and doesn't include the lower ones (core p. 190), so `dots` is their sum, and it counts toward the 7 Advantage dots; clan-restricted sheets are offered to that clan only. A player may take more than one loresheet at creation (a house ruling, V5.md §4 step 12), each sheet once. The clan's own Flaws (`creation.flaws` of the catalog clan: Caitiff start with Suspect •, core p. 107) are added with `source: "clan"` unless the player listed them already. Suspect counts toward the 2 Flaw dots of the player's own, and the forge says so (a house ruling: the book doesn't say, see `docs/rules/V5.md` §4 step 11). A predator grant that stands for a whole group ("any Mythic Flaw", Osiris) asks which entry of the group, and the row keeps the group name in front with the chosen entry's id: `{ "id": "flaw:folkloric-bane", "name": "Mythic: Folkloric Bane", "kind": "predator" }`. Thin-blood Merits and Flaws are picked from the catalog but stored as names. Rows without an `id` (older sheets, or no catalog) keep working: the read-only sheet and the PDF Reference page find them by name (a trailing "(note)" ignored), and the sheet opens their description on click, loresheets with the levels taken.

The server checks a new V5 sheet against the creation rules (`backend/services/v5_chargen.py`, V5.md §4.1) and records the result in `wod_meta.creation`, which only the server writes (edits keep it): `{ validated: true, at, rules: "v2" }`; `{ validated: false, at, rules, override: { by, reason, at }, problems: [{ code, params }] }` when the Storyteller or staff approved it outside the rules; `{ validated: false, at, rules, reason }` when the rules couldn't be checked (`"catalog_missing"`: no catalog, or one without clans, Disciplines or predator types; `"catalog_error"`: reading it or the check failed), and an override record then carries the same `reason`.

**Saved points** (Forge v2 part D). Advantage dots left unspent and the free specialty of the player's choice left unused are kept: `wod_meta.saved = { advantage_dots, specialty }` (`savedAtCreation` in `validation.js`; dots up to `creation_settings.saved_points.advantage_dots_cap`, the specialty only when `allow_specialty`; bounds 0-20 and 0-1 in `character_sheet_v5.py`). The saved dots count toward the 7 (+2) Advantage dots in the server's creation check (`adv_over` in `v5_chargen.py`), so a sheet can't claim more than it left unspent; after the check `create_character` stores the server's own count (`saved_at_creation` in `services/saved_points.py`, the same rule), or the forge's number when that is lower (the server counts a predator type's skill dot as rated, the forge doesn't). The cap counts everything spent from saved points (the rows' `saved_dots`), not each spend alone. The Advantages and Skills steps say what will be saved. On the read-only sheet the "Saved points" block (`components/SavedPointsBlock.jsx`) shows them, lets the owner spend them with a live rule check (`characterSheet/v5/savedPoints.js`, the same codes as `services/saved_points.py`) and lists the character's spends. With the catalog the form offers the player's own rows (to raise), the catalog's Backgrounds and Merits open to the clan (with a note) and the loresheets open to the sheet (a level each); without it, free text. A spend is a row in `character_spend_requests` (`routes/spend_requests.py`); when it is approved (by the Storyteller, or at once by the rule check in a chronicle with `st_mode: 'ai'`):

- Advantage dots raise the player's own row with the same name ("Allies (police)"; never a predator grant), or add a row `{id?, name, dots, kind, note?}`. A loresheet item takes levels (`{kind: 'loresheet', levels: [2]}`, each level costs its rating, core p. 190) on the player's row of that loresheet or a new one, as the forge stores them (`levels`, dots = their sum). Either way the row gets `saved_dots` (how many of its dots came from saved points), `merits_flaws.entries` follows, and `saved.advantage_dots` goes down (not below 0).
- The rule check runs the rows a spend makes through the creation check's own row rules (`v5_chargen.check_advantage_rows`: the catalog rating with Allies 1-6, loresheet levels and restrictions, clan restrictions, custom rows; the same codes as at creation), plus what only a spend needs: a name the installed catalog lacks (`adv_unknown`), a row taken too often (`adv_repeat`), a prerequisite to verify (`adv_requires`), a book the chronicle leaves out. A catalog that can't be read makes every Advantage spend a house rule (`catalog_error`).
- The specialty is added to `skills.specialties` as `{skill, name, source: 'saved'}` and `saved.specialty` goes to 0.
- Only the columns a spend touches are written back; a column that doesn't hold a JSON object is refused (500), never overwritten.
- Approve runs the rule check again on the sheet as it is then; if the spend breaks the rules now, the Storyteller has to confirm it as a house rule (`confirm_house_rule: true`, else 409 `now_house_rule`).
- Reverse puts back only the touched keys (`wod_meta.advantages`, `wod_meta.saved`, `merits_flaws.entries`, or `skills.specialties` and `wod_meta.saved`) from the request's `before_state`, and only while they still hold what the approval wrote (a later spend is reversed first).

The sheet view marks saved-point dots ("+1 from saved points") and specialties ("– saved points").

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

`kind` is `attribute` / `skill` (`trait` = storage key), `discipline` (`trait` = name), `specialty` (`skill` + `trait` = name, from 0 to 1) or `ritual` (`trait` = name, from 0 to the ritual level). A first dot in Academics, Craft, Performance or Science also has `specialty` (its free specialty, which is added to `skills.specialties` without a `source`). One log entry per dot, in the order bought; `cost` is the new rating × the multiplier from V5.md §4 (XP costs). XP specialties must not repeat a specialty on the same skill (case-insensitive). Backend bounds (`character_sheet_v5.py`): `total`, `spent`, `unspent` required ints, `spent ≤ total`, `unspent = total − spent`, at most 200 log entries, each with a known `kind`, a `trait` (at most 120 characters), `skill` (a V5 skill key) on specialties, `from`/`to` 0-5 with `to > from`, `cost` 0-100, and `spent` equal to the sum of the log costs. `total` is not tied to the age grant (15 / 35) by these bounds: XP is also awarded in play (V5.md, 1 per session + 1 per story), so it is only capped at 10000. At creation the server check ties it to the age and re-prices every entry. The read-only sheet shows "+N XP" next to XP-bought dots and "(XP)" after XP specialties.

## V5: Ghoul (retainer or player ghoul)

A ghoul is a mortal kept on a vampire's Blood. Its sheet is a V5 `characters` row like a vampire's (`system_type 'vampire'`, `rules_edition 'v5'`), told apart by `wod_meta.sheet_kind = 'ghoul'` (`is_ghoul()` in `backend/services/character_sheet_v5.py`, `isGhoul()` in `frontend/src/characterSheet/v5/ghoul.js`). **A ghoul has no chronicle of its own**: `campaign_id` stays `NULL`, it belongs to its domitor's owner, it goes where its domitor goes (`POST /api/characters/<id>/assign` refuses it with `ghoul_follows_domitor`), and the Storyteller of the domitor's chronicle may read it and its PDF. It is never a playing character.

Code: the forge in `frontend/src/components/characterCreation/ghoul/` (`GhoulForge.jsx`, the state in `useGhoulForgeState.js`, one component per step; the Advantages step is the V5 `CatalogAdvantages` with the ghoul's rules through its `rules` prop), opened from a V5 vampire's sheet or Profile card ("Add a ghoul retainer": `/profile/characters/new?ghoul_of=<id>`); rules and payload in `characterSheet/v5/ghoul.js` (`validateGhoulSheet`, `buildGhoulPayload`); the read-only sheet `components/V5GhoulSheetView.js`; the server check `backend/services/v5_ghoul_chargen.py` (V5.md §7). Section ids are `V5_SECTION_IDS`, plus `bond`.

| Block | Contents | Primary storage |
|-------|----------|-----------------|
| `identity` | Domitor (one of the user's V5 vampires), name, concept, ambition, desire; template (Weak / Average / Gifted / Deadly mortal, core p. 185, or player ghoul, Players Guide p. 140) and the Retainers dots the domitor pays; age, looks, ghoul since | `name`, `wod_meta.concept`, `wod_meta.ghoul` |
| `attributes` | The template's spread (Gifted: one at 4, two at 3, two at 2, the rest at 1; player ghoul: the vampire one) | `attributes` |
| `skills` | The template's Skill counts (its key is `skills.distribution`; a player ghoul picks Jack / Balanced / Specialist); specialties: the template's own (`source: 'template'`) plus one for each rated Academics, Craft, Performance, Science | `skills` |
| `disciplines` | The ghoul power: one level-1 power of a Discipline the domitor has (the domitor's own listed first) | `wod_meta.disciplines` `[{name, level: 1, powers: [name], ghoul: true}]` |
| `advantages` | The template's Advantage and Flaw caps (no minimum; Retainers •• Average: no Advantages), a player ghoul's 7 and at least 2; catalog entries without Domain, Feeding, Herd, thin-blood, Caitiff or coterie ones; the ghoul-only Merits and Flaws are offered | `wod_meta.advantages`, `wod_meta.flaws` (the V5 rows above), mirrored into `merits_flaws.entries` |
| `bond` | Blood Bond to the domitor (Bond Strength 0-6 or not set), a second one only with the Two Masters Flaw; when it last fed on the domitor's Blood and a feeding note (a note, not a track: a V5 ghoul has no vitae, Hunger or Blood Potency) | `wod_meta.ghoul.bonds`, `wod_meta.ghoul.feeding` |
| `humanity` | Health and Willpower (Crone's Curse: one Health box less); Humanity 7 when tracked (always for a player ghoul); Convictions with Touchstones (1-3 for a player ghoul, 0-3 for a retainer) | `wod_meta.humanity`, `wod_meta.health`, `wod_meta.willpower`, `wod_meta.touchstones` |
| `story` | Background text | `background` |

```jsonc
"wod_meta": {
  "edition": "v5", "sheet_kind": "ghoul", "concept": "…", "ambition": "", "desire": "",
  "ghoul": {
    "template": "gifted",            // weak | average | gifted | deadly | player
    "retainer_dots": 3,              // 1-3 or null: the domitor's Retainers that pay for the ghoul
    "domitor": { "character_id": 17, "name": "Darius Vale", "clan": "Ventrue" },   // name and clan copied by the server
    "age": 55, "apparent_age": 53,   // 0-150 or null
    "ghouled_since": "…",            // up to 200 characters
    "bonds": [ { "character_id": 17, "name": "Darius Vale", "strength": null, "note": "…" } ],  // 1-2, strength 0-6 or null
    "feeding": { "last": "", "note": "…" }   // when it last fed on the domitor's Blood: 60 / 500 characters; `vitae` on the first sheets
  },
  "disciplines": [ { "name": "Dominate", "level": 1, "powers": ["Cloud Memory"], "ghoul": true } ],
  "humanity": 7, "stains": 0, "health": { "max": 4, … }, "willpower": { "max": 3, … },
  "advantages": [ … ], "flaws": [ … ], "touchstones": [], "chronicle_tenets": "",
  "forge": { "version": 2, "kind": "ghoul", "settings_v": 1 },
  "creation": { "validated": true, "at": "…", "rules": "ghoul-v1" }
}
```

A ghoul's sheet has no `clan`, `sire`, `generation`, `age` (the bracket), `predator_type`, `hunger`, `blood_potency`, `experience`, `saved`, `rituals`, thin-blood Merits or Flaws and no predator rows (the check refuses them: `ghoul_vampire_field`). The bounds (`character_sheet_v5.py`) hold the `wod_meta.ghoul` block to the limits above and its Disciplines to 1 dot.

**API.** `POST /api/characters/` with `wod_meta.sheet_kind: 'ghoul'` takes `campaign_id: null` (an id gives 400 `ghoul_has_no_chronicle`) and `wod_meta.ghoul.domitor.character_id` (missing: 400 `ghoul_domitor_missing`): the domitor must be the caller's vampire (staff: anyone's; the Storyteller of the domitor's chronicle: a player's there, with an override only), else 403 `ghoul_domitor_not_yours`, 404 `ghoul_domitor_not_found` or 400 `ghoul_domitor_not_vampire` (another line, a ghoul). A Classic vampire's ghoul is a Classic sheet (Classic: Ghoul above). The ghoul belongs to the domitor's owner and a player's ghoul is locked at creation; the server copies the domitor's name and clan, runs `validate_ghoul_creation` (with the domitor's chronicle settings when it has one: allowed books, Flaw cap) and records `wod_meta.creation` with `rules: 'ghoul-v1'`. A sheet that breaks the rules is refused (`creation_invalid` with the codes) unless `creation_override: {reason}` comes from the domitor's Storyteller or staff (a site admin when the domitor has no chronicle, as for any sheet without one); `POST /<id>/creation-override` does the same for a stored ghoul. The one-locked-character rule doesn't apply (no chronicle). Names are unique among the owner's characters without a chronicle. `GET /api/characters/<id>` adds `domitor: {id, name, clan, generation, campaign_id, campaign_name, exists}` to a ghoul (`exists: false` when the domitor's row is gone: the stored name still shows; `generation` is null for a V5 domitor) and `retainers: [{id, name, portrait_url, template, kind, retainer_dots, rules_edition, is_active}]` to a vampire of either edition; every row carries `sheet_kind`. A domitor's ghouls are found by owner and `wod_meta.ghoul.domitor.character_id` (`services/retainers.py`); there is no column for the link. Deleting a domitor leaves its ghouls (they show "sheet no longer exists").

**PDF.** Two ghoul pages (`_render_v5_ghoul` in `services/character_sheet_pdf.py`): template, domitor, age and looks on top; Attributes and Skills; a ghoul power box (the power at one dot, lines for level-1 powers bought later) and a Blood Bond & feeding box (fields `ghoul.domitor`, `ghoul.template`, `power.discipline`, `power.name`, `bond.regnant`, `bond.strength.1`-`6`, `bond.flaws`, `bond.note`, `feeding.last`, `feeding.note`, `bond2.*`; the feeding fields are notes with the cadence printed under them, never boxes or a pool); then Advantages & Flaws, Health and Willpower, Humanity only when tracked, Convictions, Experience, Background & Notes. No Hunger or Blood Potency. Its chronicle is the domitor's; the footer says "Ghoul of …". The Reference page starts with the Retainers Background (core p. 194).

**Background & Notes on every PDF.** A Background or Notes text too long for its box on page 2 (V5, ghoul and Classic) keeps what fits there, as a field at the box's size, and goes on over "Background & Notes (continued)" page(s) right after page 2 (fields `background.cont1`, `background.cont2`…, `notes.cont1`…), before the Reference pages; the box title says on which page. A text that fits at 7 pt or more still shrinks into the box. Up to 40 000 characters of each are printed.

## Out of scope

Chat, dice, chronicle administration and rule books (RAG) are not part of this block map.
