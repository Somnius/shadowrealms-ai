import { buildTimeline, GROUP_WINDOW_MS } from '../grouping';
import { mergeMessages, lastServerId } from '../useRoomMessages';
import { messageKind, presentSpeaker, speakerKey } from '../messageModel';

const at = (iso) => new Date(iso).toISOString();
let seq = 0;
const msg = (over) => ({
  id: ++seq,
  user_id: 1,
  username: 'lef',
  role: 'user',
  speaker_mode: 'character',
  character_id: 7,
  character_name: 'Yorika',
  message_type: 'ic',
  content: 'hi',
  created_at: at('2026-10-04T20:00:00Z'),
  ...over,
});

beforeEach(() => {
  seq = 0;
});

test('consecutive messages of one speaker within the window form one group', () => {
  const rows = buildTimeline(
    [
      msg({ created_at: at('2026-10-04T20:00:00Z') }),
      msg({ created_at: at('2026-10-04T20:03:00Z') }),
      msg({ created_at: at('2026-10-04T20:04:59Z') }),
    ],
    { timeZone: 'UTC' }
  );
  const groups = rows.filter((r) => r.type === 'group');
  expect(groups).toHaveLength(1);
  expect(groups[0].messages).toHaveLength(3);
});

test('a gap longer than the window starts a new group', () => {
  const rows = buildTimeline(
    [msg({ created_at: at('2026-10-04T20:00:00Z') }), msg({ created_at: new Date(Date.parse('2026-10-04T20:00:00Z') + GROUP_WINDOW_MS + 1000).toISOString() })],
    { timeZone: 'UTC' }
  );
  expect(rows.filter((r) => r.type === 'group')).toHaveLength(2);
});

test('different voices of the same user do not group (IC vs OOC vs Storyteller voice)', () => {
  const rows = buildTimeline(
    [
      msg({}),
      msg({ speaker_mode: 'player', character_id: null, character_name: null }),
      msg({ speaker_mode: 'staff', character_id: null, staff_kind: 'storyteller' }),
    ],
    { timeZone: 'UTC' }
  );
  expect(rows.filter((r) => r.type === 'group')).toHaveLength(3);
});

test('day separators are inserted when the calendar day changes', () => {
  const rows = buildTimeline(
    [msg({ created_at: at('2026-10-03T23:58:00Z') }), msg({ created_at: at('2026-10-04T00:01:00Z') })],
    { timeZone: 'UTC' }
  );
  expect(rows.map((r) => r.type)).toEqual(['day', 'group', 'day', 'group']);
});

test('the unread divider goes right before the first unread message and breaks the group', () => {
  const list = [msg({}), msg({}), msg({}), msg({})];
  const rows = buildTimeline(list, { firstUnreadId: 3, timeZone: 'UTC' });
  expect(rows.map((r) => r.type)).toEqual(['day', 'group', 'unread', 'group']);
  expect(rows[3].messages[0].id).toBe(3);
});

test('dice markers are dropped, rolls and system lines become cards, hidden ids are skipped', () => {
  const list = [
    msg({ role: 'assistant', ai_message_kind: 'dice_animation:abc', content: '{}' }),
    msg({ ai_message_kind: 'dice_roll:abc', message_type: 'action' }),
    msg({ message_type: 'system', role: 'user', content: 'Room closed' }),
    msg({ role: 'assistant', ai_message_kind: 'slash_assistant', content: 'pong' }),
    msg({ ai_message_kind: 'dice_roll:def', message_type: 'action' }),
  ];
  const rows = buildTimeline(list, { timeZone: 'UTC', hiddenIds: new Set(['5']) });
  expect(rows.filter((r) => r.type === 'card').map((r) => r.kind)).toEqual(['dice', 'system', 'diagnostic']);
});

test('AI narration groups as the Storyteller, not as the posting user', () => {
  const ai = msg({ role: 'assistant', content: 'The rain falls.' });
  expect(messageKind(ai)).toBe('ai');
  expect(speakerKey(ai)).toBe('ai');
  expect(presentSpeaker(ai).tone).toBe('ai');
});

test('mergeMessages dedupes by id, sorts, and keeps optimistic rows last', () => {
  const temp = { client_id: 'tmp-1', temp: true, content: 'sending' };
  const merged = mergeMessages([{ id: 2 }, { id: 1 }, temp], [{ id: 3 }, { id: 2, content: 'updated' }]);
  expect(merged.map((m) => m.id || m.client_id)).toEqual([1, 2, 3, 'tmp-1']);
  expect(merged[1].content).toBe('updated');
  expect(lastServerId(merged)).toBe(3);
});
