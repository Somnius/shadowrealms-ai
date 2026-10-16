import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import DotTrack from '../DotTrack';
import { V5_ATTRIBUTES, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { PLAYER_GHOUL } from '../../../characterSheet/v5/ghoul';
import { ghoulTemplateName } from '../../../characterSheet/i18nErrors';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, SpreadChips, rowStyle, useForge } from '../v5/forgeUi';

/** Attributes: the template's spread (core p. 185), or the vampire one for a player ghoul (PG p. 140). */
export default function GhoulAttributesStep() {
  const f = useForge();
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.attributes}
      title={<Term id="attributes" />}
      subtitle={
        f.template === PLAYER_GHOUL
          ? t('wizard:ghoul.attributesPlayer', 'One at 4, three at 3, four at 2, one at 1 (Players Guide p. 140).')
          : t('wizard:ghoul.attributesTemplate', 'The {{template}} spread (core p. 185): the chips show what is left.', { template: ghoulTemplateName(f.template) })
      }
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
                  maxRank={f.attrMax}
                  accent={ACCENT}
                  onChange={(n) => f.setAttributes((prev) => ({ ...prev, [k]: Math.max(f.attrMin, n) }))}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </ResponsiveSheetBlock>
  );
}
