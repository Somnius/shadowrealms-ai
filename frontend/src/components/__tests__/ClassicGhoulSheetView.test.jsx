/**
 * A Classic ghoul's read-only sheet (ClassicGhoulSheetView, through CharacterSheetModal): the
 * domitor, kind and duties, the Blood Pool boxes (a Classic ghoul has one; a V5 ghoul doesn't), the
 * Blood Bond in drinks, feeding and overdosing; and a Classic vampire's Retainers block.
 */
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import CharacterSheetModal from '../CharacterSheetModal';
import ClassicGhoulSheetView from '../ClassicGhoulSheetView';
import { buildClassicGhoulPayload } from '../../characterSheet/classicGhoul';
import { THEO, martaSheet } from '../../characterSheet/__fixtures__/classicGhoulFixtures';
import { setLanguage } from '../../i18n';

afterEach(async () => {
  await act(() => setLanguage('en', { remember: false, save: false }));
});

const marta = (over = {}) => {
  const payload = buildClassicGhoulPayload(martaSheet({ overdosing: 'Can cram 2 extra (Stamina 2)', feedingLast: 'Sunday' }), THEO);
  return {
    id: 40,
    name: 'Marta Ionescu',
    user_id: 3,
    campaign_id: null,
    rules_edition: 'classic',
    sheet_kind: 'ghoul',
    background: "Theodore's driver since 1998.",
    ...payload,
    merits_flaws: { entries: [{ name: 'Unbondable', points: 3 }] },
    domitor: { id: 21, name: 'Theodore Doukas', clan: 'Ventrue', generation: 12, campaign_id: 12, campaign_name: 'Constantinople', exists: true },
    ...over,
  };
};

test('identity: the domitor as a link, its clan and generation, kind and duties', () => {
  const open = jest.fn();
  render(<ClassicGhoulSheetView character={marta()} onOpenSheet={open} />);
  fireEvent.click(screen.getByRole('button', { name: 'Theodore Doukas' }));
  expect(open).toHaveBeenCalledWith(21);
  expect(screen.getByText('Ventrue, generation 12')).toBeInTheDocument();
  expect(screen.getByText('Vassal')).toBeInTheDocument();
  expect(screen.getByText('Drives, keeps the house')).toBeInTheDocument();
  expect(screen.getByText('51 / 38')).toBeInTheDocument();
});

test('the Blood Pool: 10 boxes, the vitae held filled; the Bond in drinks; feeding and overdosing', () => {
  render(<ClassicGhoulSheetView character={marta()} />);
  const pool = document.querySelector('[data-blood-pool]');
  expect(pool).toHaveAttribute('data-blood-pool', '6');
  expect(pool.querySelectorAll('[data-filled="true"]')).toHaveLength(6);
  expect(pool.querySelectorAll('[data-filled]')).toHaveLength(10);
  expect(screen.getByText('6 / 10 · 1 per turn')).toBeInTheDocument();
  expect(screen.getByText(/No Hunger, no Rouse Checks/)).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Blood Bond: 3 of 3' })).toBeInTheDocument();
  expect(screen.getByText('3 of 3 drinks · fully Bound')).toBeInTheDocument();
  expect(screen.getByText('Third drink in 1998')).toBeInTheDocument();
  expect(screen.getByText('Sunday')).toBeInTheDocument();
  expect(screen.getByText('Can cram 2 extra (Stamina 2)')).toBeInTheDocument();
  // Potence first, then the other Discipline
  const items = [...document.querySelectorAll('#classic-ghoul-view-advantages li')].map((li) => li.textContent);
  expect(items.slice(0, 2)).toEqual(['Potence', 'Dominate']);
});

test('the modal: a Classic ghoul gets its own blocks, then the Classic Attributes and Abilities', () => {
  render(<CharacterSheetModal character={marta()} onClose={() => {}} onOpenSheet={() => {}} viewerId={3} />);
  expect(screen.getByText('Ghoul of Theodore Doukas')).toBeInTheDocument();
  expect(screen.getByText(/Ghoul sheet, Classic \(Revised\)/)).toBeInTheDocument();
  expect(document.querySelector('[data-blood-pool]')).not.toBeNull();
  expect(document.getElementById('view-attr')).not.toBeNull();
  expect(document.getElementById('view-template')).toBeNull(); // no Clan / Generation of its own
  expect(screen.getByText('Unbondable')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add a ghoul retainer' })).toBeNull();
});

test('in Greek', async () => {
  await act(() => setLanguage('el', { remember: false, save: false }));
  render(<ClassicGhoulSheetView character={marta()} />);
  expect(screen.getByText('6 / 10 · 1 ανά γύρο')).toBeInTheDocument();
  expect(screen.getByText('3 από 3 γουλιές · πλήρως δεμένο')).toBeInTheDocument();
  expect(screen.getByText(/Φύλλο ghoul, Classic \(Revised\)/)).toBeInTheDocument();
});

const theoSheet = {
  ...THEO,
  attributes: {},
  skills: {},
  retainers: [{ id: 40, name: 'Marta Ionescu', portrait_url: null, template: null, kind: 'vassal', retainer_dots: null, rules_edition: 'classic', is_active: true }],
};

test("a Classic vampire's Retainers: each opens its sheet; the owner may add one", () => {
  const open = jest.fn();
  const add = jest.fn();
  render(<CharacterSheetModal character={theoSheet} onClose={() => {}} onOpenSheet={open} onAddGhoul={add} viewerId={3} />);
  const row = document.querySelector('[data-retainer="40"]');
  expect(row).toHaveTextContent('Marta Ionescu Vassal');
  fireEvent.click(within(row).getByRole('button', { name: 'Open sheet' }));
  expect(open).toHaveBeenCalledWith(40);
  fireEvent.click(screen.getByRole('button', { name: 'Add a ghoul retainer' }));
  expect(add).toHaveBeenCalledWith(21);
});

test('a Classic vampire read by its Storyteller: Retainers without the add button; a werewolf has none', () => {
  render(<CharacterSheetModal character={{ ...theoSheet, user_id: 3 }} onClose={() => {}} onOpenSheet={() => {}} onAddGhoul={() => {}} viewerId={2} />);
  expect(screen.getByText('Marta Ionescu')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add a ghoul retainer' })).toBeNull();
});

test('a werewolf has no Retainers block', () => {
  render(<CharacterSheetModal character={{ id: 5, name: 'Garou', user_id: 3, system_type: 'werewolf', rules_edition: 'classic', wod_meta: {} }} onClose={() => {}} onAddGhoul={() => {}} viewerId={3} />);
  expect(screen.queryByRole('button', { name: 'Add a ghoul retainer' })).toBeNull();
});
