# Character creation — Classic World of Darkness (reference)

This document summarizes **public, high-level** structure of **old / classic World of Darkness** character creation (late 1990s–2000s **Revised** era: *Vampire: The Masquerade Revised*, *Werewolf: The Apocalypse Revised*, *Mage: The Ascension Revised*). It is **not** a substitute for the official books or your Storyteller’s house rules. Terminology and dot allocations vary slightly by edition and chronicle.

ShadowRealms supports two rules editions per chronicle, chosen when the chronicle is created: **Classic (Revised)** for Vampire, Werewolf and Mage, covered here, and **V5** for Vampire: The Masquerade only. For V5 creation see [rules/V5.md](rules/V5.md) §4; the exact numbers the app uses for Classic are in [rules/CLASSIC_REVISED.md](rules/CLASSIC_REVISED.md). How the forge stores each block is in [CHARACTER_SHEET_BLOCKS.md](CHARACTER_SHEET_BLOCKS.md).

## Legal / practical note

- **Official mechanics** (exact dot pools, clan banes, rank costs, etc.) are **copyrighted**. Players and developers should **own or license** the core books (PDF/print) or use publisher-approved reference material.
- ShadowRealms stores structured data in `characters.wod_meta`, `attributes`, `skills`, and related fields; the **wizard** in the app encodes a **baseline** sheet spine so play can start, then the Storyteller adjusts details in-world or via admin tools.

## Shared spine (all three lines)

1. **Concept** — Short hook (e.g. “burned-out forensic tech”).
2. **Attributes** — Three categories: **Physical**, **Social**, **Mental**, each with three traits.
   - **Physical:** Strength, Dexterity, Stamina  
   - **Social:** Charisma, Manipulation, Appearance (some tables use related social traits; *Revised Vampire* uses Appearance rather than later-edition substitutes.)  
   - **Mental:** Perception, Intelligence, Wits  
3. **Priority (7 / 5 / 3)** — Every attribute starts with **1** free dot. One category then receives **7** added dots to split among its three attributes, another **5**, another **3** (category totals 10 / 8 / 6), with **no** attribute above **5**.
4. **Abilities** (Skills) — Talents, Skills, Knowledges (or merged lists depending on book). *Vampire: The Masquerade Revised* uses **13 / 9 / 5** (primary / secondary / tertiary) **Ability** dots across the three columns, with no Ability above **3** before freebies. The app uses the same budget for all three lines.
5. **Advantages** — Line-specific (Clan, Disciplines, Rage/Gnosis, Spheres, etc.).
6. **Backgrounds** — Allies, Contacts, Resources, etc. (names and costs vary).
7. **Willpower, Virtues / Morality track** — Humanity (Vampire), etc.; derived or assigned per book tables.
8. **Freebie points** — **15** points (plus up to **7** more from Flaws) to raise traits after the main allocation. The forge prices them per dot and shows the running total.

## Vampire: The Masquerade (Revised) — outline

Typical steps:

- Choose **Clan** (defines thematic angle and in-clan Discipline access).
- **Nature** and **Demeanor** (archetypes reflecting inner drive vs. outward mask).
- **Generation** (affects blood pool and max traits; neonates are often higher generation numbers such as 13th).
- Assign **virtues** (each starts at **1**, plus **7** dots to add) and derive **Humanity** (Conscience + Self-Control) and **Willpower** (Courage); alternate Paths where the Storyteller allows.
- **Disciplines** — **3** in-clan dots plus, at Storyteller discretion, limited out-of-clan choices.
- **Backgrounds** — **5** dots.
- **Blood pool** — From generation table.

Public wikis (e.g. Paradox / fan wikis) give **overview**; numbers should be verified against your corebook.

## Werewolf: The Apocalypse (Revised) — outline

Garou characters usually pick:

- **Breed** — Homid, Metis, or Lupus (influences starting **Gnosis** and upbringing).
- **Auspice** — Phase under which one was born (Ahroun, Galliard, Philodox, Ragabash, Theurge); ties to **starting Rage** and role.
- **Tribe** — Cultural and spiritual affiliation; affects **starting Willpower** in many charts and tribal gifts.
- **Rank** — Starting characters are typically **Rank 0** or **1** per chronicle.
- **Gifts** — Auspice / breed / tribe selections at appropriate ranks.

**Lupus** characters may lack mundane Abilities (Drive, Law, etc.) unless justified by the chronicle.

## Mage: The Ascension (Revised) — outline

- **Tradition** (or other appropriate template if the Storyteller allows) — Defines outlook and often **affinity Spheres**.
- **Arete** — Measures enlightenment; **starts at 1** for new PCs in standard Revised chargen.
- **Spheres** — Distribute **Sphere dots** (often **6** discretionary dots plus affinity allowances in **M20**-adjacent references; **Revised** uses its own chart — confirm with your book).
- **Quintessence / Paradox / Resonance** — Advanced tracking; usually relevant after initial creation.

> **Note:** *Mage: The Ascension 20th Anniversary Edition* (M20) uses related Sphere names but **different** detail than **Revised**. Pick one edition per chronicle and stay consistent.

## ShadowRealms implementation mapping

| Book concept        | App storage (typical)                          |
|---------------------|-----------------------------------------------|
| Concept, clan, etc. | `characters.wod_meta` (JSON)                |
| Attribute dots      | `characters.attributes` (JSON map)          |
| Abilities           | `characters.skills` (JSON: `talents`, `skills`, `knowledges` maps + optional `allocation` / `notes`) |
| Bio / history       | `characters.background` (text)               |
| Merits / flaws      | `characters.merits_flaws` (JSON)            |
| Portrait            | `characters.portrait_url`                    |
| Game line           | `characters.system_type` + `campaigns.game_system` (`vampire` / `werewolf` / `mage`) |
| Rules edition       | `characters.rules_edition` (`classic` / `v5`), copied from `campaigns.rules_edition` at creation |

Sheets default to **`sheet_locked = true`** after wizard completion. The forge has no portrait step: players set a character's **portrait** afterwards from **Profile → Characters** or from their character in a play room (the only field a locked sheet lets a player change). Other edits go through **downtime requests** (Profile → Downtime), reviewed by an admin.

## Further reading (third-party summaries)

- [Vampire: The Masquerade — Attributes (wiki)](https://vtm.paradoxwikis.com/Attributes)  
- [Werewolf: The Apocalypse — Character creation (wiki)](https://wta.paradoxwikis.com/Character_creation)  
- [Mage: The Ascension Revised (fandom overview)](https://whitewolf.fandom.com/wiki/Mage:_The_Ascension_Revised_Edition)  

Always **cross-check** any wiki against your **licensed** PDF or print corebook before running numbers at the table.

## RAG / vector DB

If you ingest **licensed** PDFs or SRD excerpts you have rights to use, tag chunks with `game_line`, `edition` (e.g. `vtm_revised`), and `topic` (`attributes`, `disciplines`, …) so retrieval stays edition-accurate. Do **not** upload pirated or unauthorized full-text books.
