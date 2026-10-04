import React from 'react';
import DotTrack from './characterCreation/DotTrack';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import { V5_ATTRIBUTES, V5_SKILLS, V5_SKILL_LABELS } from '../characterSheet/v5/constants';

const ACCENT = '#e94560';
const obj = (v) => (v && typeof v === 'object' ? v : {});
const n = (v) => {
  const x = parseInt(v, 10);
  return Number.isFinite(x) ? x : 0;
};

function StaticDots({ value, maxRank = 5, accent = ACCENT }) {
  return <DotTrack value={n(value)} maxRank={maxRank} accent={accent} disabled onChange={() => {}} />;
}

/** Health / Willpower boxes: aggravated (X), superficial (/), empty. */
function TrackerBoxes({ label, track, fallbackMax }) {
  const t = obj(track);
  const max = Math.max(0, n(t.max) || n(fallbackMax));
  const agg = Math.min(max, n(t.aggravated));
  const sup = Math.min(max - agg, n(t.superficial));
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ color: '#c4b5fd', fontSize: '12px', marginBottom: '4px' }}>
        {label} {max ? `(${max})` : ''}
      </div>
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }} aria-label={`${label}: ${sup} superficial, ${agg} aggravated of ${max}`}>
        {Array.from({ length: max }, (_, i) => {
          const mark = i < agg ? 'X' : i < agg + sup ? '/' : '';
          return (
            <span
              key={i}
              style={{
                width: '20px',
                height: '20px',
                border: '1px solid #64748b',
                borderRadius: '3px',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: mark === 'X' ? '#f87171' : '#fbbf24',
                fontWeight: 700,
                fontSize: '13px',
              }}
            >
              {mark}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** Humanity track: filled left to right, Stains right to left. */
function HumanityTrack({ humanity, stains }) {
  const h = n(humanity);
  const s = n(stains);
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ color: '#c4b5fd', fontSize: '12px', marginBottom: '4px' }}>
        Humanity {h}
        {s ? ` · ${s} Stains` : ''}
      </div>
      <div style={{ display: 'flex', gap: '4px' }}>
        {Array.from({ length: 10 }, (_, i) => {
          const filled = i < h;
          const stained = i >= 10 - s;
          return (
            <span
              key={i}
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                border: `2px solid ${filled ? ACCENT : '#4b5568'}`,
                background: filled ? ACCENT : 'transparent',
                color: '#fbbf24',
                fontSize: '11px',
                lineHeight: '12px',
                textAlign: 'center',
              }}
            >
              {stained ? '/' : ''}
            </span>
          );
        })}
      </div>
    </div>
  );
}

const p = (label, value) =>
  value != null && String(value).trim() !== '' ? (
    <p style={{ margin: '0 0 6px', color: '#e0e0e0' }}>
      <strong style={{ color: '#c4b5fd' }}>{label}:</strong> {String(value)}
    </p>
  ) : null;

/**
 * Read-only V5 sheet body (rendered inside CharacterSheetModal).
 */
export default function V5CharacterSheetView({ character }) {
  const wm = obj(character?.wod_meta);
  const attrs = obj(character?.attributes);
  const sk = obj(character?.skills);
  const specialties = Array.isArray(sk.specialties) ? sk.specialties : [];
  const disciplines = Array.isArray(wm.disciplines) ? wm.disciplines : [];
  const advantages = Array.isArray(wm.advantages) ? wm.advantages : [];
  const flaws = Array.isArray(wm.flaws) ? wm.flaws : [];
  const touchstones = Array.isArray(wm.touchstones) ? wm.touchstones : [];

  const column = (title, rows, values) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div style={{ textAlign: 'center', fontFamily: 'Cinzel, serif', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
        {title}
      </div>
      {rows.map(([k, label]) => {
        const sp = specialties.filter((s) => s && s.skill === k).map((s) => s.name);
        return (
          <div
            key={k}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '8px', padding: '4px 6px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px' }}
          >
            <span style={{ color: '#cbd5e1', fontSize: '12px', flex: 1 }}>
              {label}
              {sp.length ? <span style={{ color: '#94a3b8' }}> ({sp.join(', ')})</span> : null}
            </span>
            <StaticDots value={values[k]} />
          </div>
        );
      })}
    </div>
  );

  return (
    <>
      <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: 0, lineHeight: 1.5 }}>
        Vampire: The Masquerade 5th Edition sheet (read-only).
      </p>

      <ResponsiveSheetBlock sectionId="v5-view-identity" title="Identity" accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px 16px', fontSize: '14px' }}>
          {p('Concept', wm.concept)}
          {p('Clan', wm.clan)}
          {p('Generation', wm.generation)}
          {p('Predator type', wm.predator_type)}
          {p('Sire', wm.sire)}
          {p('Ambition', wm.ambition)}
          {p('Desire', wm.desire)}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-trackers" title="Trackers" accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
          <div>
            {/* Older/partial sheets may lack the tracker objects: fall back to the derived max. */}
            <TrackerBoxes label="Health" track={wm.health} fallbackMax={n(attrs.stamina) + 3} />
            <TrackerBoxes
              label="Willpower"
              track={wm.willpower}
              fallbackMax={n(attrs.composure) + n(attrs.resolve)}
            />
          </div>
          <div>
            <HumanityTrack humanity={wm.humanity} stains={wm.stains} />
            <div style={{ color: '#c4b5fd', fontSize: '12px', marginBottom: '4px' }}>Hunger {n(wm.hunger)}</div>
            <StaticDots value={wm.hunger} maxRank={5} accent="#dc2626" />
            <div style={{ color: '#c4b5fd', fontSize: '12px', margin: '10px 0 4px' }}>Blood Potency {n(wm.blood_potency)}</div>
            <StaticDots value={wm.blood_potency} maxRank={10} />
          </div>
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-attributes" title="Attributes" accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_ATTRIBUTES[c], attrs)}</React.Fragment>
          ))}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-skills" title="Skills" accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_SKILLS[c], obj(sk[c]))}</React.Fragment>
          ))}
        </div>
        {specialties.some((s) => s && !V5_SKILL_LABELS[s.skill]) ? (
          <p style={{ color: '#94a3b8', fontSize: '12px' }}>
            Other specialties:{' '}
            {specialties.filter((s) => s && !V5_SKILL_LABELS[s.skill]).map((s) => `${s.skill}: ${s.name}`).join(', ')}
          </p>
        ) : null}
      </ResponsiveSheetBlock>

      {disciplines.length ? (
        <ResponsiveSheetBlock sectionId="v5-view-disciplines" title="Disciplines" accent={ACCENT}>
          {disciplines.map((d, i) => (
            <div key={i} style={{ marginBottom: '10px', color: '#e0e0e0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <strong style={{ minWidth: '140px' }}>{d.name}</strong>
                <StaticDots value={d.level} />
              </div>
              {Array.isArray(d.powers) && d.powers.length ? (
                <div style={{ color: '#94a3b8', fontSize: '12px', marginTop: '2px' }}>{d.powers.join(' · ')}</div>
              ) : null}
            </div>
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {advantages.length || flaws.length ? (
        <ResponsiveSheetBlock sectionId="v5-view-advantages" title="Advantages & flaws" accent={ACCENT}>
          {[...advantages, ...flaws.map((f) => ({ ...f, flaw: true }))].map((a, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px', color: a.flaw ? '#fca5a5' : '#e0e0e0' }}>
              <span style={{ flex: 1 }}>
                {a.name}
                <span style={{ color: '#94a3b8', fontSize: '12px' }}>
                  {' '}
                  {a.flaw ? 'flaw' : a.kind || ''}
                  {a.kind === 'predator' && a.flaw ? ' (predator type)' : ''}
                </span>
              </span>
              <StaticDots value={a.dots} accent={a.flaw ? '#f87171' : ACCENT} />
            </div>
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {touchstones.length || wm.chronicle_tenets ? (
        <ResponsiveSheetBlock sectionId="v5-view-convictions" title="Convictions & touchstones" accent={ACCENT}>
          {touchstones.map((t, i) => (
            <p key={i} style={{ margin: '0 0 6px', color: '#e0e0e0' }}>
              <strong style={{ color: '#c4b5fd' }}>{t.conviction}</strong> — {t.name}
            </p>
          ))}
          {p('Chronicle tenets', wm.chronicle_tenets)}
        </ResponsiveSheetBlock>
      ) : null}

      {character?.background != null && String(character.background).trim() ? (
        <ResponsiveSheetBlock sectionId="v5-view-story" title="Background & notes" accent={ACCENT}>
          <p style={{ color: '#d1d5db', whiteSpace: 'pre-wrap', lineHeight: 1.55, margin: 0 }}>{String(character.background)}</p>
        </ResponsiveSheetBlock>
      ) : null}
    </>
  );
}
