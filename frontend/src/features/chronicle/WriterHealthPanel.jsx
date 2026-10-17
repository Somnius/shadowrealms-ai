/**
 * Admin → AI system: the chronicle writer at a glance, next to Voice health
 * (GET /api/chronicle-health, site admins only; docs/CHRONICLE.md).
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Panel } from '../../design';
import { apiFetch, getCurrentToken } from '../../app/http';
import { t } from '../../i18n';
import { jobError } from './ChronicleSoFarPanel';

function statusText(job) {
  if (job.status === 'running') return t('chronicle:health.running', 'writing');
  if (job.status === 'waiting') return t('chronicle:health.waiting', 'waiting for a quiet moment');
  return t('chronicle:health.queued', 'queued');
}

export default function WriterHealthPanel() {
  const [h, setH] = useState(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    apiFetch(getCurrentToken(), '/chronicle-health').then((r) => {
      if (r.ok && r.data && r.data.jobs) {
        setH(r.data);
        setFailed(false);
      } else setFailed(true);
    });
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  return (
    <Panel title={t('chronicle:health.title', 'Chronicle writer')} className="sr-admin__panel" data-testid="writer-health">
      {failed ? <p className="sr-admin__warn">{t('chronicle:health.failed', 'Could not read the writer status.')}</p> : null}
      {h ? (
        <div className="sr-admin__kv">
          <div>
            <strong>{t('chronicle:health.today', 'Today:')}</strong>{' '}
            {t('chronicle:health.todayLine', '{{jobs}} jobs, {{failures}} failed', { jobs: h.jobs_today, failures: h.failures_today })}
          </div>
          <div>
            <strong>{t('chronicle:health.speed', 'Median per night:')}</strong>{' '}
            {t('chronicle:health.seconds', '{{seconds}} s', { seconds: h.seconds_per_night })}
          </div>
          <div>
            <strong>{t('chronicle:health.lastError', 'Last error:')}</strong>{' '}
            {h.last_error ? `${jobError(h.last_error.code)} (${h.last_error.code})${h.last_error.at ? ` · ${h.last_error.at.slice(0, 16).replace('T', ' ')}` : ''}` : t('chronicle:health.none', 'none')}
          </div>
          <div>
            <strong>{t('chronicle:health.nightly', 'Nightly run:')}</strong>{' '}
            {t('chronicle:health.nightlyLine', '{{time}} server time, for chronicles that turned it on', { time: h.nightly_at })}
          </div>
          <div data-testid="writer-jobs">
            <strong>{t('chronicle:health.jobs', 'Running and queued:')}</strong>{' '}
            {h.jobs.length ? (
              <ul className="sr-admin__list">
                {h.jobs.map((j) => (
                  <li key={j.id}>
                    {j.campaign_name || `#${j.campaign_id}`} · {statusText(j)}
                    {j.status === 'running' && j.nights ? ` · ${t('chronicle:health.night', 'night {{night}} of {{nights}}', { night: j.night || 1, nights: j.nights })}` : ''}
                    {j.nightly ? ` · ${t('chronicle:health.byNightly', 'nightly')}` : ''}
                  </li>
                ))}
              </ul>
            ) : t('chronicle:health.noJobs', 'nothing')}
          </div>
        </div>
      ) : null}
      <Button type="button" variant="secondary" onClick={load}>{t('chronicle:health.refresh', 'Refresh')}</Button>
    </Panel>
  );
}
