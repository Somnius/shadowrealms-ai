/**
 * Rules edition helpers (mirror of backend/services/rules_edition.py).
 *
 * A campaign picks its edition at creation and it never changes:
 * - 'classic' — oWoD, Vampire: The Masquerade Revised (default for everything old)
 * - 'v5'      — Vampire: The Masquerade 5th Edition (only for game_system 'vampire')
 * Characters copy the edition of their campaign.
 */

export const CLASSIC = 'classic';
export const V5 = 'v5';
export const RULES_EDITIONS = [CLASSIC, V5];
export const DEFAULT_RULES_EDITION = CLASSIC;

const ALIASES = {
  classic: CLASSIC,
  revised: CLASSIC,
  owod: CLASSIC,
  v5: V5,
  '5e': V5,
  vtm5: V5,
};

/** Map a raw value to 'classic' | 'v5'; unknown/empty → null. */
export function normalizeEdition(value) {
  if (value == null) return null;
  const s = String(value).trim().toLowerCase();
  return ALIASES[s] || null;
}

/** V5 is only offered for Vampire chronicles. */
export function isV5Allowed(gameSystem) {
  return String(gameSystem || '').trim().toLowerCase() === 'vampire';
}

/**
 * Edition of a campaign/character object (or a raw string). Missing or unknown → classic.
 */
export function editionOf(objOrValue) {
  if (objOrValue == null) return DEFAULT_RULES_EDITION;
  const raw =
    typeof objOrValue === 'object' ? objOrValue.rules_edition : objOrValue;
  return normalizeEdition(raw) || DEFAULT_RULES_EDITION;
}

export function isV5(objOrValue) {
  return editionOf(objOrValue) === V5;
}

/** Short badge text: 'V5' / 'Classic'. `long` gives the full name. */
export function editionLabel(objOrValue, { long = false } = {}) {
  const ed = editionOf(objOrValue);
  if (ed === V5) return long ? 'V5 (5th Edition)' : 'V5';
  return long ? 'Classic (Revised)' : 'Classic';
}
