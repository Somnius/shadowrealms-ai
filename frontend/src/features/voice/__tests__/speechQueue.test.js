import { createSpeechQueue, QUEUE_CAP } from '../speechQueue';
import { pickVoice } from '../phoneVoice';

function fakeEngine() {
  const e = { said: [], pending: null, cancels: 0 };
  e.speak = (item, done) => {
    e.said.push(item.id);
    e.pending = done;
  };
  e.cancel = () => {
    e.cancels += 1;
  };
  e.finish = () => {
    const d = e.pending;
    e.pending = null;
    d && d();
  };
  return e;
}
const items = (ids) => ids.map((id) => ({ id, text: `m${id}`, speaker: 'x' }));

test('speaks in order, once each', () => {
  const e = fakeEngine();
  const q = createSpeechQueue(e);
  q.enqueue(items([1, 2]));
  q.enqueue(items([2, 3]));
  expect(e.said).toEqual([1]);
  e.finish();
  e.finish();
  e.finish();
  expect(e.said).toEqual([1, 2, 3]);
  expect(q.state().current).toBeNull();
});

test('cap keeps the newest and counts the missed', () => {
  const e = fakeEngine();
  const q = createSpeechQueue(e);
  q.pause();
  q.enqueue(items(Array.from({ length: QUEUE_CAP + 5 }, (_, i) => i + 1)));
  expect(q.state().queued).toBe(QUEUE_CAP);
  expect(q.state().missed).toBe(5);
  q.resume();
  expect(e.said).toEqual([6]);
});

test('skip, pause puts the line back, hide waits for a tap, stop clears', () => {
  const e = fakeEngine();
  const q = createSpeechQueue(e);
  q.enqueue(items([1, 2, 3]));
  const stale = e.pending;
  q.skip();
  stale(); // a late onend from the cancelled line is ignored
  expect(e.said).toEqual([1, 2]);
  q.pause();
  expect(q.state()).toMatchObject({ paused: true, current: null, queued: 2 });
  q.resume();
  expect(e.said).toEqual([1, 2, 2]);
  q.hide();
  expect(q.state().needsResume).toBe(true);
  q.resume();
  q.stop();
  expect(q.state()).toMatchObject({ current: null, queued: 0, missed: 0 });
});

test('pickVoice by language and accent', () => {
  const voices = [{ lang: 'en-US', name: 'a' }, { lang: 'en_GB', name: 'b' }, { lang: 'el-GR', name: 'c' }];
  expect(pickVoice(voices, 'el').name).toBe('c');
  expect(pickVoice(voices, 'en', 'gb').name).toBe('b');
  expect(pickVoice(voices, 'en', 'us').name).toBe('a');
  expect(pickVoice([], 'el')).toBeNull();
});
