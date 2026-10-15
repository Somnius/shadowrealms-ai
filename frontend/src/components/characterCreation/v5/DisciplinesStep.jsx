import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { CAITIFF, THIN_BLOOD, V5_NAME_MAX, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { startingRitualAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import PredatorPreview from './PredatorPreview';
import { ACCENT, InlineError, SourceDots, inputStyle, labelStyle, useForge } from './forgeUi';

/** Step 5 (core p. 136): two clan Disciplines (2 + 1), a power per dot, and the predator preview. */
export default function DisciplinesStep() {
  const f = useForge();
  const { clan, discRows, setDisc } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.disciplines}
      title={<Term id="discipline">Disciplines</Term>}
      subtitle={
        clan === THIN_BLOOD
          ? t('wizard:v5.discThin', 'Thin-bloods start with no Disciplines.')
          : clan === CAITIFF
            ? t('wizard:v5.discCaitiff', 'Any two Disciplines: one at 2 dots, one at 1. One power per dot.')
            : t('wizard:v5.discClan', 'Two clan Disciplines: one at 2 dots, one at 1. One power per dot.')
      }
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.disciplines} />
      {discRows.map((row, i) => {
        const discLabel = row.name || `Discipline ${i + 1}`;
        const setPower = (p, value) => {
          const powers = [...row.powers];
          powers[p] = value;
          if (row.pick != null) setDisc(row.pick, { powers });
          else f.setExtraPowers((prev) => ({ ...prev, [row.name]: powers }));
        };
        return (
          <div key={row.pick != null ? `pick-${row.pick}` : `extra-${row.name}`} style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
              {row.pick != null ? (
                <select
                  aria-label={t('wizard:v5.discAt', { one: 'Discipline at {{count}} dot', other: 'Discipline at {{count}} dots' }, { count: row.base })}
                  value={row.name}
                  onChange={(e) => {
                    // A new name starts with no powers, except the ones already typed on
                    // that Discipline's own (predator/XP) row, which this pick now absorbs.
                    const next = e.target.value;
                    const absorbed = discRows.find((r) => r.pick == null && r.name === next);
                    setDisc(row.pick, { name: next, powers: absorbed ? absorbed.powers : [] });
                  }}
                  style={{ ...inputStyle, flex: '1 1 200px', width: 'auto', padding: '8px' }}
                >
                  <option value="">{t('wizard:v5.discAtPick', { one: 'Discipline at {{count}} dot…', other: 'Discipline at {{count}} dots…' }, { count: row.base })}</option>
                  {f.discOptions.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              ) : (
                <strong style={{ flex: '1 1 200px', color: 'var(--sr-bone-100)', fontSize: '14px', padding: '8px 0' }}>{row.name}</strong>
              )}
              <SourceDots label={discLabel} row={row} />
            </div>
            {row.predator || row.xp ? (
              <div style={{ color: 'var(--sr-gold-400)', fontSize: '12px', marginTop: '4px' }}>
                {row.predator ? t('wizard:v5.predatorDotNote', '+1 from {{type}}', { type: f.predatorType }) : null}
                {row.predator && row.xp ? ' · ' : null}
                {row.xp ? t('wizard:v5.xpDotNote', '+{{n}} from XP', { n: row.xp }) : null}
              </div>
            ) : null}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
              {row.powers.map((pw, p) => (
                <input
                  key={p}
                  value={pw}
                  aria-label={t('wizard:v5.powerLabel', '{{disc}} power {{n}}', { disc: discLabel, n: p + 1 })}
                  placeholder={t('wizard:v5.powerPlaceholder', 'Power {{n}} (optional)', { n: p + 1 })}
                  onChange={(e) => setPower(p, e.target.value)}
                  style={{ ...inputStyle, flex: '1 1 180px', width: 'auto', padding: '6px 8px', fontSize: '12px' }}
                />
              ))}
            </div>
          </div>
        );
      })}
      {startingRitualAllowed(f.sheet) ? (
        <div style={{ marginTop: '6px', maxWidth: '420px' }}>
          <label htmlFor="v5-field-starting-ritual" style={labelStyle}>
            {t('wizard:v5.startingRitual', 'Starting ritual (Level 1)')}
          </label>
          <input
            id="v5-field-starting-ritual"
            value={f.startingRitual}
            maxLength={V5_NAME_MAX}
            onChange={(e) => f.setStartingRitual(e.target.value)}
            placeholder={t('wizard:v5.startingRitualPlaceholder', 'optional: one Level 1 Blood Sorcery ritual')}
            style={inputStyle}
          />
        </div>
      ) : null}
      <PredatorPreview />
    </ResponsiveSheetBlock>
  );
}
