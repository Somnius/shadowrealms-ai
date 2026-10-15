import { fireEvent, render, screen, within } from '@testing-library/react';
import V5CharacterCreationWizard from '../characterCreation/V5CharacterCreationWizard';
import fixture from '../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';

const campaigns = [{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5' }];
const renderForge = () =>
  render(<V5CharacterCreationWizard token="x" campaigns={campaigns} campaignId="2" onCampaignChange={() => {}} />);
const pick = (el, value) => fireEvent.change(el, { target: { value } });

beforeAll(() => applyV5Catalog(fixture));
afterAll(() => applyV5Catalog(null));

test('the catalog clans are offered, with bane and compulsion', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Hecata');
  expect(screen.getByText(/Painful Kiss/)).toBeInTheDocument();
  expect(screen.getByText(/Morbidity/)).toBeInTheDocument();
});

test('powers are picked from a list by level, with the description under the choice', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Dominate');
  const p1 = screen.getByLabelText('Dominate power 1');
  expect(screen.queryAllByRole('option', { name: /Submerged Directive/ })).toHaveLength(0); // level 3 at Dominate 2
  pick(p1, 'Cloud Memory');
  expect(screen.getByText(/Victim forgets the last moments\./)).toBeInTheDocument();
  expect(screen.getByText('(Corebook, p. 256)')).toBeInTheDocument();
  // the same power can't be taken twice
  expect(screen.getAllByRole('option', { name: 'Cloud Memory (level 1)' })[1]).toBeDisabled();
});

test('a "one of" predator grant is a choice, and a split has number inputs', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Hecata');
  pick(document.getElementById('v5-field-predator'), 'Grim Reaper');
  expect(screen.getByRole('radio', { name: /Allies \(medical community\)/ })).toBeInTheDocument();
  expect(within(document.getElementById('v5-field-predator-discipline')).getByRole('option', { name: 'Oblivion' })).toBeInTheDocument();
  pick(document.getElementById('v5-field-predator'), 'Osiris');
  expect(screen.getByLabelText('Fame dots')).toBeInTheDocument();
  expect(screen.getByLabelText('Herd dots')).toBeInTheDocument();
});

test('Oblivion with The Binding Fetter offers the starting ceremony', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Hecata');
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Oblivion');
  expect(document.getElementById('v5-field-starting-ceremony')).toBeNull();
  pick(screen.getByLabelText('Oblivion power 1'), 'The Binding Fetter');
  const sel = document.getElementById('v5-field-starting-ceremony');
  pick(sel, 'Summon Spirit');
  expect(sel).toHaveValue('Summon Spirit');
});
