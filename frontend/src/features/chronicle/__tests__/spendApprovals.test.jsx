/**
 * The Storyteller's side of saved points (Forge v2 part D): the Approvals card and the approval
 * mode and saved-point cap in the creation rules.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import SpendApprovalsPanel from '../SpendApprovalsPanel';
import CreationRulesPanel from '../CreationRulesPanel';

const api = jest.fn();
const toast = jest.fn();

const rows = [
  {
    id: 5, character_name: 'Eleni', username: 'eleni', kind: 'saved_advantage', status: 'pending',
    payload: { items: [{ name: 'Resources', dots: 1 }] }, changes: [],
    rule_check: { ok: true, house_rule: false, problems: [] },
  },
  {
    id: 6, character_name: 'Volkan', username: 'volkan', kind: 'saved_advantage', status: 'pending',
    payload: { items: [{ name: 'Allies', dots: 4 }] }, changes: [],
    rule_check: { ok: false, house_rule: true, problems: [{ code: 'saved_short', params: { need: 4, have: 2 } }] },
  },
  {
    id: 4, character_name: 'Eleni', username: 'eleni', kind: 'saved_specialty', status: 'approved', approver: 'ai',
    payload: { skill: 'occult', name: 'Byzantine rites' }, changes: [{ skill: 'occult', name: 'Byzantine rites' }],
    rule_check: { ok: true, house_rule: false, problems: [] },
  },
];

beforeEach(() => {
  api.mockImplementation(async (path, opts) => {
    if (opts && opts.method === 'PATCH') return { ok: true, status: 200, data: { request: {} } };
    const pending = path.endsWith('?status=pending');
    return { ok: true, status: 200, data: { requests: pending ? rows.filter((r) => r.status === 'pending') : rows, st_mode: 'ai' } };
  });
});

const renderPanel = () =>
  render(
    <DesignProvider>
      <SpendApprovalsPanel api={api} campaignId={10} user={{ id: 2 }} toast={toast} />
    </DesignProvider>
  );

const item = (name) => screen.getByText(name, { selector: 'strong' }).closest('li');

test('in AI Storyteller mode it opens on all spends', async () => {
  render(
    <DesignProvider>
      <SpendApprovalsPanel api={api} campaignId={10} user={{ id: 2 }} toast={toast} initialStMode="ai" />
    </DesignProvider>
  );
  expect(await screen.findByText('Occult: Byzantine rites')).toBeInTheDocument();
  expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests');
});

test('lists what waits, with house rules flagged and explained', async () => {
  renderPanel();
  await screen.findByText('Volkan');
  expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests?status=pending');
  expect(screen.getByText(/AI Storyteller mode/)).toBeInTheDocument();
  const volkan = item('Volkan');
  expect(within(volkan).getByText('House rule')).toBeInTheDocument();
  expect(within(volkan).getByText('Needs 4 saved Advantage dots; 2 are saved.')).toBeInTheDocument();
  expect(within(item('Eleni')).queryByText('House rule')).toBeNull();
});

test('a rule-following spend is approved in one click; a house rule asks first', async () => {
  const user = setupUser();
  renderPanel();
  await screen.findByText('Volkan');
  await user.click(within(item('Eleni')).getByRole('button', { name: 'Approve' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests/5', { method: 'PATCH', body: { action: 'approve' } }));
  expect(toast).toHaveBeenCalledWith({ tone: 'ok', title: 'Approved and added to the sheet.' });

  await user.click(within(item('Volkan')).getByRole('button', { name: 'Approve' }));
  expect(api).not.toHaveBeenCalledWith('/campaigns/10/spend-requests/6', expect.anything());
  await user.type(within(item('Volkan')).getByLabelText('Why allow this house rule? (optional)'), 'War veteran');
  await user.click(within(item('Volkan')).getByRole('button', { name: 'Approve' }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests/6', { method: 'PATCH', body: { action: 'approve', reason: 'War veteran' } })
  );
});

test('reject asks for a reason; approved spends can be reversed', async () => {
  const user = setupUser();
  renderPanel();
  await screen.findByText('Volkan');
  await user.click(within(item('Volkan')).getByRole('button', { name: 'Reject' }));
  await user.type(within(item('Volkan')).getByLabelText('Reason for the player (optional)'), 'Not now');
  await user.click(within(item('Volkan')).getByRole('button', { name: 'Reject' }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests/6', { method: 'PATCH', body: { action: 'reject', reason: 'Not now' } })
  );

  await user.selectOptions(screen.getByLabelText('Show'), 'all');
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests'));
  const done = (await screen.findByText('Occult: Byzantine rites')).closest('li');
  expect(within(done).getByText('by the AI Storyteller (rule check)')).toBeInTheDocument();
  await user.click(within(done).getByRole('button', { name: 'Reverse' }));
  await user.click(within(done).getByRole('button', { name: 'Reverse' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/campaigns/10/spend-requests/4', { method: 'PATCH', body: { action: 'reverse' } }));
});

test('the creation rules set who approves and how much may be saved', async () => {
  const user = setupUser();
  const onSave = jest.fn();
  render(
    <DesignProvider>
      <CreationRulesPanel campaign={{ id: 10, creation_settings: {} }} saving={false} onSave={onSave} suggestAi />
    </DesignProvider>
  );
  expect(screen.getByText(/You play a character in this chronicle yourself/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Who approves spending saved points'), 'ai');
  expect(screen.queryByText(/You play a character in this chronicle yourself/)).toBeNull();
  expect(screen.getByText(/not the language model/)).toBeInTheDocument();
  const cap = screen.getByLabelText('Advantage dots a player may leave unspent and save for later (0–20)');
  await user.clear(cap);
  await user.type(cap, '3');
  await user.click(screen.getByLabelText('Players may save the free specialty of their choice'));
  await user.click(screen.getByRole('button', { name: 'Save creation rules' }));
  expect(onSave).toHaveBeenCalledWith(
    expect.objectContaining({ st_mode: 'ai', saved_points: { advantage_dots_cap: 3, allow_specialty: false } })
  );
});
