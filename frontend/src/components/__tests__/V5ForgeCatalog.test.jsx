import { act, fireEvent, render, screen, within } from '@testing-library/react';
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
    expect(screen.getByRole('img', { name: 'Beautiful: 2 dots' })).toHaveTextContent('●●'); // fixed rating
    add('Merit');
    expect(within(screen.getByLabelText('Merit 2')).getByRole('option', { name: 'Beautiful (2)' })).toBeDisabled();
  });

  test('Caitiff start with Suspect and are offered no Status', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Caitiff');
    expect(document.querySelector('[data-clan-flaw="flaw:suspect"]')).toHaveTextContent('Suspect');
    // a house ruling (V5.md §4 step 11), said as a plain rule
    expect(document.querySelector('[data-clan-flaw="flaw:suspect"]')).toHaveTextContent(
      'Caitiff start with it (core p. 107). It counts toward your 2 Flaw dots.'
    );
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
    fireEvent.click(screen.getByRole('checkbox', { name: 'Level 1: The Ashen Mask' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Level 3: The White Mask' }));
    expect(screen.getByText('4 dots')).toBeInTheDocument();
    expect(screen.getByText(/Test level 3 of Harbingers of Ashur\./)).toBeInTheDocument();
    expect(count()).toHaveTextContent('Advantages 4/7');
  });

  test('more than one loresheet at creation (a house ruling), each sheet once', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    expect(screen.getByText(/This app lets you take more than one at creation, a house ruling/)).toBeInTheDocument();
    add('Loresheet');
    pick(screen.getByLabelText('Loresheet 1'), 'loresheet:harbingers-of-ashur');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Level 1: The Ashen Mask' }));
    add('Loresheet');
    const second = screen.getByLabelText('Loresheet 2');
    expect(within(second).getByRole('option', { name: /^Harbingers of Ashur/ })).toBeDisabled();
    pick(second, 'loresheet:the-bahari');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Level 2: Ritual Scarification' }));
    expect(count()).toHaveTextContent('Advantages 3/7');
    add('Loresheet');
    expect(within(screen.getByLabelText('Loresheet 3')).getByRole('option', { name: /^The Bahari/ })).toBeDisabled();
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

  test('what the predator type gives is not offered again', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    pick(document.getElementById('v5-field-predator'), 'Grim Reaper'); // Prey Exclusion (healthy mortals)
    add('Flaw');
    expect(within(screen.getByLabelText('Flaw 1')).getByRole('option', { name: 'Prey Exclusion (1)' })).toBeDisabled();
  });

  test('rows typed before the catalog loaded move over to the dropdowns', () => {
    applyV5Catalog(null);
    const view = renderForge();
    pick(screen.getAllByPlaceholderText('Name')[0], 'Allies (police)');
    pick(screen.getAllByTitle('Points (+ merit / − flaw)')[0], '2');
    act(() => {
      applyV5Catalog(fixture);
    });
    view.rerender(<V5CharacterCreationWizard token="x" campaigns={campaigns} campaignId="2" onCampaignChange={() => {}} />);
    expect(screen.getByLabelText('Background 1')).toHaveValue('background:allies');
    expect(screen.getByLabelText('Background 1 note')).toHaveValue('police');
    expect(count()).toHaveTextContent('Advantages 2/7');
  });

  test('a thin-blood Flaw greys out the Merit it rules out (core p. 183)', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Thin-blood');
    pick(screen.getByLabelText('Thin-blood Flaw 1'), 'Dead Flesh');
    expect(within(screen.getByLabelText('Thin-blood Merit 1')).getByRole('option', { name: 'Lifelike' })).toBeDisabled();
    expect(within(screen.getByLabelText('Thin-blood Merit 1')).getByRole('option', { name: 'Day Drinker' })).not.toBeDisabled();
  });

  test('"any Mythic Flaw" from a predator type asks which one', () => {
    const mythic = {
      ...fixture.advantages.find((a) => a.id === 'flaw:prey-exclusion'),
      id: 'flaw:stake-bait', name: 'Stake Bait', group: 'Mythic', dots: { min: 2, max: 2 },
      desc: { en: 'Test text for Stake Bait.', el: 'Κείμενο δοκιμής.' },
    };
    applyV5Catalog({
      ...fixture,
      advantages: [...fixture.advantages, mythic],
      predator_types: fixture.predator_types.map((p) =>
        p.id === 'predator:montero' ? { ...p, flaws: [{ pick: 'all', options: [{ id: 'flaw:mythic', dots: 2, note: 'any Mythic Flaw', group: true }] }] } : p
      ),
    });
    renderForge();
    pick(document.getElementById('v5-field-predator'), 'Montero');
    const which = screen.getByLabelText('Which Mythic Flaw');
    pick(which, 'flaw:stake-bait');
    expect(screen.getByText(/Test text for Stake Bait\./)).toBeInTheDocument();
    expect(document.getElementById('v5-predator-rows')).toHaveTextContent('Mythic: Stake Bait ●●');
    applyV5Catalog(fixture);
  });

  test('the predator type\'s rows show in the step with their catalog names', () => {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    pick(document.getElementById('v5-field-predator'), 'Grim Reaper');
    expect(document.getElementById('v5-predator-rows')).toHaveTextContent('Prey Exclusion (healthy mortals) ●');
  });
});

test('a catalog ritual bought with XP keeps its own level', () => {
  applyV5Catalog({
    ...fixture,
    disciplines: [...fixture.disciplines, { id: 'discipline:blood-sorcery', name: 'Blood Sorcery', powers: [] }],
  });
  try {
    renderForge();
    pick(document.getElementById('v5-field-clan'), 'Caitiff');
    pick(screen.getByLabelText('Discipline at 2 dots'), 'Blood Sorcery');
    pick(screen.getByLabelText('What to buy'), 'ritual');
    const level = screen.getByLabelText('Ritual level');
    expect(level).not.toBeDisabled();
    pick(screen.getByLabelText('Ritual name'), 'Blood Walk');
    expect(level).toBeDisabled();
    expect(level).toHaveValue('1');
    fireEvent.click(screen.getByRole('button', { name: /^Buy/ }));
    expect(screen.getByRole('list', { name: 'Bought with XP' })).toHaveTextContent('Ritual: Blood Walk, Level 1');
  } finally {
    applyV5Catalog(fixture);
  }
});

describe("the chronicle's allowed books (Forge v2)", () => {
  const COREBOOK = { allowed_books: ['v5-corebook'] };
  const forge = (creation_settings) => (
    <V5CharacterCreationWizard
      token="x"
      campaigns={[{ ...campaigns[0], creation_settings }]}
      campaignId="2"
      onCampaignChange={() => {}}
    />
  );

  test('only entries from the allowed books are offered', () => {
    const { rerender } = render(forge(null));
    pick(document.getElementById('v5-field-clan'), 'Ventrue');
    fireEvent.click(screen.getByRole('button', { name: '+ Add Merit' }));
    expect(within(screen.getByLabelText('Merit 1')).getByRole('option', { name: /City Secrets/ })).toBeInTheDocument();
    rerender(forge(COREBOOK));
    expect(within(screen.getByLabelText('Merit 1')).queryByRole('option', { name: /City Secrets/ })).toBeNull();
    expect(within(document.getElementById('v5-field-clan')).queryByRole('option', { name: /Hecata/ })).toBeNull();
    const pred = document.getElementById('v5-field-predator');
    expect(within(pred).queryByRole('option', { name: /Grim Reaper|Montero/ })).toBeNull();
    expect(within(pred).getByRole('option', { name: 'Osiris' })).toBeInTheDocument();
    pick(screen.getByLabelText('Discipline at 2 dots'), 'Dominate');
    const p1 = screen.getByLabelText('Dominate power 1');
    expect(within(p1).queryByRole('option', { name: /Implant Suggestion/ })).toBeNull();
    expect(within(p1).getByRole('option', { name: 'Cloud Memory (level 1)' })).toBeInTheDocument();
  });

  test("a Caitiff is offered Disciplines from the chronicle's books; a pick from another stays", () => {
    // the fixture's Disciplines have no book: give Oblivion the Players Guide's for this test
    applyV5Catalog({ ...fixture, disciplines: fixture.disciplines.map((d) => (d.name === 'Oblivion' ? { ...d, book: 'v5-players-guide' } : d)) });
    try {
      const { rerender } = render(forge(null));
      pick(document.getElementById('v5-field-clan'), 'Caitiff');
      pick(screen.getByLabelText('Discipline at 1 dot'), 'Oblivion');
      rerender(forge(COREBOOK));
      expect(screen.getByLabelText('Discipline at 1 dot')).toHaveValue('Oblivion');
      expect(within(screen.getByLabelText('Discipline at 2 dots')).queryByRole('option', { name: 'Oblivion' })).toBeNull();
      expect(within(screen.getByLabelText('Discipline at 2 dots')).getByRole('option', { name: 'Auspex' })).toBeInTheDocument();
    } finally {
      applyV5Catalog(fixture);
    }
  });

  test('a chosen entry from a book left out stays, marked, and the check says why', () => {
    // jsdom has no scrollIntoView (the forge scrolls to the first section with an error)
    Element.prototype.scrollIntoView = jest.fn();
    const { rerender } = render(forge(null));
    pick(document.getElementById('v5-field-clan'), 'Hecata');
    pick(document.getElementById('v5-field-predator'), 'Grim Reaper');
    rerender(forge(COREBOOK));
    expect(document.getElementById('v5-field-clan')).toHaveValue('Hecata');
    expect(screen.getByRole('option', { name: 'Hecata (not in this chronicle)' })).toBeDisabled();
    expect(document.getElementById('v5-field-predator')).toHaveValue('Grim Reaper');
    expect(screen.getAllByRole('option', { name: 'Grim Reaper (not in this chronicle)' })[0]).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Create character' }));
    expect(screen.getByText("Hecata comes from a book this chronicle doesn't use (Players Guide).")).toBeInTheDocument();
    delete Element.prototype.scrollIntoView;
  });
});
