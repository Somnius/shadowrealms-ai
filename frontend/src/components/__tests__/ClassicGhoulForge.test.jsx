/**
 * The Classic ghoul forge (characterCreation/classicGhoul/): a Classic vampire's ghoul by Ghouls:
 * Fatal Addiction: the domitor's Disciplines, the Domitor Background from its generation, the Blood
 * Pool roll, the payload (no chronicle, a Blood Pool object), the client checks and the server's
 * bounds answer.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ClassicGhoulForge from '../characterCreation/classicGhoul/ClassicGhoulForge';
import { CLASSIC_GHOUL_SECTION_IDS as S } from '../../characterSheet/classicGhoul';
import { setLanguage } from '../../i18n';

// Filling a whole forge with userEvent is slow on CI runners.
jest.setTimeout(30000);

const respond = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
const THEO = {
  id: 21,
  name: 'Theodore Doukas',
  user_id: 3,
  campaign_id: 12,
  campaign_name: 'Constantinople',
  rules_edition: 'classic',
  system_type: 'vampire',
  wod_meta: { clan: 'Ventrue', generation: '12', disciplines: [{ name: 'Dominate', dots: 2 }, { name: 'Presence', dots: 1 }] },
};
const DARIUS = { id: 17, name: 'Darius', user_id: 3, rules_edition: 'v5', system_type: 'vampire', wod_meta: { edition: 'v5', clan: 'Ventrue' } };
const MARTA_ROW = { id: 40, name: 'Marta', user_id: 3, rules_edition: 'classic', system_type: 'vampire', sheet_kind: 'ghoul', wod_meta: { sheet_kind: 'ghoul' } };

beforeAll(() => {
  Element.prototype.scrollIntoView = () => {};
});
afterAll(() => {
  delete Element.prototype.scrollIntoView;
});
afterEach(async () => {
  await act(() => setLanguage('en', { remember: false, save: false }));
});

function renderForge(props = {}) {
  const done = jest.fn();
  const errors = [];
  render(
    <ClassicGhoulForge
      token="x"
      characters={[THEO, DARIUS, MARTA_ROW]}
      domitorId="21"
      onDone={done}
      onCancel={() => {}}
      showError={(m) => errors.push(m)}
      showSuccess={() => {}}
      rng={() => 0.55}
      {...props}
    />
  );
  return { done, errors };
}

const dot = (label, n) => fireEvent.click(screen.getByRole('button', { name: `Set ${label} to ${n}` }));
/** A dot in an Attribute / Ability row (those tracks have no label: the row's text names them). */
const rowDot = (text, n) => {
  const row = screen.getByText(text, { selector: 'span' }).parentElement;
  fireEvent.click(within(row).getAllByRole('button')[n - 1]);
};
const type = (el, value) => fireEvent.change(el, { target: { value } });

function fillLegal() {
  type(document.getElementById('classic-ghoul-name'), 'Marta Ionescu');
  [['strength', 3], ['dexterity', 3], ['stamina', 3], ['charisma', 3], ['manipulation', 3], ['perception', 2], ['intelligence', 2], ['wits', 2]].forEach(([k, n]) => rowDot(k, n));
  [['Alertness', 3], ['Brawl', 3], ['Subterfuge', 3], ['Dodge', 2], ['Drive', 3], ['Etiquette', 2], ['Firearms', 2], ['Finance', 2], ['Law', 2]].forEach(([k, n]) => rowDot(k, n));
  type(screen.getByLabelText('Discipline 2'), 'Dominate');
  dot('Dominate', 1);
  type(screen.getByLabelText('Background 2'), 'Resources');
  dot('Resources', 2);
  type(screen.getByLabelText('Background 3'), 'Contacts');
  dot('Contacts', 2);
  dot('Conscience', 3);
  dot('Self-Control', 3);
  dot('Courage', 4);
  fireEvent.click(screen.getByRole('button', { name: 'Roll 1d10' }));
}

test('only Classic vampires are offered as domitors', () => {
  renderForge();
  const sel = document.getElementById('classic-ghoul-domitor');
  expect(within(sel).getAllByRole('option').map((o) => o.textContent)).toEqual(['Theodore Doukas — Ventrue, generation 12 · Constantinople']);
  expect(screen.getByText(/Ghoul of Theodore Doukas/)).toBeInTheDocument();
});

test('without a Classic vampire there is nothing to forge yet', () => {
  renderForge({ characters: [DARIUS] });
  expect(screen.getByText(/you have none yet/)).toBeInTheDocument();
});

test("a vassal's Discipline comes from its domitor or the instinctive ones; an independent's from any", () => {
  renderForge();
  const opts = () => within(screen.getByLabelText('Discipline 2')).getAllByRole('option').map((o) => o.textContent);
  expect(opts()).toEqual(['—', 'Celerity', 'Dominate', 'Fortitude', 'Presence']);
  // the Domitor Background follows the 12th generation: 1 dot
  expect(screen.getByRole('group', { name: 'Domitor: 1 of 5' })).toBeInTheDocument();
  // Potence is pinned at 1 and stays there without freebies (12th generation: nothing above 1)
  expect(screen.getByRole('group', { name: 'Potence: 1 of 5' })).toBeInTheDocument();
  dot('Potence', 1);
  dot('Potence', 2);
  expect(screen.getByRole('group', { name: 'Potence: 1 of 5' })).toBeInTheDocument();
  type(document.getElementById('classic-ghoul-kind'), 'independent');
  expect(opts()).toContain('Obfuscate');
  expect(opts()).not.toContain('Thaumaturgy');
  expect(opts()).not.toContain('Potence');
});

test('the Blood Pool is a roll: a vassal may reroll a 1, an independent halves it', () => {
  renderForge({ rng: () => 0 });
  fireEvent.click(screen.getByRole('button', { name: 'Roll 1d10' }));
  expect(screen.getByText('Rolled 1')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: "Reroll the 1 (Storyteller's option)" })).toBeInTheDocument();
  expect(document.getElementById('classic-ghoul-pool')).toHaveValue(1);
});

test('an independent halves the roll and starts unbound', () => {
  renderForge({ rng: () => 0.65 });
  type(document.getElementById('classic-ghoul-kind'), 'independent');
  expect(screen.getByRole('group', { name: 'Blood Bond: 0 of 3' })).toBeInTheDocument();
  // no master to buy Domitor for (Fatal Addiction p. 65); back to vassal, the row comes back
  expect(screen.getByRole('combobox', { name: 'Background 1' })).toHaveValue('');
  type(document.getElementById('classic-ghoul-kind'), 'vassal');
  expect(screen.getByRole('combobox', { name: 'Background 1' })).toHaveValue('Domitor');
  type(document.getElementById('classic-ghoul-kind'), 'independent');
  fireEvent.click(screen.getByRole('button', { name: 'Roll 1d10' }));
  expect(screen.getByText('Rolled 7, halved: 4')).toBeInTheDocument();
  expect(document.getElementById('classic-ghoul-pool')).toHaveValue(4);
  expect(screen.queryByRole('button', { name: /Reroll/ })).toBeNull();
});

test('a legal ghoul posts a Classic sheet with a Blood Pool and no chronicle', async () => {
  global.fetch = jest.fn(async () => respond(201, { character_id: 40, sheet_kind: 'ghoul', rules_edition: 'classic' }));
  const { done, errors } = renderForge();
  fillLegal();
  expect(screen.getByRole('group', { name: 'Blood Bond: 3 of 3' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Create the ghoul' }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(errors).toEqual([]);
  const [, init] = global.fetch.mock.calls.find(([u]) => String(u) === '/api/characters/');
  const body = JSON.parse(init.body);
  expect(body.campaign_id).toBeNull();
  expect(body.system_type).toBe('vampire');
  const m = body.wod_meta;
  expect(m.sheet_kind).toBe('ghoul');
  expect(m.blood_pool).toEqual({ max: 10, current: 6, per_turn: 1 });
  expect(m.disciplines).toEqual([
    { name: 'Potence', dots: 1 },
    { name: 'Dominate', dots: 1 },
  ]);
  expect(m.backgrounds).toEqual([
    { name: 'Domitor', dots: 1 },
    { name: 'Resources', dots: 2 },
    { name: 'Contacts', dots: 2 },
  ]);
  expect([m.humanity, m.willpower]).toEqual([6, 4]);
  expect(m.ghoul).toMatchObject({ kind: 'vassal', domitor: { character_id: 21, name: 'Theodore Doukas', clan: 'Ventrue' }, bond: { stage: 3 } });
  expect(m).not.toHaveProperty('clan');
  expect(m).not.toHaveProperty('generation');
  expect(body.attributes.strength).toBe(3);
});

test('the text fields carry the server caps', () => {
  renderForge();
  expect(document.getElementById('classic-ghoul-last-fed')).toHaveAttribute('maxLength', '60');
  expect(document.getElementById('classic-ghoul-overdosing')).toHaveAttribute('maxLength', '120');
  expect(document.getElementById('classic-ghoul-duties')).toHaveAttribute('maxLength', '200');
  expect(document.getElementById('classic-ghoul-feeding-note')).toHaveAttribute('maxLength', '500');
  expect(document.getElementById('classic-ghoul-bond-note')).toHaveAttribute('maxLength', '500');
});

test('the client stops a sheet without its second Discipline, in its section', () => {
  global.fetch = jest.fn(async () => respond(201, {}));
  const { errors } = renderForge();
  fillLegal();
  dot('Dominate', 1); // back to 0
  fireEvent.click(screen.getByRole('button', { name: 'Create the ghoul' }));
  expect(errors[0]).toBe('Place the dot in a Discipline besides Potence.');
  expect(within(document.getElementById(S.advantages)).getByRole('alert')).toHaveTextContent('Place the dot in a Discipline besides Potence.');
  expect(global.fetch.mock.calls.some(([u]) => String(u) === '/api/characters/')).toBe(false);
});

test("the server's bounds answer lands on each problem's section, in Greek", async () => {
  global.fetch = jest.fn(async (url) =>
    String(url) === '/api/characters/'
      ? respond(400, {
          error_code: 'classic_ghoul_bounds',
          problems: ['wod_meta.blood_pool.max must be between 1 and 20', 'wod_meta.ghoul.feeding.last must be text of at most 60 characters'],
        })
      : respond(404, {})
  );
  const { errors } = renderForge();
  fillLegal();
  await act(() => setLanguage('el', { remember: false, save: false }));
  fireEvent.click(screen.getByRole('button', { name: /Create the ghoul|Δημιούργησε το ghoul/ }));
  await waitFor(() => expect(errors.length).toBe(1));
  expect(errors[0]).toBe('Ο server δεν δέχτηκε το χαρτί του χαρακτήρα: wod_meta.blood_pool.max must be between 1 and 20');
  expect(within(document.getElementById(S.advantages)).getByRole('alert')).toHaveTextContent('Ο server δεν δέχτηκε το χαρτί του χαρακτήρα');
  expect(within(document.getElementById(S.bond)).getByRole('alert')).toHaveTextContent('Ο server δεν δέχτηκε το χαρτί του χαρακτήρα: Τελευταία φορά που ήπιε: έως 60 χαρακτήρες.');
});
