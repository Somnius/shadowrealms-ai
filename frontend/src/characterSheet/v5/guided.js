/**
 * Guided mode of the V5 forge (Forge v2 part E). Scores the answers to the scenario questions
 * (docs/rules/v5/guided/questions.json, served by GET /api/rules/v5/guided; the format is in
 * docs/rules/v5/guided/README.md) and turns them into a suggested clan and predator type plus a
 * prefill for the forge (the `initial` of useV5ForgeState).
 *
 * No React and no fetching. Like validation.js it reads the clans and predator types from the
 * rules registry (rulesData.js: the served catalog once it has loaded).
 *
 * answers: { [questionId]: optionId | NONE_OF_THESE }
 */
import {
  THIN_BLOOD,
  V5_ATTRIBUTES,
  V5_ATTRIBUTE_SPREAD,
  V5_FREE_SPECIALTY_SKILLS,
  V5_SKILLS,
  V5_SKILL_CATEGORIES,
  V5_SKILL_DISTRIBUTIONS,
  V5_SKILL_KEYS,
  startingGeneration,
} from './constants';
import { getV5Rules } from './rulesData';
import {
  ageAllowed,
  clanAllowed,
  clanInBooks,
  defaultCreationAge,
  deriveV5,
  predatorAllowed,
  predatorInBooks,
} from './validation';

/** The answer "none of these" (option ids are lowercase words, so it can't clash with one). */
export const NONE_OF_THESE = '__none__';
/** Picking "none of these" this many times leaves the path. */
export const NONE_LIMIT = 2;
/** Used when the question set gives no thresholds (the placeholder set's values). */
export const DEFAULT_THRESHOLDS = { min_score_share: 0.3, min_lead: 2 };
export const DEFAULT_DISTRIBUTION = 'balanced';

const AXES = ['clan', 'predator', 'attributes', 'skills', 'distribution'];
/** Attribute categories, the same three as the skills' (physical, social, mental). */
const CATEGORIES = V5_SKILL_CATEGORIES;
const DISTRIBUTIONS = Object.keys(V5_SKILL_DISTRIBUTIONS); // jack, balanced, specialist
const CATEGORY_OF_SKILL = Object.fromEntries(CATEGORIES.flatMap((c) => V5_SKILLS[c].map(([k]) => [k, c])));

/** A weight as a number; anything that isn't a positive number counts 0. */
const weight = (v) => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : 0;
};

/** Point maps without a prototype, so no key from the file can reach Object.prototype. */
const pointMap = () => Object.create(null);

/** [name, points, index] sorted by points (most first), ties in list order. */
const rank = (names, points) =>
  names.map((n, i) => [n, weight(points[n]), i]).sort((a, b) => b[1] - a[1] || a[2] - b[2]);

/** The thresholds of a question set, defaults filled in. */
export function guidedThresholds(set) {
  const th = set?.thresholds || {};
  const share = th.min_score_share;
  const lead = th.min_lead;
  return {
    min_score_share: typeof share === 'number' && share > 0 && share <= 1 ? share : DEFAULT_THRESHOLDS.min_score_share,
    min_lead: typeof lead === 'number' && lead >= 0 ? lead : DEFAULT_THRESHOLDS.min_lead,
  };
}

/** The questions the guide can ask: an id and at least two options with ids. */
export function guidedQuestions(set) {
  const list = Array.isArray(set?.questions) ? set.questions : [];
  return list
    .filter((q) => q && typeof q.id === 'string' && Array.isArray(q.options))
    .map((q) => ({ ...q, options: q.options.filter((o) => o && typeof o.id === 'string') }))
    .filter((q) => q.options.length >= 2);
}

/** How many questions were answered "none of these". */
export function noneCount(set, answers) {
  return guidedQuestions(set).filter((q) => answers?.[q.id] === NONE_OF_THESE).length;
}

/**
 * Points per weight group from the chosen options: { clan, predator, attributes, skills,
 * distribution } (each { key: points }), and `picks`: [{ question, option }] in question order.
 */
export function scoreAnswers(set, answers) {
  const out = Object.fromEntries(AXES.map((a) => [a, pointMap()]));
  out.picks = [];
  guidedQuestions(set).forEach((question) => {
    const answer = answers?.[question.id];
    const option = answer && answer !== NONE_OF_THESE ? question.options.find((o) => o.id === answer) : null;
    if (!option) return;
    out.picks.push({ question, option });
    AXES.forEach((axis) => {
      const w = option.weights?.[axis];
      if (!w || typeof w !== 'object') return;
      Object.entries(w).forEach(([key, v]) => {
        const n = weight(v);
        if (n) out[axis][key] = (out[axis][key] || 0) + n;
      });
    });
  });
  return out;
}

/**
 * Clans this chronicle allows, from its books. Thin-bloods are always childer, so they also need
 * that age.
 */
export function eligibleClans(settings) {
  return getV5Rules()
    .clans.map((c) => c.name)
    .filter(
      (c) => clanAllowed(settings, c) && clanInBooks(settings, c) && (c !== THIN_BLOOD || ageAllowed(settings, 'childer'))
    );
}

/** The age the forge starts this clan and predator type at (as useV5ForgeState does). */
export function startingAge(settings, clan, predator) {
  if (clan === THIN_BLOOD) return 'childer';
  if (predator?.ancilla_only) return 'ancilla';
  return defaultCreationAge(settings);
}

/**
 * Can a character of this clan take this predator type (a rulesData predator) in this chronicle?
 * Not when the Storyteller left it out (or its book), the clan is forbidden, it is for ancillae and
 * the chronicle has none (thin-bloods never are), or its Blood Potency cap is below the starting one.
 */
export function predatorFits(settings, clan, p) {
  if (!p || !predatorAllowed(settings, p.name) || !predatorInBooks(settings, p.name)) return false;
  if ((p.forbidden_clans || []).includes(clan)) return false;
  if (p.ancilla_only && (clan === THIN_BLOOD || !ageAllowed(settings, 'ancilla'))) return false;
  if (p.max_blood_potency != null) {
    const age = startingAge(settings, clan, p);
    const bp = deriveV5({ clan, age, generation: startingGeneration(age), predatorType: p.name }).blood_potency;
    if (bp > p.max_blood_potency) return false;
  }
  return true;
}

/**
 * The 4/3/3/3/2/2/2/2/1 spread laid over the categories by their points: the strongest category
 * takes the three highest values (4, 3, 3), the next (3, 2, 2), the last (2, 2, 1). A category's
 * points are its own plus its Attributes'; inside a category the Attributes go by their own
 * points. Ties: physical, social, mental, and the sheet order inside a category.
 * Returns { attributes: {strength..resolve}, categories: [strongest..weakest] }.
 */
export function attributePrefill(points = {}) {
  const catPoints = Object.fromEntries(
    CATEGORIES.map((c) => [c, weight(points[c]) + V5_ATTRIBUTES[c].reduce((s, [k]) => s + weight(points[k]), 0)])
  );
  const categories = rank(CATEGORIES, catPoints).map(([c]) => c);
  const spread = [...V5_ATTRIBUTE_SPREAD].sort((a, b) => b - a);
  const attributes = {};
  let next = 0;
  categories.forEach((cat) => {
    const keys = V5_ATTRIBUTES[cat].map(([k]) => k);
    rank(keys, points).forEach(([k]) => {
      attributes[k] = spread[next];
      next += 1;
    });
  });
  return { attributes, categories };
}

/** The distribution with the most points; balanced when there are none or the top is tied. */
export function distributionVote(points = {}) {
  const [top, second] = rank(DISTRIBUTIONS, points);
  if (!top || top[1] <= 0 || (second && second[1] === top[1])) return DEFAULT_DISTRIBUTION;
  return top[0];
}

/**
 * The distribution's ratings given to the skills with the most points, highest first. Skills with
 * the same points go by the order of their category in `categories` (the Attributes' order), then
 * the sheet order; but among skills without points, Academics, Craft, Performance and Science come
 * last, since a dot there asks for a free specialty the player didn't choose (there are always
 * enough other skills). Exactly the distribution's ratings, so the forge's skill check passes.
 */
export function skillPrefill(points = {}, distribution = DEFAULT_DISTRIBUTION, categories = CATEGORIES) {
  const dist = V5_SKILL_DISTRIBUTIONS[distribution] || V5_SKILL_DISTRIBUTIONS[DEFAULT_DISTRIBUTION];
  const ratings = Object.entries(dist.counts)
    .flatMap(([rating, count]) => Array(count).fill(Number(rating)))
    .sort((a, b) => b - a);
  const order = V5_SKILL_KEYS.map((k, i) => {
    const p = weight(points[k]);
    const late = p === 0 && V5_FREE_SPECIALTY_SKILLS.includes(k) ? 1 : 0;
    return { k, p, late, c: categories.indexOf(CATEGORY_OF_SKILL[k]), i };
  }).sort((a, b) => b.p - a.p || a.late - b.late || a.c - b.c || a.i - b.i);
  const skills = Object.fromEntries(V5_SKILL_KEYS.map((k) => [k, 0]));
  ratings.forEach((r, i) => {
    skills[order[i].k] = r;
  });
  return skills;
}

/** The answers that gave `key` points in a weight group, most first (ties in question order). */
function reasonsFor(picks, axis, key, max = 3) {
  return picks
    .map(({ question, option }, i) => ({ i, points: weight(option.weights?.[axis]?.[key]), question, option }))
    .filter((r) => r.points > 0)
    .sort((a, b) => b.points - a.points || a.i - b.i)
    .slice(0, max)
    .map((r) => ({ question: r.question.id, option: r.option.id, text: r.option.text, points: r.points }));
}

/**
 * The guide's answer for these answers in a chronicle with these (normalised) creation settings:
 *
 *   { offPath: true, reason: 'none' | 'not_allowed' | 'unclear', share, lead }
 *     'none': "none of these" NONE_LIMIT times; 'not_allowed': the clan with the most points is
 *     not offered here; 'unclear': no clan stands out.
 *   { offPath: false, clan, predator (name or null when none scored), age, share, lead,
 *     why: { clan: [{question, option, text, points}], predator: [...] }, categories, distribution,
 *     skillFocus: [skill keys the answers gave points, most first, at most 4],
 *     prefill: { clan, predatorType, age, attributes, skillDistribution, skills } }
 *
 * The suggested clan has the most points among the allowed clans (ties in catalog order). Its
 * share is its points over all clan points the answers gave (clans the chronicle doesn't allow
 * included) and its lead the gap to the next allowed clan; below `min_score_share` or `min_lead`
 * the answers are off the path. The predator type has the most points among those that fit the
 * clan and the chronicle (predatorFits).
 */
export function guidedResult(set, answers, settings) {
  if (noneCount(set, answers) >= NONE_LIMIT) return { offPath: true, reason: 'none', share: 0, lead: 0 };
  const th = guidedThresholds(set);
  const score = scoreAnswers(set, answers);
  const clanPoints = score.clan;
  const total = Object.values(clanPoints).reduce((s, v) => s + v, 0);
  const eligible = eligibleClans(settings);
  const [top, second] = rank(eligible, clanPoints);
  const topPoints = top ? top[1] : 0;
  const share = total > 0 ? topPoints / total : 0;
  const lead = topPoints - (second ? second[1] : 0);
  if (!top || topPoints <= 0 || share < th.min_score_share || lead < th.min_lead) {
    const [best] = rank(Object.keys(clanPoints), clanPoints);
    const blocked = Boolean(best) && best[1] > topPoints && !eligible.includes(best[0]);
    return { offPath: true, reason: blocked ? 'not_allowed' : 'unclear', share, lead };
  }
  const clan = top[0];
  const fitting = getV5Rules().predators.filter((p) => predatorFits(settings, clan, p));
  const [bestPredator] = rank(fitting.map((p) => p.name), score.predator);
  const predator = bestPredator && bestPredator[1] > 0 ? bestPredator[0] : null;
  const age = startingAge(settings, clan, fitting.find((p) => p.name === predator));
  const { attributes, categories } = attributePrefill(score.attributes);
  const distribution = distributionVote(score.distribution);
  const skills = skillPrefill(score.skills, distribution, categories);
  const skillFocus = rank(V5_SKILL_KEYS, score.skills)
    .filter(([, points]) => points > 0)
    .slice(0, 4)
    .map(([k]) => k);
  return {
    offPath: false,
    clan,
    predator,
    age,
    share,
    lead,
    why: {
      clan: reasonsFor(score.picks, 'clan', clan),
      predator: predator ? reasonsFor(score.picks, 'predator', predator) : [],
    },
    categories,
    distribution,
    skillFocus,
    prefill: { clan, predatorType: predator || '', age, attributes, skillDistribution: distribution, skills },
  };
}
