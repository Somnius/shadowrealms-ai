import { Button, Glyph, IconButton } from '../../design';
import { t } from '../../i18n';
import './voice.css';

/** The ear in the room header: on / off. */
export function ListenButton({ listen }) {
  if (!listen || !listen.available) return null;
  return (
    <IconButton
      icon="ear"
      className={listen.on ? 'sr-listen--on' : undefined}
      label={listen.on ? t('voice:listen.off', 'Stop listening') : t('voice:listen.on', 'Listen: read new messages aloud')}
      aria-pressed={listen.on}
      onClick={listen.toggle}
    />
  );
}

/** One 44-px row above the composer while listening. */
export function SpeakingBar({ listen }) {
  const live = listen && listen.on ? t('voice:listen.announceOn', 'Listening on') : '';
  if (!listen || !listen.on) {
    return <div className="sr-visually-hidden" aria-live="polite">{live}</div>;
  }
  const { current, queued, paused, needsResume, missed } = listen.state;
  let text;
  if (listen.catchUp > 0) text = t('voice:catchUp', 'Read the last {{count}} messages?', { count: listen.catchUp });
  else if (needsResume) text = t('voice:tapResume', 'Paused in the background. Tap to resume.');
  else if (current) text = t('voice:speaking', 'Speaking: {{name}}', { name: current.speaker });
  else text = t('voice:waiting', 'Listening for new messages');
  return (
    <div className="sr-speakbar" role="region" aria-label={t('voice:bar', 'Read-out')}>
      <span className="sr-visually-hidden" aria-live="polite">{live}</span>
      <Glyph name="waveform" size={16} className={current && !paused ? 'sr-speakbar__wave is-on' : 'sr-speakbar__wave'} />
      <span className="sr-speakbar__text">
        {text}
        {queued > 0 && !listen.catchUp ? ` · ${t('voice:queued', '{{count}} queued', { count: queued })}` : ''}
        {missed > 0 ? ` · ${t('voice:missed', 'missed {{count}}', { count: missed })}` : ''}
      </span>
      {listen.catchUp > 0 ? (
        <>
          <Button size="sm" variant="secondary" onClick={listen.acceptCatchUp}>{t('voice:yes', 'Yes')}</Button>
          <Button size="sm" variant="ghost" onClick={listen.declineCatchUp}>{t('voice:no', 'No')}</Button>
        </>
      ) : (
        <>
          {paused ? (
            <IconButton icon="play" size="sm" label={t('voice:resume', 'Resume')} onClick={listen.resume} />
          ) : (
            <IconButton icon="pause" size="sm" label={t('voice:pause', 'Pause')} onClick={listen.pause} />
          )}
          <IconButton icon="skip" size="sm" label={t('voice:skip', 'Skip')} onClick={listen.skip} disabled={!current} />
          <IconButton icon="stop" size="sm" label={t('voice:stop', 'Stop listening')} onClick={listen.toggle} />
        </>
      )}
    </div>
  );
}
