import { useRef } from 'react';
import { Avatar, Badge, Button, DotTrack, Glyph } from '../../design';
import { editionOf, V5 } from '../../rules/rulesEdition';
import ButtonLink from '../../app/ButtonLink';
import SheetPdfButton from '../../components/SheetPdfButton';
import { lineOf } from '../../app/hooks';
import { t } from '../../i18n';
import { Term, termHint } from '../../i18n/glossary';

const MAX_PORTRAIT_BYTES = 350000;

function readImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/** "Your character" card: portrait, Hunger (V5), sheet, portrait and PDF actions. */
function CharacterCard({ campaign, character, onOpenSheet, onPortrait, toast }) {
  const fileRef = useRef(null);
  if (!character) {
    return (
      <div className="sr-member-card sr-member-card--empty">
        <Glyph name="mask" size={28} />
        <p className="sr-muted">
          {t('play:panel.noCharacter', 'You have no character in this chronicle. You can still talk out of character.')}
        </p>
        {campaign && ['vampire', 'werewolf', 'mage'].includes(lineOf(campaign.game_system)) ? (
          <ButtonLink to={`/profile/characters/new?chronicle=${campaign.id}`} variant="primary" size="sm" icon="quill">
            {t('hall:createCharacter', 'Create character')}
          </ButtonLink>
        ) : null}
      </div>
    );
  }
  const hunger = parseInt(character?.wod_meta?.hunger, 10);
  const pick = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!f) return;
    if (f.size > MAX_PORTRAIT_BYTES) {
      toast({ tone: 'danger', title: t('play:panel.portraitTooBig', 'Image is too large (max ~350 KB).') });
      return;
    }
    const dataUrl = await readImage(f);
    if (typeof dataUrl === 'string') onPortrait(dataUrl);
  };
  return (
    <div className="sr-member-card">
      <Avatar src={character.portrait_url} name={character.name} size={80} alt="" sigil="mask" />
      <div className="sr-member-card__name">{character.name}</div>
      {editionOf(campaign) === V5 && Number.isFinite(hunger) ? (
        <div title={termHint('hunger')}>
          <DotTrack label={t('glossary:hunger', 'Hunger')} value={hunger} max={5} shape="square" tone="blood" readOnly />
        </div>
      ) : null}
      <div className="sr-member-card__actions">
        <Button size="sm" variant="secondary" icon="scroll" onClick={() => onOpenSheet(character.id)}>
          {t('play:panel.sheet', 'Character sheet')}
        </Button>
        <Button size="sm" variant="ghost" icon="quill" onClick={() => fileRef.current && fileRef.current.click()}>
          {t('play:panel.portrait', 'Portrait')}
        </Button>
        <SheetPdfButton character={character} />
        <input ref={fileRef} type="file" accept="image/*" className="sr-visually-hidden" tabIndex={-1} onChange={pick} aria-hidden="true" />
      </div>
    </div>
  );
}

function MemberRow({ m, canOpen, onOpenSheet, me }) {
  const ch = m.character;
  const content = (
    <>
      <Avatar src={(ch && ch.portrait_url) || m.player_avatar_url} name={(ch && ch.name) || m.username} size={32} alt="" sigil={ch ? 'mask' : 'hood'} />
      <span className="sr-member__text">
        <span className="sr-member__name">
          {ch ? ch.name : m.username}
          {String(m.user_id) === String(me) ? <span className="sr-muted"> {t('play:panel.you', '(you)')}</span> : null}
        </span>
        <span className="sr-member__sub">{ch ? m.username : t('play:panel.noChar', 'no character')}</span>
      </span>
      {m.site_role === 'admin' || m.site_role === 'helper' ? <Badge tone="neutral">{t('play:panel.staff', 'Staff')}</Badge> : null}
    </>
  );
  return (
    <li>
      {ch && canOpen ? (
        <button type="button" className="sr-member" onClick={() => onOpenSheet(ch.id)} aria-label={t('play:panel.openSheet', 'Open {{name}}’s sheet', { name: ch.name })}>
          {content}
        </button>
      ) : (
        <div className="sr-member">{content}</div>
      )}
    </li>
  );
}

/** Right panel: your character, then members (Storyteller first), then staff tools. */
export default function MemberPanel({ campaign, character, members, user, canStaff, isAdmin, onOpenSheet, onPortrait, onDiceRules, onDiceHistory, toast }) {
  const st = members.filter((m) => m.is_storyteller);
  const players = members.filter((m) => !m.is_storyteller);
  const canOpen = (m) => canStaff || String(m.user_id) === String(user?.id);
  return (
    <div className="sr-panelcol">
      <section aria-labelledby="panel-char" className="sr-panelcol__section">
        <h3 id="panel-char" className="sr-panelcol__heading">
          {t('play:panel.yourCharacter', 'Your character')}
        </h3>
        <CharacterCard campaign={campaign} character={character} onOpenSheet={onOpenSheet} onPortrait={onPortrait} toast={toast} />
      </section>
      {st.length ? (
        <section aria-labelledby="panel-st" className="sr-panelcol__section">
          <h3 id="panel-st" className="sr-panelcol__heading">
            <Term id="storyteller">{t('play:panel.storyteller', 'Storyteller')}</Term>
          </h3>
          <ul className="sr-members">
            <li>
              <div className="sr-member">
                <span className="sr-msg__ai-avatar" style={{ width: 32, height: 32 }}>
                  <Glyph name="ai-sigil" size={26} />
                </span>
                <span className="sr-member__text">
                  <span className="sr-member__name sr-msg__name--ai">{t('chat:speaker.ai', 'Storyteller')}</span>
                  <span className="sr-member__sub">{t('play:panel.ai', 'AI')}</span>
                </span>
              </div>
            </li>
            {st.map((m) => (
              <MemberRow key={m.user_id} m={m} canOpen={canOpen(m)} onOpenSheet={onOpenSheet} me={user?.id} />
            ))}
          </ul>
        </section>
      ) : null}
      <section aria-labelledby="panel-players" className="sr-panelcol__section">
        <h3 id="panel-players" className="sr-panelcol__heading">
          {t('play:panel.players', { one: 'Player · {{count}}', other: 'Players · {{count}}' }, { count: players.length })}
        </h3>
        <ul className="sr-members">
          {players.map((m) => (
            <MemberRow key={m.user_id} m={m} canOpen={canOpen(m)} onOpenSheet={onOpenSheet} me={user?.id} />
          ))}
        </ul>
      </section>
      {isAdmin ? (
        <section aria-labelledby="panel-tools" className="sr-panelcol__section">
          <h3 id="panel-tools" className="sr-panelcol__heading">
            {t('play:panel.tools', 'Staff tools')}
          </h3>
          <div className="sr-stack sr-stack--tight">
            <Button size="sm" variant="ghost" icon="d10-crit" onClick={onDiceRules}>
              {t('dice:rules.title', 'Room dice rules')}
            </Button>
            <Button size="sm" variant="ghost" icon="scroll" onClick={onDiceHistory}>
              {t('dice:history.open', 'Roll history')}
            </Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
