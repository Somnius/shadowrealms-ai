/**
 * The Storyteller's "Allowed books" checklist in the creation rules (Forge v2): the catalog's
 * books, core ones first, all ticked = null (every book, also ones added later), at least one.
 */
import { render, screen, within } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import CreationRulesPanel from '../CreationRulesPanel';
import fixture from '../../../rules/__fixtures__/v5-catalog.json';
import { applyV5Catalog } from '../../../characterSheet/v5/rulesData';

const BOOKS = [
  { book_id: 'v5-cults-of-the-blood-gods', title: 'Cults of the Blood Gods', precedence: 40, tier: 2 },
  { book_id: 'v5-companion', title: 'Companion', precedence: 30, tier: 1 },
  { book_id: 'v5-corebook', title: 'Corebook', precedence: 10, tier: 1 },
  { book_id: 'v5-players-guide', title: 'Players Guide', precedence: 20, tier: 1 },
];

beforeAll(() => applyV5Catalog({ ...fixture, books: BOOKS }));
afterAll(() => applyV5Catalog(null));

const renderPanel = (creation_settings, onSave) =>
  render(
    <DesignProvider>
      <CreationRulesPanel campaign={{ id: 10, creation_settings }} saving={false} onSave={onSave} />
    </DesignProvider>
  );
const bookList = () => screen.getByRole('group', { name: 'Allowed books' });
const save = (user) => user.click(screen.getByRole('button', { name: 'Save creation rules' }));

test('the books, core ones first with their tier; all ticked is stored as null', async () => {
  const user = setupUser();
  const onSave = jest.fn();
  renderPanel({}, onSave);
  const boxes = within(bookList()).getAllByRole('checkbox');
  expect(boxes.map((b) => document.querySelector(`label[for="${b.id}"]`).textContent)).toEqual([
    'Corebook · Tier 1 · always allowed (the core rules)',
    'Players Guide · Tier 1',
    'Companion · Tier 1',
    'Cults of the Blood Gods · Tier 2',
  ]);
  boxes.forEach((b) => expect(b).toBeChecked());
  expect(bookList()).toHaveAccessibleDescription(/from the ticked books only/);
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ allowed_books: null }));
  await user.click(boxes[3]);
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(
    expect.objectContaining({ allowed_books: ['v5-corebook', 'v5-players-guide', 'v5-companion'] })
  );
});

const box = (name) => within(bookList()).getByRole('checkbox', { name: new RegExp(`^${name} ·`) });

test('the corebook is always allowed: unticking all but the Players Guide keeps it', async () => {
  const user = setupUser();
  const onSave = jest.fn();
  renderPanel({}, onSave);
  expect(box('Corebook')).toBeChecked();
  expect(box('Corebook')).toBeDisabled();
  await user.click(box('Corebook'));
  for (const name of ['Companion', 'Cults of the Blood Gods']) await user.click(box(name));
  expect(box('Corebook')).toBeChecked();
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ allowed_books: ['v5-corebook', 'v5-players-guide'] }));
  // and the Players Guide alone leaves the corebook
  await user.click(box('Players Guide'));
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ allowed_books: ['v5-corebook'] }));
});

test('a stored list without the corebook (an old row) gets it; ticking every book again is null', async () => {
  const user = setupUser();
  const onSave = jest.fn();
  renderPanel({ allowed_books: ['v5-players-guide'] }, onSave);
  expect(box('Corebook')).toBeChecked();
  expect(box('Players Guide')).toBeChecked();
  expect(box('Companion')).not.toBeChecked();
  for (const name of ['Companion', 'Cults of the Blood Gods']) await user.click(box(name));
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ allowed_books: null }));
});

test("a stored book the catalog no longer lists is dropped on save (the server refuses it)", async () => {
  const user = setupUser();
  const onSave = jest.fn();
  renderPanel({ allowed_books: ['v5-corebook', 'v5-removed-book'] }, onSave);
  await user.click(box('Companion'));
  await save(user);
  expect(onSave).toHaveBeenLastCalledWith(expect.objectContaining({ allowed_books: ['v5-corebook', 'v5-companion'] }));
});
