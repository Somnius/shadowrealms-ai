/**
 * Shared V5 creation test vectors (docs/rules/v5/tests/creation-cases.json, copied here as
 * __fixtures__/creation-cases.json): the client validator must agree with the codes the server
 * validator (backend/services/v5_chargen.py, backend/tests/unit/test_v5_chargen.py) reports.
 *
 * Regenerate after changing __fixtures__/creationCaseDefs.js or buildV5Payload:
 *   WRITE_CREATION_CASES=1 ./scripts/run-frontend-tests.sh src/characterSheet/v5/creationCases
 * then `python3 scripts/v5_creation_cases.py sync` (copies the fixture to docs/).
 */
import fs from 'fs';
import path from 'path';
import fixture from './__fixtures__/creation-cases.json';
import { buildCases, formatCasesFile, storedCase } from './__fixtures__/creationCaseDefs';
import { applyV5Catalog } from './rulesData';
import { validateV5Sheet } from './validation';
import { validateGhoulSheet } from './ghoul';
import { normalizeCreationSettings } from './creationSettings';

/** Client messages (validation.js, ghoul.js) -> the server's problem codes. */
const CODES = [
  // the ghoul forge (ghoul.js validateGhoulSheet; backend/services/v5_ghoul_chargen.py)
  [/^Choose a template for the ghoul\.$/, 'ghoul_template'],
  [/^Choose the ghoul's domitor\.$/, 'ghoul_domitor'],
  [/^No Retainers rating buys a Deadly mortal\.$/, 'ghoul_retainer_dots'],
  [/^A .+ ghoul takes Retainers \d+; the domitor pays \d+\.$/, 'ghoul_retainer_dots'],
  [/^Attributes don't match the .+ spread\.$/, 'ghoul_attr_spread'],
  [/^Skills don't match the .+ template: .+\.$/, 'skill_dist'],
  [/^The .+ template gives \d+ specialties here/, 'ghoul_specialty_count'],
  [/^A ghoul starts with exactly one level-1 power/, 'ghoul_power_count'],
  [/^.+ is not one of the domitor's Disciplines\.$/, 'ghoul_power_discipline'],
  [/^.+: a ghoul's power is level 1\.$/, 'ghoul_power_level'],
  [/^The domitor doesn't have .+: the first power is one the domitor has\.$/, 'ghoul_power_not_domitors'],
  [/^The .+ template allows at most \d+ dots of Flaws/, 'ghoul_flaws_over'],
  [/^.+ is not open to ghouls: .+\.$/, 'ghoul_adv_restricted'],
  [/^The .+ template has \d+ specialties of its own/, 'ghoul_template_specialty'],
  [/^The Gifted mortal template's specialty goes on one of its Skills at 4\.$/, 'ghoul_template_specialty'],
  [/^A ghoul has one Blood Bond, to the domitor/, 'ghoul_bonds'],
  [/^Bond Strength is 0–\d+\.$/, 'ghoul_bonds'],
  [/^A second Blood Bond needs the Two Masters Flaw\.$/, 'ghoul_bonds'],
  [/^Character name is required\.$/, 'name_missing'],
  [/^Choose a clan\.$/, 'clan_missing'],
  [/^Choose an age\.$/, 'age_missing'],
  [/^.+s are generation \d+–\d+\.$/, 'age_generation'],
  [/^Thin-bloods are 14th–16th generation\.$/, 'thin_blood_generation'],
  [/^14th–16th generation vampires are thin-bloods\.$/, 'generation_thin_blood'],
  [/^Attributes start between 1 and 4 at creation\.$/, 'attr_range'],
  [/^Attributes must be one at 4, three at 3, four at 2 and one at 1\.$/, 'attr_spread'],
  [/^Choose a skill distribution\.$/, 'skill_dist'],
  [/^.+: no skill above \d+ at creation\.$/, 'skill_dist'],
  [/^.+ needs exactly .+\.$/, 'skill_dist'],
  [/^You have \d+ free specialties/, 'specialty_count'],
  [/^Each specialty needs a skill\.$/, 'specialty_skill'],
  [/^Name the .+ specialty\.$/, 'specialty_name'],
  [/^.+ needs at least one dot for a specialty\.$/, 'specialty_skill'],
  [/^.+ comes with a free specialty — name it\.$/, 'specialty_missing'],
  [/^.+ already has the .+ specialty\.$/, 'specialty_duplicate'],
  [/^Thin-bloods start with no Disciplines\.$/, 'disc_thin_blood'],
  [/^Pick two (clan )?Disciplines: one at 2 dots and one at 1 dot\.$/, 'disc_pick'],
  [/^Pick two different Disciplines\.$/, 'disc_pick'],
  [/^One Discipline at 2 dots and one at 1 dot\.$/, 'disc_pick'],
  [/^.+ is not a .+ clan Discipline\.$/, 'disc_clan'],
  [/^.+: .+ is taken twice\.$/, 'power_duplicate'],
  [/^.+ is not a .+ power\.$/, 'power_unknown'],
  [/^.+ is a level \d+ power; .+ is at \d+\.$/, 'power_level'],
  [/^.+ also needs .+ \d+\.$/, 'power_amalgam'],
  [/^.+ needs .+ first\.$/, 'power_prereq'],
  [/^.+ is only for ancillae or older\.$/, 'adv_requires'],
  [/^.+ is only for .+\.$/, 'power_clan'],
  [/^The .+ ritual needs the .+ power\.$/, 'ritual_prereq'],
  [/^Choose a predator type\.$/, 'predator_missing'],
  [/^.+ cannot take the .+ predator type\.$/, 'predator_forbidden'],
  [/^Pick the predator type specialty\.$/, 'predator_specialty'],
  [/^Pick the predator type Discipline\.$/, 'predator_discipline'],
  [/^.+: (choose one of|share \d+ dots between|choose the dots for|choose which) /, 'predator_grant'],
  [/^.+ is for ancillae only\.$/, 'predator_ancilla'],
  [/^.+ needs Blood Potency \d+ or less\.$/, 'predator_bp'],
  [/^Advantages: at most \d+ dots/, 'adv_over'],
  [/^Take at least \d+ dots of Flaws/, 'flaw_under'],
  [/^Each Advantage or Flaw is 1–5 dots\.$/, 'adv_dots_range'],
  [/^Thin-bloods take \d+–\d+ thin-blood Merits/, 'thin_blood_merits'],
  [/^Take as many thin-blood Flaws as thin-blood Merits/, 'thin_blood_merits'],
  [/^This age has no starting experience to spend\.$/, 'xp_none'],
  [/^.+ can't go above \d+ dots\.$/, 'xp_max_dots'],
  [/^Names are at most \d+ characters\.$/, 'name_length'],
  [/^Name each ritual bought with XP\.$/, 'xp_log'],
  [/^Rituals are level 1 to 5\.$/, 'xp_log'],
  [/^A level \d+ ritual needs Blood Sorcery \d+/, 'ritual_blood_sorcery'],
  [/^.+ is a level \d+ ritual\.$/, 'ritual_level'],
  [/^One XP purchase is not something this step can buy\.$/, 'xp_log'],
  [/^Starting experience overspent/, 'xp_over'],
  [/^At most \d+ rituals/, 'ritual_count'],
  [/^The Storyteller doesn't allow the .+ predator type in this chronicle\.$/, 'predator_not_allowed'],
  [/^The Storyteller doesn't allow .+ characters in this chronicle\.$/, 'age_not_allowed'],
  [/^The Storyteller doesn't allow .+ in this chronicle\.$/, 'clan_not_allowed'],
  [/^This chronicle allows at most \d+ dots of Flaws of your own/, 'flaw_over'],
  [/^The Storyteller doesn't offer the Humanity 8 fledgling start/, 'fledgling_not_allowed'],
  [/^.+ comes from a book this chronicle doesn't use \(.+\)\.$/, 'book_not_allowed'],
  [/^Write \d+–\d+ Convictions, each with a Touchstone\.$/, 'conviction_count'],
  [/^Each Conviction needs a Touchstone \(and vice versa\)\.$/, 'conviction_pairs'],
  // Catalog Advantage rows (forge v2 C advantages step); the client says "can't take" for all three.
  [/^.+ takes .+ dots \(you have \d+\)\.$/, 'adv_dots_range'],
  [/^Pick at least one level of .+\.$/, 'loresheet_levels'],
  [/^.+ can't take .+ at creation\.$/, ['adv_restricted', 'loresheet_restricted', 'caitiff_status']],
  [/^.+ can be taken (only once|at most \d+ times)\.$/, 'adv_repeat'],
  [/^.+ needs .+ at \d+ dots or more\.$/, 'adv_requires'],
  [/^.+ needs .+ on the sheet\.$/, 'adv_requires'],
  [/^.+ and .+ can't be taken together\.$/, 'adv_excluded'],
];

/** The server codes a client message stands for. */
const codesOf = (msg) => {
  const hit = CODES.find(([re]) => re.test(msg));
  return hit ? [].concat(hit[1]) : [`unmapped: ${msg}`];
};

const clientMessages = (c) =>
  Object.values(
    c.kind === 'ghoul'
      ? validateGhoulSheet(c.sheet, c.domitor, normalizeCreationSettings(c.settings))
      : validateV5Sheet(c.sheet, undefined, normalizeCreationSettings(c.settings))
  );

beforeAll(() => applyV5Catalog(fixture.catalog));
afterAll(() => applyV5Catalog(null));

const FILE = path.join(__dirname, '__fixtures__', 'creation-cases.json');
// Built on import, with the fixture's catalog (the forge's rules registry is module state).
applyV5Catalog(fixture.catalog);
const CASES = buildCases();
applyV5Catalog(null);

test('the fixture is current (cases built from the definitions with buildV5Payload)', () => {
  const text = formatCasesFile({ ...fixture, cases: CASES.map(storedCase) });
  if (process.env.WRITE_CREATION_CASES === '1') {
    fs.writeFileSync(FILE, text);
    return;
  }
  expect(fixture.cases).toEqual(CASES.map(storedCase));
  expect(fs.readFileSync(FILE, 'utf8')).toBe(text);
});

test('there are enough cases, valid and invalid, with unique names', () => {
  expect(CASES.length).toBeGreaterThanOrEqual(40);
  expect(CASES.filter((c) => !c.expect.length).length).toBeGreaterThanOrEqual(10);
  expect(new Set(CASES.map((c) => c.name)).size).toBe(CASES.length);
  const ghouls = CASES.filter((c) => c.kind === 'ghoul');
  expect(ghouls.length).toBeGreaterThanOrEqual(11);
  expect(ghouls.filter((c) => !c.expect.length).length).toBeGreaterThanOrEqual(5);
});

describe.each(CASES.filter((c) => c.client).map((c) => [c.name, c]))('client agrees: %s', (_name, c) => {
  test('same verdict and codes', () => {
    const messages = clientMessages(c);
    if (!c.expect.length) {
      expect(messages).toEqual([]);
      return;
    }
    // The client keeps one message per section, so it may report fewer problems, never others.
    expect(messages.length).toBeGreaterThan(0);
    messages.forEach((m) => {
      const codes = codesOf(m);
      expect([m, codes.find((code) => c.expect.includes(code)) || codes]).toEqual([m, expect.any(String)]);
    });
  });
});
