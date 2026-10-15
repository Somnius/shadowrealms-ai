import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { THIN_BLOOD, V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { clanNames, descIn } from '../../../characterSheet/v5/rulesData';
import { ageAllowed, clanAllowed, clanInBooks } from '../../../characterSheet/v5/validation';
import { getLanguage, t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, CatalogNote, InlineError, TextField, gridStyle, inputStyle, labelStyle, noteStyle, useForge } from './forgeUi';

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
            {/* Clans from books the chronicle doesn't use aren't offered; one already chosen stays, marked. */}
            {clanNames().filter((c) => c === f.clan || clanInBooks(f.settings, c)).map((c) => {
              // Thin-bloods are always childer (14th–16th generation), so they need that age allowed.
              const ok =
                clanAllowed(f.settings, c) && clanInBooks(f.settings, c) && (c !== THIN_BLOOD || ageAllowed(f.settings, 'childer'));
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
        <div style={{ ...noteStyle, marginTop: '12px' }}>
          <CatalogNote entry={clanRow} style={{ fontSize: '13px', margin: '0 0 6px' }} />
          {clanRow.disciplines.length ? (
            <div>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Disciplines:</strong> {clanRow.disciplines.join(', ')}.
            </div>
          ) : null}
          {clanRow.bane ? (
            <div>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Bane:</strong> {clanRow.bane}
              {clanRow.bane_desc ? ` · ${descIn(clanRow.bane_desc, getLanguage())}` : ''}
            </div>
          ) : null}
          {clanRow.compulsion ? (
            <div>
              <strong style={{ color: 'var(--sr-arcane-300)' }}>Compulsion:</strong> {clanRow.compulsion}
              {clanRow.compulsion_desc ? ` · ${descIn(clanRow.compulsion_desc, getLanguage())}` : ''}
            </div>
          ) : null}
        </div>
      ) : null}
    </ResponsiveSheetBlock>
  );
}
