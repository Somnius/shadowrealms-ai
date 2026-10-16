import { useState } from 'react';
import { GothicBox } from '../../GothicDecorations';
import { V5_SECTION_IDS } from '../../../characterSheet/v5/constants';
import { useV5Catalog } from '../../../rules/v5Catalog';
import { buildGhoulPayload, isV5Domitor, validateGhoulSheet } from '../../../characterSheet/v5/ghoul';
import { serverProblemErrors, translateSheetErrors } from '../../../characterSheet/i18nErrors';
import { t } from '../../../i18n';
import { Term } from '../../../i18n/glossary';
import { authFetch } from '../../../app/http';
import { ACCENT, ForgeProvider, buttonStyle, primaryButtonStyle, scrollToSection } from '../v5/forgeUi';
import StoryStep from '../v5/StoryStep';
import useGhoulForgeState from './useGhoulForgeState';
import GhoulConceptStep from './GhoulConceptStep';
import GhoulAttributesStep from './GhoulAttributesStep';
import GhoulSkillsStep from './GhoulSkillsStep';
import GhoulPowerStep from './GhoulPowerStep';
import GhoulAdvantagesStep from './GhoulAdvantagesStep';
import GhoulBondStep from './GhoulBondStep';
import GhoulHumanityStep from './GhoulHumanityStep';

const S = V5_SECTION_IDS;
// Labels are functions so t() runs at render time. Game terms stay English.
const SECTION_ORDER = [
  [S.identity, () => t('wizard:ghoul.conceptTitle', 'Concept & domitor')],
  [S.attributes, () => 'Attributes'],
  [S.skills, () => 'Skills'],
  [S.disciplines, () => t('wizard:ghoul.powerTitle', 'Ghoul power')],
  [S.advantages, () => 'Advantages'],
  [S.bond, () => 'Blood Bond'],
  [S.humanity, () => 'Humanity'],
  [S.story, () => t('wizard:section.story', 'Story')],
];

/**
 * The ghoul forge (docs/rules/V5.md §7): a ghoul of one of the user's V5 vampires, with no
 * chronicle of its own. Pure rules: characterSheet/v5/ghoul.js; state: useGhoulForgeState.js; one
 * component per step. `characters`: the user's characters (GET /api/characters/, own rows);
 * `domitorId`: the vampire it starts from (?ghoul_of=); `chronicles`: for the domitor's creation
 * settings (allowed books, Flaw cap).
 */
export default function GhoulForge({ token, characters, chronicles, domitorId, onDone, onCancel, showError, showSuccess }) {
  useV5Catalog(token);
  const domitors = (characters || []).filter(isV5Domitor);
  const [submitting, setSubmitting] = useState(false);
  const f = useGhoulForgeState(chronicles, domitors, domitorId);
  const { derived, fieldErrors } = f;

  if (!domitors.length) {
    return (
      <div style={{ maxWidth: '760px', margin: '0 auto', padding: '20px 16px 60px' }}>
        <GothicBox theme="vampire">
          <div style={{ padding: '8px' }}>
            <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>{t('wizard:ghoul.title', 'Ghoul forge · V5')}</h2>
            <p style={{ color: 'var(--sr-bone-300)' }}>
              {t('wizard:ghoul.noDomitor', 'A ghoul belongs to one of your V5 vampires, and you have none yet. Forge the vampire first.')}
            </p>
            <button type="button" onClick={onCancel} style={buttonStyle}>
              {t('wizard:cancel', 'Cancel')}
            </button>
          </div>
        </GothicBox>
      </div>
    );
  }

  const handleSubmit = async () => {
    const err = translateSheetErrors(validateGhoulSheet(f.sheet, f.domitor, f.settings));
    f.setFieldErrors(err);
    const first = SECTION_ORDER.find(([id]) => err[id]);
    if (first) {
      showError?.(err[first[0]]);
      scrollToSection(first[0]);
      return;
    }
    const payload = buildGhoulPayload(f.sheet, f.domitor);
    if (f.meritNotes.trim()) payload.merits_flaws.notes = f.meritNotes.trim();
    setSubmitting(true);
    try {
      const res = await authFetch('/api/characters/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: f.name.trim(),
          campaign_id: null,
          ...payload,
          background: f.background.trim(),
          sheet_locked: true,
          is_active: true,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        // the server's ghoul check answers with problem codes (backend/services/v5_ghoul_chargen.py)
        const server = serverProblemErrors(body.problems, { name_length: S.skills });
        if (server.messages.length) {
          f.setFieldErrors(server.bySection);
          showError?.(`${t('wizard:problem.refused', 'The server refused the sheet:')} ${server.messages.join(' ')}`);
          const firstBad = SECTION_ORDER.find(([id]) => server.bySection[id]);
          if (firstBad) scrollToSection(firstBad[0]);
          return;
        }
        showError?.(body.error || t('wizard:error.createFailed', 'Could not create character.'));
        return;
      }
      showSuccess?.(t('wizard:ghoul.created', '{{name}} is Bound to {{domitor}}. The sheet is on your Profile.', { name: f.name.trim(), domitor: f.domitor.name }));
      onDone?.(body);
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
            <h2 style={{ fontFamily: 'var(--sr-font-display)', color: ACCENT, marginTop: 0, fontSize: '22px' }}>{t('wizard:ghoul.title', 'Ghoul forge · V5')}</h2>
            <p style={{ color: 'var(--sr-bone-500)', fontSize: '14px', lineHeight: 1.5 }}>
              {t('wizard:ghoul.intro', "A mortal fed on a vampire's Blood. Build them on a corebook mortal template, which is what the domitor's Retainers buy (core pp. 185, 194), or as a player ghoul (Players Guide pp. 140–142). One level-1 power of the domitor's Disciplines; no Hunger, no predator type.")}
            </p>
            {f.settings.house_rules ? (
              <div
                role="note"
                aria-label={t('wizard:v5.houseRules', 'House rules from your Storyteller')}
                style={{ margin: '0 0 12px', padding: '10px 12px', borderLeft: `3px solid ${ACCENT}`, background: 'rgba(0,0,0,0.25)', color: 'var(--sr-bone-100)', fontSize: '13px', whiteSpace: 'pre-wrap' }}
              >
                <strong style={{ color: 'var(--sr-arcane-300)' }}>{t('wizard:v5.houseRules', 'House rules from your Storyteller')}:</strong> {f.settings.house_rules}
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
              {SECTION_ORDER.map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => scrollToSection(id)}
                  style={{
                    fontSize: '11px',
                    padding: '6px 12px',
                    borderRadius: '999px',
                    background: fieldErrors[id] ? 'rgba(248,113,113,0.15)' : 'var(--sr-night-800)',
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
              {f.domitor ? <span style={{ color: ACCENT }}>{t('wizard:ghoul.ghoulOf', 'Ghoul of {{domitor}}', { domitor: f.domitor.name })}</span> : null}
              <span>
                <Term id="health">Health {derived.health}</Term> · <Term id="willpower">Willpower {derived.willpower}</Term>
                {derived.humanity != null ? (
                  <>
                    {' · '}
                    <Term id="humanity">Humanity {derived.humanity}</Term>
                  </>
                ) : null}
                {' · '}
                {t('wizard:ghoul.advantagesShort', 'Advantages {{adv}}/{{max}}', { adv: f.advDots, max: derived.advantage_dots })}
              </span>
            </div>
          </div>

          <div style={{ padding: '8px 16px 24px' }}>
            <GhoulConceptStep />
            <GhoulAttributesStep />
            <GhoulSkillsStep />
            <GhoulPowerStep />
            <GhoulAdvantagesStep />
            <GhoulBondStep />
            <GhoulHumanityStep />
            <StoryStep />

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '24px', justifyContent: 'space-between' }}>
              <button type="button" onClick={onCancel} style={buttonStyle}>
                {t('wizard:cancel', 'Cancel')}
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleSubmit}
                style={{ ...primaryButtonStyle, background: submitting ? 'var(--sr-night-500)' : primaryButtonStyle.background, cursor: submitting ? 'not-allowed' : 'pointer' }}
              >
                {submitting ? t('wizard:submitting', 'Sealing sheet…') : t('wizard:ghoul.submit', 'Create the ghoul')}
              </button>
            </div>
          </div>
        </GothicBox>
      </div>
    </ForgeProvider>
  );
}
