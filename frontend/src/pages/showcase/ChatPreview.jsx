import { useMemo, useState } from 'react';
import { Badge, Button, ChronicleSigil, Glyph } from '../../design';
import MessageList from '../../features/chat/MessageList';
import '../../features/chat/chat.css';
import { t, useLanguage } from '../../i18n';
import { Section } from './parts';
import { openingScene, sceneScript } from './sampleChat';

const ROOMS = [
  { id: 'elysium', glyph: 'room-elysium', name: () => t('showcase:chat.room.elysium', 'Elysium'), unread: 0 },
  { id: 'haven', glyph: 'room-haven', name: () => t('showcase:chat.room.haven', 'The haven'), unread: 2 },
  { id: 'street', glyph: 'room-street', name: () => t('showcase:chat.room.street', 'Rainy streets'), unread: 0 },
  { id: 'ooc', glyph: 'room-ooc', name: () => t('showcase:chat.room.ooc', 'Out of character'), unread: 5 },
];

export default function ChatPreview() {
  const lang = useLanguage();
  // Rebuilt when the language changes, so the scene reads in the chosen language.
  const opening = useMemo(() => openingScene(), [lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const script = useMemo(() => sceneScript(), [lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const [step, setStep] = useState(0);
  const [added, setAdded] = useState([]);
  const messages = useMemo(() => [...opening, ...added], [opening, added]);
  const done = step >= script.length;

  const next = () => {
    if (done) {
      setStep(0);
      setAdded([]);
      return;
    }
    setAdded((a) => [...a, ...script[step](Date.now())]);
    setStep((s) => s + 1);
  };

  return (
    <Section
      id="chat"
      numeral="III"
      kicker={t('showcase:chat.kicker', 'Where the story happens')}
      title={t('showcase:chat.title', 'A table that feels like home')}
      lede={t(
        'showcase:chat.lede',
        'Rooms for every location, speech in character and out of it, dice that land in the conversation, and a Storyteller who answers in prose. This scene uses the real chat components; switch the language above to read it in Greek.'
      )}
    >
      <div className="sc-chat" data-testid="chat-preview">
        <nav className="sc-chat__rail" aria-label={t('showcase:chat.rooms', 'Rooms')}>
          <div className="sc-chat__chronicle">
            <ChronicleSigil line="vampire" edition="v5" size={36} />
            <div>
              <strong>{t('showcase:chat.chronicle', 'Nights of Ash')}</strong>
              <Badge lang="en" edition="V5" tone="blood" icon="line-vampire" />
            </div>
          </div>
          <ul>
            {ROOMS.map((r) => (
              <li key={r.id}>
                <span className={`sc-chat__room${r.id === 'elysium' ? ' is-active' : ''}`} aria-current={r.id === 'elysium' ? 'true' : undefined}>
                  <Glyph name={r.glyph} size={18} />
                  <span>{r.name()}</span>
                  {r.unread ? <Badge count={r.unread} tone="blood" /> : null}
                </span>
              </li>
            ))}
          </ul>
        </nav>
        <div className="sc-chat__main">
          <header className="sc-chat__top">
            <Glyph name="room-elysium" size={20} />
            <strong>{t('showcase:chat.room.elysium', 'Elysium')}</strong>
            <span className="sc-chat__topic">{t('showcase:chat.topic', 'The Prince’s gallery, after midnight')}</span>
          </header>
          <div className="sr-chat sc-chat__list">
            <MessageList
              roomKey={`showcase-${lang}`}
              roomName={t('showcase:chat.room.elysium', 'Elysium')}
              messages={messages}
              status="ready"
              userId={999}
            />
          </div>
          <footer className="sc-chat__foot">
            <div className="sc-chat__composer" aria-hidden="true">
              <Glyph name="mask" size={18} />
              <span>{t('showcase:chat.composer', 'Speak as Mara Voss…')}</span>
              <Glyph name="send" size={18} />
            </div>
            <Button variant={done ? 'secondary' : 'primary'} icon={done ? 'reroll' : 'quill'} onClick={next} data-testid="chat-next">
              {done ? t('showcase:chat.replay', 'Replay the scene') : t('showcase:chat.next', 'Continue the scene')}
            </Button>
          </footer>
        </div>
      </div>
      <p className="sc-note">
        <Glyph name="info" size={14} />{' '}
        {t('showcase:chat.note', 'Character names and game terms such as Hunger or Messy critical stay in English in every language.')}
      </p>
    </Section>
  );
}
