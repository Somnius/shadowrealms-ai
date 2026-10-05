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
