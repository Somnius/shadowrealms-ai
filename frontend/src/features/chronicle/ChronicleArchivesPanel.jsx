/**
 * Archives of deleted chronicles (GET /api/chronicle-archives): name, Storyteller, when and by whom
 * it was deleted, size, the nights covered, and the minutes and transcript to download. Site admins
 * see all of them (Admin → Archives); a Storyteller sees their own for 30 days (/archives).
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, EmptyState, Panel, Spinner, useOptionalToast } from '../../design';
import { apiFetch, getCurrentToken } from '../../app/http';
import { getLanguage, t } from '../../i18n';
import { fmtBytes } from '../voice/VoiceHealthPanel';
import { downloadMarkdown, mdFileName, shortDate } from './soFar';
import './chronicle.css';

export default function ChronicleArchivesPanel({ admin = false }) {
  const [rows, setRows] = useState(null);
  const [days, setDays] = useState(30);
  const [failed, setFailed] = useState(false);
  const toast = useOptionalToast();
  const lang = getLanguage();

  const load = useCallback(() => {
    apiFetch(getCurrentToken(), '/chronicle-archives').then((r) => {
      if (r.ok && r.data && Array.isArray(r.data.archives)) {
        setRows(r.data.archives);
        if (r.data.st_days) setDays(r.data.st_days);
        setFailed(false);
      } else setFailed(true);
    });
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const download = async (a, which) => {
    const suffix = which === 'minutes' ? (lang === 'el' ? 'πρακτικά' : 'minutes') : (lang === 'el' ? 'μεταγραφή' : 'transcript');
    const res = await downloadMarkdown(`/chronicle-archives/${a.id}/${which}`, mdFileName(a.campaign_name, suffix, 'md'));
    if (!res.ok && toast) {
      toast({
        tone: 'danger',
        title: res.status === 410
          ? t('chronicle:archives.missing', 'The archive files are no longer on the server.')
          : t('chronicle:archives.downloadFailed', 'Download failed.'),
      });
    }
  };

  return (
    <Panel title={t('chronicle:archives.title', 'Archives of deleted chronicles')} icon="coffin" className="sr-archives" data-testid="chronicle-archives">
      <p className="sr-archives__lead">
        {admin
          ? t('chronicle:archives.leadAdmin', 'Written when a chronicle is deleted: the minutes of the nights already written and the full transcript, hidden rolls marked. Kept until removed on the server.')
          : t('chronicle:archives.leadSt', 'The chronicles you ran that were deleted, for {{days}} days after the delete: the minutes and the full transcript.', { days })}
      </p>
      {failed ? <p className="sr-archives__error">{t('chronicle:archives.loadFailed', 'Could not load the archives.')}</p> : null}
      {!rows && !failed ? <Spinner label={t('common:loading', 'Loading')} /> : null}
      {rows && !rows.length ? <EmptyState title={t('chronicle:archives.empty', 'No archived chronicles.')} /> : null}
      {rows && rows.length ? (
        <ul className="sr-archives__list">
          {rows.map((a) => (
            <li key={a.id} className="sr-archives__item">
              <strong className="sr-archives__name">{a.campaign_name}</strong>
              <span className="sr-archives__meta">
                {t('chronicle:archives.meta', 'Storyteller {{st}} · deleted {{date}} by {{by}} · {{size}} · {{written}} of {{nights}} nights written', {
                  st: a.storyteller || '—',
                  date: shortDate(a.created_at, lang),
                  by: a.deleted_by || '—',
                  size: fmtBytes(a.size),
                  written: a.nights_written,
                  nights: a.nights,
                })}
              </span>
              <span className="sr-archives__actions">
                <Button icon="scroll" onClick={() => download(a, 'minutes')}>{t('chronicle:archives.minutes', 'Minutes')}</Button>
                <Button icon="book" variant="secondary" onClick={() => download(a, 'transcript')}>{t('chronicle:archives.transcript', 'Transcript')}</Button>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Panel>
  );
}
