import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { THIN_BLOOD, V5_CLAN_NAMES, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { ageAllowed, clanAllowed } from '../../../characterSheet/v5/validation';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, TextField, gridStyle, inputStyle, labelStyle, noteStyle, useForge } from './forgeUi';

/** Step 2 (core p. 136): clan and sire. Age and generation come later, after the Convictions. */
export default function ClanStep() {
  const f = useForge();
  const { clanRow } = f;
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.clan}
      title={t('wizard:v5.clanTitle', 'Clan & Sire')}
      subtitle={t('wizard:v5.clanSubV2', 'Your clan sets your Disciplines, bane and compulsion.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.clan} />
      <div style={gridStyle}>
        <div>
          <label htmlFor="v5-field-clan" style={labelStyle}><Term id="clan" /></label>
          <select id="v5-field-clan" value={f.clan} onChange={(e) => f.changeClan(e.target.value)} style={inputStyle}>
            {V5_CLAN_NAMES.map((c) => {
              // Thin-bloods are always childer (14th–16th generation), so they need that age allowed.
              const ok = clanAllowed(f.settings, c) && (c !== THIN_BLOOD || ageAllowed(f.settings, 'childer'));
              return (
                <option key={c} value={c} disabled={!ok}>
                  {c}
                  {ok ? '' : ` ${t('wizard:v5.notAllowed', '(not in this chronicle)')}`}
                </option>
              );
            })}
          </select>
        </div>
        <TextField id="v5-field-sire" label="Sire" value={f.sire} onChange={f.setSire} placeholder={t('wizard:v5.optional', 'optional')} />
      </div>
      {clanRow ? (
        <p style={{ ...noteStyle, marginTop: '12px' }}>
          {clanRow.disciplines.length ? (
            <>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Disciplines:</strong> {clanRow.disciplines.join(', ')}.{' '}
            </>
          ) : null}
          {clanRow.bane_summary ? (
            <>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Bane:</strong> {clanRow.bane_summary}.{' '}
            </>
          ) : null}
          {clanRow.compulsion ? (
            <>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Compulsion:</strong> {clanRow.compulsion}.
            </>
          ) : null}
        </p>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
