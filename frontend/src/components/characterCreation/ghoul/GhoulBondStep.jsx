import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { GHOUL_BOND_STRENGTH_MAX, hasTwoMasters } from '../../../characterSheet/v5/ghoul';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, addButtonStyle, gridStyle, inputStyle, labelStyle, noteStyle, smallButtonStyle, useForge } from '../v5/forgeUi';

const STRENGTHS = Array.from({ length: GHOUL_BOND_STRENGTH_MAX + 1 }, (_, i) => i);

function StrengthSelect({ id, value, onChange }) {
  return (
    <select id={id} value={value == null ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} style={inputStyle}>
      <option value="">{t('wizard:ghoul.strengthNotSet', 'not set (Storyteller)')}</option>
      {STRENGTHS.map((n) => (
        <option key={n} value={n}>
          {n} {'●'.repeat(n)}
        </option>
      ))}
    </select>
  );
}

/**
 * Blood Bond(s) and a feeding note (core pp. 233–234; Two Masters: Blood-Stained Love p. 151). A V5
 * ghoul has no vitae track, Hunger or Blood Potency: when it last fed is a note, nothing is counted.
 */
export default function GhoulBondStep() {
  const f = useForge();
  const { bonds, setBonds, feeding, setFeeding, domitor } = f;
  const set = (i, patch) => setBonds((prev) => prev.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  const two = hasTwoMasters(f.sheet);
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.bond}
      title={<Term id="bloodBond">{t('wizard:ghoul.bondTitle', 'Blood Bond & feeding')}</Term>}
      subtitle={t('wizard:ghoul.bondSub', 'Strength = drinks of the regnant\'s Blood, up to 6; −1 for each month without. To act against the regnant: Resolve + Intelligence vs Bond Strength (core p. 234).')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.bond} />
      <div style={gridStyle}>
        <div>
          <span style={labelStyle}>{t('wizard:ghoul.regnant', 'Regnant')}</span>
          <div id="ghoul-regnant" style={{ ...inputStyle, background: 'transparent' }}>
            {domitor ? domitor.name : '—'}
          </div>
        </div>
        <div>
          <label htmlFor="ghoul-field-strength" style={labelStyle}>{t('wizard:ghoul.strength', 'Bond Strength')}</label>
          <StrengthSelect id="ghoul-field-strength" value={bonds[0]?.strength} onChange={(v) => set(0, { strength: v })} />
        </div>
      </div>
      <label htmlFor="ghoul-field-bond-note" style={{ ...labelStyle, marginTop: '10px' }}>{t('wizard:ghoul.bondNote', 'Note on the Bond')}</label>
      <input id="ghoul-field-bond-note" value={bonds[0]?.note || ''} maxLength={500} onChange={(e) => set(0, { note: e.target.value })} style={inputStyle} />
      {bonds.length > 1 ? (
        <div id="ghoul-second-bond" style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px solid var(--sr-night-700)' }}>
          <div style={gridStyle}>
            <div>
              <label htmlFor="ghoul-field-bond2-name" style={labelStyle}>{t('wizard:ghoul.secondRegnant', 'Second regnant')}</label>
              <input id="ghoul-field-bond2-name" value={bonds[1].name || ''} maxLength={120} onChange={(e) => set(1, { name: e.target.value })} style={inputStyle} />
            </div>
            <div>
              <label htmlFor="ghoul-field-bond2-strength" style={labelStyle}>{t('wizard:ghoul.strength', 'Bond Strength')}</label>
              <StrengthSelect id="ghoul-field-bond2-strength" value={bonds[1].strength} onChange={(v) => set(1, { strength: v })} />
            </div>
          </div>
          <label htmlFor="ghoul-field-bond2-note" style={{ ...labelStyle, marginTop: '10px' }}>{t('wizard:ghoul.bondNote', 'Note on the Bond')}</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input id="ghoul-field-bond2-note" value={bonds[1].note || ''} maxLength={500} onChange={(e) => set(1, { note: e.target.value })} style={inputStyle} />
            <button type="button" aria-label={t('wizard:ghoul.removeSecondBond', 'Remove the second Blood Bond')} onClick={() => setBonds((prev) => prev.slice(0, 1))} style={smallButtonStyle}>
              ×
            </button>
          </div>
        </div>
      ) : two ? (
        <button type="button" onClick={() => setBonds((prev) => [...prev, { name: '', strength: null, note: '' }])} style={{ ...addButtonStyle, marginTop: '12px' }}>
          {t('wizard:ghoul.addSecondBond', '+ Second Blood Bond (Two Masters)')}
        </button>
      ) : (
        <p style={{ ...noteStyle, fontSize: '12px', margin: '10px 0 0' }}>
          {t('wizard:ghoul.oneRegnant', 'One regnant: a Bound thrall resists other Bonds. A second one needs the Two Masters Flaw (Blood-Stained Love p. 151).')}
        </p>
      )}
      <div style={{ ...gridStyle, marginTop: '16px' }}>
        <div>
          <label htmlFor="ghoul-field-last-fed" style={labelStyle}>{t('wizard:ghoul.lastFed', "Last fed on the domitor's Blood")}</label>
          <input
            id="ghoul-field-last-fed"
            value={feeding.last}
            maxLength={60}
            placeholder={t('wizard:ghoul.lastFedPlaceholder', 'e.g. early October')}
            onChange={(e) => setFeeding((prev) => ({ ...prev, last: e.target.value }))}
            style={inputStyle}
          />
        </div>
      </div>
      <label htmlFor="ghoul-field-feeding-note" style={{ ...labelStyle, marginTop: '10px' }}>{t('wizard:ghoul.feedingNote', 'Feeding note: how often, from whom, what it costs')}</label>
      <textarea
        id="ghoul-field-feeding-note"
        value={feeding.note}
        maxLength={500}
        rows={2}
        onChange={(e) => setFeeding((prev) => ({ ...prev, note: e.target.value }))}
        style={{ ...inputStyle, resize: 'vertical' }}
      />
      <p style={{ ...noteStyle, fontSize: '12px', margin: '8px 0 0' }}>
        {t('wizard:ghoul.feedingRule', "A Rouse Check's worth of the domitor's Blood keeps a ghoul for about a month (core p. 234); without it the years catch up fast. A V5 ghoul has no vitae track, Hunger or Blood Potency: this is a note, nothing is counted.")}
      </p>
    </ResponsiveSheetBlock>
  );
}
