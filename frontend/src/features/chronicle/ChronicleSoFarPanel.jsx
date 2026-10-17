import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Input, Panel, ProgressBar, Spinner, Switch } from '../../design';
import { errorText } from '../../app/http';
import { getLanguage, t } from '../../i18n';
import { clock, downloadMarkdown, isLive, mdFileName, number, pollDelay, shortDate } from './soFar';

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** The live card while a job runs: night x of y, the bar, tokens from the model's stream, time, Cancel. */
export function ProgressCard({ job, onCancel, cancelling }) {
  const lang = getLanguage();
  let line;
  if (job.status === 'queued') line = t('chronicle:soFar.queued', 'Queued…');
  else if (job.phase === 'eras') line = t('chronicle:soFar.eras', 'Joining the nights into the story so far…');
  else if (job.phase === 'joining') line = t('chronicle:soFar.joining', 'Writing the story so far…');
  else if (job.nights) line = t('chronicle:soFar.night', 'Night {{night}} of {{nights}}', { night: job.night || 1, nights: job.nights });
  const tokens = job.tokens_night > 0
    ? (job.tok_per_s
      ? t('chronicle:soFar.tokens', '{{tokens}} tokens · {{rate}} tok/s', { tokens: number(job.tokens_night, lang), rate: Math.round(job.tok_per_s) })
      : t('chronicle:soFar.tokensNoRate', '{{tokens}} tokens', { tokens: number(job.tokens_night, lang) }))
    : t('chronicle:soFar.reading', 'Reading the night…');
  const waiting = job.status === 'waiting';
  return (
    <div className="sr-sofar__progress" data-testid="sofar-progress">
      {waiting ? (
        <div className="sr-sofar__waiting">
          <Spinner variant="candle" size={20} label={t('chronicle:soFar.waiting', 'Waiting for a quiet moment')} />
          <div>
            <strong>{t('chronicle:soFar.waiting', 'Waiting for a quiet moment')}</strong>
            <p className="sr-sofar__hint">{t('chronicle:soFar.waitingHint', 'The writer starts after 10 minutes with no new message, so play comes first.')}</p>
          </div>
        </div>
      ) : (
        <>
          {line ? <strong className="sr-sofar__night">{line}</strong> : null}
          <ProgressBar
            value={job.status === 'running' && job.nights ? job.nights_done || 0 : null}
            max={job.nights || 1}
            label={t('chronicle:soFar.progressLabel', 'Writing progress')}
            valueText={line}
          />
          {job.status === 'running' && job.phase === 'writing' ? <p className="sr-sofar__tokens" aria-live="polite">{tokens}</p> : null}
          <p className="sr-sofar__time">
            {t('chronicle:soFar.elapsed', 'Elapsed {{time}}', { time: clock(job.elapsed_s) })}
            {job.eta_s != null && job.status === 'running' ? ` · ${t('chronicle:soFar.left', 'about {{time}} left', { time: clock(job.eta_s) })}` : ''}
          </p>
        </>
      )}
      <Button variant="ghost" icon="close" onClick={onCancel} loading={cancelling} loadingLabel={t('chronicle:soFar.cancelling', 'Stopping…')}>
        {t('chronicle:soFar.cancel', 'Cancel')}
      </Button>
    </div>
  );
}

function statusLine(data, lang) {
  if (!data) return '';
  const parts = [];
  if (!data.nights_written) parts.push(t('chronicle:soFar.never', 'Not written yet.'));
  else if (data.nights_total > data.nights_written) {
    parts.push(t('chronicle:soFar.partial', '{{written}} of {{total}} nights; Update continues.', { written: data.nights_written, total: data.nights_total }));
  } else {
    parts.push(t('chronicle:soFar.written', 'Written {{date}} · {{written}} of {{total}} nights', {
      date: shortDate(data.written_at, lang), written: data.nights_written, total: data.nights_total,
    }));
  }
  if (data.new_since) parts.push(t('chronicle:soFar.newSince', 'New messages since the last update.'));
  const job = data.job;
  if (job && job.status === 'failed') parts.push(t('chronicle:soFar.failed', 'The last update failed: {{error}}', { error: job.error || '—' }));
  return parts.join(' ');
}

function EstimateNotice({ estimate, onStart, onClose, starting }) {
  let text;
  if (!estimate.enough) text = t('chronicle:soFar.notEnough', 'Nothing to tell yet: write a few scenes first.');
  else if (!estimate.nights_to_write) text = t('chronicle:soFar.estimateNone', 'Nothing new to write; the summary is checked again.');
  else if (estimate.seconds < 60) text = t('chronicle:soFar.estimateShort', 'This will take less than a minute: {{nights}} nights to write, then the summary.', { nights: estimate.nights_to_write });
  else text = t('chronicle:soFar.estimate', 'This will take about {{minutes}} min: {{nights}} nights to write, then the summary.', { minutes: Math.ceil(estimate.seconds / 60), nights: estimate.nights_to_write });
  return (
    <div className="sr-sofar__notice" role="alert" data-testid="sofar-estimate">
      <p>{text}</p>
      {estimate.capped ? (
        <p>{t('chronicle:soFar.capped', 'It stops after {{max}} nights ({{total}} are waiting); press Update again to carry on.', { max: estimate.max_nights, total: estimate.nights_stale })}</p>
      ) : null}
      <div className="sr-sofar__actions">
        {estimate.enough ? (
          <Button variant="primary" onClick={onStart} loading={starting}>{t('chronicle:soFar.start', 'Start')}</Button>
        ) : null}
        <Button variant="ghost" onClick={onClose}>{estimate.enough ? t('chronicle:soFar.cancel', 'Cancel') : t('chronicle:soFar.close', 'Close')}</Button>
      </div>
    </div>
  );
}

function Digest({ data, showSt, lang }) {
  const d = data.digest;
  const chapters = (data.chapters || []).filter((c) => showSt || c.visibility !== 'st');
  return (
    <div className="sr-sofar__digest">
      {d && d.tldr ? (
        <>
          <h3>{t('chronicle:soFar.inShort', 'In short')}</h3>
          <p>{d.tldr}</p>
        </>
      ) : null}
      {d && d.so_far && d.so_far.length ? (
        <>
          <h3>{t('chronicle:soFar.soFar', 'The story so far')}</h3>
          {d.so_far.map((p, i) => <p key={i}>{p}</p>)}
        </>
      ) : null}
      {d && d.threads_open && d.threads_open.length ? (
        <>
          <h3>{t('chronicle:soFar.threads', 'Open threads')}</h3>
          <ul>{d.threads_open.map((th, i) => <li key={i}>{th.text}</li>)}</ul>
        </>
      ) : null}
      {showSt && d && d.st_so_far && d.st_so_far.length ? (
        <section className="sr-sofar__st" data-testid="sofar-st">
          <h3>{t('chronicle:soFar.stTitle', 'Storyteller only')}</h3>
          {d.st_so_far.map((p, i) => <p key={i}>{p}</p>)}
        </section>
      ) : null}
      {chapters.length ? (
        <>
          <h3>{t('chronicle:soFar.nights', 'Nights')}</h3>
          {chapters.map((c) => {
            const ch = c.chapter || {};
            return (
              <details key={c.key} className="sr-sofar__night-item">
                <summary>
                  {t('chronicle:soFar.nightHeading', 'Night {{n}} · {{room}} · {{date}}', { n: c.night, room: c.room, date: shortDate(c.started_at, lang) })}
                  {c.visibility === 'st' ? ` (${t('chronicle:soFar.closedRoom', 'closed room')})` : ''}
                  {ch.title ? <span className="sr-sofar__night-title">{ch.title}</span> : null}
                </summary>
                {(ch.summary || []).map((p, i) => <p key={i}>{p}</p>)}
                {showSt && ch.st_notes && ch.st_notes.length ? (
                  <div className="sr-sofar__st">
                    <strong>{t('chronicle:soFar.stNotes', "What the players didn't see")}</strong>
                    <ul>{ch.st_notes.map((n, i) => <li key={i}>{n.text}</li>)}</ul>
                  </div>
                ) : null}
              </details>
            );
          })}
        </>
      ) : null}
    </div>
  );
}

/**
 * "The chronicle so far" in Chronicle settings, for the Storyteller, site admins and helpers who can
 * open the chronicle. Update shows how long it will take first; while it runs the card polls the job
 * every 1.5 s (5 s while waiting for a quiet moment), the way the recorder polls its jobs.
 */
export default function ChronicleSoFarPanel({ api, campaign, toast }) {
  const id = campaign.id;
  const lang = getLanguage();
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');
  const [estimate, setEstimate] = useState(null);
  const [estimating, setEstimating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [showSt, setShowSt] = useState(false);
  const [lastN, setLastN] = useState('');
  const [tableTalk, setTableTalk] = useState(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const r = await api(`/campaigns/${id}/chronicle`);
    if (!alive.current) return;
    if (!r.ok) {
      setState('error');
      return;
    }
    setData(r.data);
    setState('ready');
    if (isLive(r.data.job)) setJob(r.data.job);
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  // poll the live job until it ends (the RecorderSheet pattern: a loop with a wait, stopped on unmount)
  const jobId = job && isLive(job) ? job.id : null;
  useEffect(() => {
    if (!jobId) return undefined;
    let stop = false;
    (async () => {
      let current = job;
      while (!stop && alive.current && isLive(current)) {
        await wait(pollDelay(current));
        if (stop || !alive.current) return;
        const r = await api(`/campaigns/${id}/chronicle/jobs/${jobId}`);
        if (stop || !alive.current) return;
        if (r.ok && r.data && r.data.job) {
          current = r.data.job;
          setJob(current);
        }
      }
      if (!stop && alive.current) {
        setCancelling(false);
        load();
      }
    })();
    return () => {
      stop = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, api, id, load]);

  const askEstimate = async () => {
    setEstimating(true);
    const r = await api(`/campaigns/${id}/chronicle/estimate`);
    setEstimating(false);
    if (!r.ok) {
      toast({ tone: 'danger', title: errorText(r.data, t('chronicle:soFar.startFailed', 'Could not start the update.')) });
      return;
    }
    setEstimate(r.data);
  };

  const start = async () => {
    setStarting(true);
    const r = await api(`/campaigns/${id}/chronicle/jobs`, { method: 'POST', body: { scope: 'update' } });
    setStarting(false);
    setEstimate(null);
    if (r.ok && r.data && r.data.job) {
      setJob(r.data.job);
      return;
    }
    const code = r.data && r.data.error;
    let title = t('chronicle:soFar.startFailed', 'Could not start the update.');
    if (code === 'too_soon') title = t('chronicle:soFar.tooSoon', 'Update was pressed a moment ago; try again in {{seconds}} s.', { seconds: r.data.retry_after || 0 });
    if (code === 'job_running') title = t('chronicle:soFar.busy', 'An update is already running.');
    toast({ tone: 'danger', title });
  };

  const cancel = async () => {
    if (!job) return;
    setCancelling(true);
    const r = await api(`/campaigns/${id}/chronicle/jobs/${job.id}`, { method: 'DELETE' });
    if (r.data && r.data.job) setJob(r.data.job);
    if (r.data && r.data.job && !isLive(r.data.job)) {
      setCancelling(false);
      load();
    }
  };

  const exportStory = async () => {
    const q = tableTalk ? '?with_table_talk=1' : '';
    const res = await downloadMarkdown(`/campaigns/${id}/chronicle.md${q}`, mdFileName(campaign.name, lang === 'el' ? 'ως τώρα' : 'so far'));
    if (!res.ok) toast({ tone: 'danger', title: t('chronicle:soFar.exportFailed', 'Export failed.') });
  };

  const exportMinutes = async () => {
    const n = parseInt(lastN, 10);
    const params = [n > 0 ? `last=${n}` : '', tableTalk ? 'with_table_talk=1' : ''].filter(Boolean);
    const q = params.length ? `?${params.join('&')}` : '';
    const res = await downloadMarkdown(`/campaigns/${id}/chronicle/minutes.md${q}`, mdFileName(campaign.name, lang === 'el' ? 'πρακτικά' : 'minutes'));
    if (!res.ok) toast({ tone: 'danger', title: t('chronicle:soFar.exportFailed', 'Export failed.') });
  };

  const live = isLive(job);
  const n = parseInt(lastN, 10);
  return (
    <Panel title={t('chronicle:soFar.title', 'The chronicle so far')} icon="scroll" className="sr-sofar">
      <p className="sr-sofar__lead">{t('chronicle:soFar.lead', 'The chat written up as a story, night by night, by the local model. It only runs when you press Update, and waits for a quiet moment in play.')}</p>
      {state === 'loading' ? <Spinner label={t('common:loading', 'Loading')} /> : null}
      {state === 'error' ? <p className="sr-sofar__error">{t('chronicle:soFar.loadFailed', 'Could not load the chronicle so far.')}</p> : null}
      {state === 'ready' ? (
        <>
          <p className="sr-sofar__status" data-testid="sofar-status">{statusLine(data, lang)}</p>
          {live ? <ProgressCard job={job} onCancel={cancel} cancelling={cancelling} /> : null}
          {!live && estimate ? (
            <EstimateNotice estimate={estimate} onStart={start} onClose={() => setEstimate(null)} starting={starting} />
          ) : null}
          {!live && !estimate ? (
            <div className="sr-sofar__actions">
              <Button variant="primary" icon="reroll" onClick={askEstimate} loading={estimating} loadingLabel={t('chronicle:soFar.estimating', 'Working out how long it takes…')}>
                {t('chronicle:soFar.update', 'Update')}
              </Button>
            </div>
          ) : null}
          {data.nights_written ? (
            <div className="sr-sofar__exports">
              <Button icon="book" onClick={exportStory}>{t('chronicle:soFar.exportStory', 'Export story')}</Button>
              <div className="sr-sofar__minutes">
                <Input
                  type="number"
                  min="1"
                  inputMode="numeric"
                  value={lastN}
                  onChange={(e) => setLastN(e.target.value)}
                  aria-label={t('chronicle:soFar.lastN', 'Number of nights')}
                  placeholder="∞"
                />
                <Button icon="scroll" onClick={exportMinutes}>
                  {t('chronicle:soFar.exportMinutes', 'Export minutes')}
                  {' · '}
                  {n > 0 ? t('chronicle:soFar.minutesLast', 'the last {{n}} nights', { n }) : t('chronicle:soFar.minutesWhole', 'the whole chronicle')}
                </Button>
              </div>
              <Switch checked={tableTalk} onChange={setTableTalk} label={t('chronicle:soFar.withTableTalk', 'With table talk')} />
            </div>
          ) : null}
          {data.nights_written ? (
            <>
              <Switch checked={showSt} onChange={setShowSt} label={t('chronicle:soFar.stToggle', 'Show the Storyteller part')} />
              <Digest data={data} showSt={showSt} lang={lang} />
            </>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}
