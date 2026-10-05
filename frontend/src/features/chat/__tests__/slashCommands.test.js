import { completeSlash, parseLocalCommand, slashSuggestions } from '../slashCommands';

test('nothing is suggested unless the line starts with /', () => {
  expect(slashSuggestions('hello /ai')).toEqual([]);
  expect(slashSuggestions('')).toEqual([]);
});

test('players see local commands and /ai explain; the other /ai verbs are admin-only', () => {
  const names = slashSuggestions('/', { isAdmin: false, limit: 50 }).map((c) => c.name);
  expect(names).toEqual(expect.arrayContaining(['/roll', '/me', '/chat', '/ai explain']));
  expect(names.filter((n) => n.startsWith('/ai'))).toEqual(['/ai explain']);
  expect(slashSuggestions('/ai', { isAdmin: false }).map((c) => c.name)).toEqual(['/ai explain']);
});

test('/ai respond is described as diagnostics, pointing to /ai explain', () => {
  const [respond] = slashSuggestions('/ai respond', { isAdmin: true });
  expect(respond.description()).toMatch(/^Diagnostics only/);
  expect(respond.description()).toContain('/ai explain');
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

test('/ai dice-diff shows the arguments of the room edition', () => {
  const [generic] = slashSuggestions('/ai dice', { isAdmin: true });
  expect(generic.args).toMatch(/2-10/);
  expect(generic.args).toMatch(/no-bestial/);
  const [classic] = slashSuggestions('/ai dice', { isAdmin: true, edition: 'classic' });
  expect(classic.args).toBe('<2-10 | restore>');
  expect(classic.description()).toMatch(/floor/);
  const [v5] = slashSuggestions('/ai dice', { isAdmin: true, edition: 'v5' });
  expect(v5.args).toMatch(/no-bestial on\|off/);
  expect(v5.args).not.toMatch(/2-10/);
  expect(v5.description()).toMatch(/bestial/);
});
