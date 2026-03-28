# World of Darkness — location & scene naming (for AI suggestions)

**Purpose:** Give the location-suggestion LLM mature, system-appropriate vocabulary.  
**Edit freely:** This file is the canonical text for prompts; you can sync copies into RAG / Chroma later for retrieval-augmented generation.

**Disclaimer:** Paraphrases themes from published *World of Darkness* games. Final tone is always your table’s choice.

---

## How to use (for implementers)

- Pass the **relevant section** (by `game_system` on the campaign) into the system or user prompt alongside the campaign name and setting blurb.
- Prefer **proper nouns + functional labels**: who controls the space, what happens there, mood (decay, hunger, sacred, sterile).
- Avoid pure D&D defaults (“tavern”, “dungeon” as generic) unless the table is deliberately mash-up; WoD games favor **urban decay, institutions, intimacy, danger, secrecy**.

---

## Vampire: The Masquerade (Kindred chronicles)

**Tone:** Gothic-punk, eternal night, politics, hunger, the **Masquerade** (secrecy from mortals).

**Core location concepts (vocabulary):**

| Concept | In-fiction role | Naming hints |
|--------|-------------------|--------------|
| **Elysium** | Neutral ground where violence is forbidden; often arts, opera, museums, old money venues | “The Orpheum Gallery”, “Margrave’s Salon”, “Obsidian Hall” |
| **Haven** | A Kindred’s secure daytime refuge | “The Sub-basement Vault”, “Penthouse with blacked glass”, “Forgotten crypt annex” |
| **Domain** | Territory / influence of a vampire (often Prince, Baron, Archbishop) | Named after **streets**, **districts**, **buildings** the Kindred claims |
| **Court / salon** | Power meetings, boons, punishment | “Midnight Court”, “Velvet Tribunal” |
| **Rack** | Hunting ground (often euphemistic in play) | Nightlife strips, hospitals, shelters — name the **place type**, not slurs |
| **Chantry** (crossover) | Rare in pure VtM — use sparingly unless table mixes Mage |

**Good name patterns:**

- **Institution + adjective:** “St. Jude’s Morgue Annex”, “Redline Terminal”
- **Irony / decay:** “The Gilded Rot”, “Last Light Lounge”
- **Elysium-flavored:** theaters, galleries, private clubs, historic hotels

**Avoid:** Cartoon “Castle Dracula” unless the chronicle is camp; overusing “blood” in every name.

---

## Werewolf: The Apocalypse (Garou)

**Tone:** Rage vs Gnosis, **Gaia** vs **Wyrm**, sacred wilds, urban decay, spiritual **Umbra** journeys.

**Core location concepts:**

| Concept | In-fiction role | Naming hints |
|--------|-------------------|--------------|
| **Caern** | Sacred place of power; thin **Gauntlet**; heart of a sept | Often **natural** + **spirit name**: “Broken Pine Caern”, “Glass Lake Sept” |
| **Bawn** | Protected territory around a caern | “The Bawn — Rustwater Grid”, “Fence-line Bawn” |
| **Sept** | Garou community tied to a caern | “Thornridge Sept”, “Ashen Howl Lodge” |
| **Umbra / Scar / Realm** | Spirit reflection of a place | “The Battered Scar”, “Glass Highway Umbral Echo” |
| **Hive / Pit** | Wyrm-tainted opposite of a healthy caern (antagonist spaces) | Use only for **Wyrm** chronicles or clear danger |

**Good name patterns:**

- **Terrain + mood:** “Saltflat Howl”, “Underbridge Warren”
- **Industrial + wound:** “Slagheart Foundry”, “Chemical God’s Trench”
- **Spirit-forward:** names that sound like **totems** or **pack stories**

**Avoid:** Pure high fantasy “elven grove” unless the chronicle leans mythic; respect that Garou stories often blend **city + wild**.

---

## Mage: The Ascension (Awakened willworkers)

**Tone:** **Consensus reality**, **Paradox**, **Technocracy** vs **Traditions**, **Nodes** of Quintessence, **Horizon** weirdness.

**Core location concepts:**

| Concept | In-fiction role | Naming hints |
|--------|-------------------|--------------|
| **Chantry** | Cabal stronghold; often at a **Node** | “Obsidian Chantry”, “Paper Lantern Chantry” |
| **Node** | Place where Quintessence pools | Labs, old stones, power plants, crossroads |
| **Sanctum / laboratory** | Personal workspace; wards | “Null-Sum Lab”, “Thirteenth Stair Sanctum” |
| **Horizon realm / pocket** | Off-Consensus pocket spaces | Dream-logic names: “The House That Counts Backward” |
| **Technocracy** | Constructs, research fronts | “Harmony Solutions Annex”, “Metro Transit Substation 7 (Black)” |

**Faction flavor (optional):**

- **Order of Hermes:** libraries, towers, Latin or archaic touches  
- **Virtual Adepts:** servers, dead malls, datacenters  
- **Verbena:** groves, stone circles, blood and season imagery (tasteful)  
- **Technocracy:** corporate sterile names, “procedures”, numbers  

**Good name patterns:**

- **Paradox-friendly metaphor:** “The Uncounted Room”, “Glass Paradox Atrium”
- **Institution + wrongness:** “Fairview Institute (East Wing)”

---

## Generic / crossover WoD (when `game_system` is vague)

Use **modern urban** + **one uncanny adjective**:

- “Marrow Street Station”, “The Paper Saint’s Confessional”, “Cold Storage No. 4”

Mix **institutions** (hospitals, universities, transit) with **small secrets** (basements, maintenance tunnels, reservation offices).

---

## JSON shape reminder (for the model)

Suggested output remains an array of objects with `name`, `type`, `description` — but **`type`** should use WoD-flavored categories where possible, e.g. `elysium`, `haven`, `domain`, `caern`, `bawn`, `chantry`, `node`, `umbra`, `custom` (not only `tavern` / `dungeon`).

---

## RAG / vector sync (optional)

To ingest: chunk by `##` headings, attach metadata `{ "doc": "location-naming-world-of-darkness", "system": "vampire" }` per section, embed into your Chroma collection used for campaign tools.
