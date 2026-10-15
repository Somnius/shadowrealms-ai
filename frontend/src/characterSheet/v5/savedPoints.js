/**
 * Saved points (Forge v2 part D): spending the Advantage dots and the free specialty a player left
 * unspent at creation (wod_meta.saved). validateSpend is the live preview of the server's rule
 * check (backend/services/saved_points.py validate_spend, same problem codes). The server's check
 * is the one that counts: it runs the rows through the creation check's own row rules
 * (v5_chargen.check_advantage_rows, the chronicle's allowed books included), and checks
 * prerequisites, which this preview leaves to it. A spend that doesn't pass is a house rule: only a
 * human Storyteller can approve it.
 *
 * Items: { id?, name, kind: 'merit'|'background', dots, note? } adds dots to the player's own row
 * of that name (a raise) or makes a new row; { id?, name, kind: 'loresheet', levels: [n] } takes
 * loresheet levels (each costs its rating) on the player's row of that loresheet or a new one.
 */
import { CAITIFF, THIN_BLOOD, V5_SKILLS, V5_SKILL_CATEGORIES, V5_SKILL_LABELS } from './constants';
import { bookAllowed, entryBooks, normalizeCreationSettings } from './creationSettings';
import { advantageEntries, bookTitle, findAdvantage, findLoresheet, loresheetEntries } from './rulesData';
import { advantageAllowed, advantageDotChoices } from './validation';
import { translateProblem } from '../i18nErrors';
import { t } from '../../i18n';

export const ADVANTAGE_KINDS = ['merit', 'background', 'loresheet'];
export const SPEND_DOTS_MAX = 5;

const SKILL_GROUP = Object.fromEntries(V5_SKILL_CATEGORIES.flatMap((c) => V5_SKILLS[c].map(([k]) => [k, c])));
const key = (v) => String(v || '').trim().replace(/\s+/g, ' ').toLowerCase();
const count = (v) => (Number.isInteger(v) && v > 0 ? v : 0);
const isLore = (x) => x?.kind === 'loresheet';

/** wod_meta.saved as { advantage_dots, specialty } (0 for anything missing). */
export function savedBalance(meta) {
  const s = meta && typeof meta.saved === 'object' && meta.saved ? meta.saved : {};
  return { advantage_dots: count(s.advantage_dots), specialty: count(s.specialty) };
}

/** The player's own Advantage and loresheet rows (predator grants are not raised by saved dots). */
export function ownAdvantages(meta) {
  return (Array.isArray(meta?.advantages) ? meta.advantages : []).filter((r) => r && r.name && r.kind !== 'predator');
}

/** The dots an item spends: its own, or a loresheet's levels added up. */
export const itemDots = (it) => (isLore(it) ? (it.levels || []).reduce((n, l) => n + count(l), 0) : count(it?.dots));

/**
 * What a spend does to the rows (as the server's _apply_items): [{ name, kind, from, to, levels?,
 * row }] where row is the row as it would be after the spend.
 */
export function spendChanges(meta, items) {
  const rows = ownAdvantages(meta).map((r) => ({ ...r, levels: Array.isArray(r.levels) ? [...r.levels] : r.levels }));
  return (items || []).map((it) => {
    let row = rows.find((r) => isLore(r) === isLore(it) && key(r.name) === key(it.name));
    if (!row) {
      row = { ...(it.id ? { id: it.id } : {}), name: String(it.name || '').trim(), kind: it.kind, dots: 0, ...(isLore(it) ? { levels: [] } : {}) };
      rows.push(row);
    }
    const from = Number.isInteger(row.dots) ? row.dots : 0;
    row.dots = from + itemDots(it);
    if (isLore(it)) row.levels = [...(row.levels || []), ...(it.levels || [])].sort((a, b) => a - b);
    return { name: row.name, kind: row.kind || it.kind, from, to: row.dots, ...(isLore(it) ? { levels: [...(it.levels || [])] } : {}), row };
  });
}

function skillDots(skills, skill) {
  const v = skills?.[SKILL_GROUP[skill]]?.[skill];
  return Number.isInteger(v) ? v : 0;
}

/** May the sheet (its wod_meta) take this loresheet: clan, thin-blood, Disciplines it has? */
export function loresheetOpen(ls, meta) {
  if (ls.clans_only && !ls.clans_only.includes(meta?.clan)) return false;
  if (ls.thin_blood_only && meta?.clan !== THIN_BLOOD) return false;
  if (ls.disciplines_only) {
    const have = (Array.isArray(meta?.disciplines) ? meta.disciplines : []).filter((d) => d && count(d.level || d.dots)).map((d) => d.name);
    if (!ls.disciplines_only.some((d) => have.includes(d))) return false;
  }
  return true;
}

/** The catalog side of the preview, when the catalog is loaded (the server checks more). */
function catalogProblems(add, meta, items, changes, settings) {
  const book = (ch, e, kind) => {
    if (!bookAllowed(settings, e)) add('book_not_allowed', { name: ch.name, book: entryBooks(e)[0], kind });
  };
  const special = meta?.clan === THIN_BLOOD ? 'thin_blood' : meta?.clan === CAITIFF ? 'caitiff' : null;
  items.forEach((it, i) => {
    const ch = changes[i];
    if (isLore(it)) {
      if (!loresheetEntries().length) return;
      const ls = findLoresheet(it);
      if (!ls) {
        add('adv_unknown', { name: it.name });
        return;
      }
      const levels = ch.row.levels || [];
      if (new Set(levels).size !== levels.length) add('loresheet_levels', { name: ch.name, dots: ch.to, levels });
      if (!loresheetOpen(ls, meta)) add('loresheet_restricted', { name: ch.name, clan: meta?.clan });
      book(ch, ls, 'loresheet');
      return;
    }
    if (!advantageEntries().length) return;
    const e = findAdvantage(it, it.kind, special);
    if (!e) {
      add('adv_unknown', { name: it.name });
      return;
    }
    const choices = advantageDotChoices(e);
    if (choices.length && !choices.includes(ch.to)) {
      add('adv_dots_range', { name: ch.name, dots: ch.to, min: choices[0], max: choices[choices.length - 1] });
    }
    if (!advantageAllowed(e, meta?.clan)) add('adv_restricted', { name: ch.name, clan: meta?.clan });
    book(ch, e, 'advantage');
  });
}

/** { ok, problems: [{ code, params }], house_rule } for a spend payload (see the server's codes). */
export function validateSpend(meta, payload, settings, skills) {
  const s = normalizeCreationSettings(settings);
  const have = savedBalance(meta);
  const problems = [];
  const seen = new Set();
  const add = (code, params = {}) => {
    const k = `${code}:${JSON.stringify(params)}`;
    if (!seen.has(k)) {
      seen.add(k);
      problems.push({ code, params });
    }
  };
  if (payload?.kind === 'saved_advantage') {
    const items = payload.items || [];
    const total = items.reduce((n, it) => n + itemDots(it), 0);
    if (total > have.advantage_dots) add('saved_short', { need: total, have: have.advantage_dots });
    // The cap is on everything spent from saved points, earlier approved spends included.
    const rows = Array.isArray(meta?.advantages) ? meta.advantages : [];
    const before = rows.reduce((n, r) => n + count(r?.saved_dots), 0);
    const cap = s.saved_points.advantage_dots_cap;
    if (before + total > cap) add('over_cap', { cap, total: before + total });
    const changes = spendChanges(meta, items);
    const catalog = advantageEntries().length || loresheetEntries().length;
    changes.forEach((ch, i) => {
      if (isLore(items[i]) || (catalog && findAdvantage(items[i], items[i].kind))) return;
      if (ch.to < 1 || ch.to > SPEND_DOTS_MAX) add('adv_dots_range', { name: ch.name, dots: ch.to, min: 1, max: SPEND_DOTS_MAX });
    });
    catalogProblems(add, meta, items, changes, s);
  } else if (payload?.kind === 'saved_specialty') {
    if (!s.saved_points.allow_specialty) add('specialty_not_allowed');
    if (have.specialty < 1) add('no_saved_specialty');
    if (skillDots(skills, payload.skill) < 1) add('skill_no_dot', { skill: payload.skill });
    const specs = Array.isArray(skills?.specialties) ? skills.specialties : [];
    if (specs.some((sp) => sp && sp.skill === payload.skill && key(sp.name) === key(payload.name))) {
      add('specialty_duplicate', { skill: payload.skill, name: payload.name });
    }
  }
  return { ok: problems.length === 0, problems, house_rule: problems.length > 0 };
}

const skillLabel = (k) => V5_SKILL_LABELS[k] || k;

/** A rule-check problem in words (game terms stay English). Creation codes use the forge's words. */
export function spendProblemText(p) {
  const v = p?.params || {};
  switch (p?.code) {
    case 'saved_short':
      return t('sheet:spend.problem.savedShort', 'Needs {{need}} saved Advantage dots; {{have}} are saved.', v);
    case 'over_cap':
      return t('sheet:spend.problem.overCap', 'This chronicle saves at most {{cap}} Advantage dots (this spend uses {{total}}).', v);
    case 'adv_repeat':
      return t('sheet:spend.problem.repeat', 'The sheet already has {{name}} as often as it can be taken.', v);
    case 'adv_requires':
      return t('sheet:spend.problem.requires', '{{name}} needs {{requires}}: the Storyteller checks that.', v);
    case 'book_not_allowed':
      return t('sheet:spend.problem.book', "{{name}} comes from a book this chronicle doesn't use ({{book}}).", { ...v, book: bookTitle(v.book) });
    case 'catalog_error':
      return t('sheet:spend.problem.catalogError', 'The rules catalog could not be read, so the Storyteller decides.');
    case 'no_saved_specialty':
      return t('sheet:spend.problem.noSpecialty', 'No specialty is saved.');
    case 'specialty_not_allowed':
      return t('sheet:spend.problem.specialtyOff', "This chronicle doesn't let players save a specialty.");
    case 'skill_no_dot':
      return t('sheet:spend.problem.skillNoDot', '{{skill}} needs at least one dot for a specialty.', { skill: skillLabel(v.skill) });
    case 'specialty_duplicate':
      return t('sheet:spend.problem.duplicate', '{{skill}} already has the {{name}} specialty.', { ...v, skill: skillLabel(v.skill) });
    default:
      // adv_dots_range, adv_unknown, adv_restricted, loresheet_levels, loresheet_restricted,
      // custom_row, caitiff_status: the creation check's codes, in the forge's words
      return translateProblem(p);
  }
}

/** One line for a spend request: "Resources 3 → 4" / "The Bahari level 2" / "Occult: Byzantine rites". */
export function spendSummary(req) {
  const payload = req?.payload || {};
  if (req?.kind === 'saved_specialty') return `${skillLabel(payload.skill)}: ${payload.name}`;
  const level = (it) => t('sheet:spend.loreLevels', { one: '{{name}} level {{levels}}', other: '{{name}} levels {{levels}}' }, { name: it.name, levels: (it.levels || []).join(', '), count: (it.levels || []).length });
  const changes = Array.isArray(req?.changes) && req.changes.length ? req.changes : null;
  if (changes) return changes.map((c) => (c.levels ? level(c) : `${c.name} ${c.from} → ${c.to}`)).join(', ');
  return (payload.items || []).map((it) => (isLore(it) ? level(it) : `${it.name} +${it.dots}`)).join(', ');
}

/** A request's status in words. */
export function spendStatusLabel(status) {
  if (status === 'approved') return t('sheet:spend.status.approved', 'Approved');
  if (status === 'rejected') return t('sheet:spend.status.rejected', 'Rejected');
  if (status === 'reversed') return t('sheet:spend.status.reversed', 'Reversed');
  if (status === 'pending') return t('sheet:spend.status.pending', 'Waiting for the Storyteller');
  return status || '';
}

export const spendStatusTone = (status) =>
  status === 'approved' ? 'ok' : status === 'rejected' ? 'danger' : status === 'reversed' ? 'neutral' : 'warn';

/** Who decided: the AI Storyteller's rule check or a person. */
export function spendApproverText(req) {
  if (req?.approver === 'ai') return t('sheet:spend.byAi', 'by the AI Storyteller (rule check)');
  if (req?.resolved_by_name) return t('sheet:spend.byUser', 'by {{name}}', { name: req.resolved_by_name });
  return '';
}
