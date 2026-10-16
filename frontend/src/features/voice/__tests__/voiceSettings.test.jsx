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
  mockApi.mockImplementation(async (path) =>
    path === '/voice/voices'
      ? { ok: true, status: 200, data: { available: false, voices: [] } }
      : { ok: true, status: 200, data: { settings, can_edit: true, effective: {} } });
  const user = setupUser();
  wrap(<ChronicleVoicePanel campaignId={4} />);
  expect(await screen.findByTestId('narrator-off')).toBeInTheDocument();
  await user.click(await screen.findByLabelText('Dice results'));
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() =>
    expect(mockApi).toHaveBeenCalledWith('/campaigns/4/voice-settings', { method: 'PUT', body: {
      defaults: { ...settings.defaults, dice: false },
      narrator_voice_en: null, narrator_voice_en_gb: null, narrator_voice_el: null,
      max_clip_seconds: 180, allow_phone_stt: true,
    } })
  );
});

const VOICES = {
  available: true,
  voices: [
    { id: 'en_US-ryan-high', lang: 'en', accent: 'us', gender: 'male', default_for: ['male', 'narrator'] },
    { id: 'en_US-lessac-medium', lang: 'en', accent: 'us', gender: 'female', default_for: ['female'] },
    { id: 'en_GB-alan-medium', lang: 'en', accent: 'gb', gender: 'male', default_for: ['narrator'] },
    { id: 'el-spyros', lang: 'el', accent: 'gr', gender: 'male', default_for: ['narrator'] },
    { id: 'el-eleni', lang: 'el', accent: 'gr', gender: 'female', default_for: ['neutral'] },
  ],
};

test('chronicle panel picks a narrator voice per language', async () => {
  const settings = { defaults: { storyteller: true, ic: true, ooc: true, dice: true }, narrator_voice_el: 'el-spyros' };
  mockApi.mockImplementation(async (path) =>
    path === '/voice/voices'
      ? { ok: true, status: 200, data: VOICES }
      : { ok: true, status: 200, data: { settings, can_edit: true, effective: {} } });
  const user = setupUser();
  wrap(<ChronicleVoicePanel campaignId={4} />);
  const us = await screen.findByLabelText('English (American)');
  expect(screen.getByLabelText('Greek')).toHaveValue('el-spyros');
  expect(screen.getAllByRole('option', { name: /lessac/ })).toHaveLength(1); // US list only has US voices
  await user.selectOptions(us, 'en_US-lessac-medium');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/campaigns/4/voice-settings', expect.objectContaining({ method: 'PUT' })));
  const body = mockApi.mock.calls.find((c) => c[1] && c[1].method === 'PUT')[1].body;
  expect(body).toMatchObject({ narrator_voice_en: 'en_US-lessac-medium', narrator_voice_en_gb: null, narrator_voice_el: 'el-spyros' });
});

test('profile panel offers server voices', async () => {
  mockApi.mockResolvedValue({ ok: true, status: 200, data: USER });
  wrap(<VoiceSettingsPanel />);
  const source = await screen.findByLabelText('Read messages aloud with');
  expect(screen.getByRole('option', { name: 'Server voices' })).toBeInTheDocument();
  expect(source).toHaveValue('phone');
});
