/**
 * Admin → AI system: the speech service at a glance (GET /api/voice/health, site admins only).
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Panel } from '../../design';
import { apiFetch, getCurrentToken } from '../../app/http';
import { t } from '../../i18n';

export function fmtBytes(n) {
  if (n == null) return '—';
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.round(n / 1024)} KB`;
}

const v = (x) => (x == null ? '—' : String(x));

export default function VoiceHealthPanel() {
  const [h, setH] = useState(null);
  const [failed, setFailed] = useState(false);
  const load = useCallback(() => {
    apiFetch(getCurrentToken(), '/voice/health').then((r) => {
      if (r.ok && r.data && r.data.speech) { setH(r.data); setFailed(false); } else setFailed(true);
    });
  }, []);
  useEffect(() => { load(); }, [load]);
  return (
    <Panel title={t('voice:health.title', 'Voice (speech service)')} className="sr-admin__panel" data-testid="voice-health">
      {failed ? <p className="sr-admin__warn">{t('voice:health.failed', 'Could not read the voice status.')}</p> : null}
      {h ? (
        <div className="sr-admin__kv">
          <div><strong>{t('voice:health.service', 'Speech service:')}</strong> {h.speech.up ? t('voice:health.up', 'running') : t('voice:health.down', 'not reachable')}
            {h.speech.up ? ` · ${t('voice:health.whisper', 'Whisper')}: ${h.speech.stt_loaded ? t('voice:health.loaded', 'loaded') : t('voice:health.idle', 'unloaded (idle)')}` : ''}
            {h.speech.pocket_error ? ` · ${t('voice:health.pocketError', 'Greek voices failed to load')}` : ''}</div>
          <div><strong>{t('voice:health.queues', 'Queues:')}</strong> {t('voice:health.queueLine', 'transcribe {{stt}}, speak {{tts}}', { stt: v(h.queues.stt), tts: v(h.queues.tts) })}</div>
          <div><strong>{t('voice:health.vram', 'GPU memory:')}</strong> {t('voice:health.vramLine', '{{free}} MB free, {{needed}} MB needed to transcribe', { free: v(h.vram.free_mb), needed: v(h.vram.needed_mb) })}</div>
          <div><strong>{t('voice:health.clips', 'Recordings on disk:')}</strong> {fmtBytes(h.disk.clips_bytes)} / {fmtBytes(h.disk.clips_cap_bytes)}</div>
          <div><strong>{t('voice:health.cache', 'Spoken-line cache:')}</strong> {fmtBytes(h.disk.tts_cache_bytes)} / {fmtBytes(h.disk.tts_cache_cap_bytes)}</div>
          <div>
            <strong>{t('voice:health.today', 'Recorded today:')}</strong>{' '}
            {h.minutes_today.length
              ? h.minutes_today.map((m) => `${m.username || `#${m.user_id}`} ${m.minutes} min (${m.clips})`).join(', ')
              : t('voice:health.none', 'nothing yet')}
          </div>
        </div>
      ) : null}
      <Button type="button" variant="secondary" size="sm" onClick={load}>{t('voice:health.refresh', 'Refresh')}</Button>
    </Panel>
  );
}
