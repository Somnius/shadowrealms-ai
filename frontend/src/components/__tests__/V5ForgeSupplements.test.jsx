/**
 * The forge with supplement entries (Forge v2 part F): the jest catalog plus a few entries shaped
 * like the real ones (invented descriptions).
 */
import { fireEvent, render, screen, within } from '@testing-library/react';
import V5CharacterCreationWizard from '../characterCreation/V5CharacterCreationWizard';
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';

const campaigns = [{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5' }];
const renderForge = () =>
  render(<V5CharacterCreationWizard token="x" campaigns={campaigns} campaignId="2" onCampaignChange={() => {}} />);
const pick = (el, value) => fireEvent.change(el, { target: { value } });
const add = (kind) => fireEvent.click(screen.getByRole('button', { name: `+ Add ${kind}` }));
const levels = (names, extra = {}) => names.map((name, i) => ({ dots: i + 1, name, ...(extra[i + 1] || {}) }));

const CATALOG = {
  ...fixture,
  books: [
    ...fixture.books,
    { book_id: 'v5-chicago-by-night', title: 'Chicago by Night', precedence: 50, tier: 2 },
    { book_id: 'v5-la-by-night-loresheets', title: 'L.A. by Night Loresheets', precedence: 50, tier: 2 },
  ],
  clans: [
    ...fixture.clans,
    { id: 'clan:tremere', name: 'Tremere', book: 'v5-corebook', page: 93, disciplines: ['discipline:blood-sorcery', 'discipline:auspex', 'discipline:dominate'] },
  ],
  disciplines: [
    ...fixture.disciplines,
    {
      id: 'discipline:blood-sorcery',
      name: 'Blood Sorcery',
      book: 'v5-corebook',
      page: 271,
      powers: [
        { id: 'power:blood-sorcery:a-taste-for-blood', name: 'A Taste for Blood', level: 1, book: 'v5-corebook', page: 272 },
        { id: 'power:blood-sorcery:koldunic-sorcery', name: 'Koldunic Sorcery', level: 1, book: 'v5-blood-sigils', page: 61, clans_only: ['clan:tzimisce'], repeatable: true, at_first_dot: true },
      ],
    },
  ],
  advantages: [
    ...fixture.advantages,
    { id: 'flaw:ingrained-blunt', name: 'Blunt', kind: 'flaw', group: 'Discipline', dots: null, book: 'v5-tattered-facade', page: 109, requires: "Dominate •••+, Storyteller's consent" },
  ],
  loresheets: [
    ...fixture.loresheets,
    { id: 'loresheet:salvador-garcia', name: 'Salvador Garcia', book: 'v5-anarch', page: 190, source: 'online', levels: levels([null, null, null, null, null]) },
    {
      id: 'loresheet:tegyrius-the-vizier',
      name: 'Tegyrius the Vizier',
      book: 'v5-gehenna-war',
      page: 159,
      levels: levels(['One', 'Two', 'Three', 'Perception is Power', 'Five'], { 4: { restriction: 'Hecata characters only', clans_only: ['clan:hecata'] } }),
    },
    { id: 'loresheet:annabelle', name: 'Annabelle', book: 'v5-chicago-by-night', page: 262, levels: levels(['a', 'b', 'c', 'd', 'e']) },
    { id: 'loresheet:annabelle-la-by-night', name: 'Annabelle', book: 'v5-la-by-night-loresheets', page: 4, levels: levels(['f', 'g', 'h', 'i', 'j']) },
  ],
};

beforeAll(() => applyV5Catalog(CATALOG));
afterAll(() => applyV5Catalog(null));

test('two loresheets of one name show their book', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  add('Loresheet');
  const sel = screen.getByLabelText('Loresheet 1');
  expect(within(sel).getByRole('option', { name: 'Annabelle · Chicago by Night' })).toBeInTheDocument();
  expect(within(sel).getByRole('option', { name: 'Annabelle · L.A. by Night Loresheets' })).toBeInTheDocument();
  expect(within(sel).getByRole('option', { name: 'The Bahari' })).toBeInTheDocument();
});

test('a sheet whose level names our sources lack: "Level N", with the note, still selectable', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  add('Loresheet');
  pick(screen.getByLabelText('Loresheet 1'), 'loresheet:salvador-garcia');
  expect(screen.getByText('(names not in our sources)')).toBeInTheDocument();
  const lv2 = screen.getByRole('checkbox', { name: 'Level 2: Level 2' });
  fireEvent.click(lv2);
  expect(lv2).toBeChecked();
  expect(screen.getByText('2 dots')).toBeInTheDocument();
});

test('a level with its own restriction is not offered to other clans; the rest of the sheet is', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  add('Loresheet');
  pick(screen.getByLabelText('Loresheet 1'), 'loresheet:tegyrius-the-vizier');
  expect(screen.getByRole('checkbox', { name: 'Level 4: Perception is Power' })).toBeDisabled();
  expect(screen.getByRole('checkbox', { name: 'Level 1: One' })).not.toBeDisabled();
  expect(screen.getByText('(Hecata characters only)')).toBeInTheDocument();
});

test('a Flaw the book gives no rating: dots 1–5 and the hint', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  add('Flaw');
  const sel = screen.getByLabelText('Flaw 1');
  expect(within(sel).getByRole('option', { name: 'Blunt (?)' })).toBeInTheDocument();
  pick(sel, 'flaw:ingrained-blunt');
  expect(within(screen.getByLabelText('Blunt dots')).getAllByRole('option')).toHaveLength(5);
  expect(screen.getByText('the book prints no rating: ask your Storyteller')).toBeInTheDocument();
  expect(screen.getByText("Needs: Dominate •••+, Storyteller's consent")).toBeInTheDocument();
});

test('Koldunic Sorcery is not offered to a Tremere', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Tremere');
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Blood Sorcery');
  const p1 = screen.getByLabelText('Blood Sorcery power 1');
  expect(within(p1).getByRole('option', { name: 'A Taste for Blood (level 1)' })).toBeInTheDocument();
  expect(within(p1).queryByRole('option', { name: /Koldunic Sorcery/ })).toBeNull();
});
