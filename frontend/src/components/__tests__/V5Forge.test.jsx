import { fireEvent, render, screen } from '@testing-library/react';
import V5CharacterCreationWizard from '../characterCreation/V5CharacterCreationWizard';

const campaigns = [{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5' }];

const renderForge = () =>
  render(<V5CharacterCreationWizard token="x" campaigns={campaigns} campaignId="2" onCampaignChange={() => {}} />);

const pick = (el, value) => fireEvent.change(el, { target: { value } });

function tremereBagger(predatorDiscipline) {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Tremere');
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Blood Sorcery');
  pick(screen.getByLabelText('Discipline at 1 dot'), 'Auspex');
  pick(document.getElementById('v5-field-predator'), 'Bagger');
  pick(document.getElementById('v5-field-predator-discipline'), predatorDiscipline);
}

test('Tremere Blood Sorcery 2 + Bagger Blood Sorcery shows 3 dots and 3 power inputs', () => {
  tremereBagger('Blood Sorcery');
  const dots = screen.getByRole('group', { name: 'Blood Sorcery: 3 of 5' });
  expect(dots.querySelectorAll('[data-dot="base"]')).toHaveLength(2);
  expect(dots.querySelectorAll('[data-dot="predator"]')).toHaveLength(1);
  expect(screen.getByText('+1 from Bagger')).toBeInTheDocument();
  [1, 2, 3].forEach((n) => expect(screen.getByLabelText(`Blood Sorcery power ${n}`)).toBeInTheDocument());
  expect(screen.queryByLabelText('Blood Sorcery power 4')).toBeNull();
  // Auspex stays at its one creation dot
  expect(screen.getByRole('group', { name: 'Auspex: 1 of 5' })).toBeInTheDocument();
});

test('a predator Discipline outside the picks gets its own row and power input', () => {
  tremereBagger('Obfuscate');
  expect(screen.getByRole('group', { name: 'Blood Sorcery: 2 of 5' })).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Obfuscate: 1 of 5' })).toBeInTheDocument();
  const power = screen.getByLabelText('Obfuscate power 1');
  pick(power, 'Cloak of Shadows');
  expect(screen.getByLabelText('Obfuscate power 1')).toHaveValue('Cloak of Shadows');
});

test('thin-bloods get no Discipline rows', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Thin-blood');
  expect(screen.queryByLabelText('Discipline at 2 dots')).toBeNull();
  expect(screen.getByText('Thin-bloods start with no Disciplines.')).toBeInTheDocument();
});

test('Blood Sorcery shows the optional starting ritual input', () => {
  tremereBagger('Blood Sorcery');
  const input = screen.getByLabelText('Starting ritual (Level 1)');
  pick(input, 'Ward against Ghouls');
  expect(input).toHaveValue('Ward against Ghouls');
});

test('no Blood Sorcery, no starting ritual input', () => {
  renderForge();
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Potence');
  expect(screen.queryByLabelText('Starting ritual (Level 1)')).toBeNull();
});

test('a pick that changes Discipline drops its powers and absorbs the predator row', () => {
  renderForge();
  pick(document.getElementById('v5-field-clan'), 'Tremere');
  pick(screen.getByLabelText('Discipline at 2 dots'), 'Auspex');
  pick(screen.getByLabelText('Discipline at 1 dot'), 'Dominate');
  pick(screen.getByLabelText('Dominate power 1'), 'Cloud Memory');
  pick(document.getElementById('v5-field-predator'), 'Bagger');
  pick(document.getElementById('v5-field-predator-discipline'), 'Blood Sorcery');
  pick(screen.getByLabelText('Blood Sorcery power 1'), 'A Taste for Blood');

  // Dominate → Blood Sorcery: the predator-only row merges into the pick, its power kept
  pick(screen.getByLabelText('Discipline at 1 dot'), 'Blood Sorcery');
  expect(screen.getByRole('group', { name: 'Blood Sorcery: 2 of 5' })).toBeInTheDocument();
  expect(screen.getByLabelText('Blood Sorcery power 1')).toHaveValue('A Taste for Blood');
  expect(screen.getByLabelText('Blood Sorcery power 2')).toHaveValue('');
  expect(screen.queryByDisplayValue('Cloud Memory')).toBeNull();

  // Blood Sorcery → Dominate: the Dominate pick starts empty, not with Blood Sorcery powers
  pick(screen.getByLabelText('Discipline at 1 dot'), 'Dominate');
  expect(screen.getByLabelText('Dominate power 1')).toHaveValue('');
});

test('changing predator type clears the powers typed for its Discipline', () => {
  tremereBagger('Obfuscate');
  pick(screen.getByLabelText('Obfuscate power 1'), 'Cloak of Shadows');
  pick(document.getElementById('v5-field-predator'), 'Alleycat');
  pick(document.getElementById('v5-field-predator'), 'Bagger');
  pick(document.getElementById('v5-field-predator-discipline'), 'Obfuscate');
  expect(screen.getByLabelText('Obfuscate power 1')).toHaveValue('');
});

describe('starting experience step', () => {
  const buyLabel = () => screen.getByRole('button', { name: /^Buy/ });

  test('neonates get 15 XP, childer get no step', () => {
    renderForge();
    expect(screen.getByText('Starting experience')).toBeInTheDocument();
    expect(screen.getByText('Spent 0 of 15 XP · 15 left')).toBeInTheDocument();
    pick(document.getElementById('v5-field-age'), 'childer');
    expect(screen.queryByText('Starting experience')).toBeNull();
    pick(document.getElementById('v5-field-age'), 'ancilla');
    expect(screen.getByText('Spent 0 of 35 XP · 35 left')).toBeInTheDocument();
  });

  test('buys a dot, refuses to overspend, and can undo', () => {
    renderForge();
    pick(screen.getByLabelText('What to buy'), 'attribute');
    pick(screen.getByLabelText('Attribute'), 'strength');
    expect(buyLabel()).toHaveTextContent('Buy (10 XP)');
    fireEvent.click(buyLabel());
    expect(screen.getByText('Spent 10 of 15 XP · 5 left')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Bought with XP' })).toHaveTextContent('Strength 1 → 2');
    // Strength 2 → 3 is 15 more: over budget
    expect(buyLabel()).toHaveTextContent('Buy (15 XP)');
    expect(buyLabel()).toBeDisabled();
    expect(screen.getByText('Starting experience overspent: 25 of 15 XP.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove Strength' }));
    expect(screen.getByText('Spent 0 of 15 XP · 15 left')).toBeInTheDocument();
  });

  test('an XP Discipline dot shows in the Disciplines block', () => {
    renderForge(); // Brujah
    pick(screen.getByLabelText('What to buy'), 'discipline');
    pick(screen.getByLabelText('Discipline'), 'Auspex');
    expect(buyLabel()).toHaveTextContent('Buy (7 XP)');
    fireEvent.click(buyLabel());
    const dots = screen.getByRole('group', { name: 'Auspex: 1 of 5' });
    expect(dots.querySelectorAll('[data-dot="xp"]')).toHaveLength(1);
    expect(screen.getByText('+1 from XP')).toBeInTheDocument();
  });

  test('rituals are offered only with Blood Sorcery, up to its rating', () => {
    renderForge();
    expect(screen.queryByRole('option', { name: 'Ritual' })).toBeNull();
    pick(document.getElementById('v5-field-clan'), 'Tremere');
    pick(screen.getByLabelText('Discipline at 2 dots'), 'Blood Sorcery');
    pick(screen.getByLabelText('What to buy'), 'ritual');
    pick(screen.getByLabelText('Ritual name'), 'Blood Walk');
    pick(screen.getByLabelText('Ritual level'), '2');
    expect(screen.queryByRole('option', { name: 'Level 3' })).toBeNull();
    fireEvent.click(buyLabel());
    expect(screen.getByText('Spent 6 of 15 XP · 9 left')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Bought with XP' })).toHaveTextContent('Ritual: Blood Walk, Level 2');
  });
});

describe('starting experience step: review fixes', () => {
  const buyButton = () => screen.getByRole('button', { name: /^Buy/ });

  test('the running total is a polite live region and the preview error an alert', () => {
    renderForge();
    expect(document.getElementById('v5-xp-count')).toHaveAttribute('aria-live', 'polite');
    pick(screen.getByLabelText('What to buy'), 'attribute');
    pick(screen.getByLabelText('Attribute'), 'strength');
    fireEvent.click(buyButton());
    expect(screen.getByRole('alert')).toHaveTextContent('Starting experience overspent: 25 of 15 XP.');
  });

  test('a first XP dot in Academics asks for its free specialty', () => {
    renderForge();
    pick(screen.getByLabelText('What to buy'), 'skill');
    pick(screen.getByLabelText('Skill'), 'academics');
    expect(buyButton()).toBeDisabled();
    expect(screen.getByRole('alert')).toHaveTextContent('Academics comes with a free specialty — name it.');
    pick(screen.getByLabelText('Free Academics specialty'), 'History');
    expect(buyButton()).toHaveTextContent('Buy (3 XP)');
    fireEvent.click(buyButton());
    expect(screen.getByRole('list', { name: 'Bought with XP' })).toHaveTextContent('Academics 0 → 1 (History)');
    // the second dot needs nothing more
    expect(screen.queryByLabelText('Free Academics specialty')).toBeNull();
    expect(buyButton()).toHaveTextContent('Buy (6 XP)');
  });

  test('removing a purchase removes that purchase', () => {
    renderForge();
    pick(screen.getByLabelText('What to buy'), 'skill');
    pick(screen.getByLabelText('Skill'), 'finance');
    fireEvent.click(buyButton());
    pick(screen.getByLabelText('Skill'), 'occult');
    fireEvent.click(buyButton());
    fireEvent.click(screen.getByRole('button', { name: 'Remove Finance' }));
    const list = screen.getByRole('list', { name: 'Bought with XP' });
    expect(list).toHaveTextContent('Occult 0 → 1');
    expect(list).not.toHaveTextContent('Finance');
  });
});
