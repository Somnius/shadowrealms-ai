import {
  completeSlash, fromServer, loadSlashCommands, parseLocalCommand, resetSlashCommands, slashSuggestions,
} from '../slashCommands';
import i18next from 'i18next';

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

const SERVER = [
  { name: '/roll', args: '', admin: false, local: 'roll', description: { en: 'Roll here', el: 'Ρίξε εδώ' } },
  { name: '/ai explain', args: '', admin: false, description: { en: 'Explain a roll', el: 'Εξήγηση ρίψης' } },
  {
    name: '/ai dice-diff', args: '<x>', admin: true, description: { en: 'Leniency', el: 'Επιείκεια' },
    v5: { args: '<v5>', description: { en: 'V5 leniency', el: 'Επιείκεια V5' } },
  },
];

const ok = (body) => () => Promise.resolve({ ok: true, json: () => Promise.resolve(body) });

describe('the list from the server', () => {
  afterEach(() => resetSlashCommands());

  test('suggestions come from a provided list, as the server filtered it', () => {
    const commands = fromServer(SERVER);
    expect(slashSuggestions('/', { commands, limit: 50 }).map((c) => c.name)).toEqual(['/roll', '/ai explain', '/ai dice-diff']);
    const [v5] = slashSuggestions('/ai d', { commands, edition: 'v5' });
    expect(v5.args).toBe('<v5>');
    expect(v5.description()).toBe('V5 leniency');
  });

  test('the Greek description when the language is el', async () => {
    const prev = i18next.language;
    await i18next.changeLanguage('el');
    try {
      const [explain] = slashSuggestions('/ai e', { commands: fromServer(SERVER) });
      expect(explain.description()).toBe('Εξήγηση ρίψης');
    } finally {
      await i18next.changeLanguage(prev);
    }
  });

  test('fetched once per session, with the token', async () => {
    const fetcher = jest.fn(ok({ commands: SERVER, version: 1 }));
    const a = await loadSlashCommands('tok', fetcher);
    const b = await loadSlashCommands('tok', fetcher);
    expect(a).toBe(b);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe('/api/ai/slash/commands');
    expect(fetcher.mock.calls[0][1].headers.Authorization).toBe('Bearer tok');
  });

  test('a failed fetch rejects (the composer keeps the fallback) and is tried again', async () => {
    const down = jest.fn(() => Promise.reject(new Error('offline')));
    await expect(loadSlashCommands('tok', down)).rejects.toThrow('offline');
    await expect(loadSlashCommands('tok', jest.fn(() => Promise.resolve({ ok: false, status: 500 })))).rejects.toThrow('500');
    expect(await loadSlashCommands('tok', jest.fn(ok({ commands: SERVER })))).toHaveLength(3);
    expect(slashSuggestions('/ai', { isAdmin: false }).map((c) => c.name)).toEqual(['/ai explain']);
  });
});
