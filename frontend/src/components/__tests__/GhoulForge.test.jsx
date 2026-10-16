/**
 * The ghoul forge (characterCreation/ghoul/): the template drives the steps, the power comes from
 * the domitor's Disciplines, Two Masters opens a second Bond, the payload has no chronicle, and the
 * server's codes land on their sections in Greek.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import GhoulForge from '../characterCreation/ghoul/GhoulForge';
import fixture from '../../characterSheet/v5/__fixtures__/creation-cases.json';
import { DARIUS } from '../../characterSheet/v5/__fixtures__/ghoulFixtures';
import { applyV5Catalog } from '../../characterSheet/v5/rulesData';
import { V5_SECTION_IDS } from '../../characterSheet/v5/constants';
import { setLanguage } from '../../i18n';

// Filling a whole forge with userEvent is slow on CI runners.
jest.setTimeout(30000);

const pick = (el, value) => fireEvent.change(el, { target: { value } });
const respond = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
const THEO = { id: 21, name: 'Theo', user_id: 3, rules_edition: 'classic', system_type: 'vampire', wod_meta: {} };
const MIRA_ROW = { id: 30, name: 'Mira', user_id: 3, rules_edition: 'v5', system_type: 'vampire', sheet_kind: 'ghoul', wod_meta: { sheet_kind: 'ghoul' } };

beforeAll(() => {
  applyV5Catalog(fixture.catalog);
  // jsdom has no scrollIntoView (the forge scrolls to the first section with an error)
  Element.prototype.scrollIntoView = () => {};
});
afterAll(() => {
  applyV5Catalog(null);
  delete Element.prototype.scrollIntoView;
});
afterEach(async () => {
  await act(() => setLanguage('en', { remember: false, save: false }));
});

function renderForge(props = {}) {
  const done = jest.fn();
  const errors = [];
  render(
    <GhoulForge
      token="x"
      characters={[DARIUS, THEO, MIRA_ROW]}
      chronicles={[]}
      domitorId="17"
      onDone={done}
      onCancel={() => {}}
      showError={(m) => errors.push(m)}
      showSuccess={() => {}}
      {...props}
    />
  );
  return { done, errors };
}

const dot = (label, n) => fireEvent.click(screen.getByRole('button', { name: `Set ${label} to ${n}` }));

test('only V5 vampires are offered as domitors; ghouls and Classic sheets are not', () => {
  renderForge();
  const sel = document.getElementById('ghoul-field-domitor');
  expect(within(sel).getAllByRole('option').map((o) => o.textContent)).toEqual(['Darius Vale — Ventrue · no chronicle']);
  expect(screen.getByText(/Ghoul of Darius Vale/)).toBeInTheDocument();
});

test('without a V5 vampire there is nothing to forge yet', () => {
  renderForge({ characters: [THEO] });
  expect(screen.getByText(/you have none yet/)).toBeInTheDocument();
});

test('the template sets the spread and the Skill counts; a new one starts over', () => {
  renderForge();
  expect(document.getElementById('ghoul-field-template')).toHaveValue('gifted');
  expect(screen.queryByLabelText('Distribution')).toBeNull(); // the template fixes it
  expect(screen.getByText('Gifted mortal: 2×4, 4×3, 4×2, 4×1 (core p. 185).')).toBeInTheDocument();
  dot('Manipulation', 4);
  expect(screen.getByRole('group', { name: 'Manipulation: 4 of 4' })).toBeInTheDocument();
  pick(document.getElementById('ghoul-field-template'), 'player');
  expect(screen.getByLabelText('Distribution')).toBeInTheDocument();
  expect(screen.getByRole('group', { name: 'Manipulation: 1 of 4' })).toBeInTheDocument();
  expect(document.getElementById('ghoul-field-humanity')).toBeChecked();
  pick(document.getElementById('ghoul-field-template'), 'deadly');
  expect(screen.getByRole('group', { name: 'Strength: 2 of 5' })).toBeInTheDocument();
});

test("the power comes from the domitor's Disciplines, his own level-1 powers first", () => {
  renderForge();
  const disc = document.getElementById('ghoul-field-discipline');
  expect(within(disc).getAllByRole('option').map((o) => o.value)).toEqual(['', 'Dominate', 'Presence']);
  pick(disc, 'Dominate');
  const power = document.getElementById('ghoul-field-power');
  const names = within(power).getAllByRole('option').map((o) => o.textContent);
  expect(names[1]).toBe('Cloud Memory (your domitor has it)');
  expect(names).toContain("Compel (the domitor doesn't have it: Storyteller's call, core p. 234)");
  expect(names.some((n) => n.startsWith('Mesmerize'))).toBe(false); // level 2
});

test('Two Masters opens a second Blood Bond', () => {
  renderForge();
  expect(screen.queryByRole('button', { name: '+ Second Blood Bond (Two Masters)' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '+ Add Flaw' }));
  pick(screen.getByLabelText('Flaw 1'), 'flaw:two-masters');
  fireEvent.click(screen.getByRole('button', { name: '+ Second Blood Bond (Two Masters)' }));
  expect(document.getElementById('ghoul-field-bond2-name')).toBeInTheDocument();
});

test('ghoul-only Merits are offered, Herd and Feeding Merits are not', () => {
  renderForge();
  fireEvent.click(screen.getByRole('button', { name: '+ Add Merit' }));
  const merits = screen.getByLabelText('Merit 1');
  expect(within(merits).getByRole('option', { name: /Blood Empathy/ })).toBeInTheDocument();
  expect(within(merits).queryByRole('option', { name: /Iron Gullet/ })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '+ Add Background' }));
  expect(within(screen.getByLabelText('Background 1')).queryByRole('option', { name: /^Herd/ })).toBeNull();
});

/** A small valid Gifted ghoul, through the steps. */
function fillGifted() {
  fireEvent.change(document.getElementById('ghoul-field-name'), { target: { value: 'Mira Tanis' } });
  [['Manipulation', 4], ['Intelligence', 3], ['Wits', 3], ['Charisma', 2], ['Resolve', 2]].forEach(([k, n]) => dot(k, n));
  [['Persuasion', 4], ['Subterfuge', 4], ['Leadership', 3], ['Insight', 3], ['Etiquette', 3], ['Finance', 3],
    ['Academics', 2], ['Technology', 2], ['Politics', 2], ['Streetwise', 2], ['Awareness', 1], ['Craft', 1], ['Drive', 1], ['Investigation', 1]].forEach(([k, n]) => dot(k, n));
  ['persuasion:Negotiation', 'academics:Media studies', 'craft:Video editing'].forEach((s, i) => {
    const [skill, name] = s.split(':');
    fireEvent.click(screen.getByRole('button', { name: '+ Add specialty' }));
    pick(screen.getByLabelText(`Specialty ${i + 1} skill`), skill);
    pick(screen.getByLabelText(`Specialty ${i + 1} name`), name);
  });
  pick(document.getElementById('ghoul-field-discipline'), 'Dominate');
  pick(document.getElementById('ghoul-field-power'), 'Cloud Memory');
  fireEvent.click(screen.getByRole('button', { name: '+ Add Merit' }));
  pick(screen.getByLabelText('Merit 1'), 'merit:beautiful');
  fireEvent.click(screen.getByRole('button', { name: '+ Add Flaw' }));
  pick(screen.getByLabelText('Flaw 1'), 'flaw:bondslave');
}

test('the sheet goes to the server with no chronicle, as a ghoul of the domitor', async () => {
  global.fetch = jest.fn(async () => respond(201, { character_id: 30, sheet_kind: 'ghoul' }));
  const { done, errors } = renderForge();
  fillGifted();
  fireEvent.click(screen.getByRole('button', { name: 'Create the ghoul' }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(errors).toEqual([]);
  const [url, init] = global.fetch.mock.calls.find(([u]) => String(u) === '/api/characters/');
  expect(url).toBe('/api/characters/');
  const body = JSON.parse(init.body);
  expect(body.campaign_id).toBeNull();
  expect(body.name).toBe('Mira Tanis');
  expect(body.wod_meta.sheet_kind).toBe('ghoul');
  expect(body.wod_meta.ghoul.domitor).toEqual({ character_id: 17, name: 'Darius Vale', clan: 'Ventrue' });
  expect(body.wod_meta.disciplines).toEqual([{ name: 'Dominate', level: 1, powers: ['Cloud Memory'], ghoul: true }]);
  expect(body.skills.specialties[0]).toEqual({ skill: 'persuasion', name: 'Negotiation', source: 'template' });
  expect(body.wod_meta.health.max).toBe(4);
});

test('the client stops a sheet that breaks the template, in its section', () => {
  global.fetch = jest.fn(async () => respond(201, {}));
  const { errors } = renderForge();
  fillGifted();
  dot('Strength', 2); // one dot too many
  fireEvent.click(screen.getByRole('button', { name: 'Create the ghoul' }));
  expect(errors[0]).toBe("Attributes don't match the Gifted mortal spread.");
  expect(global.fetch.mock.calls.some(([u]) => String(u) === '/api/characters/')).toBe(false);
});

test('a server code lands on its section, in Greek', async () => {
  global.fetch = jest.fn(async (url) =>
    String(url) === '/api/characters/'
      ? respond(400, { error_code: 'creation_invalid', problems: [{ code: 'ghoul_adv_restricted', params: { name: 'Herd', why: 'herd' } }] })
      : respond(404, {})
  );
  const { errors } = renderForge();
  fillGifted();
  await act(() => setLanguage('el', { remember: false, save: false }));
  // the open forge keeps its labels until it re-renders; the messages are made at submit time
  fireEvent.click(screen.getByRole('button', { name: /Create the ghoul|Δημιούργησε το ghoul/ }));
  await waitFor(() => expect(errors.length).toBe(1));
  const section = document.getElementById(V5_SECTION_IDS.advantages);
  expect(within(section).getByText('Το Herd δεν επιτρέπεται σε ghouls: το Herd ανήκει στους Kindred (Players Guide σελ. 141).')).toBeInTheDocument();
});
