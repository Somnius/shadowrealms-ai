import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Button, useToast } from '../../design';
import CharacterCreationWizard from '../../components/CharacterCreationWizard';
import GhoulForge from '../../components/characterCreation/ghoul/GhoulForge';
import ClassicGhoulForge from '../../components/characterCreation/classicGhoul/ClassicGhoulForge';
import { canBeDomitor } from '../../characterSheet/v5/ghoul';
import { editionOf, V5 } from '../../rules/rulesEdition';
import { PageBody, TopBar } from '../../app/AppShell';
import { useApi, useAuth } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { t } from '../../i18n';
import './profile.css';

/**
 * The ghoul forge's page: the user's characters (the domitors to pick from), then the forge of the
 * domitor's edition: a V5 vampire's ghoul is a V5 sheet, a Classic one's a Classic sheet.
 */
function GhoulCreate({ domitorId }) {
  const navigate = useNavigate();
  const api = useApi();
  const { token, user } = useAuth();
  const { chronicles } = useChronicles();
  const { toast } = useToast();
  const [characters, setCharacters] = useState(null);
  useEffect(() => {
    let live = true;
    api('/characters/').then((r) => {
      if (!live) return;
      const all = r.ok && Array.isArray(r.data.characters) ? r.data.characters : [];
      // admins get every character from this endpoint: a ghoul is made for your own
      setCharacters(all.filter((c) => user && String(c.user_id) === String(user.id)));
    });
    return () => {
      live = false;
    };
  }, [api, user]);
  if (!characters) return <p className="sr-muted">{t('profile:ghoul.loading', 'Loading your characters…')}</p>;
  // a named domitor that isn't one of yours (deleted, someone else's, a ghoul): say so, don't guess
  // another vampire (maybe of the other edition)
  const named = domitorId ? characters.find((c) => String(c.id) === String(domitorId) && canBeDomitor(c)) : null;
  if (domitorId && !named) {
    return (
      <div className="sr-prose">
        <p>{t('profile:ghoul.domitorNotFound', "That vampire isn't one of your characters, or can't have ghouls. Pick the domitor again from your characters.")}</p>
        <Button type="button" variant="secondary" onClick={() => navigate('/profile/characters')}>
          {t('profile:ghoul.backToCharacters', 'Back to your characters')}
        </Button>
      </div>
    );
  }
  const target = named || characters.find(canBeDomitor);
  if (target && editionOf(target) !== V5) {
    return (
      <ClassicGhoulForge
        token={token}
        characters={characters}
        domitorId={target.id}
        onCancel={() => navigate('/profile/characters')}
        onDone={() => navigate('/profile/characters')}
        showError={(msg) => toast({ tone: 'danger', title: String(msg) })}
        showSuccess={(msg) => toast({ tone: 'ok', title: String(msg) })}
      />
    );
  }
  return (
    <GhoulForge
      token={token}
      characters={characters}
      chronicles={chronicles}
      domitorId={domitorId}
      onCancel={() => navigate('/profile/characters')}
      onDone={() => navigate('/profile/characters')}
      showError={(msg) => toast({ tone: 'danger', title: String(msg) })}
      showSuccess={(msg) => toast({ tone: 'ok', title: String(msg) })}
    />
  );
}

/** Phase 1 character creation wizard inside the shell, with a short prep guide; ?ghoul_of=<id> forges a ghoul. */
export default function CharacterCreatePage() {
  const navigate = useNavigate();
  const { token, refreshUser } = useAuth();
  const { chronicles, reload } = useChronicles();
  const { toast } = useToast();
  const [params] = useSearchParams();
  const chronicleId = params.get('chronicle');
  const ghoul = params.has('ghoul_of');
  return (
    <>
      <TopBar title={ghoul ? t('profile:ghoul.title', 'New ghoul') : t('profile:create.title', 'New character')} icon="quill" />
      <PageBody className="sr-page--legacy">
        <details className="sr-guide">
          <summary>{t('profile:create.guide', 'Before you forge a character')}</summary>
          {ghoul ? (
            <ol className="sr-prose">
              <li>{t('profile:ghoul.step1', 'A ghoul belongs to one of your vampires; it has no chronicle of its own.')}</li>
              <li>{t('profile:ghoul.step2', 'The server checks the template; your Storyteller can approve exceptions.')}</li>
              <li>{t('profile:ghoul.step3', "A Classic vampire's ghoul is a Classic sheet (Ghouls: Fatal Addiction, with a Blood Pool); a V5 vampire's is a V5 one.")}</li>
              <li>{t('profile:create.step4', 'The sheet locks when you finish. Later changes go through a downtime request.')}</li>
            </ol>
          ) : (
            <ol className="sr-prose">
              <li>{t('profile:create.step1', 'Join or create the chronicle first; the wizard asks which chronicle the character belongs to.')}</li>
              <li>{t('profile:create.step2', 'Have a concept, background, description, ties and gear ready; the Storyteller hooks plots into them.')}</li>
              <li>{t('profile:create.step3', 'Follow the Storyteller’s limits on starting dots and powers.')}</li>
              <li>{t('profile:create.step4', 'The sheet locks when you finish. Later changes go through a downtime request.')}</li>
            </ol>
          )}
        </details>
        {ghoul ? (
          <GhoulCreate domitorId={params.get('ghoul_of')} />
        ) : (
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
        )}
      </PageBody>
    </>
  );
}
