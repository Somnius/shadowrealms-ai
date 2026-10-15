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

test('a power above a lowered rating stays visible so its error makes sense', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Ventrue');
  pick(screen.getByLabelText('Discipline at 1 dot'), 'Dominate');
  pick(document.getElementById('v5-field-predator'), 'Montero');
  pick(document.getElementById('v5-field-predator-discipline'), 'Dominate');
  pick(screen.getByLabelText('Dominate power 1'), 'Mesmerize');
  pick(document.getElementById('v5-field-predator'), 'Grim Reaper'); // Dominate drops back to 1
  expect(screen.getByLabelText('Dominate power 1')).toHaveValue('Mesmerize');
});

describe('Advantages from the catalog (Forge v2 part C)', () => {
  const add = (kind) => fireEvent.click(screen.getByRole('button', { name: `+ Add ${kind}` }));
  const count = () => document.getElementById('v5-advantages-count');

  test('a Background from the grouped list: its rating, note, description and page', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    add('Background');
    const sel = screen.getByLabelText('Background 1');
    expect(within(sel).queryByRole('option', { name: /^Loresheets/ })).toBeNull(); // its own section
    expect(sel.querySelector('optgroup[label="Allies"]')).not.toBeNull();
    pick(sel, 'background:allies');
    const dots = screen.getByLabelText('Allies dots');
    expect(within(dots).getAllByRole('option')).toHaveLength(6); // up to 6 in one Ally
    pick(dots, '3');
    pick(screen.getByLabelText('Background 1 note'), 'police');
    expect(screen.getByText(/Test text for Allies\./)).toBeInTheDocument();
    expect(count()).toHaveTextContent('Advantages 3/7');
  });

  test('the clan filters the list; a non-repeatable Merit is offered once', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Ventrue');
    add('Merit');
    const sel = screen.getByLabelText('Merit 1');
    expect(within(sel).queryByRole('option', { name: /Iron Gullet/ })).toBeNull();
    expect(within(sel).queryByRole('option', { name: /Mark of Caine|All Access|Blood Empathy|Day Drinker/ })).toBeNull();
    pick(sel, 'merit:beautiful');
    expect(screen.getByLabelText('Beautiful dots')).toHaveTextContent('●●'); // fixed rating
    add('Merit');
    expect(within(screen.getByLabelText('Merit 2')).getByRole('option', { name: 'Beautiful (2)' })).toBeDisabled();
  });

  test('Caitiff start with Suspect and are offered no Status', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Caitiff');
    expect(document.querySelector('[data-clan-flaw="flaw:suspect"]')).toHaveTextContent('Suspect');
    expect(count()).toHaveTextContent('Flaws 1 (min 2)');
    add('Background');
    expect(within(screen.getByLabelText('Background 1')).queryByRole('option', { name: /^Status/ })).toBeNull();
    expect(screen.getByText("Caitiff can't buy positive Status at creation.")).toBeInTheDocument();
  });

  test('a loresheet: the levels taken cost their numbers in Advantage dots', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    add('Loresheet');
    const sel = screen.getByLabelText('Loresheet 1');
    expect(within(sel).queryByRole('option', { name: /Hardestadt/ })).toBeNull(); // Ventrue only
    pick(sel, 'loresheet:harbingers-of-ashur');
    fireEvent.click(screen.getByRole('checkbox', { name: /The Ashen Mask/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /The White Mask/ }));
    expect(screen.getByText('4 dots')).toBeInTheDocument();
    expect(screen.getByText(/Test level 3 of Harbingers of Ashur\./)).toBeInTheDocument();
    expect(count()).toHaveTextContent('Advantages 4/7');
  });

  test('a custom row for anything the catalog lacks', () => {
    renderForge();
    add('Flaw');
    pick(screen.getByLabelText('Flaw 1'), 'custom');
    pick(screen.getByLabelText('Flaw 1 name'), 'Hunted by a Lasombra');
    pick(screen.getByLabelText('Hunted by a Lasombra dots'), '2');
    expect(screen.getByText(/your Storyteller has to approve it/)).toBeInTheDocument();
    expect(count()).toHaveTextContent('Flaws 2 (min 2)');
  });

  test('thin-bloods pick their Merits and Flaws from the catalog', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Thin-blood');
    const merit = screen.getByLabelText('Thin-blood Merit 1');
    expect(within(merit).getAllByRole('option').map((o) => o.textContent)).toEqual(['Choose…', 'Day Drinker', 'Lifelike']);
    pick(merit, 'Day Drinker');
    expect(screen.getByText(/Test text for Day Drinker\./)).toBeInTheDocument();
  });

  test('the predator type\'s rows show in the step with their catalog names', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    pick(document.getElementById('v5-field-predator'), 'Grim Reaper');
    expect(document.getElementById('v5-predator-rows')).toHaveTextContent('Prey Exclusion (healthy mortals) ●');
  });
});
