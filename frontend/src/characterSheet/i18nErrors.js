/**
 * Validation messages from ./validation.js and ./v5/validation.js are English strings (their tests
 * assert them). The wizards show them through translateSheetError(), which recognises each message
 * shape and returns it in the active language. Unknown messages pass through unchanged.
 * Trait, clan and Discipline names inside the messages stay English (game terms).
 *
 * The server's V5 creation check (backend/services/v5_chargen.py) answers with problem codes
 * ({code, params}); translateProblem() / serverProblemErrors() put those in the active language.
 */
import { t } from '../i18n';
import { V5_AGE_BRACKETS, V5_ATTRIBUTES, V5_SECTION_IDS, V5_SKILL_DISTRIBUTIONS, V5_SKILL_LABELS } from './v5/constants';
import { bookTitle } from './v5/rulesData';

const atList = (s) => s.replace(/ at (\d)/g, (m, r) => t('wizard:validation.atRating', ' at {{r}}', { r }));

const PATTERNS = [
  [/^Nosferatu have Appearance (\d+) and can never raise it\.$/, (m) => t('wizard:validation.nosferatuAppearance', 'Nosferatu have Appearance {{n}} and can never raise it.', { n: m[1] })],
  [/^Each attribute must be between 1 and 5 \((.+)\)\.$/, (m) => t('wizard:validation.attrRange', 'Each attribute must be between 1 and 5 ({{key}}).', { key: m[1] })],
  [/^(.+): add exactly (\d+) dots on top of the free dot in each attribute \(added (\d+)\)\.$/, (m) => t('wizard:validation.attrPool', '{{label}}: add exactly {{n}} dots on top of the free dot in each attribute (added {{added}}).', { label: m[1], n: m[2], added: m[3] })],
  [/^Each ability must be between 0 and 5 \((.+)\)\.$/, (m) => t('wizard:validation.abilityRange', 'Each ability must be between 0 and 5 ({{key}}).', { key: m[1] })],
  [/^Each ability \(including custom rows\) must be between 0 and 5\.$/, () => t('wizard:validation.abilityRangeCustom', 'Each ability (including custom rows) must be between 0 and 5.')],
  [/^No ability above (\d+) before freebie points \((.+)\)\.$/, (m) => t('wizard:validation.abilityMax', 'No ability above {{max}} before freebie points ({{label}}).', { max: m[1], label: m[2] })],
  [/^(.+) must use all (\d+) dots, no ability above (\d+) \(currently (\d+)\)\.$/, (m) => t('wizard:validation.abilityPool', '{{label}} must use all {{n}} dots, no ability above {{max}} (currently {{current}}).', { label: m[1], n: m[2], max: m[3], current: m[4] })],
  [/^Each virtue must be between 1 and 5\.$/, () => t('wizard:validation.virtueRange', 'Each virtue must be between 1 and 5.')],
  [/^Virtues: 1 free dot each plus (\d+) more \(total (\d+); currently (\d+)\)\.$/, (m) => t('wizard:validation.virtueTotal', 'Virtues: 1 free dot each plus {{n}} more (total {{total}}; currently {{current}}).', { n: m[1], total: m[2], current: m[3] })],
  [/^Flaws give at most (\d+) extra freebie points \(you listed (\d+)\)\.$/, (m) => t('wizard:validation.flawsMax', 'Flaws give at most {{max}} extra freebie points (you listed {{listed}}).', { max: m[1], listed: m[2] })],
  [/^Freebie points overspent: (\d+) of (\d+)\.$/, (m) => t('wizard:validation.freebiesOver', 'Freebie points overspent: {{spent}} of {{available}}.', { spent: m[1], available: m[2] })],
  [/^Sphere (.+) must be 0–5\.$/, (m) => t('wizard:validation.sphereRange', 'Sphere {{key}} must be 0–5.', { key: m[1] })],
  [/^Allocate exactly 6 sphere dots at creation \(currently (\d+)\)\.$/, (m) => t('wizard:validation.spheresTotal', 'Allocate exactly 6 sphere dots at creation (currently {{current}}).', { current: m[1] })],
  // V5 whole-sheet checks (validateV5Sheet)
  // V5 catalog checks (validateV5Powers, resolvePredatorGrants)
  [/^(.+): (.+) is taken twice\.$/, (m) => t('wizard:validation.v5PowerTwice', '{{disc}}: {{name}} is taken twice.', { disc: m[1], name: m[2] })],
  [/^(.+) is not a (.+) power\.$/, (m) => t('wizard:validation.v5PowerUnknown', '{{name}} is not a {{disc}} power.', { name: m[1], disc: m[2] })],
  [/^(.+) is a level (\d+) power; (.+) is at (\d+)\.$/, (m) => t('wizard:validation.v5PowerLevel', '{{name}} is a level {{level}} power; {{disc}} is at {{rating}}.', { name: m[1], level: m[2], disc: m[3], rating: m[4] })],
  [/^(.+) also needs (.+) (\d+)\.$/, (m) => t('wizard:validation.v5PowerAmalgam', '{{name}} also needs {{disc}} {{level}}.', { name: m[1], disc: m[2], level: m[3] })],
  [/^(.+) needs (.+) first\.$/, (m) => t('wizard:validation.v5PowerPrereq', '{{name}} needs {{pre}} first.', { name: m[1], pre: m[2].replace(/ or /g, ` ${t('wizard:v5.grantOr', 'or')} `) })],
  [/^(.+): choose one of (.+)\.$/, (m) => t('wizard:validation.v5GrantOneOf', '{{type}}: choose one of {{list}}.', { type: m[1], list: m[2].replace(/ or /g, ` ${t('wizard:v5.grantOr', 'or')} `) })],
  [/^(.+): share (\d+) dots between (.+) \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5GrantSplit', '{{type}}: share {{n}} dots between {{list}} (you have {{have}}).', { type: m[1], n: m[2], list: m[3].replace(/ and /g, ` ${t('wizard:v5.grantAnd', 'and')} `), have: m[4] })],
  [/^(.+): choose the dots for (.+) \(ask your Storyteller; the book prints none\)\.$/, (m) => t('wizard:validation.v5GrantDots', '{{type}}: choose the dots for {{name}} (ask your Storyteller; the book prints none).', { type: m[1], name: m[2] })],
  [/^(.+) is for ancillae only\.$/, (m) => t('wizard:validation.v5AncillaOnly', '{{type}} is for ancillae only.', { type: m[1] })],
  // V5 catalog Advantages, Flaws and loresheets (validateV5AdvantageRows)
  [/^(.+) can't take (.+) at creation\.$/, (m) => t('wizard:validation.v5AdvNotForClan', "{{clan}} can't take {{name}} at creation.", { clan: m[1], name: m[2] })],
  [/^(.+) takes (.+) dots \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5AdvDots', '{{name}} takes {{allowed}} dots (you have {{n}}).', { name: m[1], allowed: m[2].replace(/ or /g, ` ${t('wizard:v5.grantOr', 'or')} `), n: m[3] })],
  [/^(.+) can be taken only once\.$/, (m) => t('wizard:validation.v5AdvOnce', '{{name}} can be taken only once.', { name: m[1] })],
  [/^(.+) can be taken at most (\d+) times\.$/, (m) => t('wizard:validation.v5AdvMaxTimes', '{{name}} can be taken at most {{n}} times.', { name: m[1], n: m[2] })],
  [/^(.+) needs (.+) at (\d+) dots or more\.$/, (m) => t('wizard:validation.v5AdvRequires', '{{name}} needs {{other}} at {{n}} dots or more.', { name: m[1], other: m[2], n: m[3] })],
  [/^Pick at least one level of (.+)\.$/, (m) => t('wizard:validation.v5LoreLevel', 'Pick at least one level of {{name}}.', { name: m[1] })],
  [/^(.+) and (.+) can't be taken together\.$/, (m) => t('wizard:validation.v5AdvExcludes', "{{a}} and {{b}} can't be taken together.", { a: m[1], b: m[2] })],
  [/^(.+) is only for ancillae or older\.$/, (m) => t('wizard:validation.v5AdvAncilla', '{{name}} is only for ancillae or older.', { name: m[1] })],
  [/^(.+): choose which (.+)\.$/, (m) => t('wizard:validation.v5GrantGroup', '{{type}}: choose which {{what}}.', { type: m[1], what: m[2] })],
  // V5 chronicle creation settings (settingsErrors)
  [/^The Storyteller doesn't allow the (.+) predator type in this chronicle\.$/, (m) => t('wizard:validation.v5SettingsPredator', "The Storyteller doesn't allow the {{type}} predator type in this chronicle.", { type: m[1] })],
  [/^The Storyteller doesn't allow (.+) characters in this chronicle\.$/, (m) => t('wizard:validation.v5SettingsAge', "The Storyteller doesn't allow {{age}} characters in this chronicle.", { age: m[1] })],
  [/^The Storyteller doesn't allow (.+) in this chronicle\.$/, (m) => t('wizard:validation.v5SettingsClan', "The Storyteller doesn't allow {{clan}} in this chronicle.", { clan: m[1] })],
  [/^This chronicle allows at most (\d+) dots of Flaws of your own \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5SettingsFlawCap', 'This chronicle allows at most {{max}} dots of Flaws of your own (you have {{n}}).', { max: m[1], n: m[2] })],
  [/^The Storyteller doesn't offer the Humanity 8 fledgling start in this chronicle\.$/, () => t('wizard:validation.v5SettingsFledgling', "The Storyteller doesn't offer the Humanity 8 fledgling start in this chronicle.")],
  [/^(.+) comes from a book this chronicle doesn't use \((.+)\)\.$/, (m) => t('wizard:validation.v5SettingsBook', "{{name}} comes from a book this chronicle doesn't use ({{book}}).", { name: m[1], book: m[2] })],
  [/^Character name is required\.$/, () => t('wizard:error.name', 'Character name is required.')],
  [/^Choose a clan\.$/, () => t('wizard:validation.v5Clan', 'Choose a clan.')],
  [/^Choose an age\.$/, () => t('wizard:validation.v5Age', 'Choose an age.')],
  [/^(.+)s are generation (\d+)–(\d+)\.$/, (m) => t('wizard:validation.v5AgeGeneration', '{{age}}: generation {{lo}}–{{hi}}.', { age: m[1], lo: m[2], hi: m[3] })],
  [/^Thin-bloods are 14th–16th generation\.$/, () => t('wizard:validation.v5ThinGeneration', 'Thin-bloods are 14th–16th generation.')],
  [/^14th–16th generation vampires are thin-bloods\.$/, () => t('wizard:validation.v5GenerationThin', '14th–16th generation vampires are thin-bloods.')],
  [/^Choose a predator type\.$/, () => t('wizard:validation.v5Predator', 'Choose a predator type.')],
  [/^(.+) cannot take the (.+) predator type\.$/, (m) => t('wizard:validation.v5PredatorClan', '{{clan}} cannot take the {{type}} predator type.', { clan: m[1], type: m[2] })],
  [/^Pick the predator type specialty\.$/, () => t('wizard:validation.v5PredatorSpecialty', 'Pick the predator type specialty.')],
  [/^Pick the predator type Discipline\.$/, () => t('wizard:validation.v5PredatorDiscipline', 'Pick the predator type Discipline.')],
  [/^(.+) needs Blood Potency (\d+) or less\.$/, (m) => t('wizard:validation.v5PredatorBp', '{{type}} needs Blood Potency {{n}} or less.', { type: m[1], n: m[2] })],
  [/^Advantages: at most (\d+) dots \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5AdvMax', 'Advantages: at most {{max}} dots (you have {{n}}).', { max: m[1], n: m[2] })],
  [/^Take at least (\d+) dots of Flaws \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5FlawMin', 'Take at least {{min}} dots of Flaws (you have {{n}}).', { min: m[1], n: m[2] })],
  [/^Each Advantage or Flaw is 1–5 dots\.$/, () => t('wizard:validation.v5AdvRange', 'Each Advantage or Flaw is 1–5 dots.')],
  [/^Write (\d+)–(\d+) Convictions, each with a Touchstone\.$/, (m) => t('wizard:validation.v5Convictions', 'Write {{lo}}–{{hi}} Convictions, each with a Touchstone.', { lo: m[1], hi: m[2] })],
  [/^Each Conviction needs a Touchstone \(and vice versa\)\.$/, () => t('wizard:validation.v5ConvictionPair', 'Each Conviction needs a Touchstone (and vice versa).')],
  // V5 parts
  [/^Attributes start between 1 and 4 at creation\.$/, () => t('wizard:validation.v5AttrRange', 'Attributes start between 1 and 4 at creation.')],
  [/^Attributes must be one at 4, three at 3, four at 2 and one at 1\.$/, () => t('wizard:validation.v5AttrSpread', 'Attributes must be one at 4, three at 3, four at 2 and one at 1.')],
  [/^Choose a skill distribution\.$/, () => t('wizard:validation.v5SkillDist', 'Choose a skill distribution.')],
  [/^(.+): no skill above (\d+) at creation\.$/, (m) => t('wizard:validation.v5SkillMax', '{{label}}: no skill above {{max}} at creation.', { label: m[1], max: m[2] })],
  [/^(.+) needs exactly (.+)\.$/, (m) => t('wizard:validation.v5SkillCounts', '{{label}} needs exactly {{want}}.', { label: m[1], want: atList(m[2]) })],
  [/^You have (\d+) free specialties \(one per rated Academics\/Craft\/Performance\/Science, plus one\)\.$/, (m) => t('wizard:validation.v5SpecialtyCount', 'You have {{n}} free specialties (one per rated Academics/Craft/Performance/Science, plus one).', { n: m[1] })],
  [/^Each specialty needs a skill\.$/, () => t('wizard:validation.v5SpecialtySkill', 'Each specialty needs a skill.')],
  [/^Name the (.+) specialty\.$/, (m) => t('wizard:validation.v5SpecialtyName', 'Name the {{skill}} specialty.', { skill: m[1] })],
  [/^(.+) needs at least one dot for a specialty\.$/, (m) => t('wizard:validation.v5SpecialtyDot', '{{skill}} needs at least one dot for a specialty.', { skill: m[1] })],
  [/^(.+) comes with a free specialty — name it\.$/, (m) => t('wizard:validation.v5SpecialtyFree', '{{skill}} comes with a free specialty — name it.', { skill: m[1] })],
  [/^Thin-bloods start with no Disciplines\.$/, () => t('wizard:validation.v5ThinNoDisc', 'Thin-bloods start with no Disciplines.')],
  [/^Pick two Disciplines: one at 2 dots and one at 1 dot\.$/, () => t('wizard:validation.v5DiscPickAny', 'Pick two Disciplines: one at 2 dots and one at 1 dot.')],
  [/^Pick two clan Disciplines: one at 2 dots and one at 1 dot\.$/, () => t('wizard:validation.v5DiscPickClan', 'Pick two clan Disciplines: one at 2 dots and one at 1 dot.')],
  [/^Pick two different Disciplines\.$/, () => t('wizard:validation.v5DiscDifferent', 'Pick two different Disciplines.')],
  [/^One Discipline at 2 dots and one at 1 dot\.$/, () => t('wizard:validation.v5DiscDots', 'One Discipline at 2 dots and one at 1 dot.')],
  [/^(.+) is not a (.+) clan Discipline\.$/, (m) => t('wizard:validation.v5DiscClan', '{{name}} is not a {{clan}} clan Discipline.', { name: m[1], clan: m[2] })],
  [/^Thin-bloods take (\d+)–(\d+) thin-blood Merits \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5ThinMerits', 'Thin-bloods take {{lo}}–{{hi}} thin-blood Merits (you have {{n}}).', { lo: m[1], hi: m[2], n: m[3] })],
  [/^Take as many thin-blood Flaws as thin-blood Merits \((\d+) Merits, (\d+) Flaws\)\.$/, (m) => t('wizard:validation.v5ThinFlaws', 'Take as many thin-blood Flaws as thin-blood Merits ({{m}} Merits, {{f}} Flaws).', { m: m[1], f: m[2] })],
  // V5 starting experience (xpLedger)
  [/^This age has no starting experience to spend\.$/, () => t('wizard:validation.v5XpNone', 'This age has no starting experience to spend.')],
  [/^(.+) can't go above (\d+) dots\.$/, (m) => t('wizard:validation.v5XpMaxDots', "{{label}} can't go above {{max}} dots.", { label: m[1], max: m[2] })],
  [/^Names are at most (\d+) characters\.$/, (m) => t('wizard:validation.v5NameLength', 'Names are at most {{max}} characters.', { max: m[1] })],
  [/^Name each ritual bought with XP\.$/, () => t('wizard:validation.v5XpRitualName', 'Name each ritual bought with XP.')],
  [/^Rituals are level 1 to 5\.$/, () => t('wizard:validation.v5XpRitualLevel', 'Rituals are level 1 to 5.')],
  [/^A level (\d+) ritual needs Blood Sorcery \d+ \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5XpRitualBs', 'A level {{level}} ritual needs Blood Sorcery {{level}} (you have {{bs}}).', { level: m[1], bs: m[2] })],
  [/^(.+) is a level (\d+) ritual\.$/, (m) => t('wizard:validation.v5XpRitualCatalogLevel', '{{name}} is a level {{level}} ritual.', { name: m[1], level: m[2] })],
  [/^One XP purchase is not something this step can buy\.$/, () => t('wizard:validation.v5XpUnknown', 'One XP purchase is not something this step can buy.')],
  [/^Starting experience overspent: (\d+) of (\d+) XP\.$/, (m) => t('wizard:validation.v5XpOver', 'Starting experience overspent: {{spent}} of {{total}} XP.', { spent: m[1], total: m[2] })],
  [/^At most (\d+) rituals \(you have (\d+)\)\.$/, (m) => t('wizard:validation.v5RitualsMax', 'At most {{max}} rituals (you have {{n}}).', { max: m[1], n: m[2] })],
  [/^(.+) already has the (.+) specialty\.$/, (m) => t('wizard:validation.v5SpecialtyDuplicate', '{{skill}} already has the {{name}} specialty.', { skill: m[1], name: m[2] })],
];

// ---------- V5 creation problems from the server ({code, params}) ----------

const ATTRIBUTE_LABELS = Object.fromEntries([...V5_ATTRIBUTES.physical, ...V5_ATTRIBUTES.social, ...V5_ATTRIBUTES.mental]);
const DERIVED_LABELS = { humanity: 'Humanity', blood_potency: 'Blood Potency', health: 'Health', willpower: 'Willpower', hunger: 'Hunger' };
const skillLabel = (k) => V5_SKILL_LABELS[k] || k || '';
const traitLabel = (k) => V5_SKILL_LABELS[k] || ATTRIBUTE_LABELS[k] || DERIVED_LABELS[k] || k || '';
const ageLabel = (a) => V5_AGE_BRACKETS[a]?.label || a || '';

/** One entry per code of backend/services/v5_chargen.py PROBLEM_CODES (a pytest checks it). */
const PROBLEMS = {
  clan_missing: () => t('wizard:problem.clan_missing', 'Choose a clan.'),
  age_missing: () => t('wizard:problem.age_missing', 'Choose an age.'),
  age_generation: (p) => t('wizard:problem.age_generation', '{{age}}: generation {{min}}–{{max}} (this sheet has {{generation}}).', { ...p, age: ageLabel(p.age) }),
  thin_blood_generation: () => t('wizard:problem.thin_blood_generation', 'Thin-bloods are 14th–16th generation.'),
  generation_thin_blood: () => t('wizard:problem.generation_thin_blood', '14th–16th generation vampires are thin-bloods.'),
  attr_range: () => t('wizard:problem.attr_range', 'Attributes start between 1 and 4 at creation.'),
  attr_spread: () => t('wizard:problem.attr_spread', 'Attributes must be one at 4, three at 3, four at 2 and one at 1.'),
  skill_dist: (p) =>
    V5_SKILL_DISTRIBUTIONS[p.distribution]
      ? t('wizard:problem.skill_dist', "Skills don't match the {{distribution}} distribution.", { distribution: V5_SKILL_DISTRIBUTIONS[p.distribution].label })
      : t('wizard:problem.skill_dist_missing', 'Choose a skill distribution.'),
  specialty_count: (p) => t('wizard:problem.specialty_count', 'You have {{max}} free specialties (you named {{have}}).', p),
  specialty_skill: (p) => t('wizard:problem.specialty_skill', '{{skill}} needs at least one dot for a specialty.', { skill: skillLabel(p.skill) }),
  specialty_missing: (p) => t('wizard:problem.specialty_missing', '{{skill}} comes with a free specialty — name it.', { skill: skillLabel(p.skill) }),
  specialty_duplicate: (p) => t('wizard:problem.specialty_duplicate', '{{skill}} already has the {{name}} specialty.', { skill: skillLabel(p.skill), name: p.name }),
  disc_thin_blood: () => t('wizard:problem.disc_thin_blood', 'Thin-bloods start with no Disciplines.'),
  disc_pick: () => t('wizard:problem.disc_pick', "Disciplines: two clan Disciplines, one at 2 dots and one at 1, plus the predator type's dot."),
  disc_clan: (p) => t('wizard:problem.disc_clan', '{{name}} is not a {{clan}} clan Discipline.', p),
  power_unknown: (p) => t('wizard:problem.power_unknown', '{{power}} is not a {{discipline}} power.', p),
  power_level: (p) => t('wizard:problem.power_level', '{{power}} is a level {{level}} power; {{discipline}} is at {{rating}}.', p),
  power_amalgam: (p) => t('wizard:problem.power_amalgam', '{{power}} also needs {{discipline}} {{level}}.', p),
  power_prereq: (p) => t('wizard:problem.power_prereq', '{{power}} needs {{needs}} first.', p),
  power_duplicate: (p) => t('wizard:problem.power_duplicate', '{{discipline}}: {{power}} is taken twice.', p),
  power_count: (p) => t('wizard:problem.power_count', '{{discipline}}: {{have}} powers for {{max}} dots.', p),
  predator_missing: () => t('wizard:problem.predator_missing', 'Choose a predator type.'),
  predator_forbidden: (p) => t('wizard:problem.predator_forbidden', '{{clan}} cannot take the {{predator}} predator type.', p),
  predator_specialty: () => t('wizard:problem.predator_specialty', 'Pick the predator type specialty.'),
  predator_discipline: () => t('wizard:problem.predator_discipline', 'Pick the predator type Discipline.'),
  predator_grant: () => t('wizard:problem.predator_grant', "The predator type's Advantages and Flaws don't match what the type gives."),
  predator_bp: (p) => t('wizard:problem.predator_bp', '{{predator}} needs Blood Potency {{max}} or less (this sheet has {{bp}}).', p),
  predator_ancilla: (p) => t('wizard:problem.predator_ancilla', '{{predator}} is for ancillae only.', p),
  adv_over: (p) => t('wizard:problem.adv_over', 'Advantages: at most {{max}} dots (you have {{have}}).', p),
  flaw_under: (p) => t('wizard:problem.flaw_under', 'Take at least {{min}} dots of Flaws (you have {{have}}).', p),
  flaw_over: (p) => t('wizard:problem.flaw_over', 'This chronicle allows at most {{max}} dots of Flaws of your own (you have {{have}}).', p),
  adv_dots_range: (p) => t('wizard:problem.adv_dots_range', '{{name}}: {{min}}–{{max}} dots (you have {{dots}}).', p),
  adv_unknown: (p) => t('wizard:problem.adv_unknown', '{{name}} is not in the catalog.', p),
  adv_restricted: (p) => t('wizard:problem.adv_restricted', '{{name}} is not open to {{clan}}.', p),
  loresheet_restricted: (p) => t('wizard:problem.loresheet_restricted', 'The {{name}} loresheet is not open to {{clan}}.', p),
  loresheet_levels: (p) => t('wizard:problem.loresheet_levels', 'The {{name}} loresheet: take each level once (1–5); its dots are their sum (you have {{dots}}).', p),
  custom_row: (p) => t('wizard:problem.custom_row', '{{name}} is a custom row: only the Storyteller can approve it.', p),
  caitiff_status: (p) => t('wizard:problem.caitiff_status', '{{clan}} can’t take Status at creation.', p),
  thin_blood_merits: (p) => t('wizard:problem.thin_blood_merits', 'Thin-bloods take {{min}}–{{max}} thin-blood Merits and as many thin-blood Flaws (you have {{merits}} and {{flaws}}).', p),
  thin_blood_only: () => t('wizard:problem.thin_blood_only', 'Only thin-bloods take thin-blood Merits and Flaws.'),
  conviction_count: (p) => t('wizard:problem.conviction_count', 'Write {{min}}–{{max}} Convictions, each with a Touchstone (you have {{have}}).', p),
  conviction_pairs: () => t('wizard:problem.conviction_pairs', 'Each Conviction needs a Touchstone.'),
  derived_value: (p) => t('wizard:problem.derived_value', '{{trait}} should be {{want}}, not {{have}}.', { ...p, trait: traitLabel(p.trait) }),
  xp_none: () => t('wizard:problem.xp_none', 'This age has no starting experience to spend.'),
  xp_total: (p) => t('wizard:problem.xp_total', 'Starting experience is {{want}} XP for this age, not {{have}}.', p),
  xp_log: () => t('wizard:problem.xp_log', "The starting experience log doesn't match the sheet."),
  xp_price: (p) => t('wizard:problem.xp_price', '{{trait}} costs {{want}} XP, not {{cost}}.', { ...p, trait: traitLabel(p.trait) }),
  xp_over: (p) => t('wizard:problem.xp_over', 'Starting experience overspent: {{spent}} of {{total}} XP.', p),
  xp_max_dots: (p) => t('wizard:problem.xp_max_dots', "{{trait}} can't go above {{max}} dots.", { ...p, trait: traitLabel(p.trait) }),
  name_length: (p) => t('wizard:problem.name_length', 'Names are at most {{max}} characters.', p),
  ritual_level: (p) => t('wizard:problem.ritual_level', '{{name}} is a level {{want}} ritual.', p),
  ritual_blood_sorcery: (p) => t('wizard:problem.ritual_blood_sorcery', 'A level {{level}} ritual needs Blood Sorcery {{level}} (you have {{rating}}).', p),
  ritual_start: () => t('wizard:problem.ritual_start', 'One free starting ritual, of level 1, with at least one dot of Blood Sorcery.'),
  ceremony_start: () => t('wizard:problem.ceremony_start', 'One free starting ceremony, of level 1, whose prerequisite Oblivion power the sheet has.'),
  ritual_count: (p) => t('wizard:problem.ritual_count', 'At most {{max}} rituals (you have {{have}}).', p),
  clan_not_allowed: (p) => t('wizard:problem.clan_not_allowed', "The Storyteller doesn't allow {{clan}} in this chronicle.", p),
  predator_not_allowed: (p) => t('wizard:problem.predator_not_allowed', "The Storyteller doesn't allow the {{predator}} predator type in this chronicle.", p),
  age_not_allowed: (p) => t('wizard:problem.age_not_allowed', "The Storyteller doesn't allow {{age}} characters in this chronicle.", { age: ageLabel(p.age) }),
  fledgling_not_allowed: () => t('wizard:problem.fledgling_not_allowed', "The Storyteller doesn't offer the Humanity 8 fledgling start in this chronicle."),
  book_not_allowed: (p) => t('wizard:problem.book_not_allowed', "{{name}} comes from a book this chronicle doesn't use ({{book}}).", { name: p.name, book: bookTitle(p.book) }),
};

/** One server problem ({code, params}) in the active language; a string goes through translateSheetError. */
export function translateProblem(problem) {
  if (typeof problem === 'string') return translateSheetError(problem);
  const code = problem?.code;
  if (!code) return '';
  const fn = PROBLEMS[code];
  return fn ? fn(problem.params || {}) : t('wizard:problem.unknown', 'The sheet breaks a creation rule ({{code}}).', { code });
}

// book_not_allowed: the section of the entry's kind (params.kind, backend/services/v5_chargen.py).
const BOOK_SECTIONS = {
  clan: 'clan',
  predator: 'predator',
  power: 'disciplines',
  ritual: 'disciplines',
  ceremony: 'disciplines',
  advantage: 'advantages',
  loresheet: 'advantages',
  thin_blood: 'advantages',
};

/** The forge section a problem code (and for book_not_allowed its params) belongs to (for the error marks and the scroll). */
export function problemSection(code, params) {
  const S = V5_SECTION_IDS;
  if (code === 'book_not_allowed') return S[BOOK_SECTIONS[params?.kind] || 'identity'];
  if (/^(clan_missing|clan_not_allowed)$/.test(code)) return S.clan;
  if (/^(age_|thin_blood_generation|generation_thin_blood)/.test(code)) return S.age;
  if (/^attr_/.test(code)) return S.attributes;
  if (/^(skill_|specialty_)/.test(code)) return S.skills;
  if (/^(disc_|power_|ritual_start|ceremony_start)/.test(code)) return S.disciplines;
  if (/^predator_/.test(code)) return S.predator;
  if (/^(adv_|flaw_|loresheet_|thin_blood_|custom_row|caitiff_status)/.test(code)) return S.advantages;
  if (/^(conviction_|fledgling_|derived_)/.test(code)) return S.humanity;
  if (/^(xp_|ritual_|name_length)/.test(code)) return S.experience;
  return S.identity;
}

/** The forge section of a plain English problem (the chronicle's creation rules answer in those). */
const STRING_SECTIONS = [
  [/^The Storyteller doesn't allow the .+ predator type/, 'predator'],
  [/^The Storyteller doesn't allow .+ characters/, 'age'],
  [/^The Storyteller doesn't allow /, 'clan'],
  [/^This chronicle allows at most \d+ dots of Flaws/, 'advantages'],
  [/^The Storyteller doesn't offer the Humanity 8/, 'humanity'],
];

/**
 * The problems of a 400 from POST /api/characters/: { messages: [translated], bySection:
 * {sectionId: first message} }. Codes ({code, params}) and plain English messages (the chronicle's
 * creation rules) both come out in the active language.
 */
export function serverProblemErrors(problems) {
  const bySection = {};
  const messages = [];
  (Array.isArray(problems) ? problems : []).forEach((p) => {
    let msg;
    let id;
    if (typeof p === 'string' && p.trim()) {
      msg = translateSheetError(p);
      const hit = STRING_SECTIONS.find(([re]) => re.test(p));
      id = V5_SECTION_IDS[hit ? hit[1] : 'identity'];
    } else if (p && typeof p === 'object' && p.code) {
      msg = translateProblem(p);
      id = problemSection(p.code, p.params);
    } else {
      return;
    }
    if (!bySection[id]) bySection[id] = msg;
    if (!messages.includes(msg)) messages.push(msg);
  });
  return { messages, bySection };
}

export function translateSheetError(msg) {
  if (typeof msg !== 'string' || !msg) return msg;
  for (const [re, fn] of PATTERNS) {
    const m = msg.match(re);
    if (m) return fn(m);
  }
  return msg;
}

/** Same, for every value of a { sectionId: message } map. */
export function translateSheetErrors(map) {
  const out = {};
  Object.entries(map || {}).forEach(([k, v]) => {
    out[k] = translateSheetError(v);
  });
  return out;
}

export default translateSheetError;
