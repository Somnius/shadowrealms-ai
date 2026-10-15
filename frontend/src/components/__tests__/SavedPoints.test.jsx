/**
 * Saved points (Forge v2 part D): the forge says what will be saved; the sheet shows the saved
 * points, lets the owner spend them with a live rule check, and lists the spends.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import setupUser from '../../design/testing/setupUser';
import { DesignProvider, ToastProvider } from '../../design';
import CharacterSheetModal from '../CharacterSheetModal';
import V5CharacterCreationWizard from '../characterCreation/V5CharacterCreationWizard';

const mockApiFetch = jest.fn();
jest.mock('../../app/http', () => ({
  ...jest.requireActual('../../app/http'),
  apiFetch: (...args) => mockApiFetch(...args),
}));

const eleni = {
  id: 7,
  name: 'Eleni',
  user_id: 3,
  campaign_id: 10,
  rules_edition: 'v5',
  system_type: 'vampire',
  attributes: {},
  skills: { social: { persuasion: 3 }, mental: { occult: 1 }, specialties: [{ skill: 'occult', name: 'Vampires' }] },
  wod_meta: {
    edition: 'v5',
    advantages: [{ name: 'Resources', dots: 3, kind: 'background' }],
    saved: { advantage_dots: 2, specialty: 1 },
  },
};

const requests = [
  {
    id: 2, kind: 'saved_advantage', status: 'pending', payload: { items: [{ name: 'Allies', dots: 4 }] }, changes: [],
    rule_check: { ok: false, house_rule: true, problems: [{ code: 'saved_short', params: { need: 4, have: 2 } }] },
  },
  {
    id: 1, kind: 'saved_specialty', status: 'approved', approver: 'ai', payload: { skill: 'persuasion', name: 'Bargaining' },
    changes: [{ skill: 'persuasion', name: 'Bargaining' }], rule_check: { ok: true, house_rule: false, problems: [] },
  },
  {
    id: 0, kind: 'saved_advantage', status: 'reversed', approver: 'user', resolved_by_name: 'st', reason: 'Earned it.',
    reverse_reason: 'Too strong for now.', payload: { items: [{ name: 'Fame', dots: 1 }] }, changes: [{ name: 'Fame', from: 0, to: 1 }],
    rule_check: { ok: true, house_rule: false, problems: [] },
  },
];

let info;
beforeEach(() => {
  info = {
    requests,
    saved: { advantage_dots: 2, specialty: 1 },
    settings: { st_mode: 'ai', saved_points: { advantage_dots_cap: 7, allow_specialty: true } },
    can_spend: true,
    can_review: false,
  };
  mockApiFetch.mockImplementation(async (token, path, opts) => {
    if (path === '/characters/7/spend-requests' && !opts) return { ok: true, status: 200, data: info };
    if (path === '/characters/7/spend-requests' && opts.method === 'POST') {
      return { ok: true, status: 201, data: { applied: true, request: { id: 3, status: 'approved' } } };
    }
    return { ok: false, status: 404, data: {} };
  });
});

const openSheet = (character = eleni, onChanged = jest.fn()) => {
  render(
    <DesignProvider>
      <ToastProvider>
        <CharacterSheetModal character={character} gameSystem="vampire" onClose={() => {}} onChanged={onChanged} />
      </ToastProvider>
    </DesignProvider>
  );
  return onChanged;
};

test('the sheet shows the saved points and the spends', async () => {
  openSheet();
  expect(await screen.findByText('2 Advantage dots · 1 specialty')).toBeInTheDocument();
  expect(await screen.findByText('Allies +4')).toBeInTheDocument();
  expect(screen.getByText('Waiting for the Storyteller')).toBeInTheDocument();
  expect(screen.getByText('House rule')).toBeInTheDocument();
  expect(screen.getByText('Persuasion: Bargaining')).toBeInTheDocument();
  expect(screen.getByText('by the AI Storyteller (rule check)')).toBeInTheDocument();
  expect(screen.getByText('Fame 0 → 1')).toBeInTheDocument();
  expect(screen.getByText('Storyteller: Earned it.')).toBeInTheDocument();
  expect(screen.getByText('Reversed by the Storyteller: Too strong for now.')).toBeInTheDocument();
});

test('the owner spends with a live rule check; an AI-approved spend reloads the sheet', async () => {
  const user = setupUser();
  const onChanged = openSheet();
  await user.click(await screen.findByRole('button', { name: 'Spend…' }));
  const form = screen.getByRole('group', { name: 'Spend saved points' });
  expect(within(form).getByText('Fill in the spend to see the rule check.')).toBeInTheDocument();
  await user.type(within(form).getByLabelText('Advantage 1'), 'Resources');
  expect(within(form).getByText(/Follows the rules\./)).toHaveTextContent('The AI Storyteller applies it at once');
  await user.selectOptions(within(form).getByLabelText('Dots'), '3');
  expect(within(form).getByText('Needs 3 saved Advantage dots; 2 are saved.')).toBeInTheDocument();
  expect(within(form).getByText('House rule: only your Storyteller can approve this.')).toBeInTheDocument();
  expect(within(form).getByRole('button', { name: 'Ask the Storyteller' })).toBeInTheDocument();
  await user.selectOptions(within(form).getByLabelText('Dots'), '1');
  await user.click(within(form).getByRole('button', { name: 'Spend' }));
  await waitFor(() => expect(onChanged).toHaveBeenCalled());
  const post = mockApiFetch.mock.calls.find(([, , opts]) => opts && opts.method === 'POST');
  expect(post[2].body).toEqual({ kind: 'saved_advantage', items: [{ name: 'Resources', kind: 'background', dots: 1 }] });
  expect(await screen.findByText(/Done: the AI Storyteller approved it/)).toBeInTheDocument();
});

test('a specialty spend checks the skill', async () => {
  const user = setupUser();
  openSheet();
  await user.click(await screen.findByRole('button', { name: 'Spend…' }));
  const form = screen.getByRole('group', { name: 'Spend saved points' });
  await user.selectOptions(within(form).getByLabelText('What to spend'), 'saved_specialty');
  await user.selectOptions(within(form).getByLabelText('Skill'), 'science');
  await user.type(within(form).getByLabelText('Specialty'), 'Chemistry');
  expect(within(form).getByText('Science needs at least one dot for a specialty.')).toBeInTheDocument();
});

test('others see the saved points but cannot spend them', async () => {
  info.can_spend = false;
  openSheet();
  expect(await screen.findByText('2 Advantage dots · 1 specialty')).toBeInTheDocument();
  await screen.findByText('Allies +4');
  expect(screen.queryByRole('button', { name: 'Spend…' })).toBeNull();
});

test('a sheet without saved points and spends has no block', async () => {
  info.requests = [];
  openSheet({ ...eleni, wod_meta: { edition: 'v5' } });
  await waitFor(() => expect(mockApiFetch).toHaveBeenCalled());
  expect(screen.queryByText('Saved points')).toBeNull();
});

describe('the forge says what is saved', () => {
  const renderForge = (creation_settings) =>
    render(
      <V5CharacterCreationWizard
        token="x"
        campaigns={[{ id: 2, name: 'Blood', game_system: 'vampire', rules_edition: 'v5', creation_settings }]}
        campaignId="2"
        onCampaignChange={() => {}}
      />
    );

  test('unspent Advantage dots and the unused specialty', () => {
    renderForge({});
    expect(document.getElementById('v5-advantages-saved')).toHaveTextContent('7 dots will be saved for later');
    expect(document.getElementById('v5-specialty-saved')).toHaveTextContent('it will be saved for later');
  });

  test("the chronicle's cap and specialty switch", () => {
    renderForge({ saved_points: { advantage_dots_cap: 2, allow_specialty: false } });
    expect(document.getElementById('v5-advantages-saved')).toHaveTextContent(
      '2 dots will be saved for later: spend them from your sheet, the Storyteller approves. This chronicle saves at most 2, so 5 unspent dots are lost.'
    );
    expect(document.getElementById('v5-specialty-saved')).toHaveTextContent("this chronicle doesn't save it for later");
  });
});
