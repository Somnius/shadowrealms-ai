/**
 * Per-chronicle creation settings (campaigns.creation_settings, set by the Storyteller in the
 * chronicle settings). Same shape and defaults as backend/services/creation_settings.py; the
 * server normalises before sending, this only guards against a missing or old payload.
 */
export const CREATION_AGES = ['childer', 'neonate', 'ancilla'];

export const DEFAULT_CREATION_SETTINGS = {
  v: 1,
  allowed_books: null,
  allowed_clans: null,
  allowed_predators: null,
  allowed_ages: null,
  flaws_max_dots: null,
  fledgling_humanity_8: true,
  saved_points: { advantage_dots_cap: 7, allow_specialty: true },
  st_mode: 'human',
  house_rules: '',
};

const list = (v) => (Array.isArray(v) && v.length ? v.filter((x) => typeof x === 'string' && x.trim()) : null);

export function normalizeCreationSettings(value) {
  const v = value && typeof value === 'object' ? value : {};
  return {
    ...DEFAULT_CREATION_SETTINGS,
    allowed_books: list(v.allowed_books),
    allowed_clans: list(v.allowed_clans),
    allowed_predators: list(v.allowed_predators),
    allowed_ages: list(v.allowed_ages),
    flaws_max_dots: Number.isInteger(v.flaws_max_dots) ? v.flaws_max_dots : null,
    fledgling_humanity_8: v.fledgling_humanity_8 !== false,
    saved_points: { ...DEFAULT_CREATION_SETTINGS.saved_points, ...(v.saved_points || {}) },
    st_mode: v.st_mode === 'ai' ? 'ai' : 'human',
    house_rules: typeof v.house_rules === 'string' ? v.house_rules : '',
  };
}

/** The settings of the chronicle with this id in a campaigns list (defaults when absent). */
export function settingsForCampaign(campaigns, campaignId) {
  const c = (campaigns || []).find((x) => String(x.id) === String(campaignId));
  return normalizeCreationSettings(c?.creation_settings);
}
