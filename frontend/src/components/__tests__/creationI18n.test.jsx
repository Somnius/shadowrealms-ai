import { act, render, screen } from '@testing-library/react';
import CharacterCreationWizard from '../CharacterCreationWizard';
import CharacterSheetModal from '../CharacterSheetModal';
import { setLanguage } from '../../i18n';
import { translateSheetError } from '../../characterSheet/i18nErrors';
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
});
