import { render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider, ToastProvider } from '../../../design';
import { ChronicleVoicePanel, VoiceSettingsPanel } from '../VoiceSettings';

const mockApi = jest.fn();
jest.mock('../../../app/AuthContext', () => ({ useApi: () => mockApi }));

const wrap = (ui) => render(<DesignProvider><ToastProvider>{ui}</ToastProvider></DesignProvider>);
const USER = {
  tts_source: 'phone', en_accent: 'us', rate: 1, volume: 1,
  overrides: { storyteller: null, ic: null, ooc: null, dice: null, actions: null },
};

beforeEach(() => mockApi.mockReset());

test('profile panel saves an opt-out', async () => {
  mockApi.mockImplementation(async (path, opts) => ({ ok: true, status: 200, data: opts && opts.body ? { ...USER, ...opts.body } : USER }));
  const user = setupUser();
  wrap(<VoiceSettingsPanel />);
  const ooc = await screen.findByLabelText('Out of character');
  await user.selectOptions(ooc, 'off');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/voice/settings', expect.objectContaining({ method: 'PUT' })));
  const body = mockApi.mock.calls.find((c) => c[1] && c[1].method === 'PUT')[1].body;
  expect(body.overrides.ooc).toBe(false);
  expect(body.overrides.dice).toBeNull();
});

test('chronicle panel saves read-out defaults', async () => {
  const settings = { defaults: { storyteller: true, ic: true, ooc: true, dice: true } };
  mockApi.mockResolvedValue({ ok: true, status: 200, data: { settings, can_edit: true, effective: {} } });
  const user = setupUser();
  wrap(<ChronicleVoicePanel campaignId={4} />);
  await user.click(await screen.findByLabelText('Dice results'));
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() =>
    expect(mockApi).toHaveBeenCalledWith('/campaigns/4/voice-settings', { method: 'PUT', body: { defaults: { ...settings.defaults, dice: false } } })
  );
});
