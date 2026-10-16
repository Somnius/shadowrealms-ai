/**
 * A ghoul's read-only sheet (V5GhoulSheetView, through CharacterSheetModal) and a vampire's
 * Retainers block with the "Add a ghoul retainer" button for its owner.
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import CharacterSheetModal from '../CharacterSheetModal';
import V5GhoulSheetView from '../V5GhoulSheetView';
import fixture from '../../characterSheet/v5/__fixtures__/creation-cases.json';
import { DARIUS, miraSheet } from '../../characterSheet/v5/__fixtures__/ghoulFixtures';
import { buildGhoulPayload } from '../../characterSheet/v5/ghoul';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';

beforeAll(() => applyV5Catalog(fixture.catalog));
afterAll(() => applyV5Catalog(null));

const mira = (over = {}) => ({
  id: 30,
  name: 'Mira Tanis',
  user_id: 3,
  campaign_id: null,
  system_type: 'vampire',
  rules_edition: 'v5',
  sheet_kind: 'ghoul',
  background: 'Former television executive.',
  ...buildGhoulPayload(miraSheet(), DARIUS),
  merits_flaws: { notes: 'Resources 0: in debt.' },
  domitor: { id: 17, name: 'Darius Vale', clan: 'Ventrue', campaign_id: null, campaign_name: null, exists: true },
  ...over,
});

test('identity, the domitor as a link, the template and no Hunger or Blood Potency', () => {
  const open = jest.fn();
  render(<V5GhoulSheetView character={mira()} onOpenSheet={open} />);
  fireEvent.click(screen.getByRole('button', { name: 'Darius Vale' }));
  expect(open).toHaveBeenCalledWith(17);
  expect(screen.getByText('Gifted mortal · Retainers •••')).toBeInTheDocument();
  expect(screen.getByText('55 / 53')).toBeInTheDocument();
  expect(screen.queryByText(/^Hunger/)).toBeNull();
  expect(screen.queryByText(/^Blood Potency \d/)).toBeNull();
  expect(screen.getByText(/Humanity 7/)).toBeInTheDocument();
  expect(screen.getByText('Resources 0: in debt.')).toBeInTheDocument();
});

test('the ghoul power, the Bond not set, the Bond Flaws and the feeding note (no vitae track)', () => {
  render(<V5GhoulSheetView character={mira()} />);
  const power = document.querySelector('[data-ghoul-power]');
  expect(power).toHaveTextContent('Dominate (counts as 1 dot) · Cloud Memory');
  const bond = document.querySelector('[data-bond="0"]');
  expect(within(bond).getByText('Darius Vale')).toBeInTheDocument();
  expect(within(bond).getByText('Bond Strength not set (the Storyteller sets it)')).toBeInTheDocument();
  expect(screen.getByText('Two Masters · Bondslave')).toBeInTheDocument();
  expect(screen.getByText('Blood Bond & feeding')).toBeInTheDocument();
  expect(screen.getByText("A Rouse Check's worth of Darius's Blood about once a month.")).toBeInTheDocument();
  expect(screen.getByText(/No vitae track, no Hunger/)).toBeInTheDocument();
  expect(screen.queryByText(/^Vitae$|Last vitae/)).toBeNull();
});

test('a sheet from before the rename (wod_meta.ghoul.vitae) still shows its note', () => {
  const old = mira();
  old.wod_meta.ghoul.vitae = { last: 'early October', note: 'old key' };
  delete old.wod_meta.ghoul.feeding;
  render(<V5GhoulSheetView character={old} />);
  expect(screen.getByText('early October')).toBeInTheDocument();
  expect(screen.getByText('old key')).toBeInTheDocument();
});

test('a domitor whose sheet is gone keeps its name', () => {
  render(<V5GhoulSheetView character={mira({ domitor: { id: 17, name: 'Darius Vale', exists: false } })} onOpenSheet={() => {}} />);
  expect(screen.getByText('(sheet no longer exists)')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Darius Vale' })).toBeNull();
});

test('the sheet modal shows "Ghoul of" and no saved points for a ghoul', () => {
  render(<CharacterSheetModal character={mira()} onClose={() => {}} />);
  expect(screen.getByText('Ghoul of Darius Vale')).toBeInTheDocument();
  expect(screen.getByText(/Ghoul sheet, V5/)).toBeInTheDocument();
  expect(screen.queryByText(/Saved points/i)).toBeNull();
});

const dariusSheet = { ...DARIUS, attributes: {}, skills: {}, retainers: [{ id: 30, name: 'Mira Tanis', portrait_url: null, template: 'gifted', retainer_dots: 3, is_active: true }] };

test("a vampire's Retainers: each opens its sheet; the owner may add one", () => {
  const open = jest.fn();
  const add = jest.fn();
  render(<CharacterSheetModal character={dariusSheet} onClose={() => {}} onOpenSheet={open} onAddGhoul={add} viewerId={3} />);
  const row = document.querySelector('[data-retainer="30"]');
  expect(row).toHaveTextContent('Mira Tanis Gifted mortal · Retainers •••');
  fireEvent.click(within(row).getByRole('button', { name: 'Open sheet' }));
  expect(open).toHaveBeenCalledWith(30);
  fireEvent.click(screen.getByRole('button', { name: 'Add a ghoul retainer' }));
  expect(add).toHaveBeenCalledWith(17);
});

test('the Storyteller reading the sheet sees the Retainers, without the add button', () => {
  render(<CharacterSheetModal character={dariusSheet} onClose={() => {}} onOpenSheet={() => {}} onAddGhoul={() => {}} viewerId={2} />);
  expect(screen.getByText('Mira Tanis')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add a ghoul retainer' })).toBeNull();
});
