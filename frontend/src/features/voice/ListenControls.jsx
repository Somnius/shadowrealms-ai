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

export function catchUpLabel(choice) {
  if (choice === 'last10') return t('voice:catchUpChoice.last10', 'Last 10');
  if (choice === 'resume') return t('voice:catchUpChoice.resume', 'From where I stopped');
  if (choice === 'none') return t('voice:catchUpChoice.none', 'None');
  return t('voice:catchUpChoice.last3', 'Last 3');
}

/** "Read earlier messages?" Last 3 / Last 10 / From where I stopped / None (the last choice first). */
function CatchUpChoice({ listen }) {
  const first = listen.catchUpChoice || 'last3';
  const order = [first, ...['last3', 'last10', 'resume', 'none'].filter((c) => c !== first)];
  return (
    <div className="sr-speakbar__choices" role="group" aria-label={t('voice:catchUpAsk', 'Read earlier messages?')}>
      {order.map((c, i) => (
        <Button key={c} size="sm" variant={i === 0 ? 'secondary' : 'ghost'} onClick={() => listen.chooseCatchUp(c)}>
          {catchUpLabel(c)}
        </Button>
      ))}
    </div>
  );
}

/** One 44-px row above the composer while listening (or while a "Read this" plays). */
export function SpeakingBar({ listen }) {
  const live = listen && listen.on ? t('voice:listen.announceOn', 'Listening on') : '';
  const active = listen && (listen.on || listen.active);
  if (!active) {
    return <div className="sr-visually-hidden" aria-live="polite">{live}</div>;
  }
  const { current, part, queued, paused, needsResume, missed } = listen.state;
  let text;
  if (listen.catchUp > 0) text = t('voice:catchUpAsk', 'Read earlier messages?');
  else if (needsResume) text = t('voice:tapResume', 'Paused in the background. Tap to resume.');
  else if (current) text = t('voice:speaking', 'Speaking: {{name}}', { name: current.speaker });
  else text = t('voice:waiting', 'Listening for new messages');
  const stop = listen.on ? listen.toggle : listen.stop;
  return (
    <div className="sr-speakbar" role="region" aria-label={t('voice:bar', 'Read-out')}>
      <span className="sr-visually-hidden" aria-live="polite">{live}</span>
      <Glyph name="waveform" size={16} className={current && !paused ? 'sr-speakbar__wave is-on' : 'sr-speakbar__wave'} />
      <span className="sr-speakbar__main">
        <span className="sr-speakbar__text">
          {text}
          {queued > 0 && !listen.catchUp ? ` · ${t('voice:queued', '{{count}} queued', { count: queued })}` : ''}
          {missed > 0 ? ` · ${t('voice:missed', 'missed {{count}}', { count: missed })}` : ''}
        </span>
        {current && part && part.text && !listen.catchUp ? (
          <span className="sr-speakbar__sentence" data-testid="speak-sentence">
            {part.text}
          </span>
        ) : null}
      </span>
      {listen.catchUp > 0 ? (
        <CatchUpChoice listen={listen} />
      ) : (
        <>
          {current && listen.follow === false ? (
            <Button size="sm" variant="ghost" icon="chevron-down" onClick={listen.resumeFollow}>
              {t('voice:follow', 'Follow')}
            </Button>
          ) : null}
          {paused ? (
            <IconButton icon="play" size="sm" label={t('voice:resume', 'Resume')} onClick={listen.resume} />
          ) : (
            <IconButton icon="pause" size="sm" label={t('voice:pause', 'Pause')} onClick={listen.pause} />
          )}
          <IconButton icon="skip" size="sm" label={t('voice:skip', 'Skip')} onClick={listen.skip} disabled={!current} />
          <IconButton icon="stop" size="sm" label={listen.on ? t('voice:stop', 'Stop listening') : t('voice:stopReading', 'Stop reading')} onClick={stop} />
        </>
      )}
    </div>
  );
}
