import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider, ToastProvider } from '../../../design';
import CloudVoicesPanel from '../CloudVoicesPanel';
import VoiceHealthPanel from '../VoiceHealthPanel';
import { ChronicleVoicePanel } from '../VoiceSettings';

const mockFetch = jest.fn();
jest.mock('../../../app/http', () => ({
  ...jest.requireActual('../../../app/http'),
  apiFetch: (...a) => mockFetch(...a),
  getCurrentToken: () => 'tok',
}));
const mockApi = jest.fn();
jest.mock('../../../app/AuthContext', () => ({ useApi: () => mockApi }));

const wrap = (ui) => render(<DesignProvider><ToastProvider>{ui}</ToastProvider></DesignProvider>);
const MODELS = ['gemini-3.8-flash-lite-tts', 'gemini-3.8-flash-tts'];

beforeEach(() => {
  mockFetch.mockReset();
  mockApi.mockReset();
});

test('admin panel shows keys present and saves the tier and model', async () => {
  mockFetch.mockImplementation(async (tok, path, opts) => ({
    ok: true,
    data: { tier: 'off', model: MODELS[0], models: MODELS, keys: { free: true, paid: false }, ...(opts && opts.body) },
  }));
  const user = setupUser();
  wrap(<CloudVoicesPanel />);
  expect((await screen.findByText(/Free key \(GEMINI_API_KEY\) set:/)).parentElement).toHaveTextContent('Yes');
  expect(screen.getByText(/Paid key/).parentElement).toHaveTextContent('No');
  expect(screen.getByText(/Google may use the text/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Cloud voices'), 'paid');
  expect(screen.getByText(/no key for this tier/)).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText('Model'), MODELS[1]);
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() =>
    expect(mockFetch).toHaveBeenCalledWith('tok', '/voice/cloud-settings', { method: 'PUT', body: { tier: 'paid', model: MODELS[1] } })
  );
});

test('health panel shows the cloud errors today and the last one', async () => {
  mockFetch.mockResolvedValue({ ok: true, data: {
    speech: { up: true }, queues: {}, vram: {}, disk: {}, minutes_today: [],
    cloud: { tier: 'free', errors_today: 2, last_error: { code: 'rate_limited', at: '2026-10-17T10:00:00Z' } },
  } });
  wrap(<VoiceHealthPanel />);
  const line = await screen.findByTestId('cloud-health');
  expect(line).toHaveTextContent('Free tier');
  expect(line).toHaveTextContent('errors today: 2');
  expect(line).toHaveTextContent('rate_limited');
});

const CATALOG = {
  available: true,
  voices: [{ id: 'el-spyros', lang: 'el', accent: 'gr', gender: 'male', default_for: ['narrator'] }],
  cloud_voices: [{ id: 'gemini-Kore', engine: 'gemini', lang: 'multi', style: 'Firm', gender: 'female' }],
};

test('chronicle opt-in shows Gemini narrator voices and saves cloud_voices', async () => {
  const settings = { defaults: { storyteller: true, ic: true, ooc: true, dice: true }, cloud_voices: false };
  mockApi.mockImplementation(async (path) =>
    path === '/voice/voices'
      ? { ok: true, status: 200, data: CATALOG }
      : { ok: true, status: 200, data: { settings, can_edit: true, effective: {}, cloud_available: true } });
  const user = setupUser();
  wrap(<ChronicleVoicePanel campaignId={4} />);
  const box = await screen.findByLabelText('Use cloud voices (Google Gemini)');
  const greek = await screen.findByLabelText('Greek');
  expect(greek).not.toHaveTextContent('Kore');
  await user.click(box);
  expect(screen.getByLabelText('Greek')).toHaveTextContent('Kore · Firm (Gemini)');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => {
    const put = mockApi.mock.calls.find((c) => c[1] && c[1].method === 'PUT');
    expect(put[1].body.cloud_voices).toBe(true);
  });
});

test('no cloud choice when the admin left cloud voices off', async () => {
  const settings = { defaults: { storyteller: true, ic: true, ooc: true, dice: true } };
  mockApi.mockImplementation(async (path) =>
    path === '/voice/voices'
      ? { ok: true, status: 200, data: { ...CATALOG, cloud_voices: [] } }
      : { ok: true, status: 200, data: { settings, can_edit: true, effective: {}, cloud_available: false } });
  wrap(<ChronicleVoicePanel campaignId={4} />);
  await screen.findByLabelText('Greek');
  expect(screen.queryByTestId('cloud-voices-choice')).toBeNull();
});
