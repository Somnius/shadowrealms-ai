import { act, render, screen, waitFor, within } from '@testing-library/react';
import { ToastProvider } from '../../design';
import setupUser from '../../design/testing/setupUser';
import { setLanguage } from '../../i18n';
import SecurityPanel, { describeDetails } from '../admin/SecurityPanel';

const EVENTS = [
  {
    id: 3,
    created_at: '2026-10-04T06:30:00Z',
    event: 'lockout',
    user_id: null,
    username: 'mallory',
    ip: '203.0.113.7',
    user_agent: 'curl/8.4',
    details: { seconds: 900 },
  },
  {
    id: 2,
    created_at: '2026-10-04T06:29:00Z',
    event: 'login_failed',
    user_id: 5,
    username: 'alice',
    ip: '198.51.100.2',
    user_agent: 'Mozilla/5.0',
    details: { known_user: true },
  },
];

function json(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

/** fetch mock: GET auth-events answers from `pages(url)`, POST unlock from `unlock(body)`. */
function mockFetch({ pages = () => json(200, { events: EVENTS, has_more: false }), unlock = () => json(200, { message: 'Unlocked', keys_cleared: 2 }) } = {}) {
  global.fetch = jest.fn(async (url, init = {}) => {
    if (String(url).startsWith('/api/admin/auth/unlock')) return unlock(JSON.parse(init.body));
    return pages(String(url));
  });
}

const auditCalls = () => global.fetch.mock.calls.map(([u]) => String(u)).filter((u) => u.startsWith('/api/admin/auth-events'));
const unlockCalls = () => global.fetch.mock.calls.filter(([u]) => String(u).startsWith('/api/admin/auth/unlock'));

const showSuccess = jest.fn();
const showError = jest.fn();

function mount() {
  return render(
    <ToastProvider>
      <SecurityPanel token="jwt" displayTimezone="UTC" showSuccess={showSuccess} showError={showError} />
    </ToastProvider>
  );
}

async function flush() {
  for (let i = 0; i < 3; i += 1) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
}

beforeEach(() => {
  showSuccess.mockClear();
  showError.mockClear();
});

afterEach(async () => {
  await act(async () => {
    await setLanguage('en', { remember: false, save: false });
  });
});

test('lists auth events with readable labels, local timestamps and safe details', async () => {
  mockFetch();
  mount();
  await flush();
  expect(auditCalls()[0]).toBe('/api/admin/auth-events?limit=50&offset=0');
  const rows = screen.getAllByTestId('auth-event-row');
  expect(rows).toHaveLength(2);
  const first = within(rows[0]);
  expect(first.getByText('Locked out')).toBeInTheDocument();
  expect(first.getByText('mallory')).toBeInTheDocument();
  expect(first.getByText('203.0.113.7')).toBeInTheDocument();
  expect(first.getByText('locked for 15 min')).toBeInTheDocument();
  const time = rows[0].querySelector('time');
  expect(time).toHaveAttribute('dateTime', '2026-10-04T06:30:00Z');
  expect(time.textContent).toMatch(/4 Oct 2026/);
  expect(time.textContent).toMatch(/6:30:00/);
  expect(within(rows[1]).getByText('Failed sign-in')).toBeInTheDocument();
  expect(within(rows[1]).getByText('existing account')).toBeInTheDocument();
  expect(screen.getByText('Rows 1–2')).toBeInTheDocument();
});

test('describeDetails shows only the known, non-secret fields', () => {
  expect(describeDetails({ fam: 'secret-family', code_prefix: 'SR-ABC' })).toBe('');
  expect(describeDetails({ known_user: false, retry_after: 30 })).toBe('no such account · retry in 30 s');
  expect(describeDetails({ role: 'player' })).toBe('role: player');
  expect(describeDetails(null)).toBe('');
});

test('filters are sent to the API and reset paging', async () => {
  mockFetch();
  const user = setupUser();
  mount();
  await flush();
  await user.type(screen.getByLabelText(/^Username/, { selector: '[name="audit_username"]' }), '  Alice ');
  await user.selectOptions(screen.getByLabelText('Event'), 'login_failed');
  await user.type(screen.getByLabelText('IP address', { selector: '[name="audit_ip"]' }), '198.51.100.2');
  await user.click(screen.getByRole('button', { name: 'Apply' }));
  await flush();
  expect(auditCalls().pop()).toBe('/api/admin/auth-events?username=Alice&event=login_failed&ip=198.51.100.2&limit=50&offset=0');

  await user.click(screen.getByRole('button', { name: 'Clear filters' }));
  await flush();
  expect(auditCalls().pop()).toBe('/api/admin/auth-events?limit=50&offset=0');
});

test('pages through older and newer rows', async () => {
  mockFetch({
    pages: (url) => json(200, { events: EVENTS, has_more: url.includes('offset=0') }),
  });
  const user = setupUser();
  mount();
  await flush();
  const newer = screen.getByRole('button', { name: 'Newer' });
  const older = screen.getByRole('button', { name: 'Older' });
  expect(newer).toBeDisabled();
  expect(older).toBeEnabled();
  await user.click(older);
  await flush();
  expect(auditCalls().pop()).toBe('/api/admin/auth-events?limit=50&offset=50');
  expect(screen.getByText('Rows 51–52')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Older' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Newer' }));
  await flush();
  expect(auditCalls().pop()).toBe('/api/admin/auth-events?limit=50&offset=0');

  await user.selectOptions(screen.getByLabelText('Rows per page'), '100');
  await flush();
  expect(auditCalls().pop()).toBe('/api/admin/auth-events?limit=100&offset=0');
});

test('shows an empty state when nothing matches', async () => {
  mockFetch({ pages: () => json(200, { events: [], has_more: false }) });
  mount();
  await flush();
  expect(screen.getByText('No events match these filters.')).toBeInTheDocument();
});

test('a bad IP filter shows the translated server error', async () => {
  mockFetch({
    pages: (url) => (url.includes('ip=') ? json(400, { error: 'ip must be an IPv4 or IPv6 address' }) : json(200, { events: [], has_more: false })),
  });
  const user = setupUser();
  mount();
  await flush();
  await user.type(screen.getByLabelText('IP address', { selector: '[name="audit_ip"]' }), '10.0.0.*');
  await user.click(screen.getByRole('button', { name: 'Apply' }));
  await flush();
  expect(screen.getByRole('alert')).toHaveTextContent('Enter one exact IPv4 or IPv6 address (no wildcards or ranges).');
});

test('unlock needs a username or an IP before it calls the API', async () => {
  mockFetch({ pages: () => json(200, { events: [], has_more: false }) });
  const user = setupUser();
  mount();
  await flush();
  await user.click(screen.getByRole('button', { name: 'Unlock' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a username, an IP address, or both.');
  expect(unlockCalls()).toHaveLength(0);
});

test('unlock posts the username and IP and reports what was cleared', async () => {
  mockFetch({ pages: () => json(200, { events: [], has_more: false }) });
  const user = setupUser();
  mount();
  await flush();
  const form = screen.getByTestId('unlock-form');
  await user.type(within(form).getByLabelText('Username'), ' mallory ');
  await user.type(within(form).getByLabelText(/^IP address/), '203.0.113.7');
  await user.click(within(form).getByRole('button', { name: 'Unlock' }));
  await flush();
  const [[url, init]] = unlockCalls();
  expect(url).toBe('/api/admin/auth/unlock');
  expect(init.method).toBe('POST');
  expect(init.headers.Authorization).toBe('Bearer jwt');
  expect(JSON.parse(init.body)).toEqual({ username: 'mallory', ip: '203.0.113.7' });
  expect(screen.getByTestId('unlock-result')).toHaveTextContent('Cleared 2 locks and failure counters.');
  expect(showSuccess).toHaveBeenCalledWith('Unlock applied.');
});

test('unlock with nothing to clear and a server-side IP error', async () => {
  let answer = json(200, { message: 'Unlocked', keys_cleared: 0 });
  mockFetch({ pages: () => json(200, { events: [], has_more: false }), unlock: () => answer });
  const user = setupUser();
  mount();
  await flush();
  const form = screen.getByTestId('unlock-form');
  await user.type(within(form).getByLabelText('Username'), 'nobody');
  await user.click(within(form).getByRole('button', { name: 'Unlock' }));
  await flush();
  expect(screen.getByTestId('unlock-result')).toHaveTextContent('Nothing was locked for that username or address.');

  answer = json(400, { error: 'ip must be an IPv4 or IPv6 address' });
  await user.type(within(form).getByLabelText(/^IP address/), '*');
  await user.click(within(form).getByRole('button', { name: 'Unlock' }));
  await flush();
  expect(within(form).getByRole('alert')).toHaveTextContent('Enter one exact IPv4 or IPv6 address');
});

test('the Unlock button on a lockout row fills in the unlock form', async () => {
  mockFetch();
  const user = setupUser();
  mount();
  await flush();
  await user.click(within(screen.getAllByTestId('auth-event-row')[0]).getByRole('button', { name: 'Unlock mallory / 203.0.113.7' }));
  const form = screen.getByTestId('unlock-form');
  expect(within(form).getByLabelText('Username')).toHaveValue('mallory');
  expect(within(form).getByLabelText(/^IP address/)).toHaveValue('203.0.113.7');
  expect(within(form).getByLabelText('Username')).toHaveFocus();
  // The failed sign-in row has no unlock shortcut.
  expect(within(screen.getAllByTestId('auth-event-row')[1]).queryByRole('button')).toBeNull();
});

test('is translated to Greek, with Greek dates', async () => {
  await act(async () => {
    await setLanguage('el', { remember: false, save: false });
  });
  mockFetch();
  mount();
  await flush();
  expect(screen.getByRole('heading', { name: 'Συνδέσεις & κλειδώματα' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Ξεκλείδωμα' })).toBeInTheDocument();
  const row = within(screen.getAllByTestId('auth-event-row')[0]);
  expect(row.getByText('Κλείδωμα')).toBeInTheDocument();
  expect(row.getByText('κλείδωμα για 15 λεπτά')).toBeInTheDocument();
  expect(screen.getAllByTestId('auth-event-row')[0].querySelector('time').textContent).toMatch(/Οκτ/);
  await waitFor(() => expect(auditCalls().length).toBeGreaterThan(0));
});
