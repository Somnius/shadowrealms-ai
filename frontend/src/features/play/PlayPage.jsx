import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { AiSigil, Button, CandleHalo, Drawer, EmptyState, Glyph, IconButton, Modal, Spinner, useToast } from '../../design';
import { TopBar } from '../../app/AppShell';
import ChronicleRail from '../../app/ChronicleRail';
import ButtonLink from '../../app/ButtonLink';
import { useApi, useAuth } from '../../app/AuthContext';
import { useChronicles } from '../../app/ChroniclesContext';
import { useSheet } from '../../app/SheetContext';
import { errorText } from '../../app/http';
import { canUseStaffVoice, lineOf, readLocal, useIsMobile, useIsWide, writeLocal } from '../../app/hooks';
import DiceRollOverlay from '../../components/dice/DiceRollOverlay';
import V5RerollPanel from '../../components/dice/V5RerollPanel';
import MessageList from '../chat/MessageList';
import Composer, { voiceOptions } from '../chat/Composer';
import { sendChatMessage } from '../chat/sendFlow';
import { seenParam, useRoomMessages } from '../chat/useRoomMessages';
import { useLiveUpdates } from '../chat/useLiveUpdates';
import { useDiceOverlay } from '../dice/useDiceOverlay';
import { useDiceActions } from '../dice/useDiceActions';
import { DiceHistoryDialog, DiceRulesDialog, RollDialog } from '../dice/DiceDialogs';
import ChannelList, { isOpenRoom, localizeRooms, roomGlyph, sortRooms } from './ChannelList';
import MemberPanel from './MemberPanel';
import QuickSwitcher from './QuickSwitcher';
import { closedRoomCopy } from './closedRoom';
import { t } from '../../i18n';
import '../chat/chat.css';
import './play.css';

const lastRoomKey = (cid) => `sr_last_room_${cid}`;
const voiceKey = (cid, roomType) => `sr_speak_${cid}_${roomType}`;

/** /c/:id → the last room visited in this chronicle (this browser), else the OOC room, else the first. */
export function PlayRedirect() {
  const { id } = useParams();
  const api = useApi();
  const [target, setTarget] = useState(null);
  const [state, setState] = useState('loading');
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const r = await api(`/campaigns/${id}/locations`);
      if (cancelled) return;
      const locs = r.ok && Array.isArray(r.data) ? r.data : [];
      if (!r.ok) {
        setState(errorText(r.data, t('play:error.load', 'Could not open this chronicle.')));
        return;
      }
      const last = readLocal(lastRoomKey(id));
      const pick = locs.find((l) => String(l.id) === String(last)) || sortRooms(locs).all[0];
      if (pick) setTarget(`/c/${id}/${pick.id}`);
      else setState('empty');
    })();
    return () => {
      cancelled = true;
    };
  }, [api, id]);
  if (target) return <Navigate to={target} replace />;
  return (
    <>
      <TopBar title={t('play:title', 'Chronicle')} icon="logo-mark" />
      <div className="sr-loading">
        {state === 'loading' ? <Spinner variant="candle" label={t('common:loading', 'Loading')} /> : null}
        {state === 'empty' ? (
          <EmptyState glyph="room-street" title={t('play:noRooms', 'This chronicle has no rooms yet')} ambient>
            <ButtonLink to={`/chronicles/${id}`} variant="secondary">
              {t('play:openSettings', 'Open chronicle settings')}
            </ButtonLink>
          </EmptyState>
        ) : null}
        {state !== 'loading' && state !== 'empty' ? <EmptyState glyph="warning" title={state} /> : null}
      </div>
    </>
  );
}

function usePlayData(campaignId) {
  const api = useApi();
  const { user } = useAuth();
  const { byId, chronicles } = useChronicles();
  const [data, setData] = useState({ status: 'loading' });

  const loadLocations = useCallback(async () => {
    const r = await api(`/campaigns/${campaignId}/locations`);
    if (r.ok && Array.isArray(r.data)) setData((d) => ({ ...d, locations: localizeRooms(r.data) }));
  }, [api, campaignId]);

  useEffect(() => {
    let cancelled = false;
    setData({ status: 'loading' });
    (async () => {
      const [detail, locs, chars, roster] = await Promise.all([
        api(`/campaigns/${campaignId}`),
        api(`/campaigns/${campaignId}/locations`),
        api(`/characters/?campaign_id=${campaignId}`),
        api(`/campaigns/${campaignId}/roster`),
      ]);
      if (cancelled) return;
      if (!detail.ok) {
        setData({ status: 'error', error: errorText(detail.data, t('play:error.load', 'Could not open this chronicle.')) });
        return;
      }
      setData({
        status: 'ready',
        campaign: detail.data,
        locations: locs.ok && Array.isArray(locs.data) ? localizeRooms(locs.data) : [],
        characters: chars.ok && Array.isArray(chars.data.characters) ? chars.data.characters : [],
        members: roster.ok && Array.isArray(roster.data.members) ? roster.data.members : [],
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [api, campaignId]);

  // Inside a chronicle you always play that chronicle's character (no global "active character").
  const listEntry = byId(campaignId);
  const character = useMemo(() => {
    if (data.status !== 'ready') return null;
    const mine = data.characters.filter((c) => user && String(c.user_id) === String(user.id) && c.is_active !== false);
    const playingId = listEntry ? listEntry.my_playing_character_id : null;
    return mine.find((c) => String(c.id) === String(playingId)) || (mine.length === 1 ? mine[0] : null);
  }, [data, user, listEntry]);

  const updateCharacter = useCallback((id, patch) => {
    setData((d) => ({ ...d, characters: (d.characters || []).map((c) => (c.id === id ? { ...c, ...patch } : c)) }));
  }, []);

  return { ...data, character, loadLocations, updateCharacter, chronicles };
}

export default function PlayPage() {
  const { id: campaignId, locationId } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { user, isAdmin } = useAuth();
  const { toast } = useToast();
  const { openSheet } = useSheet();
  const isMobile = useIsMobile();
  const isWide = useIsWide();
  const play = usePlayData(campaignId);
  const { campaign, locations = [], members = [], character, status: playStatus } = play;

  const location = useMemo(() => locations.find((l) => String(l.id) === String(locationId)) || null, [locations, locationId]);
  const roomType = String(location?.type || '').toLowerCase() === 'ooc' ? 'ooc' : 'ic';
  const canStaff = canUseStaffVoice(user, campaign);
  const canEnterClosed = canStaff;
  const ready = playStatus === 'ready' && !!location;

  const [navOpen, setNavOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(() => readLocal('sr_member_panel', '1') !== '0');
  const [panelDrawer, setPanelDrawer] = useState(false);
  const [rollOpen, setRollOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [closedModal, setClosedModal] = useState(null);
  const [sending, setSending] = useState(false);
  const [aiPending, setAiPending] = useState(false);
  const [aiFailure, setAiFailure] = useState(null);
  const [unread, setUnread] = useState({});
  const [atBottom, setAtBottom] = useState(true);
  const composerRef = useRef(null);

  useEffect(() => {
    if (location) writeLocal(lastRoomKey(campaignId), location.id);
  }, [campaignId, location]);

  // ---- speaking as: one control, remembered per chronicle and room type ----
  const voices = useMemo(() => voiceOptions({ character, user, canStaff }), [character, user, canStaff]);
  const [speakAs, setSpeakAs] = useState('player');
  useEffect(() => {
    if (!ready) return;
    const stored = readLocal(voiceKey(campaignId, roomType));
    const ok = (v) => voices.some((x) => x.id === v);
    const fallback = roomType === 'ooc' ? 'player' : character ? 'character' : 'player';
    setSpeakAs(stored && ok(stored) ? stored : fallback);
  }, [ready, campaignId, roomType, voices, character]);
  const changeVoice = (v) => {
    setSpeakAs(v);
    writeLocal(voiceKey(campaignId, roomType), v);
  };

  // ---- room messages, dice, live updates ----
  const room = useRoomMessages({
    api,
    campaignId,
    locationId: location ? location.id : null,
    characterId: character ? character.id : null,
    userId: user ? user.id : null,
    enabled: ready,
  });
  const dice = useDiceOverlay(room.messages);
  const diceActions = useDiceActions({
    api,
    campaign,
    location,
    speakAs,
    character,
    onCharacterHunger: (h) => character && play.updateCharacter(character.id, { wod_meta: { ...(character.wod_meta || {}), hunger: h } }),
    startFromMarker: dice.startFromMarker,
    appendMessages: room.appendMessages,
    fetchRoom: room.fetchSince,
    toast,
  });

  const refreshUnread = useCallback(async () => {
    if (playStatus !== 'ready') return;
    const r = await api(`/campaigns/${campaignId}/unread?seen=${encodeURIComponent(seenParam(user ? user.id : null, campaignId, locations))}`);
    if (!r.ok || !Array.isArray(r.data.locations)) return;
    const map = {};
    for (const row of r.data.locations) map[row.location_id] = row;
    setUnread(map);
  }, [api, campaignId, locations, playStatus, user]);

  const unreadTimer = useRef(null);
  const scheduleUnread = useCallback(() => {
    if (unreadTimer.current) clearTimeout(unreadTimer.current);
    unreadTimer.current = setTimeout(refreshUnread, 400);
  }, [refreshUnread]);
  useEffect(() => () => unreadTimer.current && clearTimeout(unreadTimer.current), []);
  useEffect(() => {
    refreshUnread();
  }, [refreshUnread, locationId]);

  const liveMode = useLiveUpdates({
    api,
    campaignId,
    enabled: playStatus === 'ready',
    onChanged: (ev) => {
      if (location && String(ev.location_id) === String(location.id)) {
        if (ev.deleted) room.refresh();
        else room.fetchSince();
      } else scheduleUnread();
    },
    onPoll: () => {
      room.fetchSince();
      scheduleUnread();
    },
  });

  // Read state: reading at the bottom of a visible tab marks the room read.
  useEffect(() => {
    if (!ready || room.status !== 'ready' || !atBottom) return undefined;
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return undefined;
    const h = setTimeout(async () => {
      const changed = await room.markRead();
      if (changed) scheduleUnread();
    }, 700);
    return () => clearTimeout(h);
  }, [ready, room.status, room.messages, atBottom, room.markRead, scheduleUnread]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- keyboard: Alt+↑/↓ previous/next room, Ctrl/⌘+K quick switcher ----
  const ordered = useMemo(() => sortRooms(locations).all, [locations]);
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setSwitcherOpen(true);
        return;
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && ordered.length) {
        e.preventDefault();
        const enterable = ordered.filter((l) => isOpenRoom(l) || canEnterClosed);
        const i = enterable.findIndex((l) => String(l.id) === String(locationId));
        const next = enterable[(i + (e.key === 'ArrowDown' ? 1 : -1) + enterable.length) % enterable.length];
        if (next) navigate(`/c/${campaignId}/${next.id}`);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ordered, locationId, campaignId, canEnterClosed, navigate]);

  // Focus the composer when entering a room (desktop; on phones it would pop the keyboard).
  useEffect(() => {
    if (ready && !isMobile && composerRef.current) composerRef.current.focus();
  }, [ready, locationId, isMobile]);

  // ---- send ----
  const onSend = async (text, local) => {
    if (!ready) return false;
    setAiFailure(null);
    setSending(true);
    try {
      return await sendChatMessage(
        {
          api,
          campaign,
          location,
          user,
          speakAs,
          character,
          onOptimistic: room.addOptimistic,
          onSaved: room.resolveOptimistic,
          onAppend: room.appendMessages,
          onError: (msg) => toast({ tone: 'danger', title: msg }),
          onNotice: (n) => toast({ tone: n.tone, title: n.title, body: n.body, duration: 0 }),
          onAiPending: setAiPending,
          onAiFailed: (f) => setAiFailure({ ...f, locationId: location ? location.id : null }),
          onDiceMarker: dice.startFromMarker,
          onRoomReload: room.refresh,
          onLocationsChanged: play.loadLocations,
        },
        local && local.type === 'me' ? local.text : text,
        local && local.type === 'me' ? { messageType: 'action' } : {}
      );
    } finally {
      setSending(false);
    }
  };

  const onPortrait = async (dataUrl) => {
    if (!character) return;
    const r = await api(`/characters/${character.id}`, { method: 'PUT', body: { portrait_url: dataUrl } });
    if (!r.ok || !r.data.character) {
      toast({ tone: 'danger', title: errorText(r.data, t('play:panel.portraitFailed', 'Could not save the portrait.')) });
      return;
    }
    play.updateCharacter(character.id, r.data.character);
    toast({ tone: 'ok', title: t('play:panel.portraitSaved', 'Portrait updated.') });
  };

  const togglePanel = () => {
    if (!isWide) {
      setPanelDrawer(true);
      return;
    }
    setPanelOpen((o) => {
      writeLocal('sr_member_panel', o ? '0' : '1');
      return !o;
    });
  };

  const showClosed = (loc) => {
    const copy = closedRoomCopy(campaign?.game_system, loc.closure_reason, loc.name);
    setClosedModal(copy);
  };

  // ---- render ----
  if (playStatus === 'error') {
    return (
      <>
        <TopBar title={t('play:title', 'Chronicle')} icon="logo-mark" />
        <div className="sr-loading">
          <EmptyState glyph="lock-chain" title={play.error} action={<ButtonLink to="/chronicles">{t('play:backToHall', 'Back to the hall')}</ButtonLink>} />
        </div>
      </>
    );
  }
  if (playStatus === 'ready' && !location) {
    return <Navigate to={`/c/${campaignId}`} replace />;
  }

  const channelList = campaign ? (
    <ChannelList
      campaign={campaign}
      locations={locations}
      currentId={locationId}
      unread={unread}
      canEnterClosed={canEnterClosed}
      canManage={canStaff}
      onClosed={showClosed}
      onNavigate={() => setNavOpen(false)}
      onQuickSwitch={() => setSwitcherOpen(true)}
    />
  ) : null;

  const memberPanel = campaign ? (
    <MemberPanel
      campaign={campaign}
      character={character}
      members={members}
      user={user}
      canStaff={canStaff}
      isAdmin={isAdmin}
      onOpenSheet={(cid) => openSheet(cid, campaign.game_system)}
      onPortrait={onPortrait}
      onDiceRules={() => setRulesOpen(true)}
      onDiceHistory={() => setHistoryOpen(true)}
      toast={toast}
    />
  ) : null;

  const closed = room.status === 'closed';
  const closedCopy = closed ? closedRoomCopy(campaign?.game_system, room.closedInfo?.message || location?.closure_reason, location?.name) : null;
  const reroll = diceActions.lastV5Roll;

  return (
    <div className="sr-play" data-line={lineOf(campaign?.game_system) || undefined}>
      {!isMobile ? <aside className="sr-play__rooms">{channelList || <Spinner label={t('common:loading', 'Loading')} />}</aside> : null}
      <section className="sr-play__main" aria-labelledby="sr-room-title">
        <TopBar
          titleId="sr-room-title"
          title={location ? location.name : t('common:loading', 'Loading')}
          subtitle={location?.description || (isMobile ? campaign?.name : null)}
          icon={location ? roomGlyph(location.type) : 'logo-mark'}
          onMenu={() => setNavOpen(true)}
          menuLabel={t('play:nav.open', 'Chronicles and rooms')}
          ambient
          actions={
            <>
              {liveMode === 'polling' ? (
                <span className="sr-live sr-live--polling" title={t('play:live.pollingHint', 'Live connection unavailable: checking for new messages every 5 seconds.')}>
                  <Glyph name="moon-crescent" size={14} /> {t('play:live.polling', 'Polling')}
                </span>
              ) : null}
              <IconButton
                icon="users"
                label={isWide && panelOpen ? t('play:panel.hide', 'Hide member list') : t('play:panel.show', 'Show member list')}
                aria-pressed={isWide ? panelOpen : undefined}
                onClick={togglePanel}
              />
            </>
          }
        />
        <div className="sr-play__body">
          <div className="sr-chat">
            {closed ? (
              <div className="sr-chat__closed">
                <EmptyState glyph="lock-chain" title={closedCopy.title} ambient>
                  <p>{closedCopy.lead}</p>
                  <p className="sr-chat__flavor">{room.closedInfo?.flavor || closedCopy.flavor}</p>
                </EmptyState>
              </div>
            ) : (
              <MessageList
                roomKey={`${campaignId}:${locationId}`}
                roomName={location?.name}
                messages={room.messages}
                status={ready ? room.status : 'loading'}
                firstUnreadId={room.firstUnreadId}
                hiddenIds={dice.hiddenMessageIds}
                timeZone={user?.display_timezone || null}
                onAtBottomChange={setAtBottom}
                userId={user?.id}
              />
            )}
            <div className="sr-chat__bottom">
              <div className="sr-chat__typing" aria-live="polite">
                {aiPending ? (
                  <>
                    <CandleHalo lit size={26} tone="arcane" className="sr-chat__typing-avatar">
                      <span className="sr-msg__ai-avatar" style={{ width: 26, height: 26 }}>
                        <AiSigil size={20} className="sr-glyph--essential" />
                      </span>
                    </CandleHalo>
                    <span className="sr-chat__typing-text">{t('chat:weaving', 'The Storyteller is weaving…')}</span>
                  </>
                ) : aiFailure && String(aiFailure.locationId) === String(location?.id) ? (
                  <div className="sr-chat__aifail">
                    <Glyph name="warning" size={18} />
                    <span className="sr-chat__typing-text">
                      {t('chat:aiFailed.title', 'The Storyteller could not answer.')}
                      {aiFailure.reason ? ` ${aiFailure.reason}` : ''}
                    </span>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="reroll"
                      onClick={() => {
                        const { retry } = aiFailure;
                        setAiFailure(null);
                        retry();
                      }}
                    >
                      {t('chat:aiFailed.retry', 'Ask again')}
                    </Button>
                    <IconButton icon="close" size="sm" label={t('common:dismiss', 'Dismiss')} onClick={() => setAiFailure(null)} />
                  </div>
                ) : null}
              </div>
              {reroll && String(reroll.campaignId) === String(campaign?.id) ? (
                <V5RerollPanel
                  key={reroll.roll_id}
                  roll={reroll}
                  busy={diceActions.rerolling}
                  onReroll={diceActions.reroll}
                  onDismiss={() => diceActions.setLastV5Roll(null)}
                  elsewhere={String(reroll.locationId) !== String(location?.id)}
                />
              ) : null}
              <Composer
                inputRef={composerRef}
                draftKey={`${user ? user.id : 'anon'}:${campaignId}:${locationId}`}
                roomName={location?.name || ''}
                speakAs={speakAs}
                voices={voices}
                onSpeakAsChange={changeVoice}
                character={character}
                onSend={onSend}
                onRoll={ready && !closed ? () => setRollOpen(true) : undefined}
                busy={sending}
                disabled={!ready || closed}
                isAdmin={isAdmin}
              />
            </div>
          </div>
          {isWide && panelOpen ? <aside className="sr-play__panel" aria-label={t('play:panel.label', 'Members')}>{memberPanel}</aside> : null}
        </div>
      </section>

      {isMobile ? (
        <Drawer open={navOpen} onClose={() => setNavOpen(false)} side="left" title={t('play:nav.title', 'Chronicles & rooms')} className="sr-play__drawer">
          <div className="sr-play__drawer-body">
            <ChronicleRail onNavigate={() => setNavOpen(false)} />
            {channelList}
          </div>
        </Drawer>
      ) : null}
      {!isWide ? (
        <Drawer open={panelDrawer} onClose={() => setPanelDrawer(false)} side="right" title={t('play:panel.label', 'Members')}>
          {memberPanel}
        </Drawer>
      ) : null}

      <DiceRollOverlay overlay={dice.overlay} onDismiss={dice.dismiss} />
      {campaign && location ? (
        <>
          <RollDialog
            open={rollOpen}
            onClose={() => {
              setRollOpen(false);
              // Back to typing (the dialog would otherwise return focus to the dice button).
              requestAnimationFrame(() => composerRef.current && composerRef.current.focus());
            }}
            campaign={campaign}
            location={location}
            character={character}
            speakAs={speakAs}
            canHide={canStaff}
            isAdmin={isAdmin}
            dice={diceActions}
            onOpenHistory={() => setHistoryOpen(true)}
          />
          <DiceRulesDialog open={rulesOpen} onClose={() => setRulesOpen(false)} api={api} campaign={campaign} location={location} onSaved={play.loadLocations} toast={toast} />
          <DiceHistoryDialog open={historyOpen} onClose={() => setHistoryOpen(false)} api={api} campaign={campaign} location={location} timeZone={user?.display_timezone || null} />
        </>
      ) : null}
      <QuickSwitcher
        open={switcherOpen}
        onClose={() => setSwitcherOpen(false)}
        rooms={ordered.filter((l) => isOpenRoom(l) || canEnterClosed)}
        chronicles={play.chronicles.filter((c) => String(c.id) !== String(campaignId))}
        onPick={(tg) => {
          setSwitcherOpen(false);
          navigate(tg.kind === 'room' ? `/c/${campaignId}/${tg.id}` : `/c/${tg.id}`);
        }}
      />
      <Modal
        open={!!closedModal}
        onClose={() => setClosedModal(null)}
        title={closedModal?.title}
        icon="lock-chain"
        size="sm"
        footer={
          <Button variant="arcane" onClick={() => setClosedModal(null)}>
            {t('play:closed.ok', 'Understood')}
          </Button>
        }
      >
        <p>{closedModal?.lead}</p>
        <p className="sr-chat__flavor">{closedModal?.flavor}</p>
      </Modal>
    </div>
  );
}
