/**
 * The "Previously on…" card (0.27): the room's recent nights (titles and summaries, newest last)
 * and the story so far in short. Above the chat on wide screens, a bottom sheet on phones. Each night
 * jumps to its first message; "Read it" reads the card aloud with the user's voices (listening off
 * too). State comes from usePreviouslyOn (previouslyOn.js).
 */
import { Button, Drawer, IconButton } from '../../design';
import { recapParts } from './previouslyOn';
import { t } from '../../i18n';

function Body({ recap, onJump, onRead, canRead }) {
  return (
    <>
      <ol className="sr-recap__nights">
        {recap.nights.map((n) => (
          <li key={`${n.night}-${n.started_at}`} className="sr-recap__night">
            <h3 className="sr-recap__night-title">
              {n.title
                ? t('play:recap.nightTitled', 'Night {{n}}: {{title}}', { n: n.night, title: n.title })
                : t('play:recap.night', 'Night {{n}}', { n: n.night })}
            </h3>
            {(n.summary || []).map((p, i) => (
              <p key={i} className="sr-recap__summary">
                {p}
              </p>
            ))}
            {n.first_message_id ? (
              <Button size="sm" variant="ghost" icon="chevron-up" className="sr-recap__jump" onClick={() => onJump(n.first_message_id)}>
                {t('play:recap.jump', 'Jump to the start')}
              </Button>
            ) : null}
          </li>
        ))}
      </ol>
      <section className="sr-recap__sofar">
        <h3 className="sr-recap__night-title">{t('play:recap.soFar', 'The story so far')}</h3>
        <p className="sr-recap__summary">{recap.so_far}</p>
      </section>
      {canRead ? (
        <div className="sr-recap__actions">
          <Button size="sm" variant="secondary" icon="ear" className="sr-recap__read" onClick={onRead}>
            {t('play:recap.read', 'Read it')}
          </Button>
        </div>
      ) : null}
    </>
  );
}

export default function PreviouslyOn({ state, listen, isMobile, onJump }) {
  const { recap, open, close, hide, startJob } = state;
  if (!open || !recap) return null;
  const canRead = !!(listen && listen.available && listen.readRecap);
  const onRead = () => listen.readRecap({ key: recap.location_id, parts: recapParts(recap), startJob });
  const jump = (id) => {
    if (isMobile) (hide || close)(); // hidden, not closed: the header button brings it back
    onJump(id);
  };
  const title = t('play:recap.title', 'Previously on…');
  if (isMobile) {
    return (
      <Drawer open onClose={close} side="bottom" title={title} className="sr-recap sr-recap--sheet" closeLabel={t('play:recap.close', 'Close the recap')}>
        <Body recap={recap} onJump={jump} onRead={onRead} canRead={canRead} />
      </Drawer>
    );
  }
  return (
    <section className="sr-recap sr-recap--card" aria-labelledby="sr-recap-title">
      <header className="sr-recap__header">
        <h2 id="sr-recap-title" className="sr-recap__title">
          {title}
        </h2>
        <IconButton icon="close" label={t('play:recap.close', 'Close the recap')} onClick={close} />
      </header>
      <div className="sr-recap__scroll">
        <Body recap={recap} onJump={jump} onRead={onRead} canRead={canRead} />
      </div>
    </section>
  );
}
