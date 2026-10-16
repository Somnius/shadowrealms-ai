import { render, screen } from '@testing-library/react';
import { DesignProvider } from '../../../design';
import VoiceHealthPanel, { fmtBytes } from '../VoiceHealthPanel';
import { isPushToTalkKey } from '../recorder';

const mockFetch = jest.fn();
jest.mock('../../../app/http', () => ({
  apiFetch: (...a) => mockFetch(...a),
  getCurrentToken: () => 'tok',
}));

test('admin panel shows queues, VRAM, disk and minutes today', async () => {
  mockFetch.mockResolvedValue({ ok: true, data: {
    speech: { up: true, stt_loaded: false }, queues: { stt: 1, tts: 3 }, vram: { free_mb: 9000, needed_mb: 2150 },
    disk: { clips_bytes: 2 * 1024 ** 2, clips_cap_bytes: 20 * 1024 ** 3, tts_cache_bytes: 0, tts_cache_cap_bytes: 5 * 1024 ** 3 },
    minutes_today: [{ user_id: 3, username: 'pl', minutes: 1.5, clips: 2 }],
  } });
  render(<DesignProvider><VoiceHealthPanel /></DesignProvider>);
  expect(await screen.findByText(/transcribe 1, speak 3/)).toBeInTheDocument();
  expect(screen.getByText(/9000 MB free/)).toBeInTheDocument();
  expect(screen.getByText(/2\.0 MB \/ 20\.0 GB/)).toBeInTheDocument();
  expect(screen.getByText(/pl 1\.5 min \(2\)/)).toBeInTheDocument();
  expect(mockFetch).toHaveBeenCalledWith('tok', '/voice/health');
});

test('fmtBytes', () => {
  expect(fmtBytes(null)).toBe('—');
  expect(fmtBytes(2048)).toBe('2 KB');
});

test('Space is push-to-talk, but not while typing, repeating or with a modifier', () => {
  const div = document.createElement('div');
  const input = document.createElement('input');
  const ta = document.createElement('textarea');
  expect(isPushToTalkKey({ code: 'Space', target: div })).toBe(true);
  expect(isPushToTalkKey({ code: 'Space', target: document.body })).toBe(true);
  expect(isPushToTalkKey({ code: 'Space', target: input })).toBe(false);
  expect(isPushToTalkKey({ code: 'Space', target: ta })).toBe(false);
  expect(isPushToTalkKey({ code: 'Space', target: div, repeat: true })).toBe(false);
  expect(isPushToTalkKey({ code: 'Space', target: div, ctrlKey: true })).toBe(false);
  expect(isPushToTalkKey({ code: 'KeyA', key: 'a', target: div })).toBe(false);
});
