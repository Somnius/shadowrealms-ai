import { completeSlash, parseLocalCommand, slashSuggestions } from '../slashCommands';

test('nothing is suggested unless the line starts with /', () => {
  expect(slashSuggestions('hello /ai')).toEqual([]);
  expect(slashSuggestions('')).toEqual([]);
});

test('players see local commands only; /ai verbs are admin-only', () => {
  const names = slashSuggestions('/', { isAdmin: false, limit: 50 }).map((c) => c.name);
  expect(names).toEqual(expect.arrayContaining(['/roll', '/me', '/chat']));
  expect(names.some((n) => n.startsWith('/ai'))).toBe(false);
  expect(slashSuggestions('/ai', { isAdmin: false })).toEqual([]);
});

test('admins get the backend /ai verbs, filtered by prefix', () => {
  const names = slashSuggestions('/ai r', { isAdmin: true, limit: 50 }).map((c) => c.name);
  expect(names).toEqual(['/ai respond', '/ai roll', '/ai roll-hidden', '/ai rouse']);
});

test('suggestions stop once the command has arguments', () => {
  expect(slashSuggestions('/me waves', { isAdmin: true })).toEqual([]);
  expect(slashSuggestions('/ai roll 5@6', { isAdmin: true })).toEqual([]);
  expect(slashSuggestions('/roll\nmore', { isAdmin: true })).toEqual([]);
});

test('completion adds a space only when the command takes arguments', () => {
  const [me] = slashSuggestions('/me');
  expect(completeSlash(me)).toBe('/me ');
  const [roll] = slashSuggestions('/rol');
  expect(completeSlash(roll)).toBe('/roll');
});

test('local commands are recognised', () => {
  expect(parseLocalCommand('/roll')).toEqual({ type: 'roll' });
  expect(parseLocalCommand('/me draws a blade')).toEqual({ type: 'me', text: 'draws a blade' });
  expect(parseLocalCommand('/ai roll 5')).toBeNull();
  expect(parseLocalCommand('hello')).toBeNull();
});
