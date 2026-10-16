import { RATES, clock, nextRate, pickMime, pulsesAt, sttLang, stripFillers, timerPhase } from '../recorder';

test('timer colours: gold, warn at 1:00, blood at 2:00, bright blood from 2:45', () => {
  expect([0, 59, 60, 119, 120, 164, 165, 180].map((s) => timerPhase(s))).toEqual(
    ['gold', 'gold', 'warn', 'warn', 'blood', 'blood', 'bright', 'bright']
  );
});

test('a 60 s limit scales the colours and the last-15-s pulse', () => {
  expect([0, 19, 20, 40, 44, 45].map((s) => timerPhase(s, 60))).toEqual(['gold', 'gold', 'warn', 'blood', 'blood', 'bright']);
  expect([44, 45, 46].map((s) => pulsesAt(s, 60))).toEqual([false, true, true]);
});

test('pulse every 5 s, every second in the last 15 s', () => {
  expect([0, 1, 5, 10, 11, 160, 164, 165, 166].map((s) => pulsesAt(s))).toEqual(
    [false, false, true, true, false, true, false, true, true]
  );
});

test('one rate control steps 0.75 → 2 and wraps', () => {
  expect(RATES).toEqual([0.75, 1, 1.25, 1.5, 1.75, 2]);
  expect(nextRate(1)).toBe(1.25);
  expect(nextRate(2)).toBe(0.75);
  expect(nextRate(3)).toBe(0.75);
});

test('clock and language', () => {
  expect(clock(0)).toBe('0:00');
  expect(clock(107.9)).toBe('1:47');
  expect(sttLang('auto', 'el')).toBe('el');
  expect(sttLang('auto', 'en')).toBe('en');
  expect(sttLang('en', 'el')).toBe('en');
});

test('mime: WebM/Opus first, MP4 for iOS, nothing without MediaRecorder', () => {
  expect(pickMime({ isTypeSupported: () => true })).toBe('audio/webm;codecs=opus');
  expect(pickMime({ isTypeSupported: (m) => m === 'audio/mp4' })).toBe('audio/mp4');
  expect(pickMime(null)).toBe('');
});

test('fillers are stripped, words kept', () => {
  expect(stripFillers('Um, I open the door uh slowly.')).toBe('I open the door slowly.');
  expect(stripFillers('Εε, ανοίγω την πόρτα μμμ αργά.')).toBe('ανοίγω την πόρτα αργά.');
  expect(stripFillers('Ερμής ήρθε')).toBe('Ερμής ήρθε');
});
