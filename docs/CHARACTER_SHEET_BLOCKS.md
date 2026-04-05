# Character sheet blocks (oWoD forge)

Internal map of **UI block IDs** to **storage** for the Character sheet forge. Section order follows common multi-page oWoD PDF layouts (Identity → Attributes → Abilities → Advantages → Merits/Story); use sample PDFs under `books/oWoD/` for **visual hierarchy only**. Dot totals and chronicle rules remain **Storyteller-configurable**.

## Block IDs (all lines)

| Block id            | PDF-style region        | Primary storage |
|---------------------|-------------------------|-----------------|
| `identity`          | Chronicle, name, concept | `campaign_id`, `name`, `concept` (concept also mirrored in `wod_meta.concept`) |
| `template`          | Clan / Breed·Auspice·Tribe / Tradition | `wod_meta` |
| `nature`            | Nature & Demeanor       | `wod_meta.nature`, `wod_meta.demeanor` |
| `attributes`        | Physical / Social / Mental (9 attrs) | `attributes` JSON |
| `abilities`         | Talents / Skills / Knowledges | `skills` JSON (+ optional `skills.custom`) |
| `advantages`        | Line-specific           | `wod_meta` |
| `story`             | Background, merits & flaws | `background`, `merits_flaws` JSON |

## Vampire (`vampire`)

- **identity:** chronicle, name, concept  
- **template:** clan, generation  
- **nature:** nature/demeanor archetypes  
- **attributes:** 7/5/3 pools  
- **abilities:** 11/7/4 pools  
- **advantages:** disciplines (cap at forge), backgrounds, virtues, humanity, willpower  
- **story:** narrative background; merits/flaws rows + optional notes  

## Werewolf (`werewolf`)

- **identity:** chronicle, name, concept  
- **template:** breed, auspice, tribe  
- **nature:** nature/demeanor  
- **attributes / abilities:** same structure as VtM  
- **advantages:** Rage, Gnosis (numeric), gifts / free-text (`wod_meta`)  
- **story:** background; merits/flaws  

## Mage (`mage`)

- **identity:** chronicle, name, concept  
- **template:** tradition, Arete (fixed at 1 at creation in forge)  
- **nature:** nature/demeanor  
- **attributes / abilities:** same as above  
- **advantages:** nine spheres (6 dots at creation)  
- **story:** background; merits/flaws  

## Custom fields pattern

- **Abilities:** optional `skills.custom.talents|skills|knowledges`: `[{ key, label, dots }]` for ST-approved extra rows.  
- **Merits/flaws:** `merits_flaws.entries`: `[{ name, points, note? }]`, plus optional `notes` string; legacy `{ notes: string }` still loads.  

## Out of scope

Chat, dice, campaigns admin, books/RAG — not part of this block map.
