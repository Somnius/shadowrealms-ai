import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { domitorDisciplines, ghoulPowerOptions } from '../../../characterSheet/v5/ghoul';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, CatalogNote, InlineError, gridStyle, inputStyle, labelStyle, noteStyle, useForge } from '../v5/forgeUi';

/** One level-1 power of a Discipline the domitor has (core p. 234, Players Guide p. 141). */
export default function GhoulPowerStep() {
  const f = useForge();
  const { power, setPower, domitor } = f;
  const discs = domitorDisciplines(domitor);
  const options = power.discipline ? ghoulPowerOptions(domitor, power.discipline) : [];
  const picked = options.find((o) => o.name === power.name) || null;
  const freeText = Boolean(power.discipline) && !options.some((o) => o.entry);
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.disciplines}
      title={t('wizard:ghoul.powerTitle', 'Ghoul power')}
      subtitle={t('wizard:ghoul.powerSub', "A level-1 power of one of your domitor's Disciplines.")}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.disciplines} />
      {!discs.length ? (
        <p style={noteStyle}>{t('wizard:ghoul.powerNoDisciplines', "The domitor's sheet lists no Disciplines: ask your Storyteller which power the Blood brought.")}</p>
      ) : null}
      <div style={gridStyle}>
        <div>
          <label htmlFor="ghoul-field-discipline" style={labelStyle}>
            <Term id="discipline" />
          </label>
          <select
            id="ghoul-field-discipline"
            value={power.discipline}
            onChange={(e) => setPower({ discipline: e.target.value, name: '' })}
            style={inputStyle}
          >
            <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
            {discs.map((d) => (
              <option key={d.name} value={d.name}>
                {d.name} {'●'.repeat(d.level)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ghoul-field-power" style={labelStyle}>{t('wizard:ghoul.power', 'Power (level 1)')}</label>
          {freeText ? (
            <>
              <input
                id="ghoul-field-power"
                list="ghoul-power-list"
                value={power.name}
                maxLength={100}
                onChange={(e) => setPower({ ...power, name: e.target.value })}
                style={inputStyle}
              />
              <datalist id="ghoul-power-list">
                {options.map((o) => (
                  <option key={o.name} value={o.name} />
                ))}
              </datalist>
            </>
          ) : (
            <select
              id="ghoul-field-power"
              value={power.name}
              disabled={!power.discipline}
              onChange={(e) => setPower({ ...power, name: e.target.value })}
              style={inputStyle}
            >
              <option value="">{t('wizard:v5.choose', 'Choose…')}</option>
              {options.map((o) => (
                <option key={o.name} value={o.name}>
                  {o.name}{' '}
                  {o.domitorHas
                    ? t('wizard:ghoul.domitorHasIt', '(your domitor has it)')
                    : t('wizard:ghoul.domitorLacksIt', "(the domitor doesn't have it: Storyteller's call, core p. 234)")}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
      <CatalogNote entry={picked?.entry} />
      <p style={{ ...noteStyle, fontSize: '12px', margin: '10px 0 0' }}>
        {t('wizard:ghoul.powerNote', 'It counts as one dot in {{discipline}} (Players Guide p. 141). No Rouse Checks: a power above level 1 costs 1 Aggravated instead (core p. 234). More level-1 powers of the domitor\'s Disciplines cost 10 XP each later.', {
          discipline: power.discipline || t('wizard:ghoul.theDiscipline', 'the Discipline'),
        })}
      </p>
    </ResponsiveSheetBlock>
  );
}
