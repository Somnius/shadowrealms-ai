/** Downtime page views: the player's projects and the Storyteller's inbox. */
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import { resources } from '../../../i18n/locales';
import { setLanguage } from '../../../i18n';
import DowntimePlayerView from '../DowntimePlayerView';
import DowntimeStView from '../DowntimeStView';
import { DOWNTIME_ERROR_CODES, downtimeErrorText } from '../downtimeErrors';

const toast = jest.fn();
const ok = (data, status = 200) => ({ ok: true, status, data });
const fail = (status, data) => ({ ok: false, status, data });

const wrap = (ui) =>
  render(
    <MemoryRouter>
      <DesignProvider>{ui}</DesignProvider>
    </MemoryRouter>
  );

const phase = (over) => ({
  id: 11, project_id: 1, round_id: 3, round_title: 'Winter', round_status: 'open', action: 'Dig into the archives',
  difficulty_hidden: false, ready: false, difficulty: null, roll: null, status: 'declared',
  result_kind: null, result_text: null, result_location: null, ...over,
});

const playerData = (over = {}) => ({
  is_storyteller: false,
  round: { id: 3, title: 'Winter', status: 'open' },
  character: { id: 7, name: 'Eleni' },
  can_play: true,
  player_problem: null,
  projects: [
    { id: 1, title: 'Find the library', goal: 'Old books', status: 'active', parent_id: null, parent_title: null, phases: [phase()] },
    { id: 2, title: 'Learn the cipher', goal: '', status: 'active', parent_id: 1, parent_title: 'Find the library', phases: [] },
  ],
  ...over,
});

beforeEach(() => {
  toast.mockClear();
});

afterEach(async () => {
  await setLanguage('en', { remember: false, save: false });
});

describe('player view', () => {
  test('shows the round, the parent breadcrumb and waits for the difficulty', () => {
    const api = jest.fn();
    wrap(<DowntimePlayerView api={api} campaignId={5} isV5 data={playerData()} reload={jest.fn()} toast={toast} />);
    expect(screen.getByText('Winter', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText(/Find the library ›/)).toBeInTheDocument();
    expect(screen.getByText('Waiting for the Storyteller to set the difficulty.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Roll' })).toBeNull();
  });

  test('declares a phase for a project without one in the open round', async () => {
    const user = setupUser();
    const api = jest.fn(async () => ok({ phase: {} }, 201));
    const reload = jest.fn();
    wrap(<DowntimePlayerView api={api} campaignId={5} isV5 data={playerData()} reload={reload} toast={toast} />);
    // Only project 2 has no phase this round, so one declare form.
    await user.type(screen.getByLabelText(/What does your character do this round/), 'Ask the monks');
    await user.click(screen.getByRole('button', { name: 'Declare' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/projects/2/phases', { method: 'POST', body: { action: 'Ask the monks' } });
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  test('rolls only once the phase is ready (V5: pool only, no hunger)', async () => {
    const user = setupUser();
    const api = jest.fn(async () => ok({ phase: {} }));
    const data = playerData();
    data.projects[0].phases = [phase({ ready: true, difficulty: 3 })];
    wrap(<DowntimePlayerView api={api} campaignId={5} isV5 data={data} reload={jest.fn()} toast={toast} />);
    expect(screen.queryByText('Waiting for the Storyteller to set the difficulty.')).toBeNull();
    expect(screen.queryByLabelText(/Hunger/)).toBeNull();
    expect(screen.queryByLabelText('Specialty')).toBeNull();
    await user.type(screen.getByLabelText(/Dice pool/), '6');
    await user.click(screen.getByRole('button', { name: 'Roll' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/phases/11/roll', { method: 'POST', body: { pool_size: 6 } });
  });

  test('Classic offers specialty and willpower', async () => {
    const user = setupUser();
    const api = jest.fn(async () => ok({ phase: {} }));
    const data = playerData();
    data.projects[0].phases = [phase({ ready: true, difficulty: 6 })];
    wrap(<DowntimePlayerView api={api} campaignId={5} isV5={false} data={data} reload={jest.fn()} toast={toast} />);
    await user.type(screen.getByLabelText(/Dice pool/), '5');
    await user.click(screen.getByLabelText('Specialty'));
    await user.click(screen.getByRole('button', { name: 'Roll' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/phases/11/roll', {
      method: 'POST', body: { pool_size: 5, specialty: true, willpower: false },
    });
  });

  test('released results show the kind and the scene room', () => {
    const data = playerData({ round: null });
    data.projects[0].phases = [phase({
      round_status: 'released', status: 'resolved', result_kind: 'scene', result_text: 'The abbot waits.',
      result_location: { id: 42, name: 'Crypt' },
    })];
    wrap(<DowntimePlayerView api={jest.fn()} campaignId={5} isV5 data={data} reload={jest.fn()} toast={toast} />);
    expect(screen.getByText('Scene')).toBeInTheDocument();
    expect(screen.getByText('The abbot waits.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Scene in Crypt' })).toHaveAttribute('href', '/c/5/42');
  });

  test('read-only when the player cannot play', () => {
    const data = playerData({ can_play: false, player_problem: 'character_suspended' });
    wrap(<DowntimePlayerView api={jest.fn()} campaignId={5} isV5 data={data} reload={jest.fn()} toast={toast} />);
    expect(screen.getByRole('status')).toHaveTextContent("Your character's play is suspended.");
    expect(screen.queryByRole('button', { name: 'Declare' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Create project' })).toBeNull();
  });
});

const inbox = (over = {}) => ({
  round: { id: 3, title: 'Winter', status: 'resolving' },
  phases: [{
    id: 11, version: 4, project_id: 1, round_id: 3, round_status: 'resolving', action: 'Dig into the archives',
    difficulty: 3, difficulty_hidden: false, ready: true, roll: null, no_roll: true, result_kind: null, result_text: '',
    result_location_id: null, result_location_name: null, st_note: '', resolved: false, changes: [],
  }],
  projects: [{
    id: 1, title: 'Find the library', goal: '', status: 'active', parent_id: null, parent_title: null, character_id: 7,
    character_name: 'Eleni', orphaned: false, indicators: [{ id: 21, project_id: 1, name: 'Progress', value: 2, version: 1 }],
  }],
  variables: [{ id: 31, name: 'Masquerade', value: 5, note: '', version: 2 }],
  locations: [{ id: 42, name: 'Crypt' }],
  ...over,
});

function stApi(overrides = {}) {
  return jest.fn(async (path, opts) => {
    const key = `${(opts && opts.method) || 'GET'} ${path}`;
    if (overrides[key]) return overrides[key](opts);
    if (path.startsWith('/campaigns/5/downtime/rounds')) return ok({ rounds: [{ id: 3, title: 'Winter', status: 'resolving', phase_count: 1, unresolved_count: 1 }] });
    if (path.startsWith('/campaigns/5/downtime/inbox')) return ok(inbox());
    return ok({});
  });
}

describe('storyteller view', () => {
  test('renders rounds, inbox, indicators and variables', async () => {
    wrap(<DowntimeStView api={stApi()} campaignId={5} toast={toast} />);
    const card = await screen.findByTestId('phase-11');
    expect(within(card).getByText('Dig into the archives')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Release results' })).toBeInTheDocument();
    expect(screen.getByDisplayValue('Masquerade')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Progress')).toBeInTheDocument();
  });

  test('resolve sends the phase version, kind, room and deltas', async () => {
    const user = setupUser();
    const api = stApi();
    wrap(<DowntimeStView api={api} campaignId={5} toast={toast} />);
    const card = await screen.findByTestId('phase-11');
    await user.selectOptions(within(card).getByLabelText('Kind of result'), 'scene');
    await user.type(within(card).getByLabelText('What the player reads'), 'The abbot waits.');
    await user.selectOptions(within(card).getByLabelText('Room for the scene'), '42');
    await user.type(within(card).getByLabelText('Progress (2)'), '1');
    await user.type(within(card).getByLabelText('Masquerade (5)'), '-2');
    await user.click(within(card).getByRole('button', { name: 'Resolve' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/phases/11/resolve', {
      method: 'POST',
      body: {
        version: 4, result_kind: 'scene', result_text: 'The abbot waits.', result_location_id: 42, st_note: '',
        deltas: [{ target_kind: 'indicator', target_id: 21, delta: 1 }, { target_kind: 'variable', target_id: 31, delta: -2 }],
      },
    });
  });

  test('a version conflict says so and reloads the inbox', async () => {
    const user = setupUser();
    const api = stApi({
      'POST /campaigns/5/downtime/phases/11/resolve': () => fail(409, { code: 'version_conflict', error: 'x', current_version: 5 }),
    });
    wrap(<DowntimeStView api={api} campaignId={5} toast={toast} />);
    const card = await screen.findByTestId('phase-11');
    const inboxCalls = () => api.mock.calls.filter(([p]) => p.includes('/inbox')).length;
    const before = inboxCalls();
    await user.click(within(card).getByRole('button', { name: 'Resolve' }));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({
      tone: 'warn', title: 'Someone changed this while you were editing. It has been reloaded; check it and try again.',
    }));
    await waitFor(() => expect(inboxCalls()).toBeGreaterThan(before));
  });

  test('release with unresolved phases asks, then forces', async () => {
    const user = setupUser();
    const api = stApi({
      'POST /campaigns/5/downtime/rounds/3/release': (opts) =>
        opts.body.force ? ok({ round: {} }) : fail(409, { code: 'unresolved_phases', count: 1 }),
    });
    wrap(<DowntimeStView api={api} campaignId={5} toast={toast} />);
    await user.click(await screen.findByRole('button', { name: 'Release results' }));
    expect(await screen.findByText('1 phase has no result yet. Release anyway?')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Release anyway' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/rounds/3/release', { method: 'POST', body: { force: true } });
  });

  test('setup sends difficulty, hidden and version', async () => {
    const user = setupUser();
    const api = stApi();
    wrap(<DowntimeStView api={api} campaignId={5} toast={toast} />);
    const card = await screen.findByTestId('phase-11');
    await user.click(within(card).getByLabelText('Hide from the player'));
    await user.click(within(card).getByRole('button', { name: 'Update' }));
    expect(api).toHaveBeenCalledWith('/campaigns/5/downtime/phases/11/setup', {
      method: 'PUT', body: { version: 4, difficulty: 3, difficulty_hidden: true },
    });
  });
});

describe('Greek', () => {
  test('every backend error code has a Greek text', () => {
    const el = resources.el.downtime.err;
    DOWNTIME_ERROR_CODES.forEach((code) => expect(el[code]).toBeTruthy());
  });

  test('the player view renders in Greek', async () => {
    await setLanguage('el', { remember: false, save: false });
    wrap(<DowntimePlayerView api={jest.fn()} campaignId={5} isV5 data={playerData()} reload={jest.fn()} toast={toast} />);
    expect(screen.getByText('Περιμένεις τον Storyteller να ορίσει τη δυσκολία.')).toBeInTheDocument();
    expect(downtimeErrorText({ code: 'version_conflict' })).toMatch(/Φορτώθηκε ξανά/);
  });
});
