import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';
import { DesignProvider } from '../../../design';
import { Caption, useCaption } from '../Caption';
import { TranslationsContext, captionView, hearText, useRoomTranslations, wantedIds } from '../translations';
import { startTtsJob } from '../serverVoice';
import { toItem } from '../useListen';

jest.mock('../../../app/http', () => ({
  API_URL: '/api',
  authFetch: jest.fn(),
  getCurrentToken: () => 'tok',
}));

const en = { id: 1, user_id: 3, content: 'I open the door.', lang: 'en' };
const el = { id: 2, user_id: 5, content: 'Ανοίγω την πόρτα.', lang: 'el' };
const spoken = { id: 3, user_id: 3, content: 'I open the door.', lang: 'en', orig_lang: 'el' };

test('which messages are asked about', () => {
  const dice = { id: 4, content: 'roll', ai_message_kind: 'dice_roll:a' };
  expect(wantedIds([en, el, spoken, dice], 'el')).toEqual([1, 3]);
  expect(wantedIds([en, el, spoken], 'written')).toEqual([3]); // only originals
  expect(wantedIds([en, el, spoken], 'el', { 1: {} })).toEqual([3]); // known already
});

test('caption view: translation in the hear-in language, originals for everyone', () => {
  const rows = { el: { text: 'Ανοίγω την πόρτα.', kind: 'ai' } };
  expect(captionView(en, rows, 'el', 5)).toEqual({ body: 'Ανοίγω την πόρτα.', bodyLang: 'el', caption: 'I open the door.', captionLang: 'en', label: 'original' });
  expect(captionView(en, rows, 'written', 5)).toBeNull();
  const orig = { el: { text: 'Ανοίγω την πόρτα.', kind: 'original' } };
  expect(captionView(spoken, orig, 'written', 5).label).toBe('original'); // the Storyteller sees it too
  expect(captionView(spoken, orig, 'written', 3)).toMatchObject({ label: 'yourOriginal', caption: 'Ανοίγω την πόρτα.' });
  expect(captionView(spoken, orig, 'el', 3)).toMatchObject({ label: 'sent', body: 'Ανοίγω την πόρτα.' });
  expect(hearText(en, rows, 'el')).toEqual({ content: 'Ανοίγω την πόρτα.', lang: 'el' });
  expect(hearText(el, rows, 'el')).toBeNull();
});

function Row({ message }) {
  const cap = useCaption(message);
  return (
    <div>
      <p data-testid="body">{cap.view ? cap.bodyText : message.content}</p>
      <Caption cap={cap} />
    </div>
  );
}

test('show original swaps body and caption; EL/EN text chip; 44-px button', () => {
  const ctx = { map: { 1: { el: { text: 'Ανοίγω την πόρτα.', kind: 'ai' } } }, hearLang: 'el', userId: 5 };
  render(<DesignProvider><TranslationsContext.Provider value={ctx}><Row message={en} /></TranslationsContext.Provider></DesignProvider>);
  expect(screen.getByTestId('body')).toHaveTextContent('Ανοίγω την πόρτα.');
  expect(screen.getByTestId('msg-caption')).toHaveTextContent('EN');
  fireEvent.click(screen.getByRole('button', { name: 'Show original' }));
  expect(screen.getByTestId('body')).toHaveTextContent('I open the door.');
  expect(screen.getByTestId('msg-caption')).toHaveTextContent('EL');
  expect(screen.getByRole('button', { name: 'Show translation' })).toHaveAttribute('aria-pressed', 'true');
});

test('no caption without a translation', () => {
  render(<DesignProvider><TranslationsContext.Provider value={{ map: {}, hearLang: 'el', userId: 5 }}><Row message={en} /></TranslationsContext.Provider></DesignProvider>);
  expect(screen.queryByTestId('msg-caption')).toBeNull();
});

function Probe({ api, messages }) {
  const map = useRoomTranslations({ api, campaignId: 10, locationId: 100, messages, hearLang: 'el' });
  return <pre data-testid="map">{JSON.stringify(map)}</pre>;
}

test('room translations: asks again while some are pending', async () => {
  jest.useFakeTimers();
  const answers = [
    { ok: true, data: { translations: {}, pending: [1] } },
    { ok: true, data: { translations: { 1: { el: { text: 'Γεια', kind: 'ai' } } }, pending: [] } },
  ];
  const api = jest.fn(() => Promise.resolve(answers.shift()));
  render(<Probe api={api} messages={[en, el]} />);
  await act(async () => {});
  expect(api.mock.calls[0][0]).toBe('/voice/translations?campaign_id=10&location_id=100&ids=1&lang=el');
  await act(async () => {
    jest.advanceTimersByTime(3000);
  });
  await waitFor(() => expect(screen.getByTestId('map')).toHaveTextContent('Γεια'));
  jest.useRealTimers();
});

test('server voices wait for the translation, then read the original', async () => {
  const api = jest.fn(() => Promise.resolve({ ok: true, data: { state: 'waiting_translation' } }));
  api.mockImplementationOnce(() => Promise.resolve({ ok: true, data: { state: 'waiting_translation' } }));
  const last = { ok: true, data: { state: 'queued', job_id: 'j1' } };
  api.mockImplementation((url, opts) => Promise.resolve(opts.body.original ? last : { ok: true, data: { state: 'waiting_translation' } }));
  const r = await startTtsJob(api, 7, { tries: 2, waitMs: 0 });
  expect(r).toBe(last);
  expect(api).toHaveBeenCalledTimes(4);
  expect(api.mock.calls[3][1].body).toEqual({ message_id: 7, original: true });
});

test('phone voices read the translation when it is there by the time the line is spoken', () => {
  let rows = null;
  const item = toItem({ ...en, username: 'pl', speaker_mode: 'player' }, () => (rows ? { content: rows, lang: 'el' } : null));
  expect(item.lang).toBe('en');
  rows = 'Ανοίγω την πόρτα.';
  expect(item.lang).toBe('el');
  expect(item.text).toContain('Ανοίγω');
});
