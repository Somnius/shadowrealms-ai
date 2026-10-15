import { useEffect, useRef, useState } from 'react';
import { GothicBox } from '../GothicDecorations';
import { settingsForCampaign } from '../../characterSheet/v5/creationSettings';
import { editionLabel } from '../../rules/rulesEdition';
import { loadV5Catalog } from '../../rules/v5Catalog';
import { t } from '../../i18n';
import V5CharacterCreationWizard from './V5CharacterCreationWizard';
import GuidedWizard from './v5/GuidedWizard';
import { ACCENT, buttonStyle, inputStyle, labelStyle, noteStyle } from './v5/forgeUi';

const modeButtonStyle = {
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
  textAlign: 'left',
  padding: '14px 16px',
  borderRadius: '10px',
  border: '1px solid var(--sr-night-600)',
  background: 'var(--sr-night-850)',
  color: 'var(--sr-bone-100)',
  cursor: 'pointer',
};

function ModeButton({ id, title, help, onClick }) {
  return (
    <button type="button" onClick={onClick} aria-labelledby={`${id}-title`} aria-describedby={`${id}-help`} style={modeButtonStyle}>
      <span id={`${id}-title`} style={{ fontFamily: 'var(--sr-font-display)', fontSize: '17px', color: ACCENT }}>
        {title}
      </span>
      <span id={`${id}-help`} style={{ ...noteStyle, fontSize: '13px' }}>
        {help}
      </span>
    </button>
  );
}

function ModeChoice({ campaigns, campaignId, onCampaignChange, onGuided, onForge, onCancel, autoFocus }) {
  const introRef = useRef(null);
  useEffect(() => {
    if (autoFocus) introRef.current?.focus();
  }, [autoFocus]);
  return (
    <>
      <p ref={introRef} tabIndex={-1} style={{ color: 'var(--sr-bone-100)', fontSize: '15px', outline: 'none' }}>
        {t('wizard:guided.chooseIntro', 'How do you want to start?')}
      </p>
      <label htmlFor="v5-entry-chronicle" style={labelStyle}>
        {t('wizard:field.chronicle', 'Chronicle')}
      </label>
      <select id="v5-entry-chronicle" value={campaignId} onChange={(e) => onCampaignChange(e.target.value)} style={{ ...inputStyle, marginBottom: '16px' }}>
        {campaigns.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name} — {c.game_system}
            {String(c.game_system || '').toLowerCase() === 'vampire' ? ` (${editionLabel(c)})` : ''}
          </option>
        ))}
      </select>
      <div style={{ display: 'grid', gap: '12px', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
        <ModeButton
          id="v5-mode-guided"
          title={t('wizard:guided.modeGuided', 'Guided')}
          help={t(
            'wizard:guided.modeGuidedHelp',
            'A few questions about who your character is. The guide suggests a clan and a predator type and fills in Attributes and Skills; you finish the sheet in the forge.'
          )}
          onClick={onGuided}
        />
        <ModeButton
          id="v5-mode-forge"
          title={t('wizard:guided.modeForge', 'Full forge')}
          help={t('wizard:guided.modeForgeHelp', 'Build the character yourself, step by step in the corebook’s order.')}
          onClick={onForge}
        />
      </div>
      <div style={{ marginTop: '20px' }}>
        <button type="button" onClick={onCancel} style={buttonStyle}>
          {t('wizard:cancel', 'Cancel')}
        </button>
      </div>
    </>
  );
}

/**
 * Entry of the V5 forge (Forge v2 part E): Guided (scenario questions that suggest a clan and a
 * predator type, v5/GuidedWizard.jsx) or the full forge. The guide's suggestion opens the forge
 * prefilled (useV5ForgeState `initial`) with a banner saying so. Same props as the forge.
 */
export default function V5ForgeEntry(props) {
  const { token, campaigns, campaignId, onCampaignChange, onCancel } = props;
  // Fetch the catalog early; the guide waits for it (useV5Guided) and the forge re-renders with it.
  useEffect(() => {
    loadV5Catalog(token);
  }, [token]);
  const [mode, setMode] = useState('choose'); // choose | guided | forge
  const [suggestion, setSuggestion] = useState(null); // { initial, clan, predator }
  const [returned, setReturned] = useState(false);
  const settings = settingsForCampaign(campaigns, campaignId);

  if (mode === 'forge') {
    return (
      <V5CharacterCreationWizard
        {...props}
        initial={suggestion?.initial}
        guided={suggestion ? { clan: suggestion.clan, predator: suggestion.predator } : null}
        autoFocus
      />
    );
  }

  const openForge = (next) => {
    setSuggestion(next);
    setMode('forge');
  };
  return (
    <div style={{ maxWidth: '760px', margin: '0 auto', padding: '20px 16px 60px' }}>
      <GothicBox theme="vampire">
        <div style={{ padding: '8px 16px 20px' }}>
          <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>
            {mode === 'guided' ? t('wizard:guided.title', 'Guided creation · V5') : t('wizard:v5.title', 'Character sheet forge · V5')}
          </h2>
          {mode === 'guided' ? (
            <GuidedWizard
              token={token}
              settings={settings}
              onBack={() => {
                setReturned(true);
                setMode('choose');
              }}
              onFullForge={() => openForge(null)}
              onBuild={(initial, result) => openForge({ initial, clan: result.clan, predator: result.predator })}
            />
          ) : (
            <ModeChoice
              campaigns={campaigns}
              campaignId={campaignId}
              onCampaignChange={onCampaignChange}
              onGuided={() => setMode('guided')}
              onForge={() => openForge(null)}
              onCancel={onCancel}
              autoFocus={returned}
            />
          )}
        </div>
      </GothicBox>
    </div>
  );
}
