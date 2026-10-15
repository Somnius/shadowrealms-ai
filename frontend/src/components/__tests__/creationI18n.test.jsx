import { act, fireEvent, render, screen } from '@testing-library/react';
import CharacterCreationWizard from '../CharacterCreationWizard';
import CharacterSheetModal from '../CharacterSheetModal';
import { setLanguage } from '../../i18n';
import { problemSection, serverProblemErrors, translateProblem, translateSheetError } from '../../characterSheet/i18nErrors';
import creationCases from '../../characterSheet/v5/__fixtures__/creation-cases.json';
import { validateV5Attributes } from '../../characterSheet/v5/validation';

const classic = [{ id: 1, name: 'Night', game_system: 'vampire', rules_edition: 'classic' }];
const v5 = [{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5' }];

afterEach(async () => {
  await act(() => setLanguage('en', { remember: false, save: false }));
});

test('classic and V5 forges render in Greek, game terms stay English', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  const { unmount } = render(<CharacterCreationWizard token="x" campaigns={classic} />);
  expect(screen.getByText('Σφυρηλάτηση φύλλου χαρακτήρα')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Δημιουργία χαρακτήρα' })).toBeInTheDocument();
  // Game term label with a Greek explanation as the tooltip.
  const gen = screen.getAllByText('Generation')[0];
  expect(gen).toHaveAttribute('lang', 'en');
  expect(gen.getAttribute('title')).toMatch(/Caine/);
  unmount();

  render(<CharacterCreationWizard token="x" campaigns={v5} />);
  expect(screen.getByText('Σφυρηλάτηση φύλλου χαρακτήρα · V5')).toBeInTheDocument();
  // V5 starts with the choice between the guide and the full forge
  expect(screen.getByRole('button', { name: 'Με οδηγό' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Πλήρης σφυρηλάτηση' }));
  expect(screen.getByLabelText('Όνομα χαρακτήρα')).toBeInTheDocument();
});

test('validation messages are translated by shape, unknown ones pass through', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  const msg = validateV5Attributes({});
  expect(typeof msg).toBe('string');
  expect(translateSheetError(msg)).not.toBe(msg);
  expect(translateSheetError('Pick two different Disciplines.')).toBe('Διάλεξε δύο διαφορετικά Disciplines.');
  expect(translateSheetError('Brand new message.')).toBe('Brand new message.');
});

test('sheet modal renders in Greek', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  render(<CharacterSheetModal character={{ name: 'Ada', system_type: 'vampire', wod_meta: { clan: 'Brujah' } }} onClose={() => {}} />);
  expect(screen.getByRole('button', { name: 'Κλείσιμο' })).toBeInTheDocument();
  expect(screen.getByText('Ταυτότητα')).toBeInTheDocument();
});

test('starting experience messages are translated', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  [
    'This age has no starting experience to spend.',
    "Strength can't go above 5 dots.",
    'Names are at most 100 characters.',
    'Name each ritual bought with XP.',
    'Rituals are level 1 to 5.',
    'One XP purchase is not something this step can buy.',
  ].forEach((msg) => expect(translateSheetError(msg)).not.toBe(msg));
  expect(translateSheetError('A level 3 ritual needs Blood Sorcery 3 (you have 2).')).toBe(
    'Ένα ritual επιπέδου 3 θέλει Blood Sorcery 3 (έχεις 2).'
  );
  expect(translateSheetError('Starting experience overspent: 24 of 15 XP.')).toBe('Ξόδεψες παραπάνω XP: 24 από 15.');
  expect(translateSheetError('At most 12 rituals (you have 13).')).toBe('Το πολύ 12 rituals (έχεις 13).');
  expect(translateSheetError('Brawl already has the Grappling specialty.')).toBe('Το Brawl έχει ήδη την specialty Grappling.');
});

test('server problem codes read as sentences, with English game terms and skill labels', async () => {
  expect(translateProblem({ code: 'adv_over', params: { max: 7, have: 8 } })).toBe('Advantages: at most 7 dots (you have 8).');
  expect(translateProblem({ code: 'specialty_missing', params: { skill: 'academics' } })).toBe(
    'Academics comes with a free specialty — name it.'
  );
  expect(translateProblem({ code: 'skill_dist', params: { distribution: 'jack' } })).toBe(
    "Skills don't match the Jack of all trades distribution."
  );
  expect(translateProblem({ code: 'skill_dist', params: { distribution: '' } })).toBe('Choose a skill distribution.');
  expect(translateProblem({ code: 'power_prereq', params: { power: 'Weaving', needs: 'Rapid Reflexes' } })).toBe(
    'Weaving needs Rapid Reflexes first.'
  );
  expect(translateProblem({ code: 'no_such_code' })).toBe('The sheet breaks a creation rule (no_such_code).');
  await act(() => setLanguage('el', { remember: false, save: false }));
  expect(translateProblem({ code: 'adv_over', params: { max: 9, have: 10 } })).toBe('Advantages: το πολύ 9 τελείες (έχεις 10).');
  expect(translateProblem({ code: 'derived_value', params: { trait: 'blood_potency', have: 3, want: 1 } })).toBe(
    'Το Blood Potency πρέπει να είναι 1, όχι 3.'
  );
  expect(translateProblem({ code: 'age_not_allowed', params: { age: 'ancilla' } })).toBe(
    'Ο Storyteller δεν επιτρέπει χαρακτήρες Ancilla σε αυτό το χρονικό.'
  );
});

test('every code of the shared creation vectors has its own translation in both languages', async () => {
  const codes = [...new Set(creationCases.cases.flatMap((c) => c.expect))];
  expect(codes.length).toBeGreaterThan(40);
  const check = () =>
    codes.forEach((code) => {
      const msg = translateProblem({ code, params: {} });
      expect(msg).not.toMatch(/\(no_such|creation rule \(|κανόνα δημιουργίας \(/);
      expect(msg.length).toBeGreaterThan(10);
    });
  check();
  await act(() => setLanguage('el', { remember: false, save: false }));
  check();
});

test('the forge marks the sections the server refused, first message per section', () => {
  const out = serverProblemErrors([
    { code: 'adv_over', params: { max: 7, have: 8 } },
    { code: 'flaw_under', params: { min: 2, have: 0 } },
    { code: 'attr_spread', params: {} },
    { code: 'ritual_level', params: { name: 'Ward against Ghouls', level: 2, want: 1 } },
    'a plain string problem',
    null,
  ]);
  expect(out.messages).toEqual([
    'Advantages: at most 7 dots (you have 8).',
    'Take at least 2 dots of Flaws (you have 0).',
    'Attributes must be one at 4, three at 3, four at 2 and one at 1.',
    'Ward against Ghouls is a level 1 ritual.',
  ]);
  expect(out.bySection).toEqual({
    'v5-section-advantages': 'Advantages: at most 7 dots (you have 8).',
    'v5-section-attributes': 'Attributes must be one at 4, three at 3, four at 2 and one at 1.',
    'v5-section-experience': 'Ward against Ghouls is a level 1 ritual.',
  });
  // the settings answer of older servers (plain strings) is left to body.error
  expect(serverProblemErrors(["The Storyteller doesn't allow Brujah in this chronicle."]).messages).toEqual([]);
  expect(problemSection('ritual_start')).toBe('v5-section-disciplines');
  expect(problemSection('thin_blood_generation')).toBe('v5-section-age');
  expect(problemSection('thin_blood_merits')).toBe('v5-section-advantages');
});

test('the XP ritual level message from the catalog is translated', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  expect(translateSheetError('Ward against Ghouls is a level 1 ritual.')).toBe('Το Ward against Ghouls είναι ritual επιπέδου 1.');
});
