import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { Button, Spinner, useToast } from '../../design';
import { PageBody, TopBar } from '../../app/AppShell';
import ButtonLink from '../../app/ButtonLink';
import { useApi } from '../../app/AuthContext';
import { t } from '../../i18n';
import { downtimeApi } from './downtimeApi';
import { downtimeErrorText } from './downtimeErrors';
import DowntimePlayerView from './DowntimePlayerView';
import DowntimeStView from './DowntimeStView';
import '../chronicle/chronicle.css';
import './downtime.css';

/** /chronicles/:id/downtime: the Storyteller's tools or the player's projects (is_storyteller). */
export default function DowntimePage() {
  const { id } = useParams();
  const api = useApi();
  const { toast } = useToast();
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    const v = await downtimeApi.view(api, id);
    const text = v.ok ? null : downtimeErrorText(v.data, t('downtime:loadFailed', 'Could not load downtime.'));
    setError(text);
    if (v.ok) setView(v.data);
  }, [api, id]);

  useEffect(() => {
    reload();
  }, [reload]);

  const isV5 = Boolean(view && view.rules_edition === 'v5');
  const retry = (
    <div className="sr-downtime__readonly" role="alert">
      <p>{error}</p>
      <Button size="sm" variant="secondary" onClick={reload}>
        {t('downtime:retry', 'Try again')}
      </Button>
    </div>
  );
  return (
    <div className="sr-downtime">
      <TopBar
        title={t('downtime:title', 'Downtime')}
        icon="hourglass"
        actions={
          <ButtonLink to={`/c/${id}`} variant="ghost" size="sm" icon="chevron-left">
            {t('downtime:back', 'Back to the chronicle')}
          </ButtonLink>
        }
      />
      <PageBody narrow>
        {!view ? (
          error ? retry : <Spinner />
        ) : (
          <div className="sr-stack">
            {error ? retry : null}
            {view.is_storyteller ? (
              <>
                <DowntimeStView api={api} campaignId={id} toast={toast} isV5={isV5} />
                {view.character ? (
                  <DowntimePlayerView
                    api={api}
                    campaignId={id}
                    isV5={isV5}
                    data={view}
                    reload={reload}
                    toast={toast}
                    embedded
                    title={t('downtime:ownProjects', 'Your own projects as a player')}
                  />
                ) : null}
              </>
            ) : (
              <DowntimePlayerView api={api} campaignId={id} isV5={isV5} data={view} reload={reload} toast={toast} />
            )}
          </div>
        )}
      </PageBody>
    </div>
  );
}
