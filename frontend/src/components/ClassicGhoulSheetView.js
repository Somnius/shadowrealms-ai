import DotTrack from './characterCreation/DotTrack';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import BloodPoolBoxes from './characterCreation/classicGhoul/BloodPoolBoxes';
import { DomitorLink } from './V5GhoulSheetView';
import { StaticDots, p } from './V5CharacterSheetView';
import { kindName } from './RetainersBlock';
import { BLOOD_POOL_MAX, BLOOD_POOL_PER_TURN, BOND_DRINKS, potenceFirst } from '../characterSheet/classicGhoul';
import { t } from '../i18n';
import { Term } from '../i18n/glossary';

const ACCENT = 'var(--sr-blood-500)';
const obj = (v) => (v && typeof v === 'object' ? v : {});
const num = (v) => {
  const x = parseInt(v, 10);
  return Number.isFinite(x) ? x : null;
};

/** wod_meta.blood_pool of a Classic ghoul as {max, current, perTurn} (defaults 10 / 0 / 1). */
export function ghoulPool(wm) {
  const pool = obj(obj(wm).blood_pool);
  const max = Math.max(1, Math.min(20, num(pool.max) ?? BLOOD_POOL_MAX));
  return { max, current: Math.max(0, Math.min(max, num(pool.current) ?? 0)), perTurn: num(pool.per_turn) ?? BLOOD_POOL_PER_TURN };
}

function Rows({ title, rows }) {
  if (!rows.length) return null;
  return (
    <div style={{ marginBottom: '10px' }}>
      <strong style={{ color: 'var(--sr-arcane-300)' }}>{title}</strong>
      <ul style={{ margin: '6px 0 0', paddingLeft: '1.2rem', color: 'var(--sr-bone-100)' }}>
        {rows.map((d, i) => (
          <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span lang="en" style={{ minWidth: '120px' }}>
              {d.name}
            </span>
            <StaticDots value={d.dots ?? d.level} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The top of a Classic (Revised) ghoul's read-only sheet (wod_meta.sheet_kind 'ghoul'): the domitor,
 * kind and duties, the Blood Pool (a Classic ghoul has one: max 10, 1 point per turn), the Blood Bond
 * in drinks, feeding, overdosing, Disciplines (Potence first), Backgrounds, Virtues, Humanity and
 * Willpower. CharacterSheetModal renders it in place of the Classic identity / template blocks and
 * goes on with the shared Attributes, Abilities, Background and Merits. Rules: Revised pp. 275–276,
 * Ghouls: Fatal Addiction.
 */
export default function ClassicGhoulSheetView({ character, onOpenSheet }) {
  const wm = obj(character?.wod_meta);
  const g = obj(wm.ghoul);
  const stored = obj(g.domitor);
  const domitor = character?.domitor && typeof character.domitor === 'object' ? character.domitor : null;
  const pool = ghoulPool(wm);
  const bond = obj(g.bond);
  const stage = num(bond.stage);
  const feeding = obj(g.feeding);
  const generation = domitor?.generation ?? stored.generation;
  const domClan = [domitor?.clan || stored.clan, generation ? t('sheet:classicGhoul.generationN', 'generation {{n}}', { n: generation }) : '']
    .filter(Boolean)
    .join(', ');
  const looks = [g.age, g.apparent_age].filter((v) => v != null && v !== '').join(' / ');
  const kind = g.kind ? kindName(g.kind) + (g.kind === 'revenant' && g.family ? `: ${g.family}` : '') : '';
  const disciplines = potenceFirst(wm.disciplines);
  const backgrounds = (Array.isArray(wm.backgrounds) ? wm.backgrounds : []).filter((b) => b && String(b.name || '').trim());
  const virtues = obj(wm.virtues);
  const path = typeof wm.path === 'string' && wm.path.trim() && !/^\d+$/.test(wm.path.trim()) ? wm.path.trim() : null;
  const morality = path ? `${path} ${wm.path_rating ?? ''}`.trim() : wm.humanity;
  const damage = num(wm.health_damage);

  return (
    <>
      <p style={{ color: 'var(--sr-bone-500)', fontSize: '13px', marginTop: 0, lineHeight: 1.5 }}>
        {t('sheet:classicGhoul.intro', 'Ghoul sheet, Classic (Revised), read-only. Rules: Revised pp. 275–276, Ghouls: Fatal Addiction.')}
      </p>

      <ResponsiveSheetBlock sectionId="classic-ghoul-view-identity" title={t('sheet:identity', 'Identity')} accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px 16px', fontSize: '14px' }}>
          <p style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
            <strong style={{ color: 'var(--sr-arcane-300)' }}>
              <Term id="domitor" />:
            </strong>{' '}
            <DomitorLink domitor={domitor} stored={stored} onOpenSheet={onOpenSheet} />
          </p>
          {p(t('sheet:classicGhoul.domitorClan', "Domitor's clan and generation"), domClan)}
          {p(t('sheet:classicGhoul.kindLabel', 'Kind'), kind)}
          {p(t('sheet:classicGhoul.duties', 'Duties'), g.duties)}
          {p(t('sheet:v5.concept', 'Concept'), wm.concept)}
          {p('Nature', wm.nature)}
          {p('Demeanor', wm.demeanor)}
          {p(t('sheet:ghoul.ageLooks', 'Age / looks'), looks)}
          {p(t('sheet:ghoul.since', 'Ghoul since'), g.ghouled_since)}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="classic-ghoul-view-blood" title={t('sheet:classicGhoul.bloodTitle', 'Blood Pool & Blood Bond')} accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
          <strong style={{ color: 'var(--sr-arcane-300)' }}>
            <Term id="bloodPool" />
          </strong>
          <BloodPoolBoxes current={pool.current} max={pool.max} />
          <span style={{ color: 'var(--sr-bone-100)', fontSize: '13px' }}>
            {t('sheet:classicGhoul.poolLine', '{{current}} / {{max}} · {{perTurn}} per turn', { current: pool.current, max: pool.max, perTurn: pool.perTurn })}
          </span>
        </div>
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', lineHeight: 1.5, margin: '0 0 14px' }}>
          {t('sheet:classicGhoul.poolRule', 'Spend a point to heal a level or to raise a Physical Attribute (up to twice the original); Disciplines need at least one point; soaks lethal damage while holding vitae. No Hunger, no Rouse Checks.')}
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
          <strong lang="en" style={{ color: 'var(--sr-arcane-300)' }}>
            Blood Bond
          </strong>
          <DotTrack value={stage ?? 0} maxRank={BOND_DRINKS} accent={ACCENT} label="Blood Bond" disabled onChange={() => {}} />
          <span style={{ color: 'var(--sr-bone-100)', fontSize: '13px' }}>
            {stage == null
              ? t('sheet:classicGhoul.bondNotSet', 'not set (the Storyteller sets it)')
              : t('sheet:classicGhoul.bondStage', { one: '{{count}} of {{max}} drinks', other: '{{count}} of {{max}} drinks' }, { count: stage, max: BOND_DRINKS })}
            {stage != null && stage >= BOND_DRINKS ? ` · ${t('sheet:classicGhoul.bound', 'fully Bound')}` : ''}
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px 16px', fontSize: '14px' }}>
          {p(t('sheet:classicGhoul.bondNote', 'Bond note'), bond.note)}
          {p(t('sheet:classicGhoul.lastFed', "Last fed on the domitor's vitae"), feeding.last)}
          {p(t('sheet:ghoul.feedingNote', 'Feeding note'), feeding.note)}
          {p(t('sheet:classicGhoul.overdosing', 'Overdosing?'), g.overdosing)}
        </div>
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', lineHeight: 1.5, margin: '6px 0 0' }}>
          {t('sheet:classicGhoul.frenzyRule', "Frenzy: Self-Control, at difficulties two lower than a vampire's (Revised p. 276), never more dice than Blood Points held.")}
        </p>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="classic-ghoul-view-advantages" title="Advantages" accent={ACCENT}>
        <Rows title={<Term id="discipline">Disciplines</Term>} rows={disciplines} />
        <Rows title={<Term id="backgrounds" />} rows={backgrounds} />
        <div style={{ display: 'grid', gap: '6px', fontSize: '14px', color: 'var(--sr-bone-100)' }}>
          {Object.keys(virtues).length ? (
            <p style={{ margin: 0 }}>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>
                <Term id="virtues" />:
              </strong>{' '}
              <span lang="en">
                {[
                  ['conscience', 'Conscience'],
                  ['self_control', 'Self-Control'],
                  ['courage', 'Courage'],
                ]
                  .map(([k, label]) => `${label} ${virtues[k] ?? '—'}`)
                  .join(' · ')}
              </span>
            </p>
          ) : null}
          {morality != null && morality !== '' ? (
            <p style={{ margin: 0 }}>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>{path ? 'Path' : <Term id="humanity" />}:</strong> {String(morality)}
            </p>
          ) : null}
          {wm.willpower != null ? (
            <p style={{ margin: 0 }}>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>
                <Term id="willpower" />:
              </strong>{' '}
              {wm.willpower_current != null ? `${wm.willpower_current} / ${wm.willpower}` : String(wm.willpower)}
            </p>
          ) : null}
          {damage ? p(t('sheet:classicGhoul.damage', 'Health levels lost'), String(damage)) : null}
        </div>
      </ResponsiveSheetBlock>
    </>
  );
}
