import { act, render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider } from '../../../design';
import Composer, { voiceOptions } from '../../chat/Composer';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  authFetch: (...a) => mockAuthFetch(...a),
  getCurrentToken: () => 'tok',
  apiFetch: jest.fn(),
  errorText: (d, f) => f,
}));
const mockAuthFetch = jest.fn();

class FakeRecorder {
  static isTypeSupported(m) {
    return m === 'audio/mp4';
  }
  constructor(stream, opts) {
    this.state = 'inactive';
    this.mimeType = opts.mimeType;
    FakeRecorder.last = this;
  }
  start() {
    this.state = 'recording';
  }
  stop() {
    this.state = 'inactive';
    this.ondataavailable({ data: new Blob(['x'], { type: 'audio/mp4' }) });
    this.onstop();
  }
}

const getUserMedia = jest.fn();
beforeEach(() => {
  sessionStorage.clear();
  global.MediaRecorder = FakeRecorder;
  global.URL.createObjectURL = jest.fn(() => 'blob:1');
  global.URL.revokeObjectURL = jest.fn();
  Object.defineProperty(global.navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true });
  getUserMedia.mockReset();
  mockAuthFetch.mockReset();
});
afterEach(() => {
  delete global.MediaRecorder;
});

const userRow = { id: 1, username: 'lef' };
const character = { id: 7, name: 'Yorika' };

function renderIt(voice) {
  return render(
    <DesignProvider>
      <Composer
        roomName="Elysium"
        speakAs="character"
        voices={voiceOptions({ character, user: userRow, canStaff: false })}
        onSpeakAsChange={jest.fn()}
        character={character}
        onSend={jest.fn()}
        draftKey="r1"
        voice={voice}
      />
    </DesignProvider>
  );
}

test('record → review → transcribe → edit → send with the clip; the box comes back after', async () => {
  const u = setupUser();
  getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] });
  mockAuthFetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ clip_id: 'c'.repeat(32), job_id: 'j1', state: 'queued' }) });
  const api = jest.fn().mockResolvedValue({ ok: true, data: { state: 'done', text: 'Um, I open the door.', clip_id: 'c'.repeat(32) } });
  const onSend = jest.fn().mockResolvedValue(true);
  renderIt({ api, campaignId: 1, locationId: 2, lang: 'en', maxSeconds: 180, phoneDictation: false, canPhoneDictate: false, onSend });
  await u.click(screen.getByRole('button', { name: 'Record a voice message' }));
  expect(screen.getByTestId('recorder-sheet')).toBeInTheDocument();
  await waitFor(() => expect(FakeRecorder.last && FakeRecorder.last.state).toBe('recording'));
  expect(mockAuthFetch).not.toHaveBeenCalled(); // nothing goes up while recording
  await u.click(screen.getByRole('button', { name: 'Stop' }));
  expect(screen.getByRole('slider', { name: 'Position in the recording' })).toBeInTheDocument();
  const rate = screen.getByTestId('rate');
  expect(rate).toHaveTextContent('1×');
  await u.click(rate);
  expect(rate).toHaveTextContent('1.25×');
  expect(mockAuthFetch).not.toHaveBeenCalled(); // nor while reviewing
  await act(async () => {
    await u.click(screen.getByRole('button', { name: 'Transcribe' }));
  });
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'What you said' })).toHaveValue('I open the door.'), { timeout: 3000 });
  expect(mockAuthFetch.mock.calls[0][0]).toBe('/api/voice/clips');
  await u.click(screen.getByRole('button', { name: 'Send' }));
  expect(onSend).toHaveBeenCalledWith({ text: 'I open the door.', clipId: 'c'.repeat(32), source: 'voice' });
  await waitFor(() => expect(screen.queryByTestId('recorder-sheet')).toBeNull());
});

test('microphone denied: the record button becomes mic-off with the Settings hint', async () => {
  const u = setupUser();
  getUserMedia.mockRejectedValue(Object.assign(new Error('no'), { name: 'NotAllowedError' }));
  renderIt({ api: jest.fn(), campaignId: 1, locationId: 2, lang: 'en', maxSeconds: 180, onSend: jest.fn() });
  await u.click(screen.getByRole('button', { name: 'Record a voice message' }));
  const off = await screen.findByTestId('mic-off');
  expect(screen.queryByTestId('mic')).toBeNull();
  await u.click(off);
  expect(screen.getByText(/Allow the microphone for this site/)).toBeInTheDocument();
});

test('no recorder and no dictation: no mic button at all', () => {
  delete global.MediaRecorder;
  renderIt({ api: jest.fn(), campaignId: 1, locationId: 2, lang: 'en', onSend: jest.fn() });
  expect(screen.queryByTestId('mic')).toBeNull();
});

test('the mic tap asks for the microphone itself (iOS), once; backgrounding stops and goes to review', async () => {
  const u = setupUser();
  getUserMedia.mockResolvedValue({ getTracks: () => [{ stop: jest.fn() }] });
  renderIt({ api: jest.fn(), campaignId: 1, locationId: 2, lang: 'en', maxSeconds: 180, onSend: jest.fn() });
  await u.click(screen.getByRole('button', { name: 'Record a voice message' }));
  expect(getUserMedia).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(FakeRecorder.last && FakeRecorder.last.state).toBe('recording'));
  expect(getUserMedia).toHaveBeenCalledTimes(1);
  Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
  delete document.visibilityState;
  expect(screen.getByRole('slider', { name: 'Position in the recording' })).toBeInTheDocument();
});

test('phone dictation unavailable and the line typed: sent as a normal line, not as voice', async () => {
  const u = setupUser();
  const onSend = jest.fn().mockResolvedValue(true);
  renderIt({ api: jest.fn(), campaignId: 1, locationId: 2, lang: 'en', maxSeconds: 180, phoneDictation: true, canPhoneDictate: true, onSend });
  await u.click(screen.getByRole('button', { name: 'Dictate a message' }));
  expect(getUserMedia).not.toHaveBeenCalled();
  const box = await screen.findByRole('textbox', { name: 'What you said' });
  await u.type(box, 'I open the door');
  await u.click(screen.getByRole('button', { name: 'Send' }));
  expect(onSend).toHaveBeenCalledWith({ text: 'I open the door', clipId: null, source: null });
});
