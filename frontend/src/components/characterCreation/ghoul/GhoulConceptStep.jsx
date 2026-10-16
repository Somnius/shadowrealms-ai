import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { GHOUL_TEMPLATES, GHOUL_TEMPLATE_KEYS } from '../../../characterSheet/v5/ghoul';
import { ghoulTemplateName } from '../../../characterSheet/i18nErrors';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { ACCENT, InlineError, TextField, gridStyle, inputStyle, labelStyle, noteStyle, useForge } from '../v5/forgeUi';

const dots = (n) => '•'.repeat(Math.max(0, Number(n) || 0));
// the dropdown's order: what Retainers ••• / •• / • buy, then the Deadly mortal and the player ghoul
const ORDER = ['gifted', 'average', 'weak', 'deadly', 'player'].filter((k) => GHOUL_TEMPLATE_KEYS.includes(k));

/** "Gifted mortal — Retainers ••• (core pp. 185, 194)". */
export function templateOption(key) {
  const tpl = GHOUL_TEMPLATES[key];
  if (!tpl) return t('wizard:ghoul.templatePlayer', '{{name}} — Players Guide pp. 140–142', { name: ghoulTemplateName(key) });
  if (tpl.retainer_dots == null) return t('wizard:ghoul.templateNoRetainers', '{{name}} — no Retainers rating buys it (core p. 185)', { name: ghoulTemplateName(key) });
  return t('wizard:ghoul.templateRetainers', '{{name}} — Retainers {{dots}} (core pp. 185, 194)', { name: ghoulTemplateName(key), dots: dots(tpl.retainer_dots) });
}

/** The domitor's sheet rows that are Retainers (a hint of what it pays for). */
function retainerRows(domitor) {
  const rows = Array.isArray(domitor?.wod_meta?.advantages) ? domitor.wod_meta.advantages : [];
  return rows.filter((r) => r && (r.id === 'background:retainers' || /^retainers?\b/i.test(String(r.name || ''))));
}

/** Concept, domitor and template (core p. 185, Players Guide p. 140). */
export default function GhoulConceptStep() {
  const f = useForge();
  const { domitor } = f;
  const paid = retainerRows(domitor);
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.identity}
      title={t('wizard:ghoul.conceptTitle', 'Concept & domitor')}
      subtitle={t('wizard:ghoul.conceptSub', 'Whose ghoul, built on which template.')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.identity} />
      <label htmlFor="ghoul-field-domitor" style={labelStyle}>
        <Term id="domitor" />
      </label>
      <select
        id="ghoul-field-domitor"
        value={f.domitorId}
        onChange={(e) => f.setDomitorId(e.target.value)}
        style={{ ...inputStyle, marginBottom: '6px' }}
      >
        {f.domitors.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
            {d.wod_meta?.clan ? ` — ${d.wod_meta.clan}` : ''}
            {' · '}
            {d.campaign_name || t('wizard:ghoul.noChronicle', 'no chronicle')}
          </option>
        ))}
      </select>
      <p style={{ ...noteStyle, fontSize: '12px', margin: '0 0 14px' }}>
        {t('wizard:ghoul.domitorNote', 'A ghoul has no chronicle of its own: it goes where its domitor goes. Their Storyteller sees its sheet.')}
      </p>
      <div style={gridStyle}>
        <TextField id="ghoul-field-name" label={t('wizard:field.name', 'Character name')} value={f.name} onChange={f.setName} />
        <TextField
          id="ghoul-field-concept"
          label={t('wizard:field.concept', 'Concept')}
          value={f.concept}
          onChange={f.setConcept}
          placeholder={t('wizard:ghoul.conceptPlaceholder', 'e.g. a disgraced producer who runs the channel')}
        />
        <TextField id="ghoul-field-ambition" label="Ambition" value={f.ambition} onChange={f.setAmbition} placeholder={t('wizard:v5.ambitionPlaceholder', 'long-term goal')} />
        <TextField id="ghoul-field-desire" label="Desire" value={f.desire} onChange={f.setDesire} placeholder={t('wizard:v5.desirePlaceholder', 'this session')} />
      </div>
      <div style={{ ...gridStyle, marginTop: '14px' }}>
        <div>
          <label htmlFor="ghoul-field-template" style={labelStyle}>{t('wizard:ghoul.template', 'Template')}</label>
          <select id="ghoul-field-template" value={f.template} onChange={(e) => f.setTemplate(e.target.value)} style={inputStyle}>
            {ORDER.map((k) => (
              <option key={k} value={k}>
                {templateOption(k)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ghoul-field-retainers" style={labelStyle}>{t('wizard:ghoul.retainerDots', 'Retainers dots the domitor pays')}</label>
          <select
            id="ghoul-field-retainers"
            value={f.retainerDots == null ? '' : String(f.retainerDots)}
            onChange={(e) => f.setRetainerDots(e.target.value === '' ? null : Number(e.target.value))}
            style={inputStyle}
          >
            <option value="">{t('wizard:ghoul.retainerNone', 'none (not a Retainers Background)')}</option>
            {[1, 2, 3].map((n) => (
              <option key={n} value={n}>
                {dots(n)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {paid.length ? (
        <p id="ghoul-domitor-retainers" style={{ ...noteStyle, fontSize: '12px', margin: '8px 0 0' }}>
          {t('wizard:ghoul.domitorRetainers', "{{domitor}}'s sheet lists: {{rows}}.", {
            domitor: domitor.name,
            rows: paid.map((r) => `${r.name} ${dots(r.dots)}`).join('; '),
          })}
        </p>
      ) : null}
      {f.template === 'average' && f.retainerDots === 2 ? (
        <p style={{ ...noteStyle, fontSize: '12px', margin: '8px 0 0' }}>
          {t('wizard:ghoul.noAdvantagesHint', 'Retainers •• buys a ghoul built with no Advantages (core p. 194): Flaws only.')}
        </p>
      ) : null}
      <div style={{ ...gridStyle, marginTop: '14px' }}>
        <div>
          <label htmlFor="ghoul-field-age" style={labelStyle}>{t('wizard:ghoul.age', 'Age')}</label>
          <input id="ghoul-field-age" type="number" min={0} max={150} value={f.age} onChange={(e) => f.setAge(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label htmlFor="ghoul-field-apparent" style={labelStyle}>{t('wizard:ghoul.apparentAge', 'Looks (apparent age)')}</label>
          <input id="ghoul-field-apparent" type="number" min={0} max={150} value={f.apparentAge} onChange={(e) => f.setApparentAge(e.target.value)} style={inputStyle} />
        </div>
        <div>
          <label htmlFor="ghoul-field-since" style={labelStyle}>{t('wizard:ghoul.since', 'Ghoul since')}</label>
          <input
            id="ghoul-field-since"
            value={f.ghouledSince}
            maxLength={200}
            placeholder={t('wizard:ghoul.sincePlaceholder', 'e.g. two years ago, before the move')}
            onChange={(e) => f.setGhouledSince(e.target.value)}
            style={inputStyle}
          />
        </div>
      </div>
      <p style={{ ...noteStyle, fontSize: '12px', margin: '8px 0 0' }}>
        {t('wizard:ghoul.ageNote', "The domitor's Blood halts aging, sometimes turns it back a few years (core p. 234).")}
      </p>
    </ResponsiveSheetBlock>
  );
}
