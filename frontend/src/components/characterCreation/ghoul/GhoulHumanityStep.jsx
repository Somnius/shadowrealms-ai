import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { GHOUL_HUMANITY, PLAYER_GHOUL } from '../../../characterSheet/v5/ghoul';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, addButtonStyle, gridStyle, inputStyle, smallButtonStyle, useForge } from '../v5/forgeUi';

/** Humanity (7 for ghouls, PG p. 142) and Convictions with Touchstones (1–3 for a player ghoul). */
export default function GhoulHumanityStep() {
  const f = useForge();
  const { derived, convictions, setConvictions } = f;
  const player = f.template === PLAYER_GHOUL;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.humanity}
      title={t('wizard:ghoul.humanityTitle', 'Humanity & Convictions')}
      subtitle={
        player
          ? t('wizard:ghoul.humanityPlayer', '1–3 Convictions, each with a Touchstone, as mortals take them (Players Guide p. 142).')
          : t('wizard:ghoul.humanityRetainer', 'Optional for a retainer: up to 3 Convictions, each with a Touchstone.')
      }
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.humanity} />
      <div style={{ ...gridStyle, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', marginBottom: '14px', color: 'var(--sr-bone-100)', fontSize: '13px' }}>
        <div><Term id="health" /> <strong>{derived.health}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Stamina + 3)</span></div>
        <div><Term id="willpower" /> <strong>{derived.willpower}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Composure + Resolve)</span></div>
        <div><Term id="humanity" /> <strong>{derived.humanity ?? '—'}</strong></div>
      </div>
      <label htmlFor="ghoul-field-humanity" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--sr-bone-300)', fontSize: '13px', marginBottom: '14px', cursor: player ? 'default' : 'pointer' }}>
        <input
          id="ghoul-field-humanity"
          type="checkbox"
          checked={player || f.humanityTracked}
          disabled={player}
          onChange={(e) => f.setHumanityTracked(e.target.checked)}
        />
        {t('wizard:ghoul.trackHumanity', 'Track Humanity (ghouls start at {{n}}, Players Guide p. 142)', { n: GHOUL_HUMANITY })}
      </label>
      {convictions.map((c, i) => (
        <div key={i} style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
          <input
            aria-label={t('wizard:v5.convictionN', 'Conviction {{n}}', { n: i + 1 })}
            value={c.conviction}
            placeholder={t('wizard:v5.convictionPlaceholder', 'Conviction (e.g. Never kill a child)')}
            onChange={(e) => setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, conviction: e.target.value } : x)))}
            style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
          />
          <input
            aria-label={t('wizard:v5.touchstoneN', 'Touchstone {{n}}', { n: i + 1 })}
            value={c.touchstone}
            placeholder={t('wizard:v5.touchstonePlaceholder', 'Touchstone (a living mortal)')}
            onChange={(e) => setConvictions((prev) => prev.map((x, j) => (j === i ? { ...x, touchstone: e.target.value } : x)))}
            style={{ ...inputStyle, flex: '2 1 220px', width: 'auto', padding: '8px' }}
          />
          <button
            type="button"
            onClick={() => setConvictions((prev) => prev.filter((_, j) => j !== i))}
            aria-label={t('wizard:v5.removeConviction', 'Remove conviction {{n}}', { n: i + 1 })}
            style={smallButtonStyle}
          >
            ×
          </button>
        </div>
      ))}
      {convictions.length < 3 ? (
        <button type="button" onClick={() => setConvictions((prev) => [...prev, { conviction: '', touchstone: '' }])} style={addButtonStyle}>
          {t('wizard:v5.addConviction', '+ Add conviction')}
        </button>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
