/**
 * Slash command registry for composer autocomplete.
 *
 * `/ai …` verbs mirror backend/services/ai_slash_commands.py SUPPORTED_AI_SLASH_VERBS (site admins only,
 * except `/ai explain`, which every member may use; the server runs them via POST /api/ai/slash).
 * Local commands are handled in the browser.
 * TODO(backend): GET /api/ai/slash/commands would let client and server never drift.
 */
import { t } from '../../i18n';

export const SLASH_COMMANDS = [
  // local commands (everyone)
  { name: '/roll', args: '', description: () => t('chat:slash.roll', 'Open the dice roller for this room'), local: 'roll' },
  { name: '/me', args: '<action>', description: () => t('chat:slash.me', 'Post an action / emote line'), local: 'me' },
  { name: '/chat', args: '<message>', description: () => t('chat:slash.chat', 'Ask the AI assistant directly (out of the story)') },
  // /ai explain (everyone): reply to a dice card to explain that roll, else the latest roll here
  { name: '/ai explain', args: '', description: () => t('chat:slash.ai.explain', 'Explain a dice roll step by step (reply to the dice card)') },
  // /ai verbs (site admins)
  { name: '/ai help', args: '', description: () => t('chat:slash.ai.help', 'List all /ai commands'), admin: true },
  { name: '/ai respond', args: '[note]', description: () => t('chat:slash.ai.respond', 'Diagnostics only: LLM echo with latency (to explain a roll use /ai explain)'), admin: true },
  { name: '/ai health', args: '', description: () => t('chat:slash.ai.health', 'LLM / vector store health snapshot'), admin: true },
  { name: '/ai model', args: '', description: () => t('chat:slash.ai.model', 'Configured and active model'), admin: true },
  { name: '/ai ping', args: '', description: () => t('chat:slash.ai.ping', 'Tiny generation to measure latency'), admin: true },
  { name: '/ai context', args: '', description: () => t('chat:slash.ai.context', 'Show the context sent for this room'), admin: true },
  { name: '/ai summarize', args: '<text>', description: () => t('chat:slash.ai.summarize', 'Summarize a wall of text'), admin: true },
  { name: '/ai roll', args: '<pool@diff>', description: () => t('chat:slash.ai.roll', 'Roll by campaign rules: classic 4+3@7, V5 6@3h2'), admin: true },
  { name: '/ai roll-hidden', args: '<pool@diff>', description: () => t('chat:slash.ai.rollHidden', 'Same as /ai roll, hidden from players'), admin: true },
  { name: '/ai rouse', args: '[hunger]', description: () => t('chat:slash.ai.rouse', 'V5 Rouse check'), admin: true },
  { name: '/ai clean', args: '<target>', description: () => t('chat:slash.ai.clean', 'Remove clutter (see /ai clean)'), admin: true },
  // Classic chronicles take a floor 2-10; V5 chronicles take no-bestial|no-messy on|off, successes 0-3.
  // `classic` / `v5` override args and description once the room's edition is known.
  {
    name: '/ai dice-diff',
    args: '<2-10 | no-bestial | no-messy | successes | restore>',
    description: () => t('chat:slash.ai.diceDiff', 'Room dice leniency (owner/admin): Classic floor 2-10, V5 no-bestial / no-messy / successes'),
    admin: true,
    classic: {
      args: '<2-10 | restore>',
      description: () => t('chat:slash.ai.diceDiffClassic', 'Room dice leniency (owner/admin): no 1s, one die at least the floor'),
    },
    v5: {
      args: '<no-bestial on|off | no-messy on|off | successes 0-3 | restore>',
      description: () => t('chat:slash.ai.diceDiffV5', 'Room dice leniency (owner/admin): no bestial failure, no messy critical, minimum successes'),
    },
  },
];

/**
 * Suggestions for the current composer text. Only while the caret is still in the command part:
 * the text starts with "/" and has no newline; for "/ai x" the verb may still be being typed.
 * `edition` ('classic' | 'v5', the room's campaign) picks edition-specific args and wording.
 */
export function slashSuggestions(input, { isAdmin = false, edition = null, limit = 8 } = {}) {
  const s = String(input || '');
  if (!s.startsWith('/') || s.includes('\n')) return [];
  const lower = s.toLowerCase();
  const visible = SLASH_COMMANDS.filter((c) => isAdmin || !c.admin);
  // Once a full command plus a space was typed (e.g. "/me waves"), stop suggesting.
  if (visible.some((c) => lower.startsWith(`${c.name} `) && lower.length > c.name.length + 1)) return [];
  return visible
    .filter((c) => c.name.startsWith(lower.trimEnd()) || (lower.trimEnd() === c.name))
    .slice(0, limit)
    .map((c) => (edition && c[edition] ? { ...c, ...c[edition] } : c));
}

/** Text to put in the composer when a suggestion is accepted. */
export function completeSlash(cmd) {
  return cmd.args ? `${cmd.name} ` : cmd.name;
}

/** Recognise local commands in a line about to be sent. */
export function parseLocalCommand(text) {
  const s = String(text || '').trim();
  if (/^\/roll\s*$/i.test(s)) return { type: 'roll' };
  const me = /^\/me\s+([\s\S]+)$/i.exec(s);
  if (me) return { type: 'me', text: me[1].trim() };
  return null;
}
