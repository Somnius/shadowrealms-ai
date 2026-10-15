import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import MeritFlawRows from '../MeritFlawRows';
import { THIN_BLOOD, V5_AGE_BRACKETS, V5_SECTION_IDS, V5_THIN_BLOOD_MERITS } from '../../../characterSheet/v5/constants';
import { ageAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { ACCENT, InlineError, addButtonStyle, inputStyle, labelStyle, smallButtonStyle, useForge } from './forgeUi';

/** Free-text rows for thin-blood Merits or Flaws (names only, no dots). */
function ThinRows({ kind, rows, setRows }) {
  const [, hi] = V5_THIN_BLOOD_MERITS;
  return (
    <div style={{ flex: '1 1 240px', minWidth: 0 }}>
      <div id={`v5-thin-${kind}-label`} style={labelStyle}>
        Thin-blood {kind} ({rows.filter((r) => String(r.name || '').trim()).length})
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: 'flex', gap: '8px', marginBottom: '6px' }}>
          <input
            value={r.name}
            aria-label={`Thin-blood ${kind.replace(/s$/, '')} ${i + 1}`}
            placeholder={kind === 'Merits' ? t('wizard:v5.thinMeritPlaceholder', 'e.g. Day Drinker') : t('wizard:v5.thinFlawPlaceholder', 'e.g. Baby Teeth')}
            onChange={(e) => setRows((prev) => prev.map((x, j) => (j === i ? { name: e.target.value } : x)))}
            style={{ ...inputStyle, flex: '1 1 auto', width: 'auto', padding: '8px' }}
          />
          {rows.length > 1 ? (
            <button
              type="button"
              aria-label={t('wizard:v5.removeThin', 'Remove thin-blood {{kind}} {{n}}', { kind: kind.replace(/s$/, ''), n: i + 1 })}
              onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
              style={smallButtonStyle}
            >
              ×
            </button>
          ) : null}
        </div>
      ))}
      {rows.length < hi ? (
        <button type="button" onClick={() => setRows((prev) => [...prev, { name: '' }])} style={addButtonStyle}>
          {kind === 'Merits' ? t('wizard:v5.addMerit', '+ Add Merit') : t('wizard:v5.addFlaw', '+ Add Flaw')}
        </button>
      ) : null}
    </div>
  );
}

/** Step 7 (core p. 136): 7 dots of Advantages and 2 dots of Flaws of your own. */
export default function AdvantagesStep() {
  const f = useForge();
  const { derived, advDots, flawDots, settings } = f;
  const cap = settings.flaws_max_dots;
  const over = advDots > derived.advantage_dots || flawDots < derived.flaw_min_dots || (cap != null && flawDots > cap);
  const ancilla = V5_AGE_BRACKETS.ancilla;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.advantages}
      title="Advantages & Flaws"
      subtitle={t('wizard:v5.advantagesSubV2', 'Up to {{adv}} dots of Merits and Backgrounds (+ for advantages), at least {{flaws}} dots of Flaws of your own (− for flaws). The predator type\'s advantages and Flaws are extra, on top of these.', { adv: derived.advantage_dots, flaws: derived.flaw_min_dots })}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.advantages} />
      <p id="v5-advantages-count" style={{ color: over ? 'var(--sr-blood-300)' : 'var(--sr-ok-400)', fontSize: '12px', margin: '0 0 6px' }}>
        {t('wizard:v5.advantagesCount', 'Advantages {{adv}}/{{advMax}} · Flaws {{flaws}} (min {{flawMin}})', { adv: advDots, advMax: derived.advantage_dots, flaws: flawDots, flawMin: derived.flaw_min_dots })}
        {cap != null ? ` · ${t('wizard:v5.flawCap', 'max {{n}} in this chronicle', { n: cap })}` : ''}
      </p>
      {f.age !== 'ancilla' && f.clan !== THIN_BLOOD && ageAllowed(settings, 'ancilla') ? (
        <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '0 0 10px' }}>
          {t('wizard:v5.ancillaBudgetHint', 'An ancilla (chosen in the Age step) gets {{adv}} more Advantage dots and takes {{flaws}} more Flaw dots.', { adv: ancilla.advantage_dots_bonus, flaws: ancilla.flaw_dots_bonus })}
        </p>
      ) : null}
      <MeritFlawRows rows={f.meritRows} setRows={f.setMeritRows} globalNotes={f.meritNotes} setGlobalNotes={f.setMeritNotes} />
      {f.clan === THIN_BLOOD ? (
        <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--sr-night-700)' }}>
          <p style={{ color: 'var(--sr-bone-300)', fontSize: '12px', margin: '0 0 10px', lineHeight: 1.5 }}>
            {t('wizard:v5.thinHelp', "Thin-bloods also take {{lo}}–{{hi}} thin-blood Merits and the same number of thin-blood Flaws (core p. 182). They have no dot value and don't count toward the totals above. The rules file has no list of them, so write the names from the book.", { lo: V5_THIN_BLOOD_MERITS[0], hi: V5_THIN_BLOOD_MERITS[1] })}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            <ThinRows kind="Merits" rows={f.thinBloodMerits} setRows={f.setThinBloodMerits} />
            <ThinRows kind="Flaws" rows={f.thinBloodFlaws} setRows={f.setThinBloodFlaws} />
          </div>
        </div>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
