/**
 * "The chronicle so far", 0.26: the Look choice (sheet / horror) beside Paper, and minutes for a date
 * range in the Storyteller's timezone.
 */
import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import ChronicleSoFarPanel from '../ChronicleSoFarPanel';

const toast = jest.fn();
const campaign = { id: 10, name: 'Athens' };
const written = {
  lang: 'el', own_lang: 'el', view: 'st', access: 'st', can_update: true, can_edit: true, quiet_minutes: 10,
  nights_written: 1, nights_total: 1, new_since: false, written_at: '2026-10-16T22:00:00', job: null, translation: null,
  edit: { edited: false, newer: false, edited_at: null },
  digest: { tldr: 'Με λίγα λόγια.', so_far: ['Η ιστορία.'], threads_open: [] },
  chapters: [],
};

const renderPanel = (props = {}) =>
  render(
    <DesignProvider>
      <ChronicleSoFarPanel api={jest.fn(async () => ({ ok: true, data: written }))} campaign={campaign} toast={toast} {...props} />
    </DesignProvider>
  );

beforeEach(() => {
  global.fetch = jest.fn(async () => ({ ok: true, status: 200, blob: async () => new Blob(['%PDF']) }));
  URL.createObjectURL = jest.fn(() => 'blob:x');
  URL.revokeObjectURL = jest.fn();
});

test('the horror look goes on PDF exports only; the sheet is the default and not sent', async () => {
  const user = setupUser();
  renderPanel();
  const look = await screen.findByRole('combobox', { name: 'Look' });
  expect(look).toHaveValue('sheet');
  expect(screen.getByRole('option', { name: 'Horror' })).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Export story PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle.pdf?paper=a4');
  await user.selectOptions(look, 'horror');
  await user.click(screen.getByRole('button', { name: 'Export story PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls[1][0]).toBe('/api/campaigns/10/chronicle.pdf?paper=a4&look=horror');
  await user.click(screen.getByRole('button', { name: 'Export story' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
  expect(global.fetch.mock.calls[2][0]).toBe('/api/campaigns/10/chronicle.md');
});

test('minutes for a date range send from, to and the Storyteller’s timezone', async () => {
  const user = setupUser();
  renderPanel({ timeZone: 'Europe/Athens' });
  const from = await screen.findByLabelText('From');
  const to = screen.getByLabelText('To');
  await user.type(screen.getByRole('spinbutton', { name: 'Number of nights' }), '2');
  await user.type(from, '2026-10-01');
  await user.type(to, '2026-10-05');
  const md = screen.getByRole('button', { name: /Export minutes · 2026-10-01 to 2026-10-05/ });
  await user.click(md);
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle/minutes.md?from=2026-10-01&to=2026-10-05&tz=Europe%2FAthens');
  expect(screen.getByText(/A night counts on the day of its first message \(Europe\/Athens\)/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Clear dates' }));
  expect(screen.getByRole('button', { name: /Export minutes · the last 2 nights/ })).toBeInTheDocument();
});

test('a range that ends before it starts is refused in the panel', async () => {
  const user = setupUser();
  renderPanel({ timeZone: 'UTC' });
  await user.type(await screen.findByLabelText('From'), '2026-10-05');
  await user.type(screen.getByLabelText('To'), '2026-10-01');
  expect(screen.getByText('The first day must come before the last.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Minutes PDF' })).toBeDisabled();
});

test('one date alone is open-ended', async () => {
  const user = setupUser();
  renderPanel({ timeZone: 'UTC' });
  await user.type(await screen.findByLabelText('From'), '2026-10-03');
  await user.click(screen.getByRole('button', { name: /Export minutes · from 2026-10-03 to today/ }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle/minutes.md?from=2026-10-03&tz=UTC');
  await user.clear(screen.getByLabelText('From'));
  await user.type(screen.getByLabelText('To'), '2026-10-04');
  await user.click(screen.getByRole('button', { name: /Export minutes · from the beginning to 2026-10-04/ }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls[1][0]).toBe('/api/campaigns/10/chronicle/minutes.md?to=2026-10-04&tz=UTC');
});

test('colour or print: the default follows the look and only a change is sent', async () => {
  const user = setupUser();
  renderPanel();
  const color = await screen.findByRole('combobox', { name: 'Colour' });
  expect(color).toHaveValue('print'); // the sheet
  expect(screen.getByRole('option', { name: 'Print (black and white)' })).toBeInTheDocument();
  await user.selectOptions(color, 'colour');
  await user.click(screen.getByRole('button', { name: 'Export story PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch.mock.calls[0][0]).toBe('/api/campaigns/10/chronicle.pdf?paper=a4&color=colour');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Look' }), 'horror');
  expect(color).toHaveValue('colour'); // horror's default
  await user.selectOptions(color, 'print');
  await user.click(screen.getByRole('button', { name: 'Minutes PDF' }));
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(global.fetch.mock.calls[1][0]).toBe('/api/campaigns/10/chronicle/minutes.pdf?paper=a4&look=horror&color=print');
});
