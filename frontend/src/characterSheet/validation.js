import {
  KNOWLEDGES,
  MENTAL,
  MTA_SPHERES,
  PHYSICAL,
  SKILLS,
  SOCIAL,
  TALENTS,
} from './constants';

export function emptyAttrMap() {
  const o = {};
  [...PHYSICAL, ...SOCIAL, ...MENTAL].forEach((k) => {
    o[k] = 1;
  });
  return o;
}

export function emptyAbilityMap() {
  const o = {};
  [...TALENTS, ...SKILLS, ...KNOWLEDGES].forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

export function emptySphereMap() {
  const o = {};
  MTA_SPHERES.forEach(([k]) => {
    o[k] = 0;
  });
  return o;
}

export function sumAbilitiesInCategory(abilities, keys) {
  return keys.reduce((s, [k]) => s + (parseInt(abilities[k], 10) || 0), 0);
}

export function validateAttributeSpread(attrs, pools) {
  const sum = (keys) => keys.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
  const p = sum(PHYSICAL);
  const s = sum(SOCIAL);
  const m = sum(MENTAL);
  if (p !== pools.physical) return `Physical attributes must total ${pools.physical} (currently ${p}).`;
  if (s !== pools.social) return `Social attributes must total ${pools.social} (currently ${s}).`;
  if (m !== pools.mental) return `Mental attributes must total ${pools.mental} (currently ${m}).`;
  for (const k of [...PHYSICAL, ...SOCIAL, ...MENTAL]) {
    const v = parseInt(attrs[k], 10);
    if (Number.isNaN(v) || v < 1 || v > 5) {
      return `Each attribute must be between 1 and 5 (${k}).`;
    }
  }
  return null;
}

function sumCustomDots(customList) {
  return (customList || []).reduce((s, r) => s + (parseInt(r.dots, 10) || 0), 0);
}

/**
 * @param abilities - base key map
 * @param pools - { talents, skills, knowledges }
 * @param [custom] - { talents?: [], skills?: [], knowledges?: [] } each row { dots }
 */
export function validateAbilitySpread(abilities, pools, custom) {
  const t = sumAbilitiesInCategory(abilities, TALENTS) + sumCustomDots(custom?.talents);
  const sk = sumAbilitiesInCategory(abilities, SKILLS) + sumCustomDots(custom?.skills);
  const kn = sumAbilitiesInCategory(abilities, KNOWLEDGES) + sumCustomDots(custom?.knowledges);
  if (t !== pools.talents) return `Talents must total ${pools.talents} dots (currently ${t}).`;
  if (sk !== pools.skills) return `Skills must total ${pools.skills} dots (currently ${sk}).`;
  if (kn !== pools.knowledges) return `Knowledges must total ${pools.knowledges} dots (currently ${kn}).`;
  for (const [k] of [...TALENTS, ...SKILLS, ...KNOWLEDGES]) {
    const v = parseInt(abilities[k], 10);
    if (Number.isNaN(v) || v < 0 || v > 5) {
      return `Each ability must be between 0 and 5 (${k}).`;
    }
  }
  for (const list of [custom?.talents, custom?.skills, custom?.knowledges]) {
    for (const r of list || []) {
      const v = parseInt(r.dots, 10);
      if (Number.isNaN(v) || v < 0 || v > 5) {
        return 'Each ability (including custom rows) must be between 0 and 5.';
      }
    }
  }
  return null;
}

export function validateVirtues(v) {
  const c = parseInt(v.conscience, 10) || 0;
  const sc = parseInt(v.self_control, 10) || 0;
  const co = parseInt(v.courage, 10) || 0;
  if (c < 1 || c > 5 || sc < 1 || sc > 5 || co < 1 || co > 5) {
    return 'Each virtue must be between 1 and 5.';
  }
  if (c + sc + co !== 7) {
    return 'Virtues must total exactly 7 dots (Revised neonate spread), each at least 1.';
  }
  return null;
}

export function validateSpheres(spheres) {
  let t = 0;
  for (const [k] of MTA_SPHERES) {
    const v = parseInt(spheres[k], 10) || 0;
    if (v < 0 || v > 5) return `Sphere ${k} must be 0–5.`;
    t += v;
  }
  if (t !== 6) return `Allocate exactly 6 sphere dots at creation (currently ${t}).`;
  return null;
}

/** Pool remainder helpers for UI summaries */
export function attributePoolRemainders(attrs, pools) {
  const sum = (keys) => keys.reduce((s, k) => s + (parseInt(attrs[k], 10) || 0), 0);
  return {
    physical: pools.physical - sum(PHYSICAL),
    social: pools.social - sum(SOCIAL),
    mental: pools.mental - sum(MENTAL),
  };
}

export function abilityPoolRemainders(abilities, pools, custom) {
  const sumC = (list) => (list || []).reduce((s, r) => s + (parseInt(r.dots, 10) || 0), 0);
  return {
    talents: pools.talents - sumAbilitiesInCategory(abilities, TALENTS) - sumC(custom?.talents),
    skills: pools.skills - sumAbilitiesInCategory(abilities, SKILLS) - sumC(custom?.skills),
    knowledges:
      pools.knowledges - sumAbilitiesInCategory(abilities, KNOWLEDGES) - sumC(custom?.knowledges),
  };
}
