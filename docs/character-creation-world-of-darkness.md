# Character creation — Classic World of Darkness (reference)

This document summarizes **public, high-level** structure of **old / classic World of Darkness** character creation (late 1990s–2000s **Revised** era: *Vampire: The Masquerade Revised*, *Werewolf: The Apocalypse Revised*, *Mage: The Ascension Revised*). It is **not** a substitute for the official books or your Storyteller’s house rules. Terminology and dot allocations vary slightly by edition and chronicle.

## Legal / practical note

- **Official mechanics** (exact dot pools, clan banes, rank costs, etc.) are **copyrighted**. Players and developers should **own or license** the core books (PDF/print) or use publisher-approved reference material.
- ShadowRealms stores structured data in `characters.wod_meta`, `attributes`, `skills`, and related fields; the **wizard** in the app encodes a **baseline** sheet spine so play can start, then the Storyteller adjusts details in-world or via admin tools.

## Shared spine (all three lines)

1. **Concept** — Short hook (e.g. “burned-out forensic tech”).
2. **Attributes** — Three categories: **Physical**, **Social**, **Mental**, each with three traits.
   - **Physical:** Strength, Dexterity, Stamina  
   - **Social:** Charisma, Manipulation, Appearance (some tables use related social traits; *Revised Vampire* uses Appearance rather than later-edition substitutes.)  
   - **Mental:** Perception, Intelligence, Wits  
3. **Priority (7 / 5 / 3)** — One category receives **7** dots to split among its three attributes, another **5**, another **3**, with each attribute usually **1–5** at creation and **no** attribute above **5** at chargen without explicit storyteller permission.
4. **Abilities** (Skills) — Talents, Skills, Knowledges (or merged lists depending on book). Revised chronicles often use **11 / 7 / 4** (primary / secondary / tertiary) **Ability** dots across the three columns, again with per-rating caps at chargen.
5. **Advantages** — Line-specific (Clan, Disciplines, Rage/Gnosis, Spheres, etc.).
6. **Backgrounds** — Allies, Contacts, Resources, etc. (names and costs vary).
7. **Willpower, Virtues / Morality track** — Humanity (Vampire), etc.; derived or assigned per book tables.
8. **Freebie points** (optional advance step) — Post-chargen tuning at Storyteller discretion.

## Vampire: The Masquerade (Revised) — outline

Typical steps:

- Choose **Clan** (defines thematic angle and in-clan Discipline access).
- **Nature** and **Demeanor** (archetypes reflecting inner drive vs. outward mask).
- **Generation** (affects blood pool and max traits; neonates are often higher generation numbers such as 13th).
- Assign **virtues** and **Humanity** (or alternate Paths where allowed).
- **Disciplines** — In-clan dots plus, at Storyteller discretion, limited out-of-clan choices.
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
| Abilities           | `characters.skills` (JSON; notes + structure) |
| Bio / history       | `characters.background` (text)               |
| Merits / flaws      | `characters.merits_flaws` (JSON)            |
| Portrait            | `characters.portrait_url`                    |
| Game line           | `characters.system_type` + `campaigns.game_system` (`vampire` / `werewolf` / `mage`) |

Sheets default to **`sheet_locked = true`** after wizard completion: players may change **portrait** from **Player Profile**; other edits go through **downtime requests** reviewed by **admin**.

## Further reading (third-party summaries)

- [Vampire: The Masquerade — Attributes (wiki)](https://vtm.paradoxwikis.com/Attributes)  
- [Werewolf: The Apocalypse — Character creation (wiki)](https://wta.paradoxwikis.com/Character_creation)  
- [Mage: The Ascension Revised (fandom overview)](https://whitewolf.fandom.com/wiki/Mage:_The_Ascension_Revised_Edition)  

Always **cross-check** any wiki against your **licensed** PDF or print corebook before running numbers at the table.

## RAG / vector DB

If you ingest **licensed** PDFs or SRD excerpts you have rights to use, tag chunks with `game_line`, `edition` (e.g. `vtm_revised`), and `topic` (`attributes`, `disciplines`, …) so retrieval stays edition-accurate. Do **not** upload pirated or unauthorized full-text books.
