# Guided mode questions (V5 forge)

The V5 forge starts with a choice: **Guided** or **Full forge**. Guided asks a few scenario questions, one per screen, and suggests a clan and a predator type. It also fills in the Attributes, the skill distribution and the Skills, and the player finishes the sheet in the normal forge. All of the content is in `questions.json` in this folder. The server reads that file (`GET /api/rules/v5/guided`) on the next request after it changes, so new questions need no code change and no rebuild. The set in it now is a placeholder; yours replaces it.

## The file

```json
{
  "version": 1,
  "author": "Mario",
  "thresholds": {"min_score_share": 0.3, "min_lead": 2},
  "questions": [
    {
      "id": "feeding",
      "axis": "how you feed",
      "text": {"en": "The hunger is rising. Where do you go?", "el": "Η πείνα μεγαλώνει. Πού πας;"},
      "options": [
        {
          "id": "street",
          "text": {"en": "Into the dark streets.", "el": "Στους σκοτεινούς δρόμους."},
          "weights": {
            "clan": {"Brujah": 3, "Caitiff": 1},
            "predator": {"Alleycat": 3},
            "attributes": {"physical": 1},
            "skills": {"brawl": 1, "streetwise": 1},
            "distribution": {"specialist": 1}
          }
        }
      ]
    }
  ]
}
```

- `version`: a whole number; raise it when you change the set. `author`: who wrote it.
- `questions`: 1 to 30, asked in this order. `id`: lowercase letters, digits, `_` or `-`, unique. `axis`: optional, a note for you (not shown). `text`: English and Greek, up to 300 characters each.
- `options`: 2 to 10 answers. `id` unique within the question, `text` in both languages, `weights` below. The player always gets an extra "None of these" answer, so don't write one.
- `note`: optional free text on the file, a question or an answer (JSON has no comments). Any other unknown key is reported as an error, so a typo like `weigths` can't silently drop the weights.

## Weights

Whole numbers from 1 to 5. In the placeholder set, 3 means "typical of this" and 1 means "this fits too". Leave out anything an answer says nothing about. The keys must be spelled exactly like this:

| Group | Keys |
|---|---|
| `clan` | Banu Haqim, Brujah, Caitiff, Gangrel, Hecata, Lasombra, Malkavian, Ministry, Nosferatu, Ravnos, Salubri, Thin-blood, Toreador, Tremere, Tzimisce, Ventrue |
| `predator` | Alleycat, Bagger, Blood Leech, Cleaver, Consensualist, Extortionist, Farmer, Graverobber, Grim Reaper, Montero, Osiris, Pursuer, Roadside Killer, Sandman, Scene Queen, Siren, Tithe Collector, Trapdoor |
| `attributes` | a category: `physical`, `social`, `mental`; or one Attribute: `strength`, `dexterity`, `stamina`, `charisma`, `manipulation`, `composure`, `intelligence`, `wits`, `resolve` |
| `skills` | `athletics`, `brawl`, `craft`, `drive`, `firearms`, `larceny`, `melee`, `stealth`, `survival`, `animal_ken`, `etiquette`, `insight`, `intimidation`, `leadership`, `performance`, `persuasion`, `streetwise`, `subterfuge`, `academics`, `awareness`, `finance`, `investigation`, `medicine`, `occult`, `politics`, `science`, `technology` |
| `distribution` | `jack` (Jack of all trades), `balanced`, `specialist` |

Clan and predator names are the English names of the catalog (`docs/rules/v5/catalog`).

## How the answers are scored

Code: `frontend/src/characterSheet/v5/guided.js`.

1. The weights of the chosen answers add up, key by key.
2. **Clan**: the clan with the most points among those the chronicle allows (the Storyteller's creation rules; Thin-blood only where childer are allowed). On a tie, catalog order wins.
   - *share* = its points ÷ all the clan points the answers gave, clans the chronicle doesn't allow included. Below `min_score_share`, the player is off the path.
   - *lead* = its points minus the next allowed clan's. Below `min_lead`, the player is off the path, so a tie at the top is off the path unless `min_lead` is 0.
   - Picking "None of these" twice puts the player off the path straight away.
   - Off the path, the player sees "This path doesn't fit" and goes on to the full forge, or changes their answers.
3. **Predator type**: the one with the most points among those that fit. It must be allowed in the chronicle and not forbidden to the clan (Ventrue: no Bagger, no Farmer). Tithe Collector fits only where ancillae are allowed, and never thin-bloods; the character then starts as an ancilla. Farmer doesn't fit at Blood Potency 3 or more (a chronicle of ancillae only). If no type that fits has points, the player picks one in the forge.
4. **Attributes**: the 4/3/3/3/2/2/2/2/1 spread. The category with the most points gets 4, 3, 3, the next gets 3, 2, 2 and the last gets 2, 2, 1. An Attribute's own points also count for its category, and inside a category they decide which Attribute gets the higher value. Ties go physical, social, mental, then sheet order.
5. **Skill distribution**: the one with the most points. With no points or a tie, it's balanced.
6. **Skills**: the distribution's dots go to the skills with the most points first. Skills with the same points come from the strongest Attribute category first, then in sheet order.

## Writing tips

- One idea per question (the placeholder set covers: violence or talk, night job, how you feed, what you fear, mortal ties, secrets, ambition, body or mind), with 4 to 8 answers a player could really say.
- Give each answer one main clan (3) and at most one or two that also fit (1). A clan needs to be the main clan of about three answers, or players who want it can't reach it.
- The thresholds depend on the set. For the placeholder set (16 clans, 8 questions), 0.3 and 2 send every clan's in-character answers to that clan, while about 95% of random answer sets end off the path. With 0.35, four clans could not be reached at all. Raise them to send more players to the full forge, lower them to suggest more often.
- Game terms stay English in the Greek text too (clan names, Prince, sire). Write the Greek without assuming the character's gender where you can.

## Checking a file

CI runs `backend/tests/unit/test_v5_guided.py`, which reports each problem with its question and answer id. You can run it locally from the repository root:

```sh
docker run --rm -v "$PWD":/w -w /w python:3.12-slim sh -c 'pip install -q pytest flask flask-jwt-extended && python -m pytest -q backend/tests/unit/test_v5_guided.py'
```

After that, open the forge, choose Guided, and answer once for each character you have in mind.
