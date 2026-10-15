import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import DotTrack from '../DotTrack';
import { V5_ATTRIBUTES, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, SpreadChips, rowStyle, useForge } from './forgeUi';

/** Step 3 (core p. 136): one Attribute at 4, three at 3, four at 2, one at 1. */
export default function AttributesStep() {
  const f = useForge();
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.attributes}
      title={<Term id="attributes" />}
      subtitle={t('wizard:v5.attributesSub', 'One at 4, three at 3, four at 2, one at 1.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.attributes} />
      <SpreadChips status={f.attrStatus} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px' }}>
        {['physical', 'social', 'mental'].map((cat) => (
          <div key={cat} style={{ flex: '1 1 200px', minWidth: 0 }}>
            <div style={{ textAlign: 'center', fontFamily: 'var(--sr-font-display)', fontSize: '12px', color: ACCENT, marginBottom: '10px', textTransform: 'capitalize' }}>
              {cat}
            </div>
            {V5_ATTRIBUTES[cat].map(([k, label]) => (
              <div key={k} style={rowStyle}>
                <span style={{ color: 'var(--sr-bone-100)', fontSize: '13px' }}>{label}</span>
                <DotTrack
                  label={label}
                  value={f.attributes[k]}
                  maxRank={4}
                  accent={ACCENT}
                  onChange={(n) => f.setAttributes((prev) => ({ ...prev, [k]: Math.max(1, n) }))}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </ResponsiveSheetBlock>
  );
}
