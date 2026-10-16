import { useEffect, useRef, useState } from 'react';
import { GothicBox } from '../GothicDecorations';
import { THIN_BLOOD, V5_SECTION_IDS } from '../../characterSheet/v5/constants';
import { useV5Catalog } from '../../rules/v5Catalog';
import { buildV5Payload, validateV5Sheet } from '../../characterSheet/v5/validation';
import { settingsForCampaign } from '../../characterSheet/v5/creationSettings';
import { serverProblemErrors, translateSheetErrors } from '../../characterSheet/i18nErrors';
import { t } from '../../i18n';
import { Term } from '../../i18n/glossary';
import { authFetch } from '../../app/http';
import { ACCENT, ForgeProvider, scrollToSection } from './v5/forgeUi';
import useV5ForgeState from './v5/useV5ForgeState';
import ConceptStep from './v5/ConceptStep';
import ClanStep from './v5/ClanStep';
import AttributesStep from './v5/AttributesStep';
import SkillsStep from './v5/SkillsStep';
import DisciplinesStep from './v5/DisciplinesStep';
import PredatorStep from './v5/PredatorStep';
import AdvantagesStep from './v5/AdvantagesStep';
import ConvictionsStep from './v5/ConvictionsStep';
import AgeStep from './v5/AgeStep';
import ExperienceStep from './v5/ExperienceStep';
import StoryStep from './v5/StoryStep';

const API_URL = '/api';

/** The banner over a forge the guide filled in: what it set and what is still to pick. */
function guidedBanner({ clan, predator }) {
  if (!predator) {
    return t(
      'wizard:guided.bannerNoPredator',
      'Suggested by the guide: {{clan}}. Clan, Attributes and Skills are filled in. No predator type stood out, so pick one in the Predator step. Change anything you like.',
      { clan }
    );
  }
  if (clan === THIN_BLOOD) {
    return t(
      'wizard:guided.bannerThinBlood',
      'Suggested by the guide: {{clan}} · {{predator}}. Clan, predator type, Attributes and Skills are filled in. In the Predator step you still pick its specialty. Change anything you like.',
      { clan, predator }
    );
  }
  return t(
    'wizard:guided.bannerPredator',
    'Suggested by the guide: {{clan}} · {{predator}}. Clan, predator type, Attributes and Skills are filled in. In the Predator step you still pick its specialty and Discipline dot. Change anything you like.',
    { clan, predator }
  );
}

// The corebook's order (p. 136): concept, clan and sire, Attributes, Skills, Disciplines,
// predator type, Advantages, Convictions and Touchstones, then age and generation.
// Labels are functions so t() runs at render time. Game terms stay English.
const SECTION_ORDER = [
  [V5_SECTION_IDS.identity, () => t('wizard:v5.conceptTitle', 'Concept')],
  [V5_SECTION_IDS.clan, () => 'Clan'],
  [V5_SECTION_IDS.attributes, () => 'Attributes'],
  [V5_SECTION_IDS.skills, () => 'Skills'],
  [V5_SECTION_IDS.disciplines, () => 'Disciplines'],
  [V5_SECTION_IDS.predator, () => 'Predator'],
  [V5_SECTION_IDS.advantages, () => 'Advantages'],
  [V5_SECTION_IDS.humanity, () => 'Convictions'],
  [V5_SECTION_IDS.age, () => t('wizard:v5.age', 'Age')],
  [V5_SECTION_IDS.experience, () => 'XP'],
  [V5_SECTION_IDS.story, () => t('wizard:section.story', 'Story')],
];

/**
 * V5 character forge (docs/rules/V5.md §4). Pure rules live in characterSheet/v5/validation.js,
 * the state in v5/useV5ForgeState.js, one component per step in v5/. Reached through
 * V5ForgeEntry.jsx (Guided or full forge): `initial` is the guide's prefill, `guided` its
 * {clan, predator} for the banner, `autoFocus` puts the focus on the title when the forge opens.
 */
export default function V5CharacterCreationWizard({
  token,
  campaigns,
  campaignId,
  onCampaignChange,
  onDone,
  onCancel,
  showError,
  showSuccess,
  initial,
  guided,
  autoFocus,
}) {
  useV5Catalog(token);
  const settings = settingsForCampaign(campaigns, campaignId);
  const f = useV5ForgeState(settings, initial);
  const [submitting, setSubmitting] = useState(false);
  const { sheet, derived, fieldErrors } = f;
  const titleRef = useRef(null);
  useEffect(() => {
    if (autoFocus) titleRef.current?.focus();
  }, [autoFocus]);

  const handleSubmit = async () => {
    const err = translateSheetErrors(validateV5Sheet(sheet, undefined, settings));
    if (!campaignId) err[V5_SECTION_IDS.identity] = t('wizard:error.chronicle', 'Choose a chronicle.');
    f.setFieldErrors(err);
    const first = SECTION_ORDER.find(([id]) => err[id]);
    if (first) {
      showError?.(err[first[0]]);
      scrollToSection(first[0]);
      return;
    }
    const payload = buildV5Payload(sheet, settings);
    if (f.meritNotes.trim()) payload.merits_flaws.notes = f.meritNotes.trim();
    setSubmitting(true);
    try {
      const res = await authFetch(`${API_URL}/characters/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: f.name.trim(),
          campaign_id: parseInt(campaignId, 10),
          ...payload,
          background: f.background.trim(),
          gender: f.gender || null,
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // The server's creation check answers with problem codes (backend/services/v5_chargen.py).
        const server = serverProblemErrors(body.problems);
        if (server.messages.length) {
          f.setFieldErrors(server.bySection);
          showError?.(`${t('wizard:problem.refused', 'The server refused the sheet:')} ${server.messages.join(' ')}`);
          const first = SECTION_ORDER.find(([id]) => server.bySection[id]);
          if (first) scrollToSection(first[0]);
          return;
        }
        showError?.(body.error || t('wizard:error.createFailed', 'Could not create character.'));
        return;
      }
      showSuccess?.(t('wizard:v5.created', 'Character embraced. Here is the chronicle: you can play right away.'));
      onDone?.(body, parseInt(campaignId, 10));
    } catch {
      showError?.(t('wizard:error.network', 'Network error while creating character.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ForgeProvider value={f}>
      <div style={{ maxWidth: '1040px', margin: '0 auto', padding: '20px 16px 60px' }}>
        <GothicBox theme="vampire">
          <div style={{ padding: '8px 8px 0' }}>
            <h2 ref={titleRef} tabIndex={-1} style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px', outline: 'none' }}>
              {t('wizard:v5.title', 'Character sheet forge · V5')}
            </h2>
            {guided ? (
              <div
                role="note"
                aria-label={t('wizard:guided.bannerLabel', 'Suggested by the guide')}
                style={{ margin: '0 0 12px', padding: '10px 12px', borderLeft: '3px solid var(--sr-gold-400)', background: 'rgba(0,0,0,0.25)', color: 'var(--sr-bone-100)', fontSize: '13px' }}
              >
                {guidedBanner(guided)}
              </div>
            ) : null}
            <p style={{ color: 'var(--sr-bone-500)', fontSize: '14px', lineHeight: 1.5 }}>
              {t('wizard:v5.introV2', 'Vampire: The Masquerade 5th Edition creation, in the corebook\'s order: concept, clan, a fixed attribute spread, a skill distribution, 2 + 1 Discipline dots, a predator type, 7 Advantage dots and 2 Flaw dots of your own, Convictions, then age. No freebie points in V5.')}
            </p>
            {settings.house_rules ? (
              <div
                role="note"
                aria-label={t('wizard:v5.houseRules', 'House rules from your Storyteller')}
                style={{ margin: '0 0 12px', padding: '10px 12px', borderLeft: `3px solid ${ACCENT}`, background: 'rgba(0,0,0,0.25)', color: 'var(--sr-bone-100)', fontSize: '13px', whiteSpace: 'pre-wrap' }}
              >
                <strong style={{ color: 'var(--sr-arcane-300)' }}>{t('wizard:v5.houseRules', 'House rules from your Storyteller')}:</strong>{' '}
                {settings.house_rules}
              </div>
            ) : null}
          </div>

          <div
            style={{
              position: 'sticky',
              top: 0,
              zIndex: 20,
              padding: '12px 16px',
              margin: '0 -4px 8px',
              background: 'linear-gradient(180deg, rgba(15,23,41,0.98) 70%, transparent)',
              borderBottom: '1px solid var(--sr-night-700)',
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {SECTION_ORDER.filter(([id]) => id !== V5_SECTION_IDS.experience || f.xpTotal > 0).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => scrollToSection(id)}
                  style={{
                    fontSize: '11px',
                    padding: '6px 12px',
                    borderRadius: '999px',
                    background: fieldErrors[id] ? 'rgba(248,113,113,0.15)' : 'var(--sr-night-800)',
                    // blood-400 on night-800 passes 4.5:1 at 11px (blood-500 was 4.15:1)
                    color: fieldErrors[id] ? 'var(--sr-blood-300)' : 'var(--sr-blood-400)',
                    border: `1px solid ${fieldErrors[id] ? 'var(--sr-blood-700)' : 'var(--sr-night-600)'}`,
                    cursor: 'pointer',
                    fontFamily: 'var(--sr-font-display)',
                  }}
                >
                  {label()}
                </button>
              ))}
            </div>
            <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '12px', fontSize: '12px', color: 'var(--sr-bone-300)' }}>
              <span>
                <strong style={{ color: 'var(--sr-bone-100)' }}>{f.name || '—'}</strong>
                {f.concept ? ` · ${f.concept}` : ''}
              </span>
              <span style={{ color: ACCENT }}>{f.clan}</span>
              <span>
                <Term id="health">Health {derived.health}</Term> · <Term id="willpower">Willpower {derived.willpower}</Term> ·{' '}
                <Term id="humanity">Humanity {derived.humanity}</Term> · <Term id="bloodPotency">BP {derived.blood_potency}</Term> ·{' '}
                <Term id="hunger">Hunger {derived.hunger}</Term>
              </span>
            </div>
          </div>

          <div style={{ padding: '8px 16px 24px' }}>
            <ConceptStep campaigns={campaigns} campaignId={campaignId} onCampaignChange={onCampaignChange} />
            <ClanStep />
            <AttributesStep />
            <SkillsStep />
            <DisciplinesStep />
            <PredatorStep />
            <AdvantagesStep />
            <ConvictionsStep />
            <AgeStep />
            <ExperienceStep />
            <StoryStep />

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '24px', justifyContent: 'space-between' }}>
              <button
                type="button"
                onClick={onCancel}
                style={{ padding: '10px 18px', background: 'var(--sr-night-800)', color: 'var(--sr-bone-100)', border: '1px solid var(--sr-night-600)', borderRadius: '8px', cursor: 'pointer' }}
              >
                {t('wizard:cancel', 'Cancel')}
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmit}
                style={{
                  padding: '10px 22px',
                  background: submitting ? 'var(--sr-night-500)' : 'var(--sr-arcane-500)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  fontFamily: 'var(--sr-font-display)',
                }}
              >
                {submitting ? t('wizard:submitting', 'Sealing sheet…') : t('wizard:submit', 'Create character')}
              </button>
            </div>
          </div>
        </GothicBox>
      </div>
    </ForgeProvider>
  );
}
