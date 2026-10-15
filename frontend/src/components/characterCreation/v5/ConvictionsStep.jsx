import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_FLEDGLING_HUMANITY, V5_SECTION_IDS, V5_STARTING_HUMANITY } from '../../../characterSheet/v5/constants';
import { fledglingHumanityAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, addButtonStyle, gridStyle, inputStyle, labelStyle, smallButtonStyle, useForge } from './forgeUi';

/** Step 8 (core p. 137): 1–3 Convictions with Touchstones; Humanity and the trackers. */
export default function ConvictionsStep() {
  const f = useForge();
  const { derived, convictions, setConvictions } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.humanity}
      title={t('wizard:v5.convictionsTitle', 'Convictions & Touchstones')}
      subtitle={t('wizard:v5.humanitySub', '1–3 Convictions, each with a mortal Touchstone.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.humanity} />
      <div style={{ ...gridStyle, gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', marginBottom: '16px', color: 'var(--sr-bone-100)', fontSize: '13px' }}>
        <div><Term id="health" /> <strong>{derived.health}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Stamina + 3)</span></div>
        <div><Term id="willpower" /> <strong>{derived.willpower}</strong> <span style={{ color: 'var(--sr-bone-300)' }}>(Composure + Resolve)</span></div>
        <div><Term id="humanity" /> <strong>{derived.humanity}</strong></div>
        <div><Term id="hunger" /> <strong>{derived.hunger}</strong></div>
      </div>
      {fledglingHumanityAllowed(f.sheet) && f.settings.fledgling_humanity_8 ? (
        <label
          htmlFor="v5-field-fledgling-humanity"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--sr-bone-300)', fontSize: '13px', marginBottom: '14px', cursor: 'pointer' }}
        >
          <input
            id="v5-field-fledgling-humanity"
            type="checkbox"
            checked={f.fledglingHumanity}
            onChange={(e) => f.setFledglingHumanity(e.target.checked)}
          />
          {t('wizard:v5.fledgling', 'Just-Embraced fledgling: start at Humanity {{n}} instead of {{base}} (Storyteller option)', { n: V5_FLEDGLING_HUMANITY, base: V5_STARTING_HUMANITY })}
        </label>
      ) : null}
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
          {convictions.length > 1 ? (
            <button
              type="button"
              onClick={() => setConvictions((prev) => prev.filter((_, j) => j !== i))}
              aria-label={t('wizard:v5.removeConviction', 'Remove conviction {{n}}', { n: i + 1 })}
              style={smallButtonStyle}
            >
              ×
            </button>
          ) : null}
        </div>
      ))}
      {convictions.length < 3 ? (
        <button type="button" onClick={() => setConvictions((prev) => [...prev, { conviction: '', touchstone: '' }])} style={addButtonStyle}>
          {t('wizard:v5.addConviction', '+ Add conviction')}
        </button>
      ) : null}
      <label htmlFor="v5-field-tenets" style={{ ...labelStyle, marginTop: '14px' }}>{t('wizard:v5.tenets', 'Chronicle tenets (from your Storyteller)')}</label>
      <textarea id="v5-field-tenets" value={f.tenets} onChange={(e) => f.setTenets(e.target.value)} rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
    </ResponsiveSheetBlock>
  );
}
