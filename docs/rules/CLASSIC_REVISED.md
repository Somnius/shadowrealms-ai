# Classic rules spec: Vampire: The Masquerade Revised (oWoD)

Implementation spec for the "classic" ruleset in ShadowRealms AI. The baseline is the **VtM Revised core** (3rd ed., 2000). **V20** is used only to cross-check, and only where the Revised text extraction is unreadable; every such case is flagged. Machine-readable constants are in [`classic.json`](classic.json).

Page refs ("core p. N") are the printed Revised page numbers. "V20 p. N" means the V20 core. Everything here is paraphrased. For full wording, check the book.

Conventions:

- **MUST** = rule as written. **ST** = Storyteller (in the app, the GM or AI GM). "Optional" = the book gives it as an option.
- **AMBIGUOUS** = the text is unclear or self-contradictory, or the extraction is unreadable. The app needs a configurable choice or a documented default.

---

## 1. Dice

### 1.1 Pools (core pp. 190–191)

- The app rolls d10s. Pool = dots in one Attribute + dots in one Ability, the usual case. A pool can also be one Trait alone, such as Strength to lift or Willpower.
- **At most two Traits can be added into one pool.** If a pool uses a Trait rated 1–10 (Humanity, Willpower, or a Path), no other Trait can be added to it (core p. 190).
- Modifiers add or remove dice (wound penalties, multiple actions, Backgrounds such as Herd on hunting rolls). A pool reduced to 0 or less means the action can't be attempted (core p. 192 multiple actions; p. 140 wounds).
- Untrained Abilities (core pp. 120–126):
  - **Talent** with 0 dots: roll the Attribute alone, no penalty.
  - **Skill** with 0 dots: roll the Attribute alone at **+1 difficulty**.
  - **Knowledge** with 0 dots: **no roll at all** unless the ST explicitly allows it (e.g. common trivia).
- Wound penalties apply to action pools only. They never apply to reflexive pools: soak, most Virtue checks, or Willpower rolls to abort (core p. 140).

### 1.2 Difficulty (core pp. 190–191)

- The difficulty is a **target number from 2 to 10**. The default is **6** when no difficulty is given.
- Each die showing **≥ difficulty** is one success. **A 10 is always a success.**
- Modifiers raise or lower the difficulty. The text caps the result at 10 ("to a maximum of 10" appears in several powers). The app should clamp to [2, 10].
- Table (core p. 192): 3 easy, 4 routine, 5 straightforward, 6 standard, 7 challenging, 8 difficult, 9 extremely difficult.
- Degrees of success: 1 = marginal, 2 = moderate, 3 = complete, 4 = exceptional, 5+ = phenomenal.

### 1.3 Ones and botches (core p. 192). Implement exactly.

1. Count `raw_successes` = dice ≥ difficulty, and `ones` = dice showing 1.
2. Each 1 cancels one success: `net = raw_successes - ones`, floored at 0 for display.
3. Outcome:
   - `net ≥ 1` → **success** with `net` successes.
   - `raw_successes == 0 and ones ≥ 1` → **botch**.
   - Anything else → **failure**. That includes rolls where successes were rolled but all were cancelled by 1s, even if extra 1s are left over.
4. The book's own example (p. 192): 9, 1, 1, 8, 1 at difficulty 8 is a plain failure, not a botch, because successes were rolled.

> **Check the code against this:** at commit d5686c4, `backend/services/dice_service.py` flagged a botch when `net < 0` or (`net == 0` and any 1s). Per Revised p. 192, that is wrong whenever `raw_successes > 0`. The file is being changed on this branch, so re-check it.

- Optional "free botch" (p. 192): the first botch of the session for everyone, players and ST characters alike, is ignored.
- Damage rolls and soak rolls **cannot botch**. They only fail (core pp. 207–208).

### 1.4 Specialties (core p. 117)

- A specialty can be taken only for a Trait rated **4 or more**. Exception: the book recommends taking one early for Expression, Crafts, Performance, Academics and Science (p. 120).
- **Revised effect:** on a roll covered by the specialty, each die showing **10** counts as a success **and is rerolled**. A rerolled 10 is rerolled again, with no limit.
- **AMBIGUOUS:** the text doesn't say whether a **1** on a reroll cancels a success. Recommended default: rerolled 1s don't cancel (bonus dice only add). Make it configurable.
- **V20 differs** (V20 p. 96): a specialty 10 counts as **two successes**, with no reroll. At commit d5686c4 the app code used the V20 rule. Pick one per ruleset flag: `specialty_mode: "revised_reroll" | "v20_double"`.

### 1.5 Willpower for an automatic success (core pp. 137, 193)

- Spend 1 Willpower point to add **one automatic success**.
- Limit: **one Willpower point per turn** for this purpose.
- It must be **declared before rolling**. A botch can't be fixed after the roll by spending Willpower.
- The bought success **can't be cancelled by 1s** and isn't removed by a botch.
  - Resolution: `net = 1 + max(0, raw_successes - ones)`.
  - **AMBIGUOUS:** if the dice would have botched, the text says only that the bought success stands. Recommended default: the result is a 1-success marginal success with no botch consequences. Flag it in the roll log.
- The ST can forbid Willpower on specific rolls. Examples: degeneration (Conscience) rolls (p. 221) and Willpower rolls themselves.
- Other Willpower uses:
  - Ignore wound penalties for one turn (p. 137). Not allowed while Incapacitated or in torpor.
  - Resist an instinctive reaction for a turn.
  - Suppress a derangement for a while.
  - Control a frenzied character for one action/turn (p. 229).
  - Hold off Rötschreck for a turn (p. 229).
  - Abort to a defensive action instead of rolling Willpower (p. 208).

### 1.6 Automatic success without rolling (core p. 193)

- If the pool size is **≥ the difficulty**, the ST may grant an automatic success with no roll. It counts as **1 success** (marginal).
- Not allowed in combat or other stressful situations.
- The player may roll anyway to try for more successes.

### 1.7 Retrying (core p. 193)

- After a failure, the ST may raise the difficulty of the next attempt: +1 on the 2nd try, +2 on the 3rd, and so on.
- Not used for things that are expected to fail sometimes, like gunfire, spotting an ambush, or tailing.

### 1.8 Extended, resisted, teamwork (core pp. 194–195)

- **Simple action:** one roll, and 1 success is enough.
- **Extended action:** roll repeatedly, adding successes until the target total is reached. One roll per interval (turn, hour, night) as the ST sets.
  - A **botch** may wipe the accumulated successes and force a restart, or end the attempt entirely (ST call).
  - In the book's extended example (p. 194), a botch on the 3rd roll is played as a setback. In its debate example, a botch "eliminates all accumulated successes".
  - Default: a botch resets the total to 0 and the ST decides whether a retry is allowed.
- **Resisted action:** both sides roll. Each side's difficulty is often set by one of the opponent's Traits.
  - The winner keeps only the **margin**: own successes minus opponent's successes.
  - On a tie, nobody gets net successes (a tie means no successes for either side). Combat ambush ties are a special case (p. 208).
- **Extended + resisted:** each turn, the side with more successes adds the excess to a running tally. The first side to reach the target wins.
- **Teamwork:** each helper rolls separately and their successes are added together. Pools are **never merged**. One helper's botch can spoil the whole attempt (ST call). Teamwork doesn't help with some social tasks.

### 1.9 Multiple actions (core p. 192)

- Declare N actions. The first pool loses N dice. Each later action loses one more die, cumulatively (2nd: N+1, 3rd: N+2, and so on).
- An action whose pool drops to ≤ 0 can't be taken.
- Celerity grants extra actions with no split penalty. Those extra actions can't themselves be split.

### 1.10 Combat dice (core pp. 207–218, summary)

- Attack pools:
  - Dex + Brawl (unarmed) or Dex + Melee (armed).
  - Dex + Firearms (guns) or Dex + Athletics (thrown).
  - Default difficulty 6.
- **Each success after the first adds one die to the damage pool.**
- Damage roll: difficulty 6. Each success = 1 health level. The damage pool is never below 1 die. It can't botch (a botch just glances off).
- Soak: a reflexive roll at difficulty 6. Each success removes one level. It can't botch. (In the book's example, a 1 cancels a soak success.)
- Soak pool:

| Damage type | Mortal | Vampire |
|---|---|---|
| Bashing | Stamina | Stamina + Fortitude |
| Lethal | can't soak | Stamina + Fortitude |
| Aggravated | can't soak | **Fortitude only** |

- Armor adds to soak against bashing, lethal and aggravated from teeth/claws. It doesn't help against fire or sunlight. Armor is destroyed if one attack's damage roll equals twice its rating.
- Firearms against vampires do **bashing** unless aimed at the head (difficulty 8), which makes them lethal (p. 216).
- **Bashing damage that gets through soak against a vampire is halved, rounding down** (p. 217).
- Flank attack +1 die. Rear attack +2 dice. Blind or dark: +2 difficulty, and ranged attacks are impossible.
- Initiative, maneuvers and weapon tables: core pp. 200–215. They are out of scope for this pass and can be added when combat is implemented.

---

## 2. Character sheet (Revised)

### 2.1 Attributes (9). Rated 1–5, max by generation (see 2.8). Everyone starts with 1 dot.

- Physical: Strength, Dexterity, Stamina
- Social: Charisma, Manipulation, Appearance
- Mental: Perception, Intelligence, Wits
- **Nosferatu have Appearance 0** and can never raise it (p. 105).

### 2.2 Abilities (30). Rated 0–5, no free dots (pp. 106, 120).

- **Talents:** Alertness, Athletics, Brawl, Dodge, Empathy, Expression, Intimidation, Leadership, Streetwise, Subterfuge
- **Skills:** Animal Ken, Crafts, Drive, Etiquette, Firearms, Melee, Performance, Security, Stealth, Survival
- **Knowledges:** Academics, Computer, Finance, Investigation, Law, Linguistics, Medicine, Occult, Politics, Science

### 2.3 Advantages

- **Disciplines** (Revised core ch. 4): Animalism, Auspex, Celerity, Chimerstry, Dementation, Dominate, Fortitude, Necromancy, Obfuscate, Obtenebration, Potence, Presence, Protean, Quietus, Serpentis, Thaumaturgy, Vicissitude.
  - Necromancy and Thaumaturgy are bought as Paths plus rituals. A new Path and secondary paths have their own XP costs (p. 143).
- **Backgrounds** (pp. 129–133): Allies, Contacts, Fame, Generation, Herd, Influence, Mentor, Resources, Retainers, Status. Rated 0–5.
  - Generation dots set generation: 0 → 13th, 1 → 12th, 2 → 11th, 3 → 10th, 4 → 9th, 5 → 8th (p. 131).
  - Fame lowers hunting difficulty by 1 per dot, to a minimum of 3. Herd adds 1 hunting die per dot (p. 202).
  - Minor Contacts: roll the Contacts rating at difficulty 7. Each success reaches one minor contact (p. 130).
  - Backgrounds **can't be bought with XP**. They are gained in play (p. 142).
- **Virtues** (pp. 133–134). Three, rated 1–5:
  - Conscience **or** Conviction
  - Self-Control **or** Instinct
  - Courage (everyone has it)
  - Conviction and Instinct are for Path followers (Appendix pp. 286–287). A character never has both members of a pair.

### 2.4 Morality: Humanity or a Path (pp. 133–136, 221–222, 286–287)

- Humanity or Path rating: 1–10. Characters at 0 are taken over by the ST.
- **Virtue rolls can't use more dice than the character's Humanity** (p. 134).
- **Self-Control/Instinct rolls can't use more dice than the current blood pool** (pp. 134, 138).
- Daytime: the maximum pool for any action is the Humanity score (p. 134).
- Torpor length depends on Humanity (see 4.4).
- Path followers count as Humanity 3 for dealing with mortals, or their Path rating if lower (p. 286).
- Revised Appendix Paths: Blood, Bones, Metamorphosis, Night, Paradox, Typhon.
- **Degeneration (pp. 221–222).** When the act is at or below the character's current rating on the Hierarchy of Sins:
  - Roll Conscience (or Conviction) at **difficulty 8**. Willpower can't be spent on this roll.
  - ≥1 success: no loss.
  - Failure: −1 Humanity.
  - Botch: −1 Humanity, −1 Conscience, and the character gains a derangement.
  - The Hierarchy goes from 10 (selfish thoughts) down to 1 (utter perversion). Stored in JSON.

### 2.5 Willpower (pp. 136–138)

- A permanent **rating** (1–10, the circles), which is what gets rolled, and a temporary **pool** (the squares), which is what gets spent.
- The pool never goes above the rating. The rating only rises with XP.
- Recovery:
  - The whole pool refills at the **end of a story** (not a session). The ST may require a goal to have been met.
  - Optional: +1 when first rising each night.
  - Optional: +1 for extraordinary achievements.
  - Optional: 1–3 for acting out one's Nature (Archetype).

### 2.6 Health (pp. 140–141, 216–218)

- 7 levels plus Incapacitated:

| Level | Dice penalty | Movement |
|---|---|---|
| Bruised | 0 | none |
| Hurt | −1 | none |
| Injured | −1 | max running speed halved |
| Wounded | −2 | can't run; loses dice if moving and attacking in the same turn |
| Mauled | −2 | hobble, 3 yards/turn |
| Crippled | −5 | crawl, 1 yard/turn |
| Incapacitated | — | no actions except spending blood to heal, or swallowing blood offered |

- The Injured row is unreadable in one extraction of p. 140 but readable on the character sheet and on p. 216. It is −1.
- The current penalty = the penalty of the lowest marked box.
- **Marking order:** aggravated (X) always goes above normal damage (/).
  - Bashing and lethal both count as "normal" damage for vampires.
  - When aggravated damage comes in, existing normal marks shift down.
  - Normal damage is marked last and healed first (p. 217).
- Overflow (p. 217):
  - **Vampire Incapacitated by bashing or lethal**, then takes more bashing or lethal → **torpor**.
  - Incapacitated by anything, then takes **aggravated** → **Final Death**. Same for any aggravated damage while in torpor.
  - Losing the last health level to aggravated damage → **Final Death** (p. 218).
  - Massive trauma that destroys the body (decapitation and the like) can cause Final Death at Incapacitated or in torpor.
- Incapacitated with an empty blood pool → torpor (p. 140).
- Mortals have the same 7 levels. Past Incapacitated they die.
- Optional "extras" (p. 217): nameless thugs get 4 levels: Hurt −1, Maimed −3, Incapacitated, Dead.

### 2.7 Blood pool (pp. 137–140)

- The maximum and the spend rate per turn come from generation (2.8).
- Spend **1 blood point every night** on waking, even if the vampire doesn't get up.
- At 0 blood the vampire is starving and likely to frenzy. Further blood costs are paid in health levels (p. 216).
- Uses:
  - **Heal:** 1 blood point = 1 normal health level (bashing or lethal) while resting. Limited by blood per turn.
  - **Boost Physical Attributes:** 1 blood = +1 dot to Strength, Dexterity or Stamina for the scene. Declare it at the start of the turn; the per-turn spend limit applies.
    - Free boosts go up to generation max + 1.
    - Dots above that last only 3 turns after spending stops.
    - Nothing can go above 10.
  - **Appear human** for a scene (flushed skin, breath and so on): costs **(8 − Humanity)** blood. Free at Humanity 8+. Humanity followers only, not Path followers.
  - Disciplines, per each power.
  - Give blood to others. Three drinks on three separate nights from the same vampire = **blood bond** (pp. 138, 218).
- **Starting blood pool:** the Revised example (p. 111) rolls 1d10. The rule text itself sits on the p. 103–104 summary page, which didn't survive extraction. **V20 p. 86 states it outright: roll 1d10.** Implement 1d10, capped at the generation maximum.
- Feeding (p. 139):
  - Up to **3 blood points per turn** from one vessel.
  - Average human 10 BP. Taking 20% is safe. Half needs hospital care. Draining kills.
  - Animals: cow 5, dog 2, cat 1, rat ½, bat/bird ¼. V20 lists bird ½ and bat/rat ¼.
  - Kindred can resist the Kiss: Self-Control at difficulty 8.

### 2.8 Generation chart (core p. 139; identical to V20)

| Gen | Max Trait | Blood pool max | Blood/turn |
|---|---|---|---|
| 3rd | 10 | ??? | ??? |
| 4th | 9 | 50 | 10 |
| 5th | 8 | 40 | 8 |
| 6th | 7 | 30 | 6 |
| 7th | 6 | 20 | 4 |
| 8th | 5 | 15 | 3 |
| 9th | 5 | 14 | 2 |
| 10th | 5 | 13 | 1 |
| 11th | 5 | 12 | 1 |
| 12th | 5 | 11 | 1 |
| 13th+ | 5 | 10 | 1 |

- The max Trait applies to permanent Traits (Attributes, Abilities, Disciplines). It doesn't apply to Humanity/Path or Willpower.
- The 3rd generation's blood values are "???" in the book. Store them as `null`.
- Player characters are 13th to 8th generation at creation.

---

## 3. Character creation budgets (pp. 104–111; numbers checked against the worked example on pp. 109–111)

| Step | Budget | Notes |
|---|---|---|
| Concept, clan, Nature, Demeanor | — | Caitiff are allowed (clan = "Caitiff"). Nature/Demeanor come from the Archetype list (pp. 112–115). |
| Attributes | **7 / 5 / 3** extra dots | Primary, secondary and tertiary groups, on top of 1 free dot in each Attribute. Nosferatu Appearance stays 0. |
| Abilities | **13 / 9 / 5** | Talents, Skills and Knowledges ranked by priority. **No Ability above 3 at this step**; freebies can raise it later. |
| Disciplines | **3** dots | Must be clan Disciplines. Caitiff choose any (ST approval). Disciplines bought with freebies don't have to be clan ones. |
| Backgrounds | **5** dots | Any mix. |
| Virtues | **7** dots | Humanity followers start with 1 free dot in each of the three Virtues. Conviction and Instinct start at **0** and must be raised to at least 1 (p. 287). |
| Humanity | = Conscience + Self-Control | Worked out **before** freebies go into Virtues. With 10 Virtue dots in total, this comes to **5–9** before freebies (V20 p. 86 says 5–9; the Revised extraction is garbled). |
| Willpower | = Courage | 1–5 before freebies. |
| Freebies | **15** | Costs below. |
| Blood pool | 1d10 | See 2.7. |

**Freebie costs.** The Revised chart on p. 104 is unreadable in the extraction.

| Trait | Cost per dot | Source |
|---|---|---|
| Attribute | 5 | V20 p. 82 |
| Ability | 2 | V20 p. 82; Revised example p. 111 (Finance 3→4 for 2) |
| Discipline | 7 | V20 p. 82; Revised example (7 points for 1 dot of Dominate) |
| Background | 1 | V20 p. 82; Revised example (2 points for 2 dots of Contacts) |
| Virtue | 2 | V20 p. 82 |
| Humanity/Path | 2 | V20 p. 82; Revised example (2 points for Humanity 6→7) |
| Willpower | 1 | V20 p. 82; Revised example (2 points for Willpower 4→6) |

- The example's spending adds up to exactly 15 (2+2+2+2+7). Attribute and Virtue costs could not be confirmed from the Revised text.

**Merits and Flaws** (Appendix p. 296):

- Optional, and only at creation.
- Merits are bought with freebies.
- Flaws grant extra freebies, **up to 7 points of Flaws**, for 22 freebies at most.
- Categories: Physical, Mental, Social, Supernatural.

**Path characters** (p. 287):

- Starting Willpower must be at least **5**.
- Starting Path is capped at **5**, even after freebies.
- Starting Path = the sum of the Path's two Virtues (per-Path pairing, p. 286).

**Neonate assumption:** player characters have at most **25 years** as Kindred (p. 102).

**Experience** (pp. 141–143; cost chart p. 143):

- 1 XP automatic per chapter, plus 1 each for learning, roleplaying and heroism. Truly inspired roleplaying is worth 2. Usually 1–5 per chapter.
- End of story: +1 each for success, danger and wisdom.
- **No Trait can go up more than 1 dot per story.**
- New Abilities and Disciplines need a teacher or study.
- Costs ("current rating" = the rating before the purchase):

| Purchase | XP cost |
|---|---|
| New Ability | 3 |
| New Discipline | 10 |
| New Path (Necromancy or Thaumaturgy) | 7 |
| Attribute | current × 4 |
| Ability | current × 2 |
| Clan Discipline | current × 5 (Caitiff: ×6 for all Disciplines) |
| Other Discipline | current × 7 |
| Secondary Path | current × 4 |
| Virtue | current × 2 (doesn't change Humanity or Willpower) |
| Humanity | current × 2 |
| Willpower | current × 1 |

---

## 4. Other systems the app must implement

### 4.1 Frenzy (core pp. 228–229)

- Roll Self-Control (or Instinct). Dice are capped by blood pool and by Humanity.
- Difficulty is usually 6–8. For an atrocity, use **9 − Conscience**.
- **Five successes** in total fully resist the frenzy.
  - Each success below 5 buys one turn, after which the character can roll again and keep adding successes.
  - Failure: frenzy.
  - Botch: frenzy until the ST ends it, and possibly a derangement.
- Sample difficulties:

| Trigger | Difficulty |
|---|---|
| Smell of blood (hungry) | 3+ |
| Sight of blood (hungry) | 4+ |
| Harassment | 4 |
| Life-threatening situation | 4 |
| Malicious taunts | 4 |
| Physical provocation | 6 |
| Taste of blood (hungry) | 6+ |
| Loved one in danger | 7 |
| Outright humiliation | 8 |

- While in frenzy:
  - Ignore wound penalties.
  - Dominate difficulties against the character +2. The character resists Dominate at −2 difficulty.
  - No Willpower rolls are needed.
  - Immune to Rötschreck.
  - 1 Willpower = control of one action for a turn.
  - It usually lasts a scene.
- Instinct characters (p. 287): they always frenzy unless the difficulty is below their Instinct, in which case they choose. "Riding the wave" (taking a deliberate action) means an Instinct roll against the frenzy difficulty.
- Hunger check while feeding (p. 202): if the vampire catches prey while holding fewer than **(7 − Self-Control)** blood points, make a frenzy check. On a failure, the vampire drinks until full or until the vessel dies.

### 4.2 Rötschreck (core p. 229)

- Roll Courage. Five successes in total, same structure as frenzy.
- Failure: flee in blind panic.
- Botch: immediate frenzy.
- 1 Willpower = control for a turn.
- Difficulties:

| Trigger | Difficulty |
|---|---|
| Lighting a cigarette | 3 |
| Sight of a torch | 5 |
| Bonfire | 6 |
| Obscured sunlight | 7 |
| Being burned | 7 |
| Direct sunlight | 8 |
| Trapped in a burning building | 9 |

### 4.3 Aggravated damage and its sources (pp. 218, 232)

- Sources: fire, sunlight, and the teeth and claws of vampires and other supernatural creatures.
- **Healing aggravated damage:** a full day's rest plus **5 blood points** per level. After that day's rest, each extra level costs 5 blood + 1 Willpower.
- **Sunlight:** automatic aggravated damage every turn. Only Fortitude can soak it (pool = Fortitude dots), at a difficulty set by intensity:

| Light | Soak difficulty |
|---|---|
| Faint (through a closed curtain, heavy cloud cover, twilight) | 3 |
| Fully covered (heavy clothes, sunglasses, gloves, wide hat) | 5 |
| Indirect (through a window or light curtains) | 7 |
| Outside on a cloudy day, one direct ray, sun in a mirror | 9 |
| Direct, unobscured sun | 10 |

- Damage per turn by exposure: 1 (a hand or part of the face), 2 (a limb or the whole head), 3 (half the body or more).
- Mortals hurt by an "aggravated" source (fire, for example) take it as lethal.

### 4.4 Torpor (p. 216)

- Torpor from **wounds**: minimum rest time by Humanity:

| Humanity | Minimum rest |
|---|---|
| 10 | 1 day |
| 9 | 3 days |
| 8 | 1 week |
| 7 | 2 weeks |
| 6 | 1 month |
| 5 | 1 year |
| 4 | 1 decade |
| 3 | 5 decades |
| 2 | 1 century |
| 1 | 5 centuries |
| 0 | a millennium or more |

- After the rest time: spend 1 blood and make an Awakening roll. On a failure, try again the next night for another blood point. The vampire rises at Crippled.
- Torpor from **blood loss**: being fed 1 blood point wakes the vampire, whatever their Humanity.
- Voluntary torpor: may rise after half the time, with an Awakening roll. No nightly blood cost while in torpor.

### 4.5 Hunting (core p. 202)

- Roll Perception (+ Herd dots) per hour of hunting. Difficulty by area:

| Area | Difficulty |
|---|---|
| Slum | 4 |
| Lower-income / bohemian | 5 |
| Downtown business district | 6 |
| Warehouse district | 6 |
| Suburb | 7 |
| Heavily patrolled area | 8 |

- Success: feed for **1d10 blood points**. ("One die's worth" — **AMBIGUOUS** whether that is capped by the 3-points-per-turn feeding limit or by the vessel's 10 points. Recommended: cap at the room left in the pool.)
- Failure: the hour is wasted. Botch: a complication.
- Fame lowers the difficulty by its dots, to a minimum of 3. The ST may raise it for monstrous vampires (Nosferatu, some Gangrel, Humanity ≤ 4).

---

## 5. Clans (Revised core ch. 2)

There are 13 clans plus Caitiff (core ch. 2 intro, p. 64). Clan Disciplines are listed below.

- **Camarilla:** Brujah, Gangrel, Malkavian, Nosferatu, Toreador, Tremere, Ventrue.
- **Sabbat:** Lasombra, Tzimisce.
- **Independent:** Assamite, Followers of Set, Giovanni, Ravnos.

| Clan | Sect (Revised) | Clan Disciplines |
|---|---|---|
| Assamite | Independent | Celerity, Obfuscate, Quietus |
| Brujah | Camarilla | Celerity, Potence, Presence |
| Followers of Set | Independent | Obfuscate, Presence, Serpentis |
| Gangrel | Camarilla | Animalism, Fortitude, Protean |
| Giovanni | Independent | Dominate, Necromancy, Potence |
| Lasombra | Sabbat | Dominate, Obtenebration, Potence |
| Malkavian | Camarilla | **Auspex, Dominate, Obfuscate** (Revised) |
| Nosferatu | Camarilla | Animalism, Obfuscate, Potence |
| Ravnos | Independent | Animalism, Chimerstry, Fortitude |
| Toreador | Camarilla | Auspex, Celerity, Presence |
| Tremere | Camarilla | Auspex, Dominate, Thaumaturgy |
| Tzimisce | Sabbat | Animalism, Auspex, Vicissitude |
| Ventrue | Camarilla | Dominate, Fortitude, Presence |
| Caitiff | none | none (any Disciplines, ST approval) |

- Source quality: the Revised extraction preserves the full Discipline lines only for Toreador, Lasombra and Giovanni, plus partial Brujah and Ravnos lines. The other rows were checked against V20 (V20 ch. 2, pp. 48–72), whose triples match the Revised clans.
- **Malkavian exception:** V20 gives Auspex, **Dementation**, Obfuscate. Revised gives Dominate. The Revised Malkavian entry (p. 73) treats Dementation as a power held by an offshoot of the clan "in lieu of" Dominate. Use Revised for the classic ruleset.
- Revised also mentions bloodlines, such as City Gangrel (Celerity, Obfuscate, Protean). Not needed for now.
- Clan weaknesses are in the clan write-ups (Revised ch. 2, pp. 62–97). They aren't encoded yet because several are partly unreadable in the extraction. Add them when that feature is built.

---

## 6. Ambiguities and extraction gaps (summary)

1. The freebie cost chart (p. 104) and the creation summary (p. 103) didn't survive extraction. Costs come from V20 p. 82, cross-checked against the Revised worked example where it covers them. Attribute 5 and Virtue 2 are V20-only.
2. The Revised starting-blood rule is only shown in an example (1d10). V20 states it.
3. Specialty rerolls: whether 1s on rerolled dice cancel is unspecified.
4. Willpower success on a roll that would otherwise botch: the outcome is only implied.
5. Extended action botch: "may have to start over" or the action ends, at ST discretion.
6. Clan Discipline lines for 8 clans came from V20. The Malkavian line differs between Revised and V20.
7. Hunting "one die's worth" of blood: the cap is unclear.

---

## Differences that matter for the app

- **Botch rule:** botch only when **no success was rolled at all** and at least one 1 shows. Cancelling successes down to zero is a plain failure. At d5686c4, `dice_service.py` treated net ≤ 0 with 1s, or net < 0, as a botch, which is the pre-Revised reading. Make sure the new code follows p. 192.
- **Specialty:** Revised rerolls 10s, open-ended. V20 counts a 10 as 2 successes, which is what the code did at d5686c4. Make it a ruleset option.
- **Willpower:** +1 uncancellable success, one per turn, declared before the roll. It's a pool modifier, not a reroll.
- **Difficulty** is a per-die target number (2–10, default 6). Success count only matters for degree, extended totals and contests. This is the opposite of V5.
- **Damage** uses 3 types and 7 fixed health levels with set penalties. It doesn't scale with Stamina; Stamina only soaks. For vampires, bashing that gets past soak is halved. Lethal soak is vampire-only. Aggravated can only be soaked with Fortitude.
- **Resources:** the vampire's resource is the **blood pool** (count up and down, per-turn spend limit by generation), not Hunger. Nightly cost is 1 point.
- **Generation** caps Traits and the blood pool. It is set by the Generation Background (13th − dots).
- **Morality:** Humanity/Path 1–10 with Virtue-driven rolls (Conscience/Self-Control/Courage) and Virtue dice caps. No Stains/Remorse.
- **Creation:** 7/5/3, 13/9/5, 3 Disciplines, 5 Backgrounds, 7 Virtues, 15 freebies (+ up to 7 from Flaws), Abilities ≤ 3 before freebies.
- **XP costs:** "current rating × N", one dot per story.
