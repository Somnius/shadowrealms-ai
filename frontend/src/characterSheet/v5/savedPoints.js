/**
 * Saved points (Forge v2 part D): spending the Advantage dots and the free specialty a player left
 * unspent at creation (wod_meta.saved). validateSpend is the live preview of the server's rule
 * check (backend/services/saved_points.py validate_spend, same problem codes); the server's check
 * is the one that counts, and it also checks the Advantages catalog when one is installed.
 * A spend that doesn't pass is a house rule: only a human Storyteller can approve it.
 */
import { V5_SKILLS, V5_SKILL_CATEGORIES, V5_SKILL_LABELS } from './constants';
import { normalizeCreationSettings } from './creationSettings';
import { formatList, t } from '../../i18n';

export const ADVANTAGE_KINDS = ['merit', 'background', 'loresheet'];
export const SPEND_DOTS_MAX = 5;

const SKILL_GROUP = Object.fromEntries(V5_SKILL_CATEGORIES.flatMap((c) => V5_SKILLS[c].map(([k]) => [k, c])));
const key = (v) => String(v || '').trim().replace(/\s+/g, ' ').toLowerCase();
const count = (v) => (Number.isInteger(v) && v > 0 ? v : 0);

/** wod_meta.saved as { advantage_dots, specialty } (0 for anything missing). */
export function savedBalance(meta) {
  const s = meta && typeof meta.saved === 'object' && meta.saved ? meta.saved : {};
  return { advantage_dots: count(s.advantage_dots), specialty: count(s.specialty) };
}

/** The player's own Advantage rows (predator grants are not raised by saved dots). */
export function ownAdvantages(meta) {
  return (Array.isArray(meta?.advantages) ? meta.advantages : []).filter((r) => r && r.name && r.kind !== 'predator');
}

/** What an Advantage spend does to the rows: [{ name, kind, from, to }] (a raise or a new row). */
export function spendChanges(meta, items) {
  const rows = ownAdvantages(meta).map((r) => ({ ...r }));
  return (items || []).map((it) => {
    let row = it.id ? rows.find((r) => r.id === it.id) : null;
    row = row || rows.find((r) => key(r.name) === key(it.name));
    if (!row) {
      row = { name: String(it.name || '').trim(), kind: it.kind, dots: 0 };
      rows.push(row);
    }
    const from = Number.isInteger(row.dots) ? row.dots : 0;
    row.dots = from + count(it.dots);
    return { name: row.name, kind: row.kind || it.kind, from, to: row.dots };
  });
}

function skillDots(skills, skill) {
  const v = skills?.[SKILL_GROUP[skill]]?.[skill];
  return Number.isInteger(v) ? v : 0;
}

/** { ok, problems: [{ code, params }], house_rule } for a spend payload (see the server's codes). */
export function validateSpend(meta, payload, settings, skills) {
  const s = normalizeCreationSettings(settings);
  const have = savedBalance(meta);
  const problems = [];
  const add = (code, params = {}) => problems.push({ code, params });
  if (payload?.kind === 'saved_advantage') {
    const items = payload.items || [];
    const total = items.reduce((n, it) => n + count(it.dots), 0);
    if (total > have.advantage_dots) add('saved_short', { need: total, have: have.advantage_dots });
    const cap = s.saved_points.advantage_dots_cap;
    if (total > cap) add('over_cap', { cap, total });
    spendChanges(meta, items).forEach((ch) => {
      if (ch.to < 1 || ch.to > SPEND_DOTS_MAX) add('dots_range', { name: ch.name, to: ch.to });
    });
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

/** A rule-check problem in words (game terms stay English). */
export function spendProblemText(p) {
  const v = p?.params || {};
  switch (p?.code) {
    case 'saved_short':
      return t('sheet:spend.problem.savedShort', 'Needs {{need}} saved Advantage dots; {{have}} are saved.', v);
    case 'over_cap':
      return t('sheet:spend.problem.overCap', 'This chronicle saves at most {{cap}} Advantage dots (this spend uses {{total}}).', v);
    case 'dots_range':
      return t('sheet:spend.problem.dotsRange', '{{name}} would have {{to}} dots; an Advantage has 1–5.', v);
    case 'unknown_advantage':
      return t('sheet:spend.problem.unknown', '{{name}} is not in the Advantages list.', v);
    case 'not_an_advantage':
      return t('sheet:spend.problem.flaw', '{{name}} is a Flaw, not an Advantage.', v);
    case 'adv_dots_range':
      return t('sheet:spend.problem.advRange', '{{name}} takes {{min}}–{{max}} dots, not {{to}}.', v);
    case 'book_not_allowed':
      return t('sheet:spend.problem.book', "{{name}} comes from a book this chronicle doesn't use ({{book}}).", v);
    case 'clan_only':
      return t('sheet:spend.problem.clanOnly', '{{name}} is only for {{clans}}.', { ...v, clans: formatList(v.clans || []) });
    case 'no_saved_specialty':
      return t('sheet:spend.problem.noSpecialty', 'No specialty is saved.');
    case 'specialty_not_allowed':
      return t('sheet:spend.problem.specialtyOff', "This chronicle doesn't let players save a specialty.");
    case 'skill_no_dot':
      return t('sheet:spend.problem.skillNoDot', '{{skill}} needs at least one dot for a specialty.', { skill: skillLabel(v.skill) });
    case 'specialty_duplicate':
      return t('sheet:spend.problem.duplicate', '{{skill}} already has the {{name}} specialty.', { ...v, skill: skillLabel(v.skill) });
    default:
      return String(p?.code || '');
  }
}

/** One line for a spend request: "Resources 3 → 4" / "Occult: Byzantine rites". */
export function spendSummary(req) {
  const payload = req?.payload || {};
  if (req?.kind === 'saved_specialty') return `${skillLabel(payload.skill)}: ${payload.name}`;
  const changes = Array.isArray(req?.changes) && req.changes.length ? req.changes : null;
  if (changes) return changes.map((c) => `${c.name} ${c.from} → ${c.to}`).join(', ');
  return (payload.items || []).map((it) => `${it.name} +${it.dots}`).join(', ');
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
