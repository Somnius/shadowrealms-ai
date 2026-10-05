/**
 * Validation messages from ./validation.js and ./v5/validation.js are English strings (their tests
 * assert them). The wizards show them through translateSheetError(), which recognises each message
 * shape and returns it in the active language. Unknown messages pass through unchanged.
 * Trait, clan and Discipline names inside the messages stay English (game terms).
 */
import { t } from '../i18n';

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
  [/^One XP purchase is not something this step can buy\.$/, () => t('wizard:validation.v5XpUnknown', 'One XP purchase is not something this step can buy.')],
  [/^Starting experience overspent: (\d+) of (\d+) XP\.$/, (m) => t('wizard:validation.v5XpOver', 'Starting experience overspent: {{spent}} of {{total}} XP.', { spent: m[1], total: m[2] })],
];

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
