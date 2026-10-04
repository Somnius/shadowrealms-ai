import React from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useToast } from '../../design';
import CharacterCreationWizard from '../../components/CharacterCreationWizard';
import { PageBody, TopBar } from '../../app/AppShell';
import { useAuth } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { t } from '../../i18n';
import './profile.css';

/** Phase 1 character creation wizard inside the shell, with a short prep guide. */
export default function CharacterCreatePage() {
  const navigate = useNavigate();
  const { token, refreshUser } = useAuth();
  const { chronicles, reload } = useChronicles();
  const { toast } = useToast();
  const [params] = useSearchParams();
  const chronicleId = params.get('chronicle');
  return (
    <>
      <TopBar title={t('profile:create.title', 'New character')} icon="quill" />
      <PageBody className="sr-page--legacy">
        <details className="sr-guide">
          <summary>{t('profile:create.guide', 'Before you forge a character')}</summary>
          <ol className="sr-prose">
            <li>{t('profile:create.step1', 'Join or create the chronicle first; the wizard asks which chronicle the character belongs to.')}</li>
            <li>{t('profile:create.step2', 'Have a concept, background, description, ties and gear ready; the Storyteller hooks plots into them.')}</li>
            <li>{t('profile:create.step3', 'Follow the Storyteller’s limits on starting dots and powers.')}</li>
            <li>{t('profile:create.step4', 'The sheet locks when you finish. Later changes go through a downtime request.')}</li>
          </ol>
        </details>
        <CharacterCreationWizard
          token={token}
          campaigns={chronicles}
          initialCampaignId={chronicleId}
          onCancel={() => navigate(chronicleId ? `/c/${chronicleId}` : '/profile/characters')}
          onDone={async (body, campaignId) => {
            await refreshUser();
            await reload();
            // Straight into the chronicle the character belongs to (that is where you play it).
            const cid = (body && body.character && body.character.campaign_id) || campaignId;
            navigate(cid ? `/c/${cid}` : '/profile/characters');
          }}
          showError={(msg) => toast({ tone: 'danger', title: String(msg) })}
          showSuccess={(msg) => toast({ tone: 'ok', title: String(msg) })}
        />
      </PageBody>
    </>
  );
}
