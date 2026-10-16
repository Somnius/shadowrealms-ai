import React from 'react';
import { Button } from '../design';
import ResponsiveSheetBlock from './characterCreation/ResponsiveSheetBlock';
import { V5_ATTRIBUTES, V5_SKILLS } from '../characterSheet/v5/constants';
import { GHOUL_BOND_STRENGTH_MAX } from '../characterSheet/v5/ghoul';
import { ghoulTemplateName } from '../characterSheet/i18nErrors';
import { t } from '../i18n';
import { useV5Catalog } from '../rules/v5Catalog';
import { Term } from '../i18n/glossary';
import { AdvantageRow, CatalogItem, HumanityTrack, StaticDots, TrackerBoxes, findPower, p } from './V5CharacterSheetView';

const ACCENT = 'var(--sr-blood-500)';
const obj = (v) => (v && typeof v === 'object' ? v : {});
const n = (v) => {
  const x = parseInt(v, 10);
  return Number.isFinite(x) ? x : 0;
};
// the Flaws that change how a Bond works (core p. 180, Blood-Stained Love p. 151)
const BOND_FLAWS = { 'flaw:bondslave': 'Bondslave', 'flaw:two-masters': 'Two Masters', 'flaw:bond-junkie': 'Bond Junkie', 'flaw:long-bond': 'Long Bond' };

/** The domitor: a button to its sheet when it still exists, else the name the ghoul's sheet stored. */
export function DomitorLink({ domitor, stored, onOpenSheet }) {
  const name = domitor?.name || stored?.name || '';
  if (!name) return null;
  if (domitor && domitor.exists === false) {
    return (
      <span>
        {name} <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>{t('sheet:ghoul.domitorGone', '(sheet no longer exists)')}</span>
      </span>
    );
  }
  const id = domitor?.id || stored?.character_id;
  return onOpenSheet && id ? (
    <Button size="sm" variant="ghost" onClick={() => onOpenSheet(id)}>
      {name}
    </Button>
  ) : (
    <span>{name}</span>
  );
}

/**
 * Read-only sheet of a ghoul (wod_meta.sheet_kind 'ghoul'), rendered by CharacterSheetModal in
 * place of V5CharacterSheetView: the domitor, template, the ghoul power, the Blood Bond and a note on
 * feeding; no vitae track, Hunger or Blood Potency (a V5 ghoul has none). Rules: core p. 234,
 * Players Guide pp. 140–142.
 */
export default function V5GhoulSheetView({ character, onOpenSheet }) {
  useV5Catalog();
  const wm = obj(character?.wod_meta);
  const g = obj(wm.ghoul);
  const stored = obj(g.domitor);
  const domitor = character?.domitor && typeof character.domitor === 'object' ? character.domitor : null;
  const attrs = obj(character?.attributes);
  const sk = obj(character?.skills);
  const specialties = Array.isArray(sk.specialties) ? sk.specialties : [];
  const disciplines = Array.isArray(wm.disciplines) ? wm.disciplines.filter((d) => d && d.name) : [];
  const advantages = Array.isArray(wm.advantages) ? wm.advantages.filter((a) => a && typeof a === 'object') : [];
  const flaws = Array.isArray(wm.flaws) ? wm.flaws.filter((a) => a && typeof a === 'object') : [];
  const touchstones = Array.isArray(wm.touchstones) ? wm.touchstones : [];
  const bonds = Array.isArray(g.bonds) ? g.bonds.filter((b) => b && typeof b === 'object') : [];
  // `vitae` is the key's earlier name
  const feeding = obj(g.feeding && typeof g.feeding === 'object' ? g.feeding : g.vitae);
  const bondFlaws = flaws.map((f) => BOND_FLAWS[f.id]).filter(Boolean);
  const retainerDots = n(g.retainer_dots);
  const template = [ghoulTemplateName(g.template), retainerDots ? `Retainers ${'•'.repeat(retainerDots)}` : ''].filter(Boolean).join(' · ');
  const looks = [g.age, g.apparent_age].filter((v) => v != null && v !== '').join(' / ');
  const notes = String(obj(character?.merits_flaws).notes || '').trim();

  const column = (title, rows, values, withSpecialties) => (
    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
      <div style={{ textAlign: 'center', fontFamily: 'var(--sr-font-display)', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
        {title}
      </div>
      {rows.map(([k, label]) => {
        const sp = withSpecialties ? specialties.filter((s) => s && s.skill === k).map((s) => s.name) : [];
        return (
          <div
            key={k}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '8px', padding: '4px 6px', background: 'rgba(0,0,0,0.15)', borderRadius: '6px' }}
          >
            <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px', flex: 1 }}>
              {label}
              {sp.length ? <span> ({sp.join(', ')})</span> : null}
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
        {t('sheet:ghoul.intro', 'Ghoul sheet, V5 (read-only). Rules: core p. 234, Players Guide pp. 140–142.')}
      </p>

      <ResponsiveSheetBlock sectionId="ghoul-view-identity" title={t('sheet:identity', 'Identity')} accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '4px 16px', fontSize: '14px' }}>
          {p(t('sheet:v5.concept', 'Concept'), wm.concept)}
          <p style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
            <strong style={{ color: 'var(--sr-arcane-300)' }}>
              <Term id="domitor" />:
            </strong>{' '}
            <DomitorLink domitor={domitor} stored={stored} onOpenSheet={onOpenSheet} />
          </p>
          {p(t('sheet:ghoul.domitorClan', "Domitor's clan"), domitor?.clan || stored.clan)}
          {p(t('sheet:ghoul.template', 'Template'), template)}
          {p(t('sheet:ghoul.ageLooks', 'Age / looks'), looks)}
          {p(t('sheet:ghoul.since', 'Ghoul since'), g.ghouled_since)}
          {p('Ambition', wm.ambition)}
          {p('Desire', wm.desire)}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="ghoul-view-trackers" title={t('sheet:v5.trackers', 'Trackers')} accent={ACCENT}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
          <div>
            <TrackerBoxes termId="health" label="Health" track={wm.health} fallbackMax={n(attrs.stamina) + 3} />
            <TrackerBoxes termId="willpower" label="Willpower" track={wm.willpower} fallbackMax={n(attrs.composure) + n(attrs.resolve)} />
          </div>
          <div>
            {wm.humanity != null ? <HumanityTrack humanity={wm.humanity} stains={wm.stains} /> : null}
            <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '6px 0 0' }}>
              {t('sheet:ghoul.healing', 'Heals twice as fast as a mortal, except fire (Players Guide p. 142). No Hunger, no Blood Potency.')}
            </p>
          </div>
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="ghoul-view-attributes" title={<Term id="attributes" />} accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_ATTRIBUTES[c], attrs, false)}</React.Fragment>
          ))}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="ghoul-view-skills" title={<Term id="skills" />} accent={ACCENT}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
          {['physical', 'social', 'mental'].map((c) => (
            <React.Fragment key={c}>{column(c, V5_SKILLS[c], obj(sk[c]), true)}</React.Fragment>
          ))}
        </div>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="ghoul-view-power" title={t('sheet:ghoul.powerTitle', 'Ghoul power')} accent={ACCENT}>
        {disciplines.length ? (
          disciplines.map((d, i) => (
            <div key={i} data-ghoul-power style={{ marginBottom: '8px', color: 'var(--sr-bone-100)' }}>
              <strong>{d.name}</strong>{' '}
              <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>{t('sheet:ghoul.oneDot', '(counts as 1 dot)')}</span>
              {(Array.isArray(d.powers) ? d.powers : []).map((pw, j) => {
                const name = typeof pw === 'string' ? pw : pw?.name;
                return name ? (
                  <React.Fragment key={j}>
                    {' · '}
                    <CatalogItem name={name} entry={findPower(d.name, name)} />
                  </React.Fragment>
                ) : null;
              })}
            </div>
          ))
        ) : (
          <p style={{ color: 'var(--sr-bone-300)', fontSize: '13px', margin: 0 }}>—</p>
        )}
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '4px 0 0' }}>
          {t('sheet:ghoul.powerNote', 'No Rouse Checks: a power above level 1 costs 1 Aggravated (core p. 234).')}
        </p>
      </ResponsiveSheetBlock>

      <ResponsiveSheetBlock sectionId="ghoul-view-bond" title={<Term id="bloodBond">{t('sheet:ghoul.bondTitle', 'Blood Bond & feeding')}</Term>} accent={ACCENT}>
        {bonds.map((b, i) => (
          <div key={i} data-bond={i} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', marginBottom: '8px', color: 'var(--sr-bone-100)' }}>
            <strong style={{ minWidth: '140px' }}>{b.name || (i === 0 ? stored.name : '')}</strong>
            {b.strength == null || b.strength === '' ? (
              <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>{t('sheet:ghoul.strengthNotSet', 'Bond Strength not set (the Storyteller sets it)')}</span>
            ) : (
              <>
                <span style={{ color: 'var(--sr-bone-300)', fontSize: '12px' }}>Bond Strength</span>
                <StaticDots value={b.strength} maxRank={GHOUL_BOND_STRENGTH_MAX} />
              </>
            )}
            {b.note ? <span style={{ flexBasis: '100%', color: 'var(--sr-bone-300)', fontSize: '12px' }}>{b.note}</span> : null}
          </div>
        ))}
        {bondFlaws.length ? p(t('sheet:ghoul.bondFlaws', 'Bond Flaws'), bondFlaws.join(' · ')) : null}
        {p(t('sheet:ghoul.lastFed', "Last fed on the domitor's Blood"), feeding.last)}
        {p(t('sheet:ghoul.feedingNote', 'Feeding note'), feeding.note)}
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '4px 0 0' }}>
          {t('sheet:ghoul.feedingRule', "A Rouse Check's worth of the domitor's Blood keeps a ghoul about a month (core p. 234). No vitae track, no Hunger.")}
        </p>
      </ResponsiveSheetBlock>

      {advantages.length || flaws.length ? (
        <ResponsiveSheetBlock sectionId="ghoul-view-advantages" title="Advantages & Flaws" accent={ACCENT}>
          {[...advantages, ...flaws.map((f) => ({ ...f, flaw: true }))].map((a, i) => (
            <AdvantageRow key={i} a={a} special={null} />
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {touchstones.length ? (
        <ResponsiveSheetBlock sectionId="ghoul-view-convictions" title={<Term id="convictions" />} accent={ACCENT}>
          {touchstones.map((ts, i) => (
            <p key={i} style={{ margin: '0 0 6px', color: 'var(--sr-bone-100)' }}>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>{ts.conviction}</strong> — {ts.name}
            </p>
          ))}
        </ResponsiveSheetBlock>
      ) : null}

      {String(character?.background || '').trim() || notes ? (
        <ResponsiveSheetBlock sectionId="ghoul-view-story" title={t('sheet:backgroundNotes', 'Background & notes')} accent={ACCENT}>
          {String(character?.background || '').trim() ? (
            <p style={{ color: 'var(--sr-bone-100)', whiteSpace: 'pre-wrap', lineHeight: 1.55, margin: '0 0 8px' }}>{String(character.background)}</p>
          ) : null}
          {notes ? <p style={{ color: 'var(--sr-bone-300)', whiteSpace: 'pre-wrap', margin: 0 }}>{notes}</p> : null}
        </ResponsiveSheetBlock>
      ) : null}
    </>
  );
}
