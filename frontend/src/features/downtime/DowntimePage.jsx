import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { Spinner, useToast } from '../../design';
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
  const [campaign, setCampaign] = useState(null);
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    const [c, v] = await Promise.all([api(`/campaigns/${id}`), downtimeApi.view(api, id)]);
    if (c.ok) setCampaign(c.data);
    if (!v.ok) {
      setError(downtimeErrorText(v.data, t('downtime:loadFailed', 'Could not load downtime.')));
      return;
    }
    setError(null);
    setView(v.data);
  }, [api, id]);

  useEffect(() => {
    reload();
  }, [reload]);

  const isV5 = Boolean(campaign && campaign.rules_edition === 'v5');
  return (
    <div className="sr-downtime">
      <TopBar
        title={campaign ? <span className="sr-usertitle">{campaign.name}</span> : t('downtime:title', 'Downtime')}
        subtitle={t('downtime:title', 'Downtime')}
        icon="hourglass"
        actions={
          <ButtonLink to={`/c/${id}`} variant="ghost" size="sm" icon="chevron-left">
            {t('downtime:back', 'Back to the chronicle')}
          </ButtonLink>
        }
      />
      <PageBody narrow>
        {error ? (
          <p className="sr-downtime__readonly" role="alert">{error}</p>
        ) : !view ? (
          <Spinner />
        ) : view.is_storyteller ? (
          <DowntimeStView api={api} campaignId={id} toast={toast} />
        ) : (
          <DowntimePlayerView api={api} campaignId={id} isV5={isV5} data={view} reload={reload} toast={toast} />
        )}
      </PageBody>
    </div>
  );
}
