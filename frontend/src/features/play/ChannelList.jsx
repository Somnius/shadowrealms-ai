import React from 'react';
import { Link } from 'react-router-dom';
import { Badge, Glyph, Tooltip } from '../../design';
import ButtonLink from '../../app/ButtonLink';
import { editionLabel } from '../../rules/rulesEdition';
import { t } from '../../i18n';

export function roomGlyph(type) {
  const ty = String(type || '').toLowerCase();
  if (ty === 'ooc') return 'room-ooc';
  if (ty.includes('elysium')) return 'room-elysium';
  if (ty.includes('haven') || ty.includes('home')) return 'room-haven';
  return 'room-street';
}

const DEFAULT_OOC_NAME = 'Out of Character Lobby';
const DEFAULT_OOC_DESC =
  'A place for players to discuss the campaign, ask questions, and chat as themselves (not as characters). This is the default meeting place before entering the game world.';

/**
 * The server creates every chronicle's OOC lobby with a fixed English name and description
 * (backend/routes/locations.py). Show those defaults in the interface language; anything the
 * Storyteller renamed or rewrote is shown as written.
 */
export function localizeRoom(loc) {
  if (!loc) return loc;
  const name = loc.name === DEFAULT_OOC_NAME ? t('play:room.oocDefaultName', 'Out of Character Lobby') : loc.name;
  const description = loc.description === DEFAULT_OOC_DESC
    ? t('play:room.oocDefaultDescription', 'A place for players to discuss the chronicle, ask questions and chat as themselves (not as characters). This is the meeting place before entering the game world.')
    : loc.description;
  return name === loc.name && description === loc.description ? loc : { ...loc, name, description };
}

export const localizeRooms = (list) => (Array.isArray(list) ? list.map(localizeRoom) : list);

export const isOpenRoom = (loc) => loc && loc.is_open !== false && loc.is_open !== 0;

/** OOC rooms first, then story locations, in server order. */
export function sortRooms(locations) {
  const ooc = (locations || []).filter((l) => String(l.type).toLowerCase() === 'ooc');
  const story = (locations || []).filter((l) => String(l.type).toLowerCase() !== 'ooc');
  return { ooc, story, all: [...ooc, ...story] };
}

function RoomLink({ campaignId, loc, active, unread, canEnterClosed, onClosed, onNavigate }) {
  const closed = !isOpenRoom(loc);
  const blocked = closed && !canEnterClosed;
  const count = !active && unread ? unread.unread_count : 0;
  return (
    <li>
      <Link
        to={`/c/${campaignId}/${loc.id}`}
        className={`sr-room${active ? ' is-active' : ''}${count ? ' is-unread' : ''}${closed ? ' is-closed' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={(e) => {
          if (blocked) {
            e.preventDefault();
            onClosed(loc);
            return;
          }
          if (onNavigate) onNavigate();
        }}
      >
        <Glyph name={roomGlyph(loc.type)} size={18} className="sr-room__glyph" />
        <span className="sr-room__name">{loc.name}</span>
        {closed ? <Glyph name="lock-chain" size={14} title={t('play:room.closed', 'Closed')} className="sr-room__lock" /> : null}
        {count ? (
          <Badge tone="blood" count={count} aria-label={t('play:room.unread', { one: '{{count}} unread message', other: '{{count}} unread messages' }, { count })} />
        ) : null}
      </Link>
    </li>
  );
}

/** Second column: chronicle header + rooms with unread counts. */
export default function ChannelList({ campaign, locations, currentId, unread, canEnterClosed, canManage, onClosed, onNavigate, onQuickSwitch }) {
  const { ooc, story } = sortRooms(locations);
  const section = (title, list, key) =>
    list.length ? (
      <section className="sr-rooms__section" aria-labelledby={`rooms-${key}`}>
        <h3 id={`rooms-${key}`} className="sr-rooms__heading">
          {title}
        </h3>
        <ul className="sr-rooms__list">
          {list.map((loc) => (
            <RoomLink
              key={loc.id}
              campaignId={campaign.id}
              loc={loc}
              active={String(loc.id) === String(currentId)}
              unread={unread[loc.id]}
              canEnterClosed={canEnterClosed}
              onClosed={onClosed}
              onNavigate={onNavigate}
            />
          ))}
        </ul>
      </section>
    ) : null;

  return (
    <nav className="sr-rooms" aria-label={t('play:rooms.label', 'Rooms of {{name}}', { name: campaign?.name || '' })}>
      <header className="sr-rooms__header">
        <div className="sr-rooms__title">
          <h2 className="sr-rooms__name">{campaign?.name}</h2>
          <Badge edition={editionLabel(campaign)} tone="neutral" />
        </div>
        <Tooltip content={t('play:rooms.settings', 'Chronicle details & settings')} describe={false} placement="bottom">
          <Link
            to={`/chronicles/${campaign.id}`}
            className="sr-btn sr-btn--icon sr-btn--sm sr-btn--square"
            aria-label={t('play:rooms.settings', 'Chronicle details & settings')}
            onClick={() => onNavigate && onNavigate()}
          >
            <Glyph name="settings" size={16} />
          </Link>
        </Tooltip>
      </header>
      {onQuickSwitch ? (
        <button type="button" className="sr-rooms__search" onClick={onQuickSwitch}>
          <Glyph name="search" size={16} />
          <span>{t('play:switcher.open', 'Find a room')}</span>
          <kbd className="sr-kbd">Ctrl K</kbd>
        </button>
      ) : null}
      <div className="sr-rooms__scroll">
        {section(t('play:rooms.ooc', 'Out of character'), ooc, 'ooc')}
        {section(t('play:rooms.story', 'Story locations'), story, 'story')}
        {!locations.length ? <p className="sr-muted sr-rooms__empty">{t('play:rooms.none', 'No rooms yet.')}</p> : null}
      </div>
      {canManage ? (
        <div className="sr-rooms__footer">
          <ButtonLink to={`/chronicles/${campaign.id}#locations`} variant="ghost" size="sm" icon="plus">
            {t('play:rooms.manage', 'Manage locations')}
          </ButtonLink>
        </div>
      ) : null}
    </nav>
  );
}
