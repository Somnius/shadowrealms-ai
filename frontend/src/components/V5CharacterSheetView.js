import React from 'react';
import DotTrack from './characterCreation/DotTrack';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import { V5_ATTRIBUTES, V5_SKILLS, V5_SKILL_LABELS } from '../characterSheet/v5/constants';
import { getLanguage, t } from '../i18n';
import { bookRef, descIn, findAdvantage, findLoresheet, getV5Rules, powersOf } from '../characterSheet/v5/rulesData';
import { useV5Catalog } from '../rules/v5Catalog';
import { Term } from '../i18n/glossary';

const ACCENT = 'var(--sr-blood-500)';
const obj = (v) => (v && typeof v === 'object' ? v : {});
const n = (v) => {
  const x = parseInt(v, 10);
  return Number.isFinite(x) ? x : 0;
};

function StaticDots({ value, maxRank = 5, accent = ACCENT }) {
  return <DotTrack value={n(value)} maxRank={maxRank} accent={accent} disabled onChange={() => {}} />;
}

/** Health / Willpower boxes: aggravated (X), superficial (/), empty. */
function TrackerBoxes({ termId, label, track, fallbackMax }) {
  const tr = obj(track);
  const max = Math.max(0, n(tr.max) || n(fallbackMax));
  const agg = Math.min(max, n(tr.aggravated));
  const sup = Math.min(max - agg, n(tr.superficial));
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ color: 'var(--sr-arcane-300)', fontSize: '12px', marginBottom: '4px' }}>
        <Term id={termId}>{label}</Term> {max ? `(${max})` : ''}
      </div>
      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }} aria-label={t('sheet:v5.trackerAria', '{{label}}: {{sup}} superficial, {{agg}} aggravated of {{max}}', { label, sup, agg, max })}>
        {Array.from({ length: max }, (_, i) => {
          const mark = i < agg ? 'X' : i < agg + sup ? '/' : '';
          return (
            <span
              key={i}
              style={{
                width: '20px',
                height: '20px',
                border: '1px solid var(--sr-bone-500)',
                borderRadius: '3px',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: mark === 'X' ? 'var(--sr-danger-400)' : 'var(--sr-gold-400)',
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
      <div style={{ color: 'var(--sr-arcane-300)', fontSize: '12px', marginBottom: '4px' }}>
        <Term id="humanity">Humanity {h}</Term>
        {s ? ` · ${t('sheet:v5.stains', { one: '{{count}} Stain', other: '{{count}} Stains' }, { count: s })}` : ''}
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
                border: `2px solid ${filled ? ACCENT : 'var(--sr-night-600)'}`,
                background: filled ? ACCENT : 'transparent',
                color: 'var(--sr-gold-400)',
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
    <p style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
      <strong style={{ color: 'var(--sr-arcane-300)' }}>{label}:</strong> {String(value)}
    </p>
  ) : null;

/** A power or ritual name; with a catalog description it opens to show it (and the book page). */
function CatalogItem({ name, entry }) {
  const text = entry ? descIn(entry, getLanguage()) : '';
  if (!text) return <span>{name}</span>;
  const ref = bookRef(entry);
  return (
    <details className="sr-sheet-catalog-item" style={{ display: 'inline-block', verticalAlign: 'top', marginRight: '10px' }}>
      <summary style={{ cursor: 'pointer' }}>{name}</summary>
      <span style={{ display: 'block', maxWidth: '520px', color: 'var(--sr-bone-300)', fontSize: '12px', margin: '2px 0 6px' }}>
        {text}
        {ref ? <span style={{ color: 'var(--sr-bone-500)' }}> ({ref})</span> : null}
      </span>
    </details>
  );
}

const findPower = (discipline, name) =>
  powersOf(discipline).find((p) => p.name === name || (p.aliases || []).includes(name)) || null;
const findRitual = (name) => getV5Rules().rituals.find((r) => r.name === name) || null;

/** Which clan-only entries a name may mean on this sheet ("Clan Curse" is a Caitiff and a thin-blood Flaw). */
const specialOf = (clan) => (clan === 'Caitiff' ? 'caitiff' : clan === 'Thin-blood' ? 'thin_blood' : null);

/** One Advantage, Flaw or loresheet row: the name opens its description; a loresheet lists its levels. */
function AdvantageRow({ a, special }) {
  const lore = a.kind === 'loresheet' ? findLoresheet(a) : null;
  const entry = lore || (a.kind === 'loresheet' || a.custom ? null : findAdvantage(a, a.flaw ? 'flaw' : a.kind, special));
  const levels = lore && Array.isArray(a.levels) ? lore.levels.filter((l) => a.levels.map(n).includes(l.dots)) : [];
  const tag = a.thinBlood
    ? `thin-blood ${a.flaw ? 'Flaw' : 'Merit'}`
    : a.flaw
      ? 'Flaw'
      : a.kind === 'predator'
        ? ''
        : a.kind || '';
  return (
    <div style={{ marginBottom: '6px', color: a.flaw ? 'var(--sr-blood-300)' : 'var(--sr-bone-100)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ flex: 1 }}>
          <CatalogItem name={String(a.name || '')} entry={entry} />
          <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
            {' '}
            {tag}
            {a.kind === 'predator' ? ` ${t('sheet:v5.fromPredator', '(predator type)')}` : ''}
            {a.source === 'clan' ? ` ${t('sheet:v5.fromClan', '(clan)')}` : ''}
            {a.custom ? ` ${t('sheet:v5.customRow', '(custom)')}` : ''}
            {!a.flaw && n(a.saved_dots) ? ` · ${t('sheet:v5.savedDots', '+{{n}} from saved points', { n: n(a.saved_dots) })}` : ''}
          </span>
        </span>
        {a.thinBlood ? null : <StaticDots value={a.dots} accent={a.flaw ? 'var(--sr-danger-400)' : ACCENT} />}
      </div>
      {levels.length ? (
        <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '2px 0 0 12px' }}>
          {levels.map((l, j) => (
            <React.Fragment key={l.dots}>
              {j ? ' · ' : ''}
              <CatalogItem
                name={`${'●'.repeat(l.dots)} ${l.name || t('sheet:v5.loreLevelUnnamed', 'Level {{n}}', { n: l.dots })}`}
                entry={l.desc ? { desc: l.desc } : null}
              />
            </React.Fragment>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Read-only V5 sheet body (rendered inside CharacterSheetModal).
 */
export default function V5CharacterSheetView({ character }) {
  useV5Catalog();
  const wm = obj(character?.wod_meta);
  const attrs = obj(character?.attributes);
  const sk = obj(character?.skills);
  const specialties = Array.isArray(sk.specialties) ? sk.specialties : [];
  const disciplines = Array.isArray(wm.disciplines) ? wm.disciplines : [];
  const rituals = Array.isArray(wm.rituals) ? wm.rituals.filter((r) => r && r.name) : [];
  const advantages = Array.isArray(wm.advantages) ? wm.advantages.filter((a) => a && typeof a === 'object') : [];
  const flaws = Array.isArray(wm.flaws) ? wm.flaws.filter((a) => a && typeof a === 'object') : [];
  const thinRows = (list, flaw) =>
    (Array.isArray(list) ? list : [])
      .map((x) => (typeof x === 'string' ? x : x?.name))
      .filter((x) => x && String(x).trim())
      .map((name) => ({ name, flaw, thinBlood: true }));
  const thinBlood = [...thinRows(wm.thin_blood_merits, false), ...thinRows(wm.thin_blood_flaws, true)];
  const touchstones = Array.isArray(wm.touchstones) ? wm.touchstones : [];
  // Dots bought with starting experience, from wod_meta.experience.log: { 'skill:brawl': 1 }
  const experience = obj(wm.experience);
  const xpDots = {};
  (Array.isArray(experience.log) ? experience.log : []).forEach((e) => {
    if (e && ['attribute', 'skill', 'discipline'].includes(e.kind) && e.trait) {
      const id = `${e.kind}:${e.trait}`;
      xpDots[id] = (xpDots[id] || 0) + 1;
    }
  });
  const xpNote = (kind, trait) =>
    xpDots[`${kind}:${trait}`] ? (
      <span data-xp-dots={xpDots[`${kind}:${trait}`]} style={{ color: 'var(--sr-ok-400)', fontSize: '11px' }}>
        {' '}
        {t('sheet:v5.xpDots', '+{{n}} XP', { n: xpDots[`${kind}:${trait}`] })}
      </span>
    ) : null;

  const column = (title, rows, values, kind) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div style={{ textAlign: 'center', fontFamily: 'var(--sr-font-display)', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
        {title}
      </div>
      {rows.map(([k, label]) => {
        const sp = specialties
          .filter((s) => s && s.skill === k)
          .map((s) =>
            s.source === 'xp'
              ? t('sheet:v5.xpSpecialty', '{{name}} – XP', { name: s.name })
              : s.source === 'saved'
                ? t('sheet:v5.savedSpecialty', '{{name}} – saved points', { name: s.name })
                : s.name
          );
        return (
          <div
            key={k}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '8px', padding: '4px 6px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px' }}
          >
            <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px', flex: 1 }}>
              {label}
              {sp.length ? <span style={{ color: 'var(--sr-bone-300)' }}> ({sp.join(', ')})</span> : null}
              {xpNote(kind, k)}
            </span>
            <StaticDots value={values[k]} />
          </div>
        );
      })}
    </div>
  );

  return (
    <>
      <p style={{ color: 'var(--sr-bone-500)', fontSize: '13px', marginTop: 0, lineHeight: 1.5 }}>
        {t('sheet:v5.intro', 'Vampire: The Masquerade 5th Edition sheet (read-only).')}
      </p>

      <ResponsiveSheetBlock sectionId="v5-view-identity" title={t('sheet:identity', 'Identity')} accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px 16px', fontSize: '14px' }}>
          {p(t('sheet:v5.concept', 'Concept'), wm.concept)}
          {p(<Term id="clan" />, wm.clan)}
          {p(<Term id="generation" />, wm.generation)}
          {p(<Term id="predator" />, wm.predator_type)}
          {p('Sire', wm.sire)}
          {p('Ambition', wm.ambition)}
          {p('Desire', wm.desire)}
          {n(experience.total)
            ? p('XP', t('sheet:v5.xpSummary', '{{spent}} of {{total}} spent at creation · {{left}} unspent', { spent: n(experience.spent), total: n(experience.total), left: n(experience.unspent) }))
            : null}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-trackers" title={t('sheet:v5.trackers', 'Trackers')} accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
          <div>
            {/* Older/partial sheets may lack the tracker objects: fall back to the derived max. */}
            <TrackerBoxes termId="health" label="Health" track={wm.health} fallbackMax={n(attrs.stamina) + 3} />
            <TrackerBoxes
              termId="willpower"
              label="Willpower"
              track={wm.willpower}
              fallbackMax={n(attrs.composure) + n(attrs.resolve)}
            />
          </div>
          <div>
            <HumanityTrack humanity={wm.humanity} stains={wm.stains} />
            <div style={{ color: 'var(--sr-arcane-300)', fontSize: '12px', marginBottom: '4px' }}><Term id="hunger">Hunger {n(wm.hunger)}</Term></div>
            <StaticDots value={wm.hunger} maxRank={5} accent="var(--sr-blood-600)" />
            <div style={{ color: 'var(--sr-arcane-300)', fontSize: '12px', margin: '10px 0 4px' }}><Term id="bloodPotency">Blood Potency {n(wm.blood_potency)}</Term></div>
            <StaticDots value={wm.blood_potency} maxRank={10} />
          </div>
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-attributes" title={<Term id="attributes" />} accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_ATTRIBUTES[c], attrs, 'attribute')}</React.Fragment>
          ))}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="v5-view-skills" title={<Term id="skills" />} accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_SKILLS[c], obj(sk[c]), 'skill')}</React.Fragment>
          ))}
        </div>
        {specialties.some((s) => s && !V5_SKILL_LABELS[s.skill]) ? (
          <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
            {t('sheet:v5.otherSpecialties', 'Other specialties:')}{' '}
            {specialties.filter((s) => s && !V5_SKILL_LABELS[s.skill]).map((s) => `${s.skill}: ${s.name}`).join(', ')}
          </p>
        ) : null}
      </ResponsiveSheetBlock>

      {disciplines.length ? (
        <ResponsiveSheetBlock sectionId="v5-view-disciplines" title={<Term id="discipline">Disciplines</Term>} accent={ACCENT}>
          {disciplines.map((d, i) => (
            <div key={i} style={{ marginBottom: '10px', color: 'var(--sr-bone-100)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <strong style={{ minWidth: '140px' }}>{d.name}</strong>
                <StaticDots value={d.level} />
                {xpNote('discipline', d.name)}
              </div>
              {Array.isArray(d.powers) && d.powers.length ? (
                <div style={{ color: 'var(--sr-bone-300)', fontSize: '12px', marginTop: '2px' }}>
                  {d.powers.map((pw, j) => {
                    const name = typeof pw === 'string' ? pw : pw?.name;
                    if (!name) return null;
                    return (
                      <React.Fragment key={j}>
                        {j ? ' · ' : ''}
                        <CatalogItem name={name} entry={findPower(d.name, name)} />
                      </React.Fragment>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {rituals.length ? (
        <ResponsiveSheetBlock sectionId="v5-view-rituals" title="Rituals" accent={ACCENT}>
          {rituals.map((r, i) => (
            <div key={i} style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
              <span style={{ fontWeight: 700 }}>
                <CatalogItem name={String(r.name)} entry={findRitual(String(r.name))} />
              </span>{' '}
              <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>
                {r.kind === 'ceremony' ? `${t('sheet:v5.ceremony', 'Ceremony')} · ` : ''}
                {t('sheet:v5.ritualLevel', 'Level {{n}}', { n: n(r.level) })}
                {r.source === 'xp' ? ` · ${t('sheet:v5.ritualFromXp', 'bought with XP')}` : ''}
              </span>
            </div>
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {advantages.length || flaws.length || thinBlood.length ? (
        <ResponsiveSheetBlock sectionId="v5-view-advantages" title="Advantages & Flaws" accent={ACCENT}>
          {[...advantages, ...flaws.map((f) => ({ ...f, flaw: true })), ...thinBlood].map((a, i) => (
            <AdvantageRow key={i} a={a} special={a.thinBlood ? 'thin_blood' : specialOf(wm.clan)} />
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {touchstones.length || wm.chronicle_tenets ? (
        <ResponsiveSheetBlock sectionId="v5-view-convictions" title={<Term id="convictions" />} accent={ACCENT}>
          {touchstones.map((ts, i) => (
            <p key={i} style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>{ts.conviction}</strong> — {ts.name}
            </p>
          ))}
          {p(t('sheet:v5.tenets', 'Chronicle tenets'), wm.chronicle_tenets)}
        </ResponsiveSheetBlock>
      ) : null}

      {character?.background != null && String(character.background).trim() ? (
        <ResponsiveSheetBlock sectionId="v5-view-story" title={t('sheet:backgroundNotes', 'Background & notes')} accent={ACCENT}>
          <p style={{ color: 'var(--sr-bone-100)', whiteSpace: 'pre-wrap', lineHeight: 1.55, margin: 0 }}>{String(character.background)}</p>
        </ResponsiveSheetBlock>
      ) : null}
    </>
  );
}
