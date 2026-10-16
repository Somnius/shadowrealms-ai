import ResponsiveSheetBlock from '../ResponsiveSheetBlock';
import { editionLabel } from '../../../rules/rulesEdition';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { t } from '../../../i18n';
import { GenderField } from '../../../features/voice/VoiceGender';
import { ACCENT, InlineError, TextField, gridStyle, inputStyle, labelStyle, useForge } from './forgeUi';

/** Step 1 (core p. 136): chronicle and core concept. */
export default function ConceptStep({ campaigns, campaignId, onCampaignChange }) {
  const f = useForge();
  return (
    <ResponsiveSheetBlock
      sectionId={V5_SECTION_IDS.identity}
      title={t('wizard:v5.conceptTitle', 'Concept')}
      subtitle={t('wizard:v5.identitySub', 'Chronicle and concept')}
      accent={ACCENT}
    >
      <InlineError id={V5_SECTION_IDS.identity} />
      <label htmlFor="v5-field-chronicle" style={labelStyle}>{t('wizard:field.chronicle', 'Chronicle')}</label>
      <select
        id="v5-field-chronicle"
        value={campaignId}
        onChange={(e) => onCampaignChange(e.target.value)}
        style={{ ...inputStyle, marginBottom: '16px' }}
      >
        {campaigns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} — {c.game_system}
            {String(c.game_system || '').toLowerCase() === 'vampire' ? ` (${editionLabel(c)})` : ''}
          </option>
        ))}
      </select>
      <div style={gridStyle}>
        <TextField id="v5-field-character_name" label={t('wizard:field.name', 'Character name')} value={f.name} onChange={f.setName} />
        <TextField
          id="v5-field-concept"
          label={t('wizard:field.concept', 'Concept')}
          value={f.concept}
          onChange={f.setConcept}
          placeholder={t('wizard:v5.conceptPlaceholder', 'e.g. burned-out paramedic')}
        />
        <TextField
          id="v5-field-ambition"
          label="Ambition"
          value={f.ambition}
          onChange={f.setAmbition}
          placeholder={t('wizard:v5.ambitionPlaceholder', 'long-term goal')}
        />
        <TextField
          id="v5-field-desire"
          label="Desire"
          value={f.desire}
          onChange={f.setDesire}
          placeholder={t('wizard:v5.desirePlaceholder', 'this session')}
        />
        <GenderField id="v5-field-gender" value={f.gender} onChange={f.setGender} />
      </div>
    </ResponsiveSheetBlock>
  );
}
