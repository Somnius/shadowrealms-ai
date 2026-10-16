/** Read along (0.22): chunks, roll requests and dice in the listener's language, the queue's
 * current chunk and "Read this", chunked server audio, the catch-up choice, the message menu,
 * roll-line captions and the Storyteller's "delete all recordings". */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import setupUser from '../../../design/testing/setupUser';
import { DesignProvider, ToastProvider } from '../../../design';
import { diceSentence, rollRequestSentence, spokenParts, splitChunks, CHUNK_MAX } from '../readout';
import { createSpeechQueue } from '../speechQueue';
import { serverEngine } from '../serverVoice';
import { catchUpList, toItem } from '../useListen';
import { SpeakingBar } from '../ListenControls';
import { ChronicleVoicePanel } from '../VoiceSettings';
import { MessageActions, MessageActionsContext } from '../../chat/MessageActions';
import { MessageGroup } from '../../chat/Messages';
import { TranslationsContext } from '../translations';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  getCurrentToken: () => 'tok',
  authFetch: async () => ({ ok: true, blob: async () => 'audio-bytes' }),
  errorText: (d, f) => f,
}));
const mockApi = jest.fn();
jest.mock('../../../app/AuthContext', () => ({ useApi: () => mockApi }));

const tick = () => new Promise((r) => setTimeout(r, 0));

test('chunks: sentences, Greek question mark, quotes kept, capped', () => {
  expect(splitChunks('Τι θέλεις; Φύγε τώρα.', 12)).toEqual(['Τι θέλεις;', 'Φύγε τώρα.']);
  expect(splitChunks('He said "Run." Then nothing.', 20)).toEqual(['He said "Run."', 'Then nothing.']);
  expect(splitChunks('λέξη '.repeat(120)).every((c) => c.length <= CHUNK_MAX)).toBe(true);
  expect(splitChunks('')).toEqual([]);
});

test('roll requests are said in the listener language, never the English chip text', () => {
  const st = { id: 1, role: 'assistant', content: 'Κοιτάς γύρω. [[roll: Intelligence + Investigation | 7 dice | 1 hunger | difficulty 2]]' };
  const el = spokenParts(st, { listenLang: 'el' });
  expect(el[0]).toEqual({ text: 'Κοιτάς γύρω. Intelligence + Investigation', lang: 'el' });
  expect(el[1]).toEqual({ text: 'Ρίψη: Intelligence συν Investigation, 7 ζάρια, Πείνα 1, δυσκολία 2.', lang: 'el' });
  expect(rollRequestSentence({ label: 'Wits + Awareness', pool: 1, difficulty: 6 }, 'en')).toBe('Roll: Wits plus Awareness, 1 die, difficulty 6.');
});

test('dice: one sentence from the marker in the listener language', () => {
  const m = { rules_edition: 'v5', dice_preview: [1, 2, 6, 10, 10, 7, 8], successes: 6, difficulty: 3, is_critical: true };
  expect(diceSentence('Mira', 'Mira rolls (V5) for **Intelligence + Investigation**', m, 'el')).toBe(
    'Mira: Ρίψη Intelligence συν Investigation, 7 ζάρια, 6 επιτυχίες, κρίσιμη επιτυχία.',
  );
  const msg = { id: 3, ai_message_kind: 'dice_roll:a', username: 'pl', content: 'pl rolls (V5) for **Brawl**' };
  expect(spokenParts(msg, { listenLang: 'el', marker: null })[0].lang).toBe('en'); // no marker: English voice
  const it = toItem(msg, null, { listenLang: 'el', getMarker: () => ({ rules_edition: 'v5', dice_preview: [6], successes: 1 }) });
  expect(it.parts).toEqual([{ text: 'pl: Ρίψη Brawl, 1 ζάρι, 1 επιτυχία, επιτυχία.', lang: 'el' }]);
});

test('queue: the chunk being said is in the state; play() reads a line again', () => {
  const e = { said: [], speak: jest.fn((item, done, onPart) => { e.said.push(item.id); e.done = done; onPart({ index: 0, count: 2, text: 'First.' }); }), cancel: jest.fn() };
  const onDone = jest.fn();
  const q = createSpeechQueue(e, { onDone });
  q.enqueue([{ id: 1, speaker: 'x' }]);
  expect(q.state().part.text).toBe('First.');
  e.done();
  expect(onDone).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
  q.enqueue([{ id: 1 }]);
  expect(e.said).toEqual([1]); // already read: not again from the live feed
  q.play([{ id: 1 }, { id: 2 }]);
  expect(e.said).toEqual([1, 1]);
});

test('server voices: chunk 0 plays while 1 and 2 are made, then 1 plays', async () => {
  global.URL.createObjectURL = (() => { let n = 0; return () => `blob:${(n += 1)}`; })();
  global.URL.revokeObjectURL = () => {};
  const el = { played: [], canPlayType: () => 'probably', play() { this.played.push(this.src); return Promise.resolve(); }, pause: jest.fn() };
  const api = jest.fn(async (path, opts) => ({ ok: true, data: { job_id: 'j', state: 'done', key: `k${opts.body.chunk}`, chunks: 4, text: `s${opts.body.chunk}` } }));
  const parts = [];
  const done = jest.fn();
  serverEngine({ api, getAudio: () => el, getSettings: () => ({}) }).speak({ id: 9, listenLang: 'el' }, done, (p) => parts.push(p.text));
  for (let i = 0; i < 6; i += 1) await tick();
  expect(api.mock.calls.map((c) => c[1].body.chunk).sort()).toEqual([0, 1, 2]);
  expect(api.mock.calls[0][1].body.lang).toBe('el');
  expect(parts).toEqual(['s0']);
  el.onended();
  for (let i = 0; i < 6; i += 1) await tick();
  expect(parts).toEqual(['s0', 's1']);
  expect(el.played).toHaveLength(2);
  expect(api.mock.calls.map((c) => c[1].body.chunk)).toContain(3);
});

test('catch-up choices', () => {
  const r = Array.from({ length: 12 }, (_, i) => ({ id: i + 1 }));
  expect(catchUpList(r, 'last3', 0).map((m) => m.id)).toEqual([10, 11, 12]);
  expect(catchUpList(r, 'last10', 0)).toHaveLength(10);
  expect(catchUpList(r, 'resume', 9).map((m) => m.id)).toEqual([10, 11, 12]);
  expect(catchUpList(r, 'none', 0)).toEqual([]);
});

const listenBase = (over = {}) => ({
  on: true, active: true, catchUp: 0, follow: true, catchUpChoice: 'last10', chooseCatchUp: jest.fn(), resumeFollow: jest.fn(),
  toggle: jest.fn(), pause: jest.fn(), resume: jest.fn(), skip: jest.fn(), stop: jest.fn(),
  state: { current: null, part: null, queued: 0, paused: false, needsResume: false, missed: 0 }, ...over,
});

test('speaking bar: the catch-up choice (remembered one first), the sentence, Follow', () => {
  const l = listenBase({ catchUp: 5 });
  const { rerender } = render(<DesignProvider><SpeakingBar listen={l} /></DesignProvider>);
  const buttons = screen.getAllByRole('button').map((b) => b.textContent);
  expect(buttons).toEqual(['Last 10', 'Last 3', 'From where I stopped', 'None']);
  fireEvent.click(screen.getByRole('button', { name: 'From where I stopped' }));
  expect(l.chooseCatchUp).toHaveBeenCalledWith('resume');
  const reading = listenBase({ on: false, follow: false, state: { ...l.state, current: { id: 3, speaker: 'Storyteller' }, part: { index: 1, count: 3, text: 'The door opens.' } } });
  rerender(<DesignProvider><SpeakingBar listen={reading} /></DesignProvider>);
  expect(screen.getByTestId('speak-sentence')).toHaveTextContent('The door opens.');
  fireEvent.click(screen.getByRole('button', { name: 'Follow' }));
  expect(reading.resumeFollow).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Stop reading' }));
  expect(reading.stop).toHaveBeenCalled();
});

test('message menu: Read this / Read from here', () => {
  const onRead = jest.fn();
  const msg = { id: 4, role: 'assistant', content: 'Hi' };
  const ctx = { openId: 4, setOpenId: jest.fn(), canDelete: () => false, canRead: () => true, onRead, onCopy: jest.fn(), onReply: jest.fn() };
  render(<DesignProvider><MessageActionsContext.Provider value={ctx}><MessageActions message={msg} /></MessageActionsContext.Provider></DesignProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'Read this' }));
  expect(onRead).toHaveBeenLastCalledWith(msg, false);
  fireEvent.click(screen.getByRole('button', { name: 'Read from here' }));
  expect(onRead).toHaveBeenLastCalledWith(msg, true);
});

test('message menu: no read buttons without read-out', () => {
  const ctx = { openId: 4, setOpenId: jest.fn(), canDelete: () => false, canRead: null };
  render(<DesignProvider><MessageActionsContext.Provider value={ctx}><MessageActions message={{ id: 4, content: 'x' }} /></MessageActionsContext.Provider></DesignProvider>);
  expect(screen.queryByRole('button', { name: 'Read this' })).toBeNull();
});

test('roll-request lines get a translation caption; the chips stay', () => {
  const m = { id: 8, role: 'assistant', content: 'You look around. [[roll: Wits + Awareness | 5 dice | difficulty 6]]', created_at: '2026-10-17T10:00:00Z' };
  const ctx = { map: { 8: { el: { text: 'Κοιτάς γύρω. **Wits + Awareness**', kind: 'ai' } } }, hearLang: 'el', userId: 2 };
  render(
    <DesignProvider>
      <TranslationsContext.Provider value={ctx}>
        <MessageGroup group={{ kind: 'ai', messages: [m] }} timeZone={null} now={Date.now()} />
      </TranslationsContext.Provider>
    </DesignProvider>,
  );
  expect(screen.getByTestId('msg-caption')).toHaveTextContent('You look around. Wits + Awareness');
  expect(screen.getByTestId('msg-caption')).not.toHaveTextContent('[[');
  expect(screen.getByText(/Κοιτάς γύρω/)).toBeInTheDocument();
  expect(screen.getByText(/Roll: Wits \+ Awareness/)).toBeInTheDocument();
});

test('chronicle settings: the Storyteller deletes all recordings after a confirm', async () => {
  const settings = { defaults: { storyteller: true, ic: true, ooc: true, dice: true } };
  mockApi.mockImplementation(async (path, opts) => {
    if (opts && opts.method === 'DELETE') return { ok: true, status: 200, data: { deleted: 3 } };
    if (path === '/voice/voices') return { ok: true, status: 200, data: { available: false, voices: [] } };
    return { ok: true, status: 200, data: { settings, can_edit: true, effective: {} } };
  });
  const user = setupUser();
  render(<DesignProvider><ToastProvider><ChronicleVoicePanel campaignId={4} /></ToastProvider></DesignProvider>);
  await user.click(await screen.findByRole('button', { name: 'Delete all recordings' }));
  expect(mockApi).not.toHaveBeenCalledWith('/campaigns/4/voice-clips', expect.anything());
  await user.click(screen.getByRole('button', { name: 'Delete recordings' }));
  await waitFor(() => expect(mockApi).toHaveBeenCalledWith('/campaigns/4/voice-clips', { method: 'DELETE' }));
  expect(await screen.findByText('Deleted 3 recordings.')).toBeInTheDocument();
});

test('chronicle settings: players do not see the delete button', async () => {
  mockApi.mockImplementation(async () => ({ ok: true, status: 200, data: { settings: { defaults: {} }, can_edit: false, effective: {} } }));
  render(<DesignProvider><ToastProvider><ChronicleVoicePanel campaignId={4} /></ToastProvider></DesignProvider>);
  await act(tick);
  expect(screen.queryByRole('button', { name: 'Delete all recordings' })).toBeNull();
});
