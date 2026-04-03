import React, { useState, useEffect, useLayoutEffect } from 'react';
import AdminPage from './pages/AdminPage';
import GothicShowcase from './pages/GothicShowcase';
import { GothicBox } from './components/GothicDecorations';
import ConfirmDialog from './components/ConfirmDialog';
import Footer from './components/Footer';
import LocationSuggestions from './components/LocationSuggestions';
import CharacterCreationWizard from './components/CharacterCreationWizard';
import { useToast } from './components/ToastNotification';
import { formatMessageTime } from './utils/messageTime';
import { formatDateTimeTooltip, formatDateTimeInZone } from './utils/userTimeFormat';
import { getTimezoneSelectOptions } from './utils/timezones';
import { api } from './utils/api';
import './responsive.css';

const API_URL = '/api'; // Use relative URL through nginx proxy

/** Storyteller (oWoD) pool: `5`, `4+3`, `7-1` — digits with +/− between. */
function parseStorytellerPool(input) {
  const t = String(input || '').replace(/\s/g, '');
  if (!/^\d+([+-]\d+)*$/.test(t)) {
    throw new Error('Pool must be digits with + or - (e.g. 5, 4+3, 7-1).');
  }
  return t.split(/(?=[+-])/).reduce((sum, p) => sum + parseInt(p, 10), 0);
}

/** When a room is closed to players, show thematic copy (aligned with backend `location_closed` flavor). */
function closedLocationPlayerMessage(gameSystem, closureReason, locationName) {
  const gs = (gameSystem || '').toLowerCase();
  const reason = (closureReason || '').trim();
  const label = locationName || 'This location';
  const lead = reason
    ? `${label} is sealed — “${reason}”`
    : `${label} is sealed until the Storyteller reopens it.`;
  let flavor = 'The table has called cut on this scene.';
  if (gs.includes('vampire') || gs.includes('masquerade')) {
    flavor = 'Even the oldest Kindred must wait when the Prince locks Elysium’s doors.';
  } else if (gs.includes('werewolf') || gs.includes('garou') || gs.includes('apocalypse')) {
    flavor = 'The caern’s pulse says “hunt elsewhere tonight.”';
  } else if (gs.includes('mage') || gs.includes('ascension') || gs.includes('awakening')) {
    flavor = 'The Consensus politely declines your Paradigm until further notice.';
  }
  return { title: `${label} — unavailable`, lead, flavor };
}

/** Strip BOM; bare `/ai` → `/ai help` for admins */
function normalizeChatMessageInput(raw, isAdmin) {
  const s = String(raw ?? '').replace(/^\uFEFF+/, '').trim();
  if (!s) return s;
  if (isAdmin && /^\s*\/ai\s*$/i.test(s)) return '/ai help';
  return s;
}

function GothicPageLoadingOverlay({ visible, label }) {
  if (!visible) return null;
  return (
    <div className="sr-page-loading-overlay" role="status" aria-live="polite" aria-busy="true">
      <div className="sr-page-loading-card">
        <div className="sr-page-loading-rune" aria-hidden />
        <div className="sr-page-loading-title">ShadowRealms</div>
        <div className="sr-page-loading-sub">{label || 'One moment…'}</div>
      </div>
    </div>
  );
}

function MessageCharacterAvatar({ url, size = 40 }) {
  const [broken, setBroken] = React.useState(false);
  const frame = {
    width: size,
    height: size,
    borderRadius: '8px',
    flexShrink: 0,
    border: '1px solid #2a2a4e',
    background: '#0f1729',
  };
  if (url && !broken) {
    return (
      <img
        src={url}
        alt=""
        style={{ ...frame, objectFit: 'cover' }}
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" style={frame} aria-hidden>
      <rect fill="#1e293b" width="40" height="40" rx="8" />
      <circle cx="20" cy="14" r="6" fill="#64748b" />
      <ellipse cx="20" cy="30" rx="12" ry="8" fill="#64748b" />
    </svg>
  );
}

/** Fixed chat bubble palette: AI Storyteller vs in-character vs neutral (e.g. admin without a mask). */
const CHAT_BUBBLE_AI = {
  bg: 'rgba(157, 78, 221, 0.12)',
  border: '#9d4edd',
  nameColor: '#c4b5fd',
  icon: 'fa-robot',
  italic: true,
};

const CHAT_BUBBLE_PLAYER = {
  bg: 'rgba(20, 184, 166, 0.1)',
  border: '#14b8a6',
  nameColor: '#5eead4',
  icon: 'fa-user',
  italic: false,
};

const CHAT_BUBBLE_NEUTRAL = {
  bg: 'rgba(71, 85, 105, 0.14)',
  border: '#64748b',
  nameColor: '#cbd5e1',
  icon: 'fa-user',
  italic: false,
};

function getChatMessagePresentation(msg) {
  const isAI = msg.role === 'assistant';
  if (isAI) {
    return {
      ...CHAT_BUBBLE_AI,
      label: 'AI Storyteller',
      subLabel: null,
    };
  }
  const uname = (msg.username || '').trim() || 'Player';
  const charName = (msg.character_name || '').trim();
  const hasCharacter =
    !!charName ||
    (msg.character_id != null && msg.character_id !== '' && Number(msg.character_id) > 0);
  const posterRole = String(msg.poster_role || '').toLowerCase();

  if (hasCharacter) {
    const display = charName || 'Character';
    return {
      ...CHAT_BUBBLE_PLAYER,
      label: `${display} – ${uname}`,
      subLabel: null,
    };
  }

  const isAdminPoster = posterRole === 'admin';
  return {
    ...CHAT_BUBBLE_NEUTRAL,
    icon: isAdminPoster ? 'fa-user-shield' : CHAT_BUBBLE_NEUTRAL.icon,
    nameColor: isAdminPoster ? '#94a3b8' : CHAT_BUBBLE_NEUTRAL.nameColor,
    label: uname,
    subLabel: isAdminPoster ? 'Site admin' : null,
  };
}

function SimpleApp() {
  // Initialize toast notification system
  const { showInfo, showError, showSuccess, ToastContainer } = useToast();
  
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [showGothicShowcase, setShowGothicShowcase] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState(null);
  const [locations, setLocations] = useState([]);
  const [currentLocation, setCurrentLocation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [character, setCharacter] = useState(null);
  const [campaignCharacters, setCampaignCharacters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pageOverlay, setPageOverlay] = useState({ visible: false, label: '' });
  const [error, setError] = useState('');
  
  // Ref for chat input to maintain focus
  const chatInputRef = React.useRef(null);
  const chatMessagesScrollRef = React.useRef(null);
  const chatScrollAppliedForLocationRef = React.useRef(null);
  const messagesRef = React.useRef(messages);
  const loadingRef = React.useRef(loading);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  /** After user sends (or roll posts), scroll so the new line is in view — chat-app behavior. */
  const scrollChatToBottomSoon = React.useCallback(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = chatMessagesScrollRef.current;
        if (el) el.scrollTop = el.scrollHeight;
      });
    });
  }, []);
  
  // Campaign editing state
  const [isEditingCampaignName, setIsEditingCampaignName] = useState(false);
  const [editedCampaignName, setEditedCampaignName] = useState('');
  const [isEditingCampaignDesc, setIsEditingCampaignDesc] = useState(false);
  const [editedCampaignDesc, setEditedCampaignDesc] = useState('');
  
  // Mobile responsive state
  /** Set after mount via matchMedia to avoid layout reads during first paint (FOUC / Firefox warnings). */
  const [isMobile, setIsMobile] = useState(false);
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(false);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);
  
  // Confirmation dialog state
  const [showExitConfirm, setShowExitConfirm] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState(null);
  
  // Location suggestions state
  const [showLocationSuggestions, setShowLocationSuggestions] = useState(false);
  const [newCampaignData, setNewCampaignData] = useState(null);
  const [campaignStats, setCampaignStats] = useState({
    active_players: 0,
    characters: 0,
    locations: 0,
    messages: 0
  });
  /** Full membership list for character creation wizard (WoD). */
  const [wizardCampaigns, setWizardCampaigns] = useState([]);
  const [playerCharacters, setPlayerCharacters] = useState([]);
  const [downtimeMine, setDowntimeMine] = useState([]);
  const [downtimeDraft, setDowntimeDraft] = useState('');
  const [downtimeSending, setDowntimeSending] = useState(false);
  const [locationReadState, setLocationReadState] = useState(null);
  const [firstUnreadMessageId, setFirstUnreadMessageId] = useState(null);
  /** Set when loadMessages succeeds; must match currentLocation.id before applying scroll. */
  const [messagesSyncedLocationId, setMessagesSyncedLocationId] = useState(null);
  const [chatNow, setChatNow] = useState(() => new Date());
  const [showRollModal, setShowRollModal] = useState(false);
  const [rollPoolInput, setRollPoolInput] = useState('5');
  const [rollDifficulty, setRollDifficulty] = useState(6);
  const [rollSpecialty, setRollSpecialty] = useState(false);
  const [rollReason, setRollReason] = useState('');
  const [rollHideOthers, setRollHideOthers] = useState(false);
  const [rollSubmitting, setRollSubmitting] = useState(false);
  const [showDiceHistoryModal, setShowDiceHistoryModal] = useState(false);
  const [diceHistoryLoading, setDiceHistoryLoading] = useState(false);
  const [diceHistoryRows, setDiceHistoryRows] = useState([]);
  const [diceHistoryError, setDiceHistoryError] = useState(null);
  const [discoverCampaignsList, setDiscoverCampaignsList] = useState([]);

  // Dice animation overlay (Baldur's Gate-ish feel).
  // We drive it via special marker/final messages stored in `messages.ai_message_kind`.
  const [diceOverlay, setDiceOverlay] = useState({
    visible: false,
    animationId: null,
    startedAtMs: 0,
    revealAtMs: 0,
    durationMs: 3000,
    difficulty: 6,
    diceFinal: [],
    diceRolling: [],
    extraDiceCount: 0,
    successes: 0,
    isBotch: false,
    isCritical: false,
    poolSize: 0,
  });
  const [pendingDiceAnimations, setPendingDiceAnimations] = useState({});
  const processedDiceAnimationsRef = React.useRef(new Set());
  const diceRollingIntervalRef = React.useRef(null);
  const diceRevealTimeoutRef = React.useRef(null);
  const dicePendingTimeoutsRef = React.useRef({});
  const [showAdminDiceRulesModal, setShowAdminDiceRulesModal] = useState(false);
  const [adminDiceFloorDraft, setAdminDiceFloorDraft] = useState('');
  const [adminDiceSaving, setAdminDiceSaving] = useState(false);
  const [profileTzDraft, setProfileTzDraft] = useState('');
  const [profileTzSaving, setProfileTzSaving] = useState(false);

  const renderMessageContent = (content) => {
    const text = String(content ?? '');

    // Safe, dependency-free "lite markdown" renderer.
    // Supports: **bold**, *italic*, `code`, and preserves newlines.
    const tokenRegex = /(\*\*[^*\n]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)/g;

    const renderInline = (line, lineKey) => {
      const parts = line.split(tokenRegex);
      return parts.map((part, i) => {
        const key = `${lineKey}-${i}`;
        if (!part) return null;

        if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
          return <strong key={key}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
          return <em key={key}>{part.slice(1, -1)}</em>;
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
          return (
            <code
              key={key}
              style={{
                background: 'rgba(0,0,0,0.35)',
                padding: '2px 6px',
                borderRadius: '6px',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                fontSize: '0.95em'
              }}
            >
              {part.slice(1, -1)}
            </code>
          );
        }

        return <React.Fragment key={key}>{part}</React.Fragment>;
      });
    };

    const lines = text.split('\n');
    return (
      <>
        {lines.map((line, idx) => (
          <React.Fragment key={idx}>
            {renderInline(line, idx)}
            {idx < lines.length - 1 ? <br /> : null}
          </React.Fragment>
        ))}
      </>
    );
  };

  const _randomD10 = () => Math.floor(Math.random() * 10) + 1;
  const _makeDiceAnimationId = () => `dice_${Date.now()}_${Math.random().toString(16).slice(2)}`;

  const startDiceAnimationFromMarker = (markerObj) => {
    if (!markerObj || typeof markerObj !== 'object') return;
    const animationId = markerObj.animation_id || markerObj.animationId;
    if (!animationId) return;
    const alreadyProcessed = processedDiceAnimationsRef.current.has(String(animationId));
    if (alreadyProcessed) return;
    processedDiceAnimationsRef.current.add(String(animationId));

    const startedAtMs = Number(markerObj.started_at_ms || markerObj.startedAtMs || Date.now());
    const durationMs = Number(markerObj.duration_ms || markerObj.durationMs || 3000);
    const revealAtMs = startedAtMs + durationMs;
    const remainingMs = revealAtMs - Date.now();

    const animId = String(animationId);

    // Hide the final message immediately (even if we haven't rendered yet).
    setPendingDiceAnimations((prev) => ({ ...prev, [animId]: true }));

    const diceFinal = Array.isArray(markerObj.dice_preview)
      ? markerObj.dice_preview
      : Array.isArray(markerObj.diceFinal)
        ? markerObj.diceFinal
        : [];
    const extraDiceCount = Number(markerObj.extra_dice_count || markerObj.extraDiceCount || 0);

    // If we missed the window (poll delay), don't animate — just reveal.
    if (remainingMs <= 0) {
      setPendingDiceAnimations((prev) => {
        const next = { ...prev };
        delete next[animId];
        return next;
      });
      if (dicePendingTimeoutsRef.current[animId]) {
        clearTimeout(dicePendingTimeoutsRef.current[animId]);
        delete dicePendingTimeoutsRef.current[animId];
      }
      return;
    }

    // Each animation schedules its own reveal time (so overlapping rolls don't get stuck).
    if (dicePendingTimeoutsRef.current[animId]) {
      clearTimeout(dicePendingTimeoutsRef.current[animId]);
    }
    dicePendingTimeoutsRef.current[animId] = setTimeout(() => {
      setPendingDiceAnimations((prev) => {
        const next = { ...prev };
        delete next[animId];
        return next;
      });
      delete dicePendingTimeoutsRef.current[animId];
    }, Math.max(0, remainingMs));

    setDiceOverlay({
      visible: true,
      animationId: animId,
      startedAtMs,
      revealAtMs,
      durationMs,
      difficulty: Number(markerObj.difficulty || 6),
      diceFinal,
      diceRolling: diceFinal.map(() => _randomD10()),
      extraDiceCount,
      successes: Number(markerObj.successes || 0),
      isBotch: Boolean(markerObj.is_botch || markerObj.isBotch || false),
      isCritical: Boolean(markerObj.is_critical || markerObj.isCritical || false),
      poolSize: Number(markerObj.pool_size || markerObj.poolSize || diceFinal.length),
    });
  };

  // Drive the overlay's rolling → settle transition.
  useEffect(() => {
    if (!diceOverlay.visible || !diceOverlay.animationId) return;

    const animId = String(diceOverlay.animationId);
    const finalValues = Array.isArray(diceOverlay.diceFinal) ? diceOverlay.diceFinal : [];
    const diceCount = Math.max(1, finalValues.length);
    const revealAtMs = Number(diceOverlay.revealAtMs || (Date.now() + diceOverlay.durationMs));

    // Clear any previous animation timers.
    if (diceRollingIntervalRef.current) clearInterval(diceRollingIntervalRef.current);
    if (diceRevealTimeoutRef.current) clearTimeout(diceRevealTimeoutRef.current);

    const remainingMs = revealAtMs - Date.now();
    const rollIntervalMs = 90;

    diceRollingIntervalRef.current = setInterval(() => {
      setDiceOverlay((prev) => ({
        ...prev,
        diceRolling: Array.from({ length: diceCount }, () => _randomD10()),
      }));
    }, rollIntervalMs);

    diceRevealTimeoutRef.current = setTimeout(() => {
      if (diceRollingIntervalRef.current) clearInterval(diceRollingIntervalRef.current);
      setDiceOverlay((prev) => ({
        ...prev,
        visible: false,
        diceRolling: finalValues,
      }));
      // After reveal, ensure the final dice roll line is in view.
      scrollChatToBottomSoon();
    }, Math.max(0, remainingMs));

    return () => {
      if (diceRollingIntervalRef.current) clearInterval(diceRollingIntervalRef.current);
      if (diceRevealTimeoutRef.current) clearTimeout(diceRevealTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diceOverlay.animationId]);

  const diceMarkerRevealAtById = React.useMemo(() => {
    const map = {};
    for (const m of messages || []) {
      const mk = (m.ai_message_kind || '').toLowerCase();
      if (!mk.startsWith('dice_animation:') && !mk.startsWith('dice_animation_hidden:')) continue;
      const parts = mk.split(':');
      const animationId = parts.length >= 2 ? parts[1] : null;
      if (!animationId) continue;
      let obj = null;
      try {
        obj = typeof m.content === 'string' ? JSON.parse(m.content) : m.content;
      } catch {
        obj = null;
      }
      if (!obj || typeof obj !== 'object') continue;
      const startedAtMs = Number(obj.started_at_ms || obj.startedAtMs || 0);
      const durationMs = Number(obj.duration_ms || obj.durationMs || 3000);
      if (!Number.isFinite(startedAtMs) || startedAtMs <= 0) continue;
      map[String(animationId)] = startedAtMs + durationMs;
    }
    return map;
  }, [messages]);

  // Scan for dice animation marker messages and start overlay when they arrive.
  useEffect(() => {
    if (currentPage !== 'chat') return;
    if (!Array.isArray(messages) || messages.length === 0) return;

    const markerMsgs = messages.filter((m) => {
      const mk = (m.ai_message_kind || '').toLowerCase();
      return mk.startsWith('dice_animation:') || mk.startsWith('dice_animation_hidden:');
    });

    for (const mm of markerMsgs) {
      const mk = (mm.ai_message_kind || '').toLowerCase();
      const parts = mk.split(':');
      const animationIdFromKind = parts.length >= 2 ? parts[1] : null;

      let markerObj = null;
      try {
        markerObj = typeof mm.content === 'string' ? JSON.parse(mm.content) : mm.content;
      } catch {
        markerObj = null;
      }
      if (!markerObj) continue;
      if (!markerObj.animation_id && animationIdFromKind) markerObj.animation_id = animationIdFromKind;

      startDiceAnimationFromMarker(markerObj);
    }
    // Intentionally only depend on messages; startDiceAnimationFromMarker is stable via closures.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, currentPage]);
  
  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [showLocationManager, setShowLocationManager] = useState(false);
  const [campaignLocations, setCampaignLocations] = useState([]);
  const [locEdits, setLocEdits] = useState({});
  const [closedRoomModal, setClosedRoomModal] = useState(null);
  const [showLocationDeleteConfirm, setShowLocationDeleteConfirm] = useState(false);
  const [locationToDelete, setLocationToDelete] = useState(null);

  // Load user data on mount
  useEffect(() => {
    if (token) {
      fetchUserData();
    }
  }, [token]);

  useEffect(() => {
    if (user) {
      setProfileTzDraft(user.display_timezone || '');
    }
  }, [user?.id, user?.display_timezone]);

  // Viewport: matchMedia before paint where possible; avoids early innerWidth layout reads
  useLayoutEffect(() => {
    const mql = window.matchMedia('(max-width: 767px)');
    const apply = () => {
      const mobile = mql.matches;
      setIsMobile(mobile);
      if (!mobile) {
        setLeftSidebarOpen(false);
        setRightSidebarOpen(false);
      }
    };
    apply();
    mql.addEventListener('change', apply);
    return () => mql.removeEventListener('change', apply);
  }, []);

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = (event) => {
      // If leaving chat page, show confirmation
      if (currentPage === 'chat' && event.state && event.state.page !== 'chat') {
        // Store the pending navigation
        setPendingNavigation(event.state);
        // Show custom confirmation dialog
        setShowExitConfirm(true);
        // Push current state back temporarily until user confirms
        window.history.pushState(
          { page: 'chat', selectedCampaign }, 
          '', 
          window.location.pathname
        );
        return;
      }
      
      if (event.state) {
        setCurrentPage(event.state.page || 'dashboard');
        setShowGothicShowcase(event.state.showGothicShowcase || false);
        if (event.state.selectedCampaign) {
          setSelectedCampaign(event.state.selectedCampaign);
        }
      }
    };

    window.addEventListener('popstate', handlePopState);
    
    // Set initial state if not already set
    if (!window.history.state) {
      window.history.replaceState({ page: currentPage, showGothicShowcase }, '');
    }

    return () => window.removeEventListener('popstate', handlePopState);
  }, [currentPage, currentLocation, selectedCampaign]);

  // Navigate with browser history support
  const navigateTo = (page, campaign = null) => {
    const state = { 
      page, 
      showGothicShowcase: false,
      selectedCampaign: campaign 
    };
    window.history.pushState(state, '', window.location.pathname);
    setCurrentPage(page);
    if (campaign) {
      setSelectedCampaign(campaign);
    }
  };

  const showShowcase = (show) => {
    const state = { 
      page: currentPage,
      showGothicShowcase: show,
      selectedCampaign
    };
    if (show) {
      window.history.pushState(state, '', window.location.pathname);
    }
    setShowGothicShowcase(show);
  };

  // Fetch user data (returns /me JSON or null)
  const fetchUserData = async () => {
    try {
      const response = await fetch(`${API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data)); // Persist user data
        return data;
      } else if (response.status === 401) {
        // Token expired or invalid, force logout
        console.error('Token expired or invalid');
        handleLogout();
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    }
    return null;
  };

  // Fetch campaigns (for_active_character=1 filters to active PC’s chronicle when set)
  const fetchCampaigns = async (authToken, opts = {}) => {
    const t = authToken ?? token;
    if (!t) return;
    const q =
      opts.forActiveCharacter === true ? '?for_active_character=1' : '';
    try {
      const response = await fetch(`${API_URL}/campaigns/${q}`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (response.ok) {
        const data = await response.json();
        // Backend returns array directly, not wrapped in object
        setCampaigns(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('Failed to load campaigns:', err);
      setError('Failed to load campaigns');
    }
  };

  const hydrateSessionAfterAuth = async (accessToken) => {
    if (!accessToken) return null;
    try {
      const r = await fetch(`${API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!r.ok) return null;
      const me = await r.json();
      setUser(me);
      localStorage.setItem('user', JSON.stringify(me));
      const owned = me.statistics?.characters_owned ?? 0;
      if (owned > 0 && (me.active_character_id == null || me.active_character_id === '')) {
        setCurrentPage('selectCharacter');
      } else {
        setCurrentPage('dashboard');
        await fetchCampaigns(accessToken, { forActiveCharacter: true });
      }
      return me;
    } catch (e) {
      console.error('hydrateSessionAfterAuth', e);
      return null;
    }
  };

  const applyActiveCharacter = async (characterId) => {
    if (!token) return;
    try {
      const r = await fetch(`${API_URL}/users/me`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ active_character_id: characterId }),
      });
      const errBody = await r.json().catch(() => ({}));
      if (!r.ok) {
        if (r.status === 403 && errBody.error_code === 'character_suspended') {
          showError(
            [errBody.message, errBody.contact_hint].filter(Boolean).join('\n\n')
          );
        } else {
          showError(errBody.error || 'Could not set active character');
        }
        return;
      }
      setUser(errBody);
      localStorage.setItem('user', JSON.stringify(errBody));
      setCurrentPage('dashboard');
      await fetchCampaigns(token, { forActiveCharacter: true });
      showSuccess('Active character updated.');
    } catch (e) {
      showError('Connection error while saving active character');
    }
  };

  const fetchCampaignStats = async (campaignId) => {
    if (!campaignId) return;
    try {
      const response = await fetch(`${API_URL}/campaigns/${campaignId}/stats`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        console.error('Failed to load campaign stats:', await response.text());
        return;
      }
      const data = await response.json();
      setCampaignStats({
        active_players: data.active_players ?? 0,
        characters: data.characters ?? 0,
        locations: data.locations ?? 0,
        messages: data.messages ?? 0
      });
    } catch (error) {
      console.error('Error fetching campaign stats:', error);
    }
  };

  const handleJoinDiscoverCampaign = async (campaignId) => {
    try {
      const r = await api.joinCampaign(token, campaignId);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        showError(d.error || 'Could not join this chronicle');
        return;
      }
      showSuccess('You have joined this chronicle.');
      fetchCampaigns(undefined, { forActiveCharacter: true });
      const r2 = await api.discoverCampaigns(token);
      if (r2.ok) {
        const d2 = await r2.json();
        setDiscoverCampaignsList(Array.isArray(d2) ? d2 : []);
      }
    } catch (e) {
      showError('Connection error');
    }
  };

  const handleSaveEnrollmentSettings = async (e) => {
    e.preventDefault();
    if (!selectedCampaign?.id) return;
    const fd = new FormData(e.target);
    const listing = (fd.get('listing_visibility') || 'private').toString();
    const accepting = fd.get('accepting_players') === 'on';
    const maxRaw = fd.get('max_players');
    let maxPlayers = selectedCampaign.max_players;
    if (maxRaw !== '' && maxRaw != null) {
      const n = parseInt(maxRaw, 10);
      if (Number.isFinite(n) && n >= 0) maxPlayers = n;
    }
    try {
      setLoading(true);
      const r = await api.updateCampaign(token, selectedCampaign.id, {
        listing_visibility: listing,
        accepting_players: accepting,
        max_players: maxPlayers,
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        showError(d.error || 'Save failed');
        return;
      }
      const r2 = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r2.ok) {
        const upd = await r2.json();
        setSelectedCampaign((prev) => ({ ...prev, ...upd }));
      }
      showSuccess('Enrollment settings saved');
    } catch (err) {
      showError('Save failed');
    } finally {
      setLoading(false);
    }
  };

  // Load campaigns when dashboard is shown
  useEffect(() => {
    if (currentPage === 'dashboard' && token) {
      fetchCampaigns(undefined, { forActiveCharacter: true });
    }
  }, [currentPage, token]);

  useEffect(() => {
    if (currentPage !== 'dashboard' || !token) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.discoverCampaigns(token);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled) setDiscoverCampaignsList(Array.isArray(d) ? d : []);
      } catch (_) {
        if (!cancelled) setDiscoverCampaignsList([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [currentPage, token]);

  // WoD character wizard: need every chronicle the user can join (membership / ownership)
  useEffect(() => {
    if (currentPage !== 'characterCreate' || !token) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/campaigns/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled) setWizardCampaigns(Array.isArray(d) ? d : []);
      } catch (_) {}
    })();
    return () => {
      cancelled = true;
    };
  }, [currentPage, token]);

  useEffect(() => {
    if (!token || !['selectCharacter', 'playerProfile'].includes(currentPage)) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/characters/`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (r.ok && !cancelled) {
          const d = await r.json();
          setPlayerCharacters(Array.isArray(d.characters) ? d.characters : []);
        }
        if (currentPage === 'playerProfile') {
          const r2 = await fetch(`${API_URL}/characters/downtime-requests/mine`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (r2.ok && !cancelled) {
            const d2 = await r2.json();
            setDowntimeMine(Array.isArray(d2.requests) ? d2.requests : []);
          }
        }
      } catch (_) {}
    })();
    return () => {
      cancelled = true;
    };
  }, [currentPage, token]);

  // Require character selection when the account already has PCs but none active
  useEffect(() => {
    if (!token || !user) return;
    const owned = user.statistics?.characters_owned ?? 0;
    if (
      owned > 0 &&
      (user.active_character_id == null || user.active_character_id === '') &&
      currentPage === 'dashboard'
    ) {
      setCurrentPage('selectCharacter');
    }
  }, [token, user?.active_character_id, user?.statistics?.characters_owned, currentPage]);

  // Auto-focus chat input when entering a location
  useEffect(() => {
    if (currentLocation && chatInputRef.current) {
      // Small delay to ensure DOM is ready
      setTimeout(() => {
        if (chatInputRef.current) {
          chatInputRef.current.focus();
        }
      }, 100);
    }
  }, [currentLocation]);

  // Handle login
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setPageOverlay({ visible: true, label: 'The gates recognize your name…' });

    const formData = new FormData(e.target);
    const credentials = {
      username: formData.get('username'),
      password: formData.get('password')
    };

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.access_token);
        localStorage.setItem('token', data.access_token);
        setError('');
        setPageOverlay({ visible: true, label: 'Summoning your chronicles…' });
        await hydrateSessionAfterAuth(data.access_token);
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setPageOverlay({ visible: false, label: '' });
      setLoading(false);
    }
  };

  // Handle register
  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setPageOverlay({ visible: true, label: 'Forging your shadow…' });

    const formData = new FormData(e.target);
    const userData = {
      username: formData.get('username'),
      email: formData.get('email'),
      password: formData.get('password'),
      invite_code: formData.get('invite_code')
    };

    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });

      const data = await response.json();

      if (response.ok) {
        setToken(data.access_token);
        localStorage.setItem('token', data.access_token);
        setError('');
        showSuccess('✅ Account created! Check your email for a welcome message (if SMTP is configured).');
        setPageOverlay({ visible: true, label: 'Summoning your chronicles…' });
        await hydrateSessionAfterAuth(data.access_token);
      } else {
        setError(data.error || 'Registration failed');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setPageOverlay({ visible: false, label: '' });
      setLoading(false);
    }
  };

  // Handle logout
  const handleLogout = () => {
    setToken(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user'); // Clear persisted user data
    setUser(null);
    setCurrentPage('dashboard');
    setCampaigns([]);
    setSelectedCampaign(null);
  };

  // Handle create campaign
  const handleCreateCampaign = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setPageOverlay({ visible: true, label: 'Weaving a new chronicle…' });

    const formData = new FormData(e.target);
    const campaignData = {
      name: formData.get('campaignName'),
      description: formData.get('description'),
      game_system: formData.get('game_system')
    };

    try {
      const response = await fetch(`${API_URL}/campaigns`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(campaignData)
      });

      const data = await response.json();

      if (response.ok) {
        console.log('✅ Campaign created:', data);
        const createdCampaign = {
          id: data.campaign_id, // Backend returns campaign_id
          name: campaignData.name,
          description: campaignData.description,
          game_system: campaignData.game_system
        };
        showSuccess('✅ Campaign created successfully!');
        e.target.reset();
        await fetchCampaigns(undefined, { forActiveCharacter: true });
        setSelectedCampaign(createdCampaign);
        navigateTo('campaignDetails', createdCampaign);
      } else {
        setError(data.error || 'Failed to create campaign');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setPageOverlay({ visible: false, label: '' });
      setLoading(false);
    }
  };

  // Fetch locations for a campaign from database
  const fetchCampaignLocations = async (campaignId) => {
    try {
      const response = await fetch(`${API_URL}/campaigns/${campaignId}/locations`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`📍 Loaded ${data.length} locations for campaign ${campaignId}`);
        return data;
      } else {
        console.error('Failed to load locations:', await response.text());
        return [];
      }
    } catch (error) {
      console.error('Error fetching locations:', error);
      return [];
    }
  };

  // Function to load locations for location manager
  const loadCampaignLocationsForManager = async (campaignId) => {
    try {
      const locations = await fetchCampaignLocations(campaignId);
      setCampaignLocations(locations);
    } catch (error) {
      console.error('Error loading campaign locations:', error);
      showError('Failed to load locations');
    }
  };

  // Function to trigger location delete confirmation
  const handleDeleteLocation = (locationId) => {
    setLocationToDelete(locationId);
    setShowLocationDeleteConfirm(true);
  };

  // Function to execute location deletion after confirmation
  const executeDeleteLocation = async () => {
    if (!locationToDelete) return;

    // Close confirmation modal immediately
    setShowLocationDeleteConfirm(false);
    const locationId = locationToDelete;
    setLocationToDelete(null);

    try {
      setLoading(true);
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/locations/${locationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMsg = errorData.error || `Failed to delete location (${response.status})`;
        throw new Error(errorMsg);
      }

      const data = await response.json();
      console.log('✅ Location deleted:', data);
      
      showSuccess('✅ Location deleted successfully!');
      
      // Reload locations list
      await loadCampaignLocationsForManager(selectedCampaign.id);
      
    } catch (error) {
      console.error('❌ Error deleting location:', error);
      showError(`❌ ${error.message || 'Failed to delete location'}`);
    } finally {
      setLoading(false);
    }
  };

  const userCanBypassClosedLocation = () => {
    if (!user || !selectedCampaign) return false;
    const role = String(user.role || '').toLowerCase();
    if (role === 'admin' || role === 'helper') return true;
    const uid = Number(user.id);
    const st = Number(selectedCampaign.created_by);
    return Number.isFinite(uid) && Number.isFinite(st) && uid === st;
  };

  const canEditLocationAccess =
    !!user &&
    !!selectedCampaign &&
    (String(user.role || '').toLowerCase() === 'admin' ||
      Number(user.id) === Number(selectedCampaign.created_by));

  useEffect(() => {
    if (!showLocationManager || !campaignLocations.length) return;
    const next = {};
    campaignLocations.forEach((l) => {
      next[l.id] = {
        is_open: l.is_open !== false && l.is_open !== 0,
        closure_reason: l.closure_reason || '',
      };
    });
    setLocEdits(next);
  }, [showLocationManager, campaignLocations]);

  const saveLocationAccess = async (locationId) => {
    const draft = locEdits[locationId];
    if (!draft) return;
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/locations/${locationId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          is_open: draft.is_open,
          closure_reason: draft.closure_reason || '',
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `Save failed (${res.status})`);
      }
      showSuccess('Location access updated');
      await loadCampaignLocationsForManager(selectedCampaign.id);
      const locs = await fetchCampaignLocations(selectedCampaign.id);
      setLocations(locs);
      if (currentLocation?.id === locationId) {
        const updated = locs.find((x) => x.id === locationId);
        if (updated) setCurrentLocation(updated);
      }
    } catch (e) {
      showError(e.message || 'Failed to save');
    } finally {
      setLoading(false);
    }
  };

  // Function to open location manager
  const openLocationManager = async () => {
    await loadCampaignLocationsForManager(selectedCampaign.id);
    setShowLocationManager(true);
  };

  // Function to trigger AI location suggestions for existing campaign
  const handleAddLocationsWithAI = () => {
    setNewCampaignData(selectedCampaign); // Reuse the same component
    setShowLocationSuggestions(true);
    setShowLocationManager(false); // Close manager while showing suggestions
  };

  // Callback when AI suggestions are completed (for existing campaign)
  const handleLocationSuggestionsComplete = async () => {
    setShowLocationSuggestions(false);
    setNewCampaignData(null);
    // Reload locations and reopen manager
    await loadCampaignLocationsForManager(selectedCampaign.id);
    setShowLocationManager(true);
    showSuccess('New locations added successfully!');
  };

  const fetchCampaignCharactersList = async (campaignId) => {
    try {
      const response = await fetch(`${API_URL}/characters/?campaign_id=${campaignId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return [];
      const data = await response.json();
      return Array.isArray(data.characters) ? data.characters : [];
    } catch (err) {
      console.error('Failed to load campaign characters:', err);
      return [];
    }
  };

  // Enter campaign (load locations from database and switch to chat view)
  const enterCampaign = async (campaign) => {
    setPageOverlay({ visible: true, label: 'Crossing into the chronicle…' });
    try {
      // We need `created_by` (campaign creator) to enable storyteller/admin-only UI,
      // like hidden dice rolls visibility.
      let campaignWithCreator = campaign;
      try {
        const detailRes = await fetch(`${API_URL}/campaigns/${campaign.id}`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (detailRes.status === 403) {
          const errBody = await detailRes.json().catch(() => ({}));
          if (errBody.error_code === 'character_suspended') {
            showError(
              [errBody.message, errBody.contact_hint].filter(Boolean).join('\n\n')
            );
            setPageOverlay({ visible: false, label: '' });
            return;
          }
        }
        if (detailRes.ok) {
          const detail = await detailRes.json();
          campaignWithCreator = { ...campaign, ...detail };
        }
      } catch {
        // If the detail fetch fails, we still let the user enter the campaign.
      }
      setSelectedCampaign(campaignWithCreator);

      const chars = await fetchCampaignCharactersList(campaign.id);
      setCampaignCharacters(chars);
      const aid = user?.active_character_id;
      let primary = null;
      if (aid != null && aid !== '') {
        primary = chars.find((c) => c.id === aid) || null;
      }
      if (!primary) {
        primary = chars[0] || null;
      }
      if (aid != null && aid !== '' && !primary) {
        showError(
          'Your active character is not part of this chronicle. Open Player Profile and select a character that belongs here.'
        );
        setPageOverlay({ visible: false, label: '' });
        return;
      }
      setCharacter(primary);

      setPageOverlay({ visible: true, label: 'Gathering places and whispers…' });
      const campaignLocations = await fetchCampaignLocations(campaign.id);

      let initialLocation = null;
      if (campaignLocations.length > 0) {
        setLocations(campaignLocations);
        const oocLocation = campaignLocations.find(
          (loc) => String(loc.type || '').toLowerCase() === 'ooc'
        );
        initialLocation = oocLocation || campaignLocations[0];
        setCurrentLocation(initialLocation);
      } else {
        console.warn('⚠️ No locations found for campaign, using fallback');
        const fallbackLoc = { id: 0, name: '💬 OOC Chat', type: 'ooc' };
        setLocations([fallbackLoc]);
        setCurrentLocation(fallbackLoc);
        initialLocation = fallbackLoc;
      }

      if (initialLocation && initialLocation.id) {
        setPageOverlay({ visible: true, label: 'Unsealing this room…' });
        await loadMessages(campaign.id, initialLocation.id, { characterForRead: primary });
      }

      navigateTo('chat', campaignWithCreator);
    } catch (err) {
      console.error(err);
      showError('Could not open this campaign. Try again.');
    } finally {
      setPageOverlay({ visible: false, label: '' });
    }
  };

  // When viewing campaign settings, load stats for the selected campaign
  useEffect(() => {
    if (token && currentPage === 'campaignDetails' && selectedCampaign?.id) {
      fetchCampaignStats(selectedCampaign.id);
    }
  }, [token, currentPage, selectedCampaign?.id]);

  // Handle leaving chat with confirmation
  const handleLeaveCampaign = () => {
    setShowExitConfirm(true);
  };

  // Confirm exit from campaign
  const confirmLeaveCampaign = () => {
    setShowExitConfirm(false);
    navigateTo('dashboard');
    setSelectedCampaign(null);
    setCurrentLocation(null);
    setLocations([]);
    setMessages([]);
    setMessagesSyncedLocationId(null);
    setCampaignCharacters([]);
    setCharacter(null);
    if (pendingNavigation) {
      setPendingNavigation(null);
    }
  };

  // Cancel exit from campaign
  const cancelLeaveCampaign = () => {
    setShowExitConfirm(false);
    // If there was a pending navigation (from back button), restore chat state
    if (pendingNavigation) {
      window.history.pushState(
        { page: 'chat', selectedCampaign }, 
        '', 
        window.location.pathname
      );
      setPendingNavigation(null);
    }
  };

  // Handle send message
  const handleSendMessage = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const messageText = normalizeChatMessageInput(formData.get('message'), user?.role === 'admin');

    if (!messageText.trim()) return;

    if (/^\s*\/ai(\s+|$)/i.test(messageText) && user?.role !== 'admin') {
      setError(
        'Only site administrators can use /ai commands. Use Roll dice in the sidebar for Storyteller (d10) pool rolls.'
      );
      return;
    }

    setLoading(true);
    setError('');

    // Add user message to UI immediately (optimistic update)
    const tempUserMessage = {
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString(),
      location_id: currentLocation.id,
      username: user.username,
      poster_role: user?.role || '',
      character_id: character?.id,
      character_name: character?.name,
      character_portrait_url: character?.portrait_url || null,
      temp: true, // Mark as temporary
    };
    setMessages(prev => [...prev, tempUserMessage]);
    e.target.reset();
    scrollChatToBottomSoon();

    const slashMatch = messageText.match(/^\s*\/ai\s+(\S+)(?:\s+([\s\S]*))?$/i);

    try {
      // Save user message to database
      const saveResponse = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: messageText,
          message_type:
            String(currentLocation?.type || '').toLowerCase() === 'ooc' ? 'ooc' : 'ic',
          role: 'user',
          ...(character?.id ? { character_id: character.id } : {}),
          ...(slashMatch ? { ai_message_kind: 'slash_user' } : {}),
        })
      });

      const inOocRoom = String(currentLocation?.type || '').toLowerCase() === 'ooc';

      if (saveResponse.ok) {
        const saveData = await saveResponse.json();
        console.log('✅ Message saved to database:', saveData);
        
        // Replace temp message with saved message
        setMessages(prev => 
          prev.map(msg => msg.temp ? saveData.data : msg)
        );
      } else {
        console.error('❌ Failed to save message to database');
      }

      // /ai … slash commands (diagnostics & tools) — bypass normal storyteller chat
      if (slashMatch) {
        const slashRes = await fetch(`${API_URL}/ai/slash`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            line: messageText.trim(),
            campaign_id: selectedCampaign.id,
            location_id: currentLocation.id,
          }),
        });
        const slashData = await slashRes.json().catch(() => ({}));
        const assistantContent =
          slashData.display_markdown ||
          slashData.llm_acknowledgment ||
          null;
        const showSlashReply = Boolean(
          assistantContent && String(assistantContent).trim() !== ''
        );
        if (!slashRes.ok && !showSlashReply) {
          setError(slashData.error || 'Slash command failed');
        } else {
          if (!slashRes.ok && slashData.error) {
            setError(slashData.error);
          }

          const isDiceRollSlash =
            slashData.command === 'roll' || slashData.command === 'roll-hidden';
          if (isDiceRollSlash) {
            const slashAssistantType = inOocRoom ? 'ooc' : 'ic';
            const isHidden = slashData.command === 'roll-hidden';

            const roll = slashData.roll || {};
            const allDice = Array.isArray(roll.dice) ? roll.dice : [];
            const preview = allDice.slice(0, 10);
            const extraDiceCount = Math.max(0, allDice.length - preview.length);

            const startedAtMs = Date.now();
            const durationMs = 3000;
            const animationId = _makeDiceAnimationId();

            const markerObj = {
              animation_id: animationId,
              started_at_ms: startedAtMs,
              duration_ms: durationMs,
              difficulty: Number(roll.difficulty || 6),
              dice_preview: preview,
              extra_dice_count: extraDiceCount,
              successes: Number(roll.net_successes || 0),
              is_botch: Boolean(roll.botch),
              is_critical: false,
              pool_size: allDice.length,
            };

            startDiceAnimationFromMarker(markerObj);

            const markerKind = isHidden
              ? `dice_animation_hidden:${animationId}`
              : `dice_animation:${animationId}`;
            const finalKind = isHidden
              ? `dice_roll_hidden:${animationId}`
              : `dice_roll:${animationId}`;

            const markerRes = await fetch(
              `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`,
              {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  content: JSON.stringify(markerObj),
                  message_type: slashAssistantType,
                  role: 'assistant',
                  ai_message_kind: markerKind,
                }),
              }
            );
            const markerData = await markerRes.json().catch(() => ({}));
            if (!markerRes.ok) {
              setError(markerData.error || 'Could not post dice animation marker.');
              return;
            }

            const finalRes = await fetch(
              `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`,
              {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  content: assistantContent,
                  message_type: slashAssistantType,
                  role: 'assistant',
                  ai_message_kind: finalKind,
                }),
              }
            );
            const finalData = await finalRes.json().catch(() => ({}));
            if (!finalRes.ok) {
              setError(finalData.error || 'Could not post dice roll result.');
              return;
            }

            setMessages((prev) => [...prev, markerData.data, finalData.data]);
          } else if (showSlashReply) {
            const slashAssistantType = inOocRoom ? 'ooc' : 'ic';
            const aiSaveResponse = await fetch(
              `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`,
              {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  content: assistantContent,
                  message_type: slashAssistantType,
                  role: 'assistant',
                  ai_message_kind: 'slash_assistant',
                }),
              }
            );
            if (aiSaveResponse.ok) {
              const aiSaveData = await aiSaveResponse.json();
              setMessages((prev) => [...prev, aiSaveData.data]);
            } else {
              setMessages((prev) => [
                ...prev,
                {
                  role: 'assistant',
                  content: assistantContent,
                  created_at: new Date().toISOString(),
                  location_id: currentLocation.id,
                  username: 'AI',
                  message_type: slashAssistantType,
                },
              ]);
            }
          }
          if (
            slashData.clean_target === 'ai' &&
            typeof slashData.deleted_count === 'number' &&
            selectedCampaign?.id &&
            currentLocation?.id
          ) {
            await loadMessages(selectedCampaign.id, currentLocation.id, { characterForRead: character });
          }
          if (slashData.command === 'dice-diff' && selectedCampaign?.id) {
            const locs = await fetchCampaignLocations(selectedCampaign.id);
            setLocations(locs);
            const upd = locs.find((l) => l.id === currentLocation.id);
            if (upd) setCurrentLocation(upd);
          }
          if (Array.isArray(slashData.future_commands_suggestion) && slashData.future_commands_suggestion.length) {
            console.info('/ai commands:', slashData.future_commands_suggestion);
          }
        }
      } else {
      // Get AI response (OOC rooms: backend may return ooc_no_reply — no in-game storyteller)
      const aiResponse = await fetch(`${API_URL}/ai/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: messageText,
          campaign_id: selectedCampaign.id,
          location: currentLocation.id,
          location_type: currentLocation.type,
        })
      });

      const aiData = await aiResponse.json();

      if (aiResponse.ok) {
        const skipOoc = Boolean(aiData.ooc_no_reply);
        const rawContent = aiData.response ?? aiData.message;
        const aiMessageContent =
          rawContent != null && String(rawContent).trim() !== ''
            ? String(rawContent).trim()
            : null;

        if (skipOoc || !aiMessageContent) {
          /* OOC: model chose not to answer, or empty — no assistant line */
        } else {
          const assistantMsgType = inOocRoom ? 'ooc' : 'ic';
          const aiSaveResponse = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              content: aiMessageContent,
              message_type: assistantMsgType,
              role: 'assistant'
            })
          });

          if (aiSaveResponse.ok) {
            const aiSaveData = await aiSaveResponse.json();
            console.log('✅ AI message saved to database:', aiSaveData);
            setMessages(prev => [...prev, aiSaveData.data]);
          } else {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: aiMessageContent,
              created_at: new Date().toISOString(),
              location_id: currentLocation.id,
              username: 'AI'
            }]);
          }
        }
      } else {
        setError(aiData.error || 'Failed to get AI response');
      }
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
      scrollChatToBottomSoon();

      // Restore focus to input after all state updates complete
      // Use setTimeout to ensure DOM has updated after React re-renders
      setTimeout(() => {
        if (chatInputRef.current) {
          chatInputRef.current.focus();
        }
      }, 0);
    }
  };

  // Load messages for a location
  const loadMessages = async (campaignId, locationId, opts = {}) => {
    const charForRead =
      opts.characterForRead !== undefined ? opts.characterForRead : character;
    setMessagesSyncedLocationId(null);
    try {
      console.log(`📨 Loading messages for location ${locationId}...`);
      const response = await fetch(`${API_URL}/campaigns/${campaignId}/locations/${locationId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log(`✅ Loaded ${data.length} messages for location ${locationId}`);
        setMessages(data);
        setMessagesSyncedLocationId(locationId);

        // Load per-character read state (for unread marker + jump)
        if (charForRead?.id) {
          try {
            const rs = await fetch(`${API_URL}/campaigns/${campaignId}/locations/${locationId}/read-state?character_id=${charForRead.id}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            if (rs.ok) {
              const readState = await rs.json();
              setLocationReadState(readState);
              setFirstUnreadMessageId(readState.first_unread_message_id || null);
            } else {
              setLocationReadState(null);
              setFirstUnreadMessageId(null);
            }
          } catch (e) {
            setLocationReadState(null);
            setFirstUnreadMessageId(null);
          }
        } else {
          setLocationReadState(null);
          setFirstUnreadMessageId(null);
        }
      } else {
        const errText = await response.text();
        let payload = {};
        try {
          payload = JSON.parse(errText);
        } catch (e) {
          /* not JSON */
        }
        if (response.status === 403 && payload.error === 'location_closed') {
          const loc = locations.find((l) => l.id === locationId);
          const m = closedLocationPlayerMessage(
            selectedCampaign?.game_system,
            payload.message,
            loc?.name,
          );
          setClosedRoomModal({
            title: m.title,
            lead: (payload.message && String(payload.message).trim()) || m.lead,
            flavor: payload.flavor || m.flavor,
          });
        }
        console.error('❌ Failed to load messages:', errText);
        setMessages([]);
        setMessagesSyncedLocationId(null);
        setLocationReadState(null);
        setFirstUnreadMessageId(null);
      }
    } catch (error) {
      console.error('❌ Error loading messages:', error);
      setMessages([]);
      setMessagesSyncedLocationId(null);
      setLocationReadState(null);
      setFirstUnreadMessageId(null);
    }
  };

  // Change location
  const changeLocation = async (location) => {
    const open = location.is_open !== false && location.is_open !== 0;
    if (!open && !userCanBypassClosedLocation()) {
      const m = closedLocationPlayerMessage(
        selectedCampaign?.game_system,
        location.closure_reason,
        location.name,
      );
      setClosedRoomModal({
        title: m.title,
        lead: m.lead,
        flavor: m.flavor,
      });
      return;
    }
    setCurrentLocation(location);
    await loadMessages(selectedCampaign.id, location.id, { characterForRead: character });
  };

  // Near–real-time: poll for new messages while in chat (other sessions / tabs)
  useEffect(() => {
    if (currentPage !== 'chat' || !token || !selectedCampaign?.id || !currentLocation?.id) {
      return undefined;
    }
    const campaignId = selectedCampaign.id;
    const locationId = currentLocation.id;

    const poll = async () => {
      if (loadingRef.current) return;
      try {
        const prev = messagesRef.current;
        const maxId = prev.reduce(
          (acc, m) => (m.id && !m.temp ? Math.max(acc, m.id) : acc),
          0
        );
        const hasServerMessages = prev.some((m) => m.id);
        const url = !hasServerMessages || maxId < 1
          ? `${API_URL}/campaigns/${campaignId}/locations/${locationId}?recent=1&limit=120`
          : `${API_URL}/campaigns/${campaignId}/locations/${locationId}?since_id=${maxId}&limit=100`;

        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) {
          if (response.status === 403) {
            try {
              const err = await response.json();
              if (err.error === 'location_closed') {
                const m = closedLocationPlayerMessage(
                  selectedCampaign?.game_system,
                  err.message,
                  currentLocation?.name,
                );
                setClosedRoomModal({
                  title: m.title,
                  lead: err.message || m.lead,
                  flavor: err.flavor || m.flavor,
                });
              }
            } catch (e) {
              /* ignore */
            }
          }
          return;
        }
        const incoming = await response.json();
        if (!Array.isArray(incoming) || incoming.length === 0) return;

        setMessages((prevList) => {
          if (!prevList.some((m) => m.id)) {
            const temps = prevList.filter((m) => m.temp);
            return [...incoming, ...temps];
          }
          const existingIds = new Set(prevList.filter((m) => m.id).map((m) => m.id));
          const toAdd = incoming.filter((m) => m.id && !existingIds.has(m.id));
          if (toAdd.length === 0) return prevList;
          const core = [...prevList.filter((m) => m.id), ...toAdd].sort((a, b) => a.id - b.id);
          const temps = prevList.filter((m) => m.temp);
          return [...core, ...temps];
        });
      } catch (e) {
        /* ignore transient poll errors */
      }
    };

    const kickoff = setTimeout(poll, 400);
    // Dice animations rely on marker messages; poll a bit faster so everyone sees it.
    const intervalId = setInterval(poll, 1200);
    return () => {
      clearTimeout(kickoff);
      clearInterval(intervalId);
    };
  }, [currentPage, token, selectedCampaign?.id, currentLocation?.id]);

  useEffect(() => {
    if (currentPage !== 'chat') return undefined;
    setChatNow(new Date());
    const id = setInterval(() => setChatNow(new Date()), 60000);
    return () => clearInterval(id);
  }, [currentPage, currentLocation?.id]);

  useEffect(() => {
    chatScrollAppliedForLocationRef.current = null;
  }, [currentLocation?.id, character?.id]);

  useEffect(() => {
    if (currentPage !== 'chat') return;
    const lid = currentLocation?.id;
    if (!lid || messagesSyncedLocationId !== lid) return;
    if (chatScrollAppliedForLocationRef.current === lid) return;
    const scrollEl = chatMessagesScrollRef.current;
    if (!scrollEl) return;

    const run = () => {
      if (messages.length === 0) {
        chatScrollAppliedForLocationRef.current = lid;
        return;
      }
      if (firstUnreadMessageId) {
        const node = document.getElementById(`msg-${firstUnreadMessageId}`);
        if (node && scrollEl.contains(node)) {
          const cRect = scrollEl.getBoundingClientRect();
          const nRect = node.getBoundingClientRect();
          scrollEl.scrollTop += nRect.top - cRect.top - 12;
        } else {
          scrollEl.scrollTop = scrollEl.scrollHeight;
        }
      } else {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
      chatScrollAppliedForLocationRef.current = lid;
    };

    requestAnimationFrame(() => requestAnimationFrame(run));
  }, [
    currentPage,
    currentLocation?.id,
    messagesSyncedLocationId,
    firstUnreadMessageId,
    messages
  ]);

  const jumpToMessage = (messageId) => {
    if (!messageId) return;
    const node = document.getElementById(`msg-${messageId}`);
    if (!node) return;
    const scrollEl = chatMessagesScrollRef.current;
    if (scrollEl && scrollEl.contains(node)) {
      const cRect = scrollEl.getBoundingClientRect();
      const nRect = node.getBoundingClientRect();
      scrollEl.scrollTop += nRect.top - cRect.top - 12;
    } else {
      node.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const markLocationRead = async () => {
    if (!selectedCampaign?.id || !currentLocation?.id || !character?.id) return;
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage?.id) return;

    try {
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}/read-state`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          character_id: character.id,
          last_read_message_id: lastMessage.id
        })
      });
      if (response.ok) {
        const readState = await response.json();
        setLocationReadState(readState);
        setFirstUnreadMessageId(readState.first_unread_message_id || null);
      }
    } catch (e) {
      // ignore
    }
  };

  // Update campaign name
  const handleUpdateCampaignName = async () => {
    if (!editedCampaignName.trim()) {
      setError('Campaign name cannot be empty');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: editedCampaignName })
      });

      if (response.ok) {
        // Update local state
        setSelectedCampaign({ ...selectedCampaign, name: editedCampaignName });
        setIsEditingCampaignName(false);
        // Refresh campaigns list
        fetchCampaigns(undefined, { forActiveCharacter: true });
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update campaign name');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateCampaignDesc = async () => {
    if (!editedCampaignDesc.trim()) {
      setError('Campaign description cannot be empty');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ description: editedCampaignDesc })
      });

      if (response.ok) {
        // Update local state
        setSelectedCampaign({ ...selectedCampaign, description: editedCampaignDesc });
        setIsEditingCampaignDesc(false);
        // Refresh campaigns list
        fetchCampaigns(undefined, { forActiveCharacter: true });
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update campaign description');
      }
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Get campaign theme based on game system
  const getCampaignTheme = (campaign) => {
    if (!campaign || !campaign.game_system) return 'none';
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Check for Vampire
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return 'vampire';
    }
    
    // Check for Mage
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return 'mage';
    }
    
    // Check for Werewolf
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return 'werewolf';
    }
    
    return 'none';
  };

  // Get campaign emoji based on game system
  const getCampaignEmoji = (campaign) => {
    if (!campaign || !campaign.game_system) return '📜';
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Vampire campaigns
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return '🦇';
    }
    
    // Mage campaigns
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return '🔮';
    }
    
    // Werewolf campaigns
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return '🐺';
    }
    
    // Changeling
    if (gameSystem.includes('changeling') || gameSystem.includes('dreaming')) {
      return '🧚';
    }
    
    // Hunter
    if (gameSystem.includes('hunter') || gameSystem.includes('reckoning')) {
      return '🗡️';
    }
    
    // Wraith
    if (gameSystem.includes('wraith') || gameSystem.includes('oblivion')) {
      return '👻';
    }
    
    // D&D / Fantasy
    if (gameSystem.includes('d&d') || gameSystem.includes('dungeons') || gameSystem.includes('pathfinder')) {
      return '⚔️';
    }
    
    // Default - ancient scroll
    return '📜';
  };

  // Get campaign color scheme based on game system
  const getCampaignColor = (campaign) => {
    if (!campaign || !campaign.game_system) {
      return {
        primary: '#e94560',
        bg: 'rgba(233, 69, 96, 0.2)',
        shadow: 'rgba(233, 69, 96, 0.3)'
      };
    }
    
    const gameSystem = campaign.game_system.toLowerCase();
    
    // Vampire campaigns - Blood Red
    if (gameSystem.includes('vampire') || gameSystem.includes('masquerade') || gameSystem.includes('vtm')) {
      return {
        primary: '#e94560',
        bg: 'rgba(233, 69, 96, 0.2)',
        shadow: 'rgba(233, 69, 96, 0.3)'
      };
    }
    
    // Mage campaigns - Mystic Purple
    if (gameSystem.includes('mage') || gameSystem.includes('ascension') || gameSystem.includes('mta')) {
      return {
        primary: '#9d4edd',
        bg: 'rgba(157, 78, 221, 0.2)',
        shadow: 'rgba(157, 78, 221, 0.3)'
      };
    }
    
    // Werewolf campaigns - Amber/Golden
    if (gameSystem.includes('werewolf') || gameSystem.includes('apocalypse') || gameSystem.includes('wta') || gameSystem.includes('garou')) {
      return {
        primary: '#d97706',
        bg: 'rgba(217, 119, 6, 0.2)',
        shadow: 'rgba(217, 119, 6, 0.3)'
      };
    }
    
    // Changeling - Fae Green
    if (gameSystem.includes('changeling') || gameSystem.includes('dreaming')) {
      return {
        primary: '#10b981',
        bg: 'rgba(16, 185, 129, 0.2)',
        shadow: 'rgba(16, 185, 129, 0.3)'
      };
    }
    
    // Hunter - Silver
    if (gameSystem.includes('hunter') || gameSystem.includes('reckoning')) {
      return {
        primary: '#94a3b8',
        bg: 'rgba(148, 163, 184, 0.2)',
        shadow: 'rgba(148, 163, 184, 0.3)'
      };
    }
    
    // Wraith - Ghost White/Blue
    if (gameSystem.includes('wraith') || gameSystem.includes('oblivion')) {
      return {
        primary: '#60a5fa',
        bg: 'rgba(96, 165, 250, 0.2)',
        shadow: 'rgba(96, 165, 250, 0.3)'
      };
    }
    
    // Default - Blood Red
    return {
      primary: '#e94560',
      bg: 'rgba(233, 69, 96, 0.2)',
      shadow: 'rgba(233, 69, 96, 0.3)'
    };
  };

  const appHeaderButton = (variant) => {
    const base = {
      padding: '8px 16px',
      borderRadius: '5px',
      cursor: 'pointer',
      fontWeight: 'bold',
      border: '2px solid',
      fontSize: '14px',
    };
    if (variant === 'violet') {
      return {
        ...base,
        background: 'rgba(157, 78, 221, 0.15)',
        color: '#c4b5fd',
        borderColor: '#7c3aed',
      };
    }
    if (variant === 'rose') {
      return {
        ...base,
        background: 'rgba(233, 69, 96, 0.12)',
        color: '#fda4af',
        borderColor: '#e94560',
        fontFamily: 'Cinzel, serif',
      };
    }
    if (variant === 'muted') {
      return {
        ...base,
        background: 'rgba(15, 23, 41, 0.9)',
        color: '#94a3b8',
        borderColor: '#475569',
        fontSize: '13px',
      };
    }
    if (variant === 'admin') {
      return {
        ...base,
        background: 'rgba(233, 69, 96, 0.3)',
        color: '#e94560',
        borderColor: '#e94560',
      };
    }
    return {
      ...base,
      background: 'rgba(233, 69, 96, 0.2)',
      color: '#e94560',
      borderColor: '#e94560',
    };
  };

  /** Shared top bar after login: Chronicle hall (logo), account nav, logout — same on every sub-page. */
  const renderAppPageHeader = ({ title }) => (
      <div
        style={{
          background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
          padding: isMobile ? '15px' : '20px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between',
          alignItems: isMobile ? 'stretch' : 'center',
          gap: isMobile ? '15px' : '0',
          borderBottom: '2px solid #2a2a4e',
        }}
      >
        <button
          type="button"
          onClick={() => navigateTo('dashboard')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '15px',
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            textAlign: isMobile ? 'center' : 'left',
            justifyContent: isMobile ? 'center' : 'flex-start',
            width: isMobile ? '100%' : 'auto',
          }}
          aria-label="Chronicle hall (dashboard)"
        >
          <img src="/logo-header.png" alt="" style={{ width: isMobile ? '40px' : '50px', height: 'auto' }} />
          <h1
            style={{
              color: '#e94560',
              margin: 0,
              fontSize: isMobile ? '20px' : '24px',
              fontFamily: 'Cinzel, serif',
            }}
          >
            {title}
          </h1>
        </button>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: isMobile ? '10px' : '15px',
            justifyContent: isMobile ? 'center' : 'flex-end',
            flexWrap: 'wrap',
          }}
        >
          <span style={{ color: '#b5b5c3', fontWeight: '500', fontSize: isMobile ? '14px' : '16px' }}>
            👤 {user?.username}
          </span>
          <button type="button" onClick={() => navigateTo('profile')} style={appHeaderButton('violet')}>
            Profile
          </button>
          <button type="button" onClick={() => navigateTo('playerProfile')} style={appHeaderButton('rose')}>
            Player Profile
          </button>
          <button type="button" onClick={() => navigateTo('selectCharacter')} style={appHeaderButton('muted')}>
            Switch character
          </button>
          {user?.role === 'admin' && (
            <button type="button" onClick={() => navigateTo('admin')} style={appHeaderButton('admin')}>
              👑 Admin Panel
            </button>
          )}
          <button type="button" onClick={handleLogout} style={appHeaderButton('logout')}>
            🚪 Logout
          </button>
        </div>
      </div>
  );

  // ========== RENDER FUNCTIONS ==========

  // Render login page
  const renderLogin = () => (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #0f0f1e 100%)',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {/* Main Content - takes up available space */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}>
      {/* Logo and Title */}
      <div style={{ textAlign: 'center', marginBottom: '40px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <img 
          src="/logo-login.png" 
          alt="ShadowRealms AI" 
          style={{ 
            width: '240px', 
            height: 'auto', 
            marginBottom: '20px',
            filter: 'drop-shadow(0 0 20px rgba(233, 69, 96, 0.5))'
          }}
        />
        <h1 style={{ color: '#e94560', marginBottom: '10px', fontSize: '32px', fontWeight: 'bold' }}>
          ShadowRealms AI
        </h1>
        <p style={{ color: '#8b8b9f', marginBottom: '0', fontSize: '16px' }}>
          Immersive Tabletop RPG with AI
        </p>
        
        {/* Gothic Theme Preview Button */}
        <button
          onClick={() => showShowcase(true)}
          style={{
            marginTop: '20px',
            padding: '10px 25px',
            background: 'linear-gradient(135deg, #9d4edd 0%, #5a0099 100%)',
            border: '2px solid #9d4edd',
            color: 'white',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 'bold',
            boxShadow: '0 0 20px rgba(157, 78, 221, 0.4)',
            transition: 'all 0.3s'
          }}
        >
          💀 Preview Gothic Horror Theme 💀
        </button>
      </div>

      {/* Login and Register Side by Side (stacks on mobile) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, 1fr)',
        gap: isMobile ? '20px' : '30px',
        width: '100%',
        maxWidth: isMobile ? '100%' : '950px',
        padding: isMobile ? '0 10px' : '0'
      }}>

        {/* Login Box with Blood Theme */}
        <GothicBox theme="vampire" style={{
          background: '#16213e',
          padding: '35px',
          borderRadius: '15px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          border: '1px solid #2a2a4e'
        }}>
          <h2 style={{ fontSize: '24px', color: '#e94560', marginBottom: '25px', textAlign: 'center', fontFamily: 'Cinzel, serif' }}>
            Login
          </h2>
          <form onSubmit={handleLogin}>
            <div style={{ marginBottom: '15px' }}>
              <label htmlFor="shadowrealms-login-username" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Username:
              </label>
              <input
                id="shadowrealms-login-username"
                type="text"
                name="username"
                autoComplete="username"
                required
                placeholder="Enter your username"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label htmlFor="shadowrealms-login-password" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Password:
              </label>
              <input
                id="shadowrealms-login-password"
                type="password"
                name="password"
                autoComplete="current-password"
                required
                placeholder="Enter your password"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px',
                background: loading ? '#4a4a5e' : '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                marginBottom: '15px',
                boxShadow: loading ? 'none' : '0 4px 15px rgba(233, 69, 96, 0.3)'
              }}
            >
              {loading ? 'Logging in...' : 'LOGIN'}
            </button>
          </form>
        </GothicBox>

        {/* Register Box with Magic Theme */}
        <GothicBox theme="mage" style={{
          background: '#16213e',
          padding: '35px',
          borderRadius: '15px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          border: '1px solid #2a2a4e'
        }}>
          <h2 style={{ fontSize: '24px', color: '#9d4edd', marginBottom: '25px', textAlign: 'center', fontFamily: 'Cinzel, serif' }}>
            Register
          </h2>
          <form onSubmit={handleRegister}>
            <div style={{ marginBottom: '15px' }}>
              <label htmlFor="shadowrealms-register-username" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Username:
              </label>
              <input
                id="shadowrealms-register-username"
                type="text"
                name="username"
                autoComplete="username"
                required
                placeholder="Choose a username"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label htmlFor="shadowrealms-register-email" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Email:
              </label>
              <input
                id="shadowrealms-register-email"
                type="email"
                name="email"
                autoComplete="email"
                required
                placeholder="Enter your email"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '15px' }}>
              <label htmlFor="shadowrealms-register-password" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Password:
              </label>
              <input
                id="shadowrealms-register-password"
                type="password"
                name="password"
                autoComplete="new-password"
                required
                placeholder="Choose a password"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label htmlFor="shadowrealms-register-invite" style={{ display: 'block', marginBottom: '5px', color: '#b5b5c3', fontWeight: '600' }}>
                Invite Code: <span style={{ color: '#e94560' }}>*</span>
              </label>
              <input
                id="shadowrealms-register-invite"
                type="text"
                name="invite_code"
                autoComplete="off"
                required
                placeholder="Enter your invite code"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e0e0e0',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
              <small style={{ color: '#8b8b9f', fontSize: '12px', marginTop: '5px', display: 'block' }}>
                Required: Get an invite code from the admin
              </small>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '12px',
                background: loading ? '#4a4a5e' : '#9d4edd',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: loading ? 'none' : '0 4px 15px rgba(157, 78, 221, 0.4)',
                fontFamily: 'Cinzel, serif'
              }}
            >
              {loading ? 'Creating account...' : 'REGISTER'}
            </button>
          </form>
        </GothicBox>
      </div>

      {/* Error Message */}
      {error && (
        <div style={{
          marginTop: '30px',
          padding: '15px 25px',
          background: 'rgba(233, 69, 96, 0.1)',
          border: '2px solid #e94560',
          borderRadius: '8px',
          color: '#e94560',
          fontWeight: '500',
          maxWidth: '950px',
          width: '100%',
          textAlign: 'center'
        }}>
          ⚠️ {error}
        </div>
      )}
      </div>

      {/* Footer - sticks to bottom */}
      <Footer />
    </div>
  );

  const saveProfileTimezone = async () => {
    if (!token) return;
    setProfileTzSaving(true);
    try {
      const res = await fetch(`${API_URL}/users/me`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          display_timezone: profileTzDraft.trim() ? profileTzDraft.trim() : null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data));
        showSuccess('Display time zone saved.');
      } else {
        showError(data.error || 'Failed to save time zone');
      }
    } catch (e) {
      showError('Connection error while saving time zone');
    } finally {
      setProfileTzSaving(false);
    }
  };

  const renderProfile = () => (
    <div style={{
      minHeight: '100vh',
      background: '#0f0f1e',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {renderAppPageHeader({ title: 'Profile' })}
      <div style={{ flex: 1, maxWidth: '560px', margin: '0 auto', padding: isMobile ? '20px 15px' : '40px 20px', width: '100%', boxSizing: 'border-box' }}>
        <div style={{
          background: '#16213e',
          borderRadius: '10px',
          padding: '24px',
          border: '1px solid #2a2a4e',
          boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
        }}>
          <p style={{ color: '#b5b5c3', marginTop: 0 }}>
            <strong style={{ color: '#e0e0e0' }}>Username:</strong> {user?.username}
          </p>
          <p style={{ color: '#b5b5c3' }}>
            <strong style={{ color: '#e0e0e0' }}>Email:</strong> {user?.email}
          </p>
          <p style={{ color: '#b5b5c3' }}>
            <strong style={{ color: '#e0e0e0' }}>Role:</strong> {user?.role}
          </p>
          <label htmlFor="profile-timezone" style={{ display: 'block', color: '#e94560', fontWeight: 600, marginTop: '20px', marginBottom: '8px' }}>
            Display time zone
          </label>
          <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: 0, marginBottom: '10px', lineHeight: 1.5 }}>
            Message times, dice history, and admin timestamps follow this zone. Leave as browser default to use your device clock.
          </p>
          <select
            id="profile-timezone"
            value={profileTzDraft}
            onChange={(e) => setProfileTzDraft(e.target.value)}
            style={{
              width: '100%',
              maxWidth: '100%',
              padding: '10px',
              borderRadius: '6px',
              background: '#0f1729',
              color: '#e0e0e0',
              border: '2px solid #2a2a4e',
              marginBottom: '16px',
            }}
          >
            <option value="">Browser default (device local time)</option>
            {getTimezoneSelectOptions().map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={saveProfileTimezone}
            disabled={profileTzSaving}
            style={{
              padding: '10px 20px',
              background: profileTzSaving ? '#4a4a5e' : '#9d4edd',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 'bold',
              cursor: profileTzSaving ? 'not-allowed' : 'pointer',
            }}
          >
            {profileTzSaving ? 'Saving…' : 'Save time zone'}
          </button>
        </div>
      </div>
      <Footer />
    </div>
  );

  const renderSelectCharacter = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
      {renderAppPageHeader({ title: 'Choose your mask' })}
      <div style={{ flex: 1, maxWidth: '900px', margin: '0 auto', padding: '24px 16px 48px', width: '100%', boxSizing: 'border-box' }}>
        <GothicBox theme="vampire" style={{ padding: '20px', marginBottom: '24px' }}>
          <p style={{ color: '#b5b5c3', marginTop: 0, lineHeight: 1.6 }}>
            Select which character you are playing <strong>right now</strong>. Your chronicle list will only show games
            that character belongs to. Swap masks anytime from <strong>Player Profile</strong>.
          </p>
        </GothicBox>
        {playerCharacters.length === 0 ? (
          <GothicBox theme="mage" style={{ padding: '28px', textAlign: 'center' }}>
            <p style={{ color: '#b5b5c3' }}>You have no characters yet.</p>
            <button
              type="button"
              onClick={() => navigateTo('characterCreate')}
              style={{
                marginTop: '16px',
                padding: '12px 24px',
                background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontFamily: 'Cinzel, serif',
              }}
            >
              Forge a character
            </button>
          </GothicBox>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(260px, 1fr))',
              gap: '16px',
            }}
          >
            {playerCharacters.map((ch) => (
              <GothicBox key={ch.id} theme="werewolf" style={{ padding: '18px' }}>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '12px' }}>
                  <MessageCharacterAvatar url={ch.portrait_url} size={52} />
                  <div>
                    <div style={{ color: '#e94560', fontFamily: 'Cinzel, serif', fontWeight: 'bold' }}>{ch.name}</div>
                    <div style={{ color: '#8b8b9f', fontSize: '13px' }}>{ch.campaign_name}</div>
                  </div>
                </div>
                {ch.play_suspended && (
                  <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '10px', lineHeight: 1.5 }}>
                    <strong>Unavailable for play</strong>
                    {ch.play_suspension_reason_code
                      ? ` (${String(ch.play_suspension_reason_code).replace(/_/g, ' ')})`
                      : ''}
                    {ch.play_suspension_message ? ` — ${ch.play_suspension_message}` : ''}
                    <br />
                    <span style={{ color: '#94a3b8' }}>
                      Contact your Storyteller or a site administrator.
                    </span>
                  </p>
                )}
                <button
                  type="button"
                  disabled={!!ch.play_suspended}
                  onClick={() => applyActiveCharacter(ch.id)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: ch.play_suspended ? '#475569' : '#9d4edd',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: ch.play_suspended ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  {ch.play_suspended ? 'Unavailable' : `Play as ${ch.name}`}
                </button>
              </GothicBox>
            ))}
          </div>
        )}
        <div style={{ textAlign: 'center', marginTop: '28px' }}>
          <button
            type="button"
            onClick={() => navigateTo('characterCreate')}
            style={{
              padding: '10px 20px',
              background: 'transparent',
              color: '#c4b5fd',
              border: '2px solid #7c3aed',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
          >
            + Create another character
          </button>
        </div>
      </div>
      <Footer />
    </div>
  );

  const renderPlayerProfile = () => {
    const activeId = user?.active_character_id;
    const activeChar = playerCharacters.find((c) => c.id === activeId) || user?.active_character;
    return (
      <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
        {renderAppPageHeader({ title: 'Player Profile' })}
        <div style={{ flex: 1, maxWidth: '800px', margin: '0 auto', padding: '24px 16px 48px', width: '100%', boxSizing: 'border-box' }}>
          <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={() => navigateTo('characterCreate')}
              style={{
                padding: '8px 16px',
                background: 'rgba(157, 78, 221, 0.2)',
                color: '#c4b5fd',
                border: '2px solid #9d4edd',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontFamily: 'Cinzel, serif',
              }}
            >
              New character
            </button>
          </div>
          <GothicBox theme="vampire" style={{ padding: '20px', marginBottom: '20px' }}>
            <h3 style={{ marginTop: 0, color: '#e94560', fontFamily: 'Cinzel, serif' }}>Active character</h3>
            {activeChar ? (
              <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <MessageCharacterAvatar url={activeChar.portrait_url} size={72} />
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <div style={{ color: '#e0e0e0', fontWeight: 'bold', fontSize: '18px' }}>{activeChar.name}</div>
                  <div style={{ color: '#8b8b9f', fontSize: '14px' }}>
                    {activeChar.campaign_name || activeChar.campaignName || 'Chronicle'}
                  </div>
                  <p style={{ color: '#b5b5c3', fontSize: '14px', lineHeight: 1.5 }}>
                    Sheets are <strong>locked</strong> after creation. Update your portrait here; for anything else, submit a downtime request below or ask the Storyteller.
                  </p>
                  <label style={{ color: '#c4b5fd', fontSize: '13px', display: 'block', marginBottom: '6px' }}>
                    Character portrait (IC locations use this)
                  </label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f || !activeId) return;
                      if (f.size > 360000) {
                        showError('Image is too large (max ~350KB).');
                        return;
                      }
                      const reader = new FileReader();
                      reader.onload = async () => {
                        const dataUrl = reader.result;
                        const res = await fetch(`${API_URL}/characters/${activeId}`, {
                          method: 'PUT',
                          headers: {
                            Authorization: `Bearer ${token}`,
                            'Content-Type': 'application/json',
                          },
                          body: JSON.stringify({ portrait_url: dataUrl }),
                        });
                        const body = await res.json().catch(() => ({}));
                        if (res.ok && body.character) {
                          showSuccess('Portrait updated.');
                          setPlayerCharacters((prev) =>
                            prev.map((c) => (c.id === activeId ? { ...c, ...body.character } : c))
                          );
                          await fetchUserData();
                        } else {
                          showError(body.error || 'Could not update portrait');
                        }
                      };
                      reader.readAsDataURL(f);
                    }}
                  />
                </div>
              </div>
            ) : (
              <p style={{ color: '#b5b5c3' }}>No active character. Visit <strong>Choose your mask</strong> from the chronicle hall or create one.</p>
            )}
          </GothicBox>

          <GothicBox theme="mage" style={{ padding: '20px', marginBottom: '20px' }}>
            <h3 style={{ marginTop: 0, color: '#9d4edd', fontFamily: 'Cinzel, serif' }}>OOC identity</h3>
            <p style={{ color: '#b5b5c3', fontSize: '14px', lineHeight: 1.5 }}>
              This portrait appears only in <strong>Out of Character</strong> lobby rooms. In story rooms, others see your character portrait.
            </p>
            <MessageCharacterAvatar url={user?.player_avatar_url} size={64} />
            <input
              type="file"
              accept="image/*"
              style={{ marginTop: '10px' }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                if (f.size > 360000) {
                  showError('Image is too large (max ~350KB).');
                  return;
                }
                const reader = new FileReader();
                reader.onload = async () => {
                  const dataUrl = reader.result;
                  const res = await fetch(`${API_URL}/users/me`, {
                    method: 'PUT',
                    headers: {
                      Authorization: `Bearer ${token}`,
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ player_avatar_url: dataUrl }),
                  });
                  const body = await res.json().catch(() => ({}));
                  if (res.ok) {
                    setUser(body);
                    localStorage.setItem('user', JSON.stringify(body));
                    showSuccess('OOC portrait saved.');
                  } else {
                    showError(body.error || 'Could not save OOC portrait');
                  }
                };
                reader.readAsDataURL(f);
              }}
            />
          </GothicBox>

          <GothicBox theme="werewolf" style={{ padding: '20px', marginBottom: '20px' }}>
            <h3 style={{ marginTop: 0, color: '#e94560', fontFamily: 'Cinzel, serif' }}>Your characters</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {playerCharacters.map((ch) => (
                <div
                  key={ch.id}
                  style={{
                    border: ch.id === activeId ? '2px solid #9d4edd' : '1px solid #2a2a4e',
                    borderRadius: '8px',
                    padding: '12px',
                    background: '#0f1729',
                  }}
                >
                  <div style={{ color: '#e0e0e0', fontWeight: 'bold' }}>
                    {ch.name}
                    {ch.id === activeId ? (
                      <span style={{ color: '#9d4edd', marginLeft: '8px', fontSize: '12px' }}>(active)</span>
                    ) : null}
                  </div>
                  <div style={{ color: '#8b8b9f', fontSize: '13px' }}>{ch.campaign_name}</div>
                  <button
                    type="button"
                    disabled={ch.id === activeId}
                    onClick={() => applyActiveCharacter(ch.id)}
                    style={{
                      marginTop: '8px',
                      padding: '6px 14px',
                      background: ch.id === activeId ? '#333' : '#2a2a4e',
                      color: '#e0e0e0',
                      border: '1px solid #4a4a5e',
                      borderRadius: '6px',
                      cursor: ch.id === activeId ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {ch.id === activeId ? 'Currently active' : 'Swap to this character'}
                  </button>
                </div>
              ))}
            </div>
          </GothicBox>

          <GothicBox theme="vampire" style={{ padding: '20px', marginBottom: '20px' }}>
            <h3 style={{ marginTop: 0, color: '#e94560', fontFamily: 'Cinzel, serif' }}>Downtime requests</h3>
            <p style={{ color: '#8b8b9f', fontSize: '14px' }}>
              Ask the Storyteller / admin to adjust your locked sheet. They can approve or reject with a reason.
            </p>
            <textarea
              value={downtimeDraft}
              onChange={(e) => setDowntimeDraft(e.target.value)}
              rows={4}
              disabled={!activeId}
              placeholder={activeId ? 'Describe what should change on your sheet…' : 'Select an active character first.'}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                padding: '10px',
                borderRadius: '8px',
                border: '2px solid #2a2a4e',
                background: '#0f1729',
                color: '#e0e0e0',
                marginBottom: '10px',
              }}
            />
            <button
              type="button"
              disabled={!activeId || downtimeSending || !downtimeDraft.trim()}
              onClick={async () => {
                if (!activeId || !downtimeDraft.trim()) return;
                setDowntimeSending(true);
                try {
                  const res = await fetch(`${API_URL}/characters/${activeId}/downtime-requests`, {
                    method: 'POST',
                    headers: {
                      Authorization: `Bearer ${token}`,
                      'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ request_text: downtimeDraft.trim() }),
                  });
                  const body = await res.json().catch(() => ({}));
                  if (res.ok) {
                    setDowntimeDraft('');
                    showSuccess('Request sent to the admin queue.');
                    const r2 = await fetch(`${API_URL}/characters/downtime-requests/mine`, {
                      headers: { Authorization: `Bearer ${token}` },
                    });
                    if (r2.ok) {
                      const d2 = await r2.json();
                      setDowntimeMine(Array.isArray(d2.requests) ? d2.requests : []);
                    }
                  } else {
                    showError(body.error || 'Could not submit request');
                  }
                } catch (_) {
                  showError('Network error');
                } finally {
                  setDowntimeSending(false);
                }
              }}
              style={{
                padding: '10px 20px',
                background: downtimeSending ? '#555' : '#e94560',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: downtimeSending ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
              }}
            >
              {downtimeSending ? 'Sending…' : 'Submit request'}
            </button>
            <div style={{ marginTop: '20px' }}>
              <h4 style={{ color: '#b5b5c3', fontSize: '14px' }}>Your recent requests</h4>
              {downtimeMine.length === 0 ? (
                <p style={{ color: '#6b6b7f', fontSize: '13px' }}>None yet.</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {downtimeMine.map((r) => (
                    <li
                      key={r.id}
                      style={{
                        borderBottom: '1px solid #2a2a4e',
                        padding: '10px 0',
                        color: '#b5b5c3',
                        fontSize: '13px',
                      }}
                    >
                      <strong style={{ color: '#e0e0e0' }}>{r.status}</strong> — {r.character_name}{' '}
                      <span style={{ color: '#6b6b7f' }}>({r.campaign_name})</span>
                      <div style={{ marginTop: '4px' }}>{r.request_text}</div>
                      {r.admin_reason ? (
                        <div style={{ marginTop: '6px', color: '#9d4edd' }}>Staff: {r.admin_reason}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </GothicBox>
        </div>
        <Footer />
      </div>
    );
  };

  const renderCharacterCreate = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
      {renderAppPageHeader({ title: 'Character creation' })}
      <CharacterCreationWizard
        token={token}
        campaigns={wizardCampaigns}
        onCancel={() =>
          navigateTo(playerCharacters.length ? 'playerProfile' : 'selectCharacter')
        }
        onDone={async () => {
          await fetchUserData();
          navigateTo('playerProfile');
        }}
        showError={showError}
        showSuccess={showSuccess}
      />
      <Footer />
    </div>
  );

  // Render dashboard
  const renderDashboard = () => (
    <div style={{ 
      minHeight: '100vh', 
      background: '#0f0f1e',
      display: 'flex',
      flexDirection: 'column'
    }}>
      {renderAppPageHeader({ title: 'ShadowRealms AI' })}

      {/* Main content - takes up available space */}
      <div style={{ flex: 1 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: isMobile ? '20px 15px' : '40px 20px' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'stretch' : 'center', 
          gap: isMobile ? '15px' : '0',
          marginBottom: isMobile ? '20px' : '30px' 
        }}>
          <h2 style={{ color: '#e94560', margin: 0, fontSize: isMobile ? '20px' : '24px', textAlign: isMobile ? 'center' : 'left' }}>📚 Your Campaigns</h2>
          <button
            onClick={() => navigateTo('createCampaign')}
            style={{
              padding: '10px 20px',
              background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              color: 'white',
              border: '2px solid #e94560',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '16px',
              boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
              fontFamily: 'Cinzel, serif',
              transition: 'all 0.3s'
            }}
            onMouseOver={(e) => {
              e.target.style.boxShadow = '0 6px 25px rgba(233, 69, 96, 0.6)';
              e.target.style.transform = 'translateY(-2px)';
            }}
            onMouseOut={(e) => {
              e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
              e.target.style.transform = 'translateY(0)';
            }}
          >
            ✚ New Campaign
          </button>
        </div>

        {discoverCampaignsList.length > 0 && (
          <div style={{
            marginBottom: '28px',
            padding: '20px',
            background: '#16213e',
            borderRadius: '10px',
            border: '1px solid #2a2a4e',
          }}
          >
            <h3 style={{ color: '#e94560', marginTop: 0, marginBottom: '12px', fontFamily: 'Cinzel, serif' }}>
              Open chronicles you can join
            </h3>
            <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '16px' }}>
              These games are listed by their Storyteller and accept new players. Joining adds you to the chronicle so you can create a character for that setting.
            </p>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {discoverCampaignsList.map((dc) => (
                <li
                  key={dc.id}
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    padding: '12px 0',
                    borderBottom: '1px solid #2a2a4e',
                  }}
                >
                  <div>
                    <strong style={{ color: '#e0e0e8' }}>{dc.name}</strong>
                    <span style={{ color: '#64748b', marginLeft: '10px', fontSize: '13px' }}>
                      {dc.game_system}
                    </span>
                    {dc.max_players != null && (
                      <span style={{ color: '#64748b', marginLeft: '8px', fontSize: '12px' }}>
                        · max {dc.max_players} players
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleJoinDiscoverCampaign(dc.id)}
                    style={{
                      padding: '8px 16px',
                      background: '#0ea5e9',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: '600',
                    }}
                  >
                    Join
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {campaigns.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '60px 20px',
            background: '#16213e',
            borderRadius: '10px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e'
          }}>
            <p style={{ fontSize: '18px', color: '#b5b5c3' }}>
              No campaigns yet. Create your first campaign to begin!
            </p>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: isMobile ? '15px' : '20px'
          }}>
            {campaigns.map(campaign => {
              // Extract first line or truncate description
              const firstLine = campaign.description.split('\n')[0];
              const shortDesc = firstLine.length > 100 
                ? firstLine.substring(0, 100) + '...' 
                : firstLine;
              
              const themeColor = getCampaignColor(campaign);
              
              return (
                <div
                  key={campaign.id}
                  style={{
                    position: 'relative',
                    background: '#16213e',
                    padding: '25px',
                    borderRadius: '10px',
                    boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
                    cursor: 'pointer',
                    transition: 'transform 0.2s, border-color 0.2s, box-shadow 0.2s',
                    border: `2px solid #2a2a4e`,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    minHeight: '200px',
                    overflow: 'hidden'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.transform = 'translateY(-5px)';
                    e.currentTarget.style.borderColor = themeColor.primary;
                    e.currentTarget.style.boxShadow = `0 4px 20px ${themeColor.shadow}`;
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.borderColor = '#2a2a4e';
                    e.currentTarget.style.boxShadow = '0 2px 10px rgba(0,0,0,0.5)';
                  }}
                >
                  {/* Gothic Ribbon - Top Left Corner */}
                  <div style={{
                    position: 'absolute',
                    top: '15px',
                    left: '-10px',
                    background: `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}cc 100%)`,
                    color: 'white',
                    padding: '8px 25px 8px 18px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    fontFamily: 'Cinzel, serif',
                    textTransform: 'uppercase',
                    letterSpacing: '1.5px',
                    boxShadow: `0 4px 15px ${themeColor.shadow}`,
                    borderRadius: '0 5px 5px 0',
                    zIndex: 10,
                    clipPath: 'polygon(10px 0, 100% 0, 100% 100%, 10px 100%, 0 50%)',
                    border: `2px solid ${themeColor.primary}`,
                    borderLeft: 'none',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    <span style={{ fontSize: '18px', lineHeight: '1' }}>{getCampaignEmoji(campaign)}</span>
                    <span>{campaign.game_system}</span>
                  </div>

                  <div onClick={() => enterCampaign(campaign)} style={{ marginTop: '45px' }}>
                    <h3 style={{ color: themeColor.primary, marginBottom: '10px', fontSize: '20px', fontFamily: 'Cinzel, serif' }}>
                      {campaign.name}
                    </h3>
                    <p style={{ color: '#b5b5c3', marginBottom: '15px', fontSize: '14px', lineHeight: '1.5', fontFamily: 'Crimson Text, serif' }}>
                      {shortDesc}
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '10px' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        navigateTo('campaignDetails', campaign);
                      }}
                      style={{
                        flex: 1,
                        padding: '8px 16px',
                        background: themeColor.bg,
                        color: themeColor.primary,
                        border: `1px solid ${themeColor.primary}`,
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600',
                        fontFamily: 'Cinzel, serif',
                        transition: 'all 0.2s'
                      }}
                      onMouseOver={(e) => {
                        e.target.style.background = themeColor.primary;
                        e.target.style.color = 'white';
                      }}
                      onMouseOut={(e) => {
                        e.target.style.background = themeColor.bg;
                        e.target.style.color = themeColor.primary;
                      }}
                    >
                      ⚙️ Settings
                    </button>
                    <button
                      onClick={() => enterCampaign(campaign)}
                      style={{
                        flex: 1,
                        padding: '8px 16px',
                        background: `linear-gradient(135deg, ${themeColor.primary} 0%, ${themeColor.primary}dd 100%)`,
                        color: 'white',
                        border: `2px solid ${themeColor.primary}`,
                        borderRadius: '5px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '600',
                        boxShadow: `0 2px 10px ${themeColor.shadow}`,
                        fontFamily: 'Cinzel, serif',
                        transition: 'all 0.2s'
                      }}
                      onMouseOver={(e) => {
                        e.target.style.boxShadow = `0 4px 15px ${themeColor.shadow}`;
                        e.target.style.transform = 'translateY(-1px)';
                      }}
                      onMouseOut={(e) => {
                        e.target.style.boxShadow = `0 2px 10px ${themeColor.shadow}`;
                        e.target.style.transform = 'translateY(0)';
                      }}
                    >
                      ▶ Enter
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        </div>
      </div>

      {/* Footer - sticks to bottom */}
      <Footer />
    </div>
  );

  // Render campaign details/settings page
  const renderCampaignDetails = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
      {renderAppPageHeader({ title: 'Campaign settings' })}
      <div style={{ flex: 1, padding: '20px' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div style={{
          background: '#16213e',
          padding: '40px',
          borderRadius: '10px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
            <h1 style={{ color: '#e94560', margin: 0 }}>⚙️ Campaign Settings</h1>
            <button
              onClick={() => enterCampaign(selectedCampaign)}
              style={{
                padding: '10px 20px',
                background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                color: 'white',
                border: '2px solid #e94560',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: 'bold',
                fontSize: '16px',
                boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
                fontFamily: 'Cinzel, serif',
                transition: 'all 0.3s'
              }}
              onMouseOver={(e) => {
                e.target.style.boxShadow = '0 6px 25px rgba(233, 69, 96, 0.6)';
                e.target.style.transform = 'translateY(-2px)';
              }}
              onMouseOut={(e) => {
                e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
                e.target.style.transform = 'translateY(0)';
              }}
            >
              ▶ Enter Campaign
            </button>
          </div>

          {/* Campaign Name - Editable for Admin */}
          <div style={{ marginBottom: '30px', paddingBottom: '20px', borderBottom: '2px solid #2a2a4e' }}>
            {isEditingCampaignName ? (
              <div style={{ marginBottom: '15px' }}>
                <input
                  type="text"
                  value={editedCampaignName}
                  onChange={(e) => setEditedCampaignName(e.target.value)}
                  autoFocus
                  style={{
                    width: '100%',
                    padding: '12px',
                    fontSize: '24px',
                    fontWeight: 'bold',
                    color: '#e94560',
                    background: '#16213e',
                    border: '2px solid #e94560',
                    borderRadius: '8px',
                    marginBottom: '10px',
                    fontFamily: 'Cinzel, serif'
                  }}
                />
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleUpdateCampaignName}
                    disabled={loading}
                    style={{
                      padding: '8px 20px',
                      background: '#28a745',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    {loading ? 'Saving...' : '✓ Save'}
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingCampaignName(false);
                      setEditedCampaignName('');
                      setError('');
                    }}
                    style={{
                      padding: '8px 20px',
                      background: '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    ✗ Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '10px' }}>
                <h2 style={{ color: '#e94560', fontSize: '24px', margin: 0, fontFamily: 'Cinzel, serif' }}>
                  {selectedCampaign?.name}
                </h2>
                {user?.role === 'admin' && (
                  <button
                    onClick={() => {
                      setIsEditingCampaignName(true);
                      setEditedCampaignName(selectedCampaign?.name || '');
                    }}
                    style={{
                      padding: '6px 12px',
                      background: '#16213e',
                      color: '#e94560',
                      border: '2px solid #e94560',
                      borderRadius: '5px',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif'
                    }}
                  >
                    ✏️ Edit Name
                  </button>
                )}
              </div>
            )}
            <div style={{
              display: 'inline-block',
              padding: '5px 15px',
              background: 'rgba(157, 78, 221, 0.2)',
              color: '#9d4edd',
              border: '1px solid #9d4edd',
              borderRadius: '15px',
              fontSize: '14px',
              fontWeight: '600',
              fontFamily: 'Crimson Text, serif'
            }}>
              {selectedCampaign?.game_system}
            </div>
          </div>

          {/* Campaign Description/World Info */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '10px', fontFamily: 'Cinzel, serif' }}>
              📖 Campaign World & Setting
            </h3>
            {/* Warning about editing */}
            <div style={{
              background: 'rgba(233, 69, 96, 0.1)',
              border: '1px solid #e94560',
              borderRadius: '5px',
              padding: '10px',
              marginBottom: '10px',
              fontSize: '12px',
              color: '#e94560',
              fontFamily: 'Crimson Text, serif'
            }}>
              ⚠️ <strong>Warning:</strong> Changing this world setting will add or remove critical information that affects world generation, NPC behavior, and character interactions. Edit carefully.
            </div>
            {isEditingCampaignDesc ? (
              <div>
                <textarea
                  value={editedCampaignDesc}
                  onChange={(e) => setEditedCampaignDesc(e.target.value)}
                  autoFocus
                  style={{
                    width: '100%',
                    minHeight: '300px',
                    padding: '20px',
                    background: '#16213e',
                    color: '#d0d0e0',
                    border: '2px solid #e94560',
                    borderRadius: '8px',
                    fontSize: '15px',
                    lineHeight: '1.8',
                    fontFamily: 'Crimson Text, serif',
                    resize: 'vertical',
                    boxShadow: '0 0 20px rgba(233, 69, 96, 0.3)'
                  }}
                />
                <div style={{ marginTop: '10px', display: 'flex', gap: '10px' }}>
                  <button
                    onClick={handleUpdateCampaignDesc}
                    disabled={loading}
                    style={{
                      padding: '10px 20px',
                      background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                      color: 'white',
                      border: '2px solid #e94560',
                      borderRadius: '5px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif',
                      boxShadow: '0 4px 15px rgba(233, 69, 96, 0.4)',
                      opacity: loading ? 0.6 : 1
                    }}
                  >
                    ✓ Save Changes
                  </button>
                  <button
                    onClick={() => {
                      setIsEditingCampaignDesc(false);
                      setEditedCampaignDesc('');
                    }}
                    disabled={loading}
                    style={{
                      padding: '10px 20px',
                      background: '#6c757d',
                      color: 'white',
                      border: 'none',
                      borderRadius: '5px',
                      cursor: loading ? 'not-allowed' : 'pointer',
                      fontWeight: '600',
                      fontFamily: 'Cinzel, serif',
                      opacity: loading ? 0.6 : 1
                    }}
                  >
                    ✗ Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{
                background: '#16213e',
                padding: '20px',
                borderRadius: '8px',
                border: '2px solid #2a2a4e',
                whiteSpace: 'pre-wrap',
                lineHeight: '1.8',
                fontSize: '15px',
                color: '#d0d0e0',
                maxHeight: '400px',
                overflowY: 'auto',
                fontFamily: 'Crimson Text, serif',
                boxShadow: 'inset 0 0 20px rgba(0,0,0,0.3)'
              }}>
                {selectedCampaign?.description}
              </div>
            )}
          </div>

          {(String(user?.id) === String(selectedCampaign?.created_by) ||
            user?.role === 'admin') && (
            <div style={{
              marginBottom: '30px',
              padding: '20px',
              background: 'rgba(14, 165, 233, 0.08)',
              border: '1px solid #0ea5e9',
              borderRadius: '8px',
            }}
            >
              <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '12px', fontFamily: 'Cinzel, serif' }}>
                Open enrollment
              </h3>
              <p style={{ color: '#94a3b8', fontSize: '14px', marginBottom: '16px' }}>
                List this chronicle on the dashboard so players can self-join (subject to max players). You can still add people via the site admin if needed.
              </p>
              <form
                key={`enroll-${selectedCampaign?.id}`}
                onSubmit={handleSaveEnrollmentSettings}
                style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '420px' }}
              >
                <label style={{ color: '#b5b5c3', fontSize: '14px' }}>
                  Visibility
                  <select
                    name="listing_visibility"
                    defaultValue={selectedCampaign?.listing_visibility || 'private'}
                    style={{
                      display: 'block',
                      width: '100%',
                      marginTop: '6px',
                      padding: '10px',
                      background: '#0f1729',
                      border: '1px solid #2a2a4e',
                      borderRadius: '6px',
                      color: '#fff',
                    }}
                  >
                    <option value="private">Private (invite / admin only)</option>
                    <option value="listed">Listed on &quot;Open chronicles&quot;</option>
                  </select>
                </label>
                <label style={{ color: '#b5b5c3', fontSize: '14px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input
                    type="checkbox"
                    name="accepting_players"
                    defaultChecked={!!selectedCampaign?.accepting_players}
                  />
                  Accepting new players (self-serve join)
                </label>
                <label style={{ color: '#b5b5c3', fontSize: '14px' }}>
                  Max players (0 = no limit enforced here)
                  <input
                    type="number"
                    name="max_players"
                    min={0}
                    defaultValue={
                      selectedCampaign?.max_players != null ? selectedCampaign.max_players : 6
                    }
                    style={{
                      display: 'block',
                      width: '100%',
                      marginTop: '6px',
                      padding: '10px',
                      background: '#0f1729',
                      border: '1px solid #2a2a4e',
                      borderRadius: '6px',
                      color: '#fff',
                    }}
                  />
                </label>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    padding: '10px 18px',
                    background: loading ? '#475569' : '#0ea5e9',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: '600',
                    alignSelf: 'flex-start',
                  }}
                >
                  Save enrollment
                </button>
              </form>
            </div>
          )}

          {/* Admin Actions */}
          <div style={{ marginBottom: '30px' }}>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px' }}>
              👑 Admin Actions
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <button
                onClick={() => {
                  setIsEditingCampaignDesc(true);
                  setEditedCampaignDesc(selectedCampaign?.description || '');
                }}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => {
                  e.target.style.background = '#ff556f';
                  e.target.style.boxShadow = '0 4px 15px rgba(233, 69, 96, 0.4)';
                }}
                onMouseOut={(e) => {
                  e.target.style.background = '#e94560';
                  e.target.style.boxShadow = 'none';
                }}
              >
                ✏️ Edit Campaign Info
              </button>
              <button 
                onClick={() => showInfo('👥 Player management UI coming soon!\n\nFor now, players can join campaigns through invite codes.', 6000)}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                👥 Manage Players
              </button>
              <button 
                onClick={openLocationManager}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600',
                  fontFamily: 'Cinzel, serif'
                }}
              >
                🗺️ Manage Locations
              </button>
              <button 
                onClick={() => showInfo('📚 Rule book management coming soon!')}
                style={{
                  padding: '12px',
                  background: '#e94560',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                📚 Add Rule Books
              </button>
              <button 
                onClick={() => showInfo('💾 Export feature coming soon!')}
                style={{
                  padding: '12px',
                  background: '#ffc107',
                  color: '#e94560',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                💾 Export Campaign
              </button>
              <button 
                onClick={() => {
                  setDeleteConfirmText('');
                  setShowDeleteConfirm(true);
                }}
                style={{
                  padding: '12px',
                  background: '#dc3545',
                  color: 'white',
                  border: 'none',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                🗑️ Delete Campaign
              </button>
            </div>
          </div>

          {/* Campaign Stats - Gothic Horror Style */}
          <div>
            <h3 style={{ color: '#e94560', fontSize: '18px', marginBottom: '15px', fontFamily: 'Cinzel, serif' }}>
              💀 Campaign Statistics
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
              {/* Active Players - Blood Red */}
              <div style={{ 
                background: '#1a0a0a', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(233, 69, 96, 0.3)',
                boxShadow: '0 0 15px rgba(233, 69, 96, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#e94560', fontFamily: 'Cinzel, serif' }}>{campaignStats.active_players}</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-users"></i> Active Players
                </div>
              </div>
              
              {/* Characters - Purple Magic */}
              <div style={{ 
                background: '#0a0a1a', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(157, 78, 221, 0.3)',
                boxShadow: '0 0 15px rgba(157, 78, 221, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#9d4edd', fontFamily: 'Cinzel, serif' }}>{campaignStats.characters}</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-user-secret"></i> Characters
                </div>
              </div>
              
              {/* Locations - Amber Werewolf */}
              <div style={{ 
                background: '#1a1206', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(217, 119, 6, 0.3)',
                boxShadow: '0 0 15px rgba(217, 119, 6, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#d97706', fontFamily: 'Cinzel, serif' }}>{campaignStats.locations}</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-map-marker-alt"></i> Story locations
                </div>
              </div>
              
              {/* Messages - Silver */}
              <div style={{ 
                background: '#0f0f0f', 
                padding: '15px', 
                borderRadius: '8px', 
                textAlign: 'center',
                border: '2px solid rgba(181, 181, 195, 0.3)',
                boxShadow: '0 0 15px rgba(181, 181, 195, 0.2)'
              }}>
                <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#b5b5c3', fontFamily: 'Cinzel, serif' }}>{campaignStats.messages}</div>
                <div style={{ fontSize: '12px', color: '#8b8b9f', marginTop: '8px', fontFamily: 'Crimson Text, serif', textTransform: 'uppercase', letterSpacing: '1px' }}>
                  <i className="fas fa-comment"></i> Story messages
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      </div>
      <Footer />
    </div>
  );

  // Render create campaign page
  const renderCreateCampaign = () => (
    <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
      {renderAppPageHeader({ title: 'Create campaign' })}
      <div style={{ flex: 1, padding: '20px' }}>
      <div style={{ maxWidth: '700px', margin: '0 auto' }}>
        <div style={{
          background: '#16213e',
          padding: '40px',
          borderRadius: '10px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.1)'
        }}>
          <h1 style={{ color: '#e94560', marginBottom: '30px' }}>✨ Create New Campaign</h1>

          <form onSubmit={handleCreateCampaign}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Campaign Name:
              </label>
              <input
                type="text"
                name="campaignName"
                required
                placeholder="Enter campaign name..."
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Description:
              </label>
              <textarea
                name="description"
                rows="5"
                required
                placeholder="Describe your campaign..."
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                  resize: 'vertical'
                }}
              ></textarea>
            </div>

            <div style={{ marginBottom: '30px' }}>
              <label style={{
                display: 'block',
                marginBottom: '8px',
                color: '#b5b5c3',
                fontWeight: '600',
                fontSize: '15px'
              }}>
                Game System:
              </label>
              <select
                name="game_system"
                required
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '2px solid #2a2a4e',
                  borderRadius: '5px',
                  fontSize: '16px',
                  color: '#e94560',
                  background: '#0f1729',
                  cursor: 'pointer',
                  boxSizing: 'border-box'
                }}
              >
                <option value="vampire">🧛 Vampire: The Masquerade</option>
                <option value="werewolf">🐺 Werewolf: The Apocalypse</option>
                <option value="mage">✨ Mage: The Ascension</option>
                <option value="custom">🎲 Custom System</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                padding: '15px',
                background: loading ? '#ccc' : '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '16px',
                fontWeight: 'bold',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
              }}
            >
              {loading ? '⏳ Creating...' : '🚀 Create Campaign'}
            </button>
          </form>

          {error && (
            <div style={{
              marginTop: '20px',
              padding: '15px',
              background: '#fee',
              border: '2px solid #fcc',
              borderRadius: '8px',
              color: '#c33',
              fontWeight: '500'
            }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </div>
      </div>
      <Footer />
    </div>
  );

  const submitSidebarRoll = async () => {
    if (!token || !selectedCampaign?.id || !currentLocation?.id) {
      showError('Join a campaign room first.');
      return;
    }
    let poolSize;
    try {
      poolSize = parseStorytellerPool(rollPoolInput);
    } catch (e) {
      showError(e.message || 'Invalid pool');
      return;
    }
    if (poolSize < 1) {
      showError('Pool must be at least 1.');
      return;
    }
    if (poolSize > 50) {
      showError('Pool cannot exceed 50 dice.');
      return;
    }
    const d = Number(rollDifficulty);
    if (Number.isNaN(d) || d < 2 || d > 10) {
      showError('Difficulty must be between 2 and 10.');
      return;
    }
    setRollSubmitting(true);
    try {
      const rollRes = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}/roll`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          pool_size: poolSize,
          difficulty: d,
          specialty: rollSpecialty,
          character_id: character?.id ?? undefined,
          action_description: rollReason.trim() || 'Dice roll',
          location_id: currentLocation.id,
        }),
      });
      const rollData = await rollRes.json().catch(() => ({}));
      if (!rollRes.ok) {
        showError(rollData.error || 'Roll failed.');
        return;
      }
      const rollResult = rollData.roll_result || {};
      const chatBody = rollData.chat_message || '';

      const results = Array.isArray(rollResult.results) ? rollResult.results : [];
      const preview = results.slice(0, 10);
      const extraDiceCount = Math.max(0, results.length - preview.length);

      const startedAtMs = Date.now();
      const durationMs = 3000;
      const animationId = _makeDiceAnimationId();

      const isCampaignOwner =
        selectedCampaign?.created_by != null &&
        user?.id != null &&
        String(selectedCampaign.created_by) === String(user.id);
      const canHideRollToOthers =
        user?.role === 'admin' || user?.role === 'helper' || isCampaignOwner;
      const hiddenToOthers = canHideRollToOthers && rollHideOthers;

      const markerKind = hiddenToOthers
        ? `dice_animation_hidden:${animationId}`
        : `dice_animation:${animationId}`;
      const finalKind = hiddenToOthers
        ? `dice_roll_hidden:${animationId}`
        : `dice_roll:${animationId}`;

      const markerObj = {
        animation_id: animationId,
        started_at_ms: startedAtMs,
        duration_ms: durationMs,
        difficulty: Number(rollResult.difficulty || d),
        dice_preview: preview,
        extra_dice_count: extraDiceCount,
        successes: Number(rollResult.successes || 0),
        is_botch: Boolean(rollResult.is_botch),
        is_critical: Boolean(rollResult.is_critical),
        pool_size: results.length,
      };

      // Start local animation immediately; the final chat line is hidden until the timer completes.
      startDiceAnimationFromMarker(markerObj);

      const markerRes = await fetch(
        `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: JSON.stringify(markerObj),
            message_type: 'system',
            role: 'assistant',
            ai_message_kind: markerKind,
          }),
        }
      );
      const markerData = await markerRes.json().catch(() => ({}));
      if (!markerRes.ok) {
        showError(markerData.error || 'Could not post dice animation marker.');
        return;
      }

      const msgRes = await fetch(
        `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: chatBody,
            message_type: 'action',
            role: 'user',
            ai_message_kind: finalKind,
            ...(character?.id ? { character_id: character.id } : {}),
          }),
        }
      );
      const msgData = await msgRes.json().catch(() => ({}));
      if (!msgRes.ok) {
        showError(msgData.error || 'Roll saved but could not post to chat.');
        return;
      }

      setMessages((prev) => [...prev, markerData.data, msgData.data]);
      scrollChatToBottomSoon();
      setShowRollModal(false);
      showSuccess(hiddenToOthers ? 'Private roll posted to this room.' : 'Roll posted to this room.');
    } catch (err) {
      console.error(err);
      showError('Network error while rolling.');
    } finally {
      setRollSubmitting(false);
    }
  };

  const saveAdminDiceLeniency = async (opts) => {
    if (!token || !selectedCampaign?.id || !currentLocation?.id) {
      showError('Join a campaign room first.');
      return;
    }
    setAdminDiceSaving(true);
    try {
      let body;
      if (opts?.restore) {
        body = { dice_leniency_floor: null };
      } else {
        const t = adminDiceFloorDraft.trim();
        if (!t) {
          showError('Enter a floor from 2–10, or tap Restore normal.');
          return;
        }
        const n = parseInt(t, 10);
        if (Number.isNaN(n) || n < 2 || n > 10) {
          showError('Enter a floor from 2–10, or tap Restore normal.');
          return;
        }
        body = { dice_leniency_floor: n };
      }
      const res = await fetch(
        `${API_URL}/campaigns/${selectedCampaign.id}/locations/${currentLocation.id}/dice-leniency`,
        {
          method: 'PUT',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(body),
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError(data.error || 'Could not update dice rules.');
        return;
      }
      const locs = await fetchCampaignLocations(selectedCampaign.id);
      setLocations(locs);
      const upd = locs.find((l) => l.id === currentLocation.id);
      if (upd) setCurrentLocation(upd);
      showSuccess(
        data.dice_leniency_floor != null
          ? `Leniency floor ${data.dice_leniency_floor} saved for this room.`
          : 'Leniency off — normal d10 randomness for this room.'
      );
      if (opts?.restore) setAdminDiceFloorDraft('');
      setShowAdminDiceRulesModal(false);
    } catch (e) {
      console.error(e);
      showError('Network error.');
    } finally {
      setAdminDiceSaving(false);
    }
  };

  const openDiceHistory = async () => {
    if (!token || !selectedCampaign?.id || !currentLocation?.id) {
      showError('Join a campaign room first.');
      return;
    }
    setShowDiceHistoryModal(true);
    setDiceHistoryError(null);
    setDiceHistoryLoading(true);
    setDiceHistoryRows([]);
    try {
      const res = await fetch(
        `${API_URL}/campaigns/${selectedCampaign.id}/rolls?location_id=${currentLocation.id}&limit=100`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setDiceHistoryError(data.error || 'Could not load roll history.');
        return;
      }
      setDiceHistoryRows(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setDiceHistoryError('Network error while loading history.');
    } finally {
      setDiceHistoryLoading(false);
    }
  };

  const closeRollModal = () => {
    setShowDiceHistoryModal(false);
    setShowRollModal(false);
  };

  // Render in-campaign chat (Gothic "Dark Conclave" style — matches GothicShowcase preview)
  const renderChat = () => {
    const campaignTheme = getCampaignTheme(selectedCampaign);
    const isCampaignOwner =
      selectedCampaign?.created_by != null &&
      user?.id != null &&
      String(selectedCampaign.created_by) === String(user.id);
    const canHideRollToOthers =
      user?.role === 'admin' || user?.role === 'helper' || isCampaignOwner;

    return (
    <div style={{
      height: '100vh',
      maxHeight: '100vh',
      width: '100%',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'stretch',
      background: '#0f0f1e',
      position: 'relative'
    }}>
      {diceOverlay.visible && (
        <div
          role="presentation"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 3000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0,0,0,0.35)',
            padding: '16px',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            style={{
              width: 'min(760px, 100%)',
              background: 'linear-gradient(135deg, rgba(157, 78, 221, 0.18) 0%, rgba(233, 69, 96, 0.12) 100%)',
              border: '2px solid rgba(233, 69, 96, 0.35)',
              borderRadius: '14px',
              boxShadow: '0 20px 70px rgba(0,0,0,0.65)',
              padding: '18px 18px 16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px', marginBottom: '10px' }}>
              <div style={{ color: '#e94560', fontFamily: 'Cinzel, serif', fontSize: '18px', fontWeight: 700 }}>
                <i className="fas fa-dice" style={{ marginRight: '10px' }} />
                Rolling…
              </div>
              <div style={{ color: '#b5b5c3', fontFamily: 'Crimson Text, serif', fontSize: '12px' }}>
                TN {diceOverlay.difficulty} · {diceOverlay.successes} net
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
              {diceOverlay.diceFinal.map((_, i) => {
                const v = diceOverlay.diceRolling[i] ?? diceOverlay.diceFinal[i] ?? 1;
                const isSuccess = v >= diceOverlay.difficulty;
                const isBotchDie = v === 1;
                const bg = isBotchDie
                  ? '#8b0000'
                  : v === 10
                    ? '#ffd700'
                    : isSuccess
                      ? '#2d7a3e'
                      : '#374151';
                return (
                  <div
                    key={`${diceOverlay.animationId}-die-${i}`}
                    style={{
                      width: '54px',
                      height: '54px',
                      borderRadius: '12px',
                      border: '1px solid rgba(255,255,255,0.12)',
                      background: `linear-gradient(180deg, ${bg} 0%, rgba(15, 23, 41, 0.2) 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      boxShadow: '0 10px 35px rgba(0,0,0,0.45)',
                      color: v === 10 ? '#1b1b1b' : 'white',
                      fontFamily: 'Cinzel, serif',
                      fontSize: '18px',
                      fontWeight: 900,
                      userSelect: 'none',
                    }}
                  >
                    {v}
                  </div>
                );
              })}
              {diceOverlay.extraDiceCount > 0 && (
                <div style={{ alignSelf: 'center', color: '#8b8b9f', fontFamily: 'Crimson Text, serif', fontSize: '14px', marginLeft: '4px' }}>
                  +{diceOverlay.extraDiceCount} more
                </div>
              )}
            </div>

            <div style={{ marginTop: '12px', color: '#b5b5c3', fontFamily: 'Crimson Text, serif', fontSize: '12px', textAlign: 'center' }}>
              The roll resolves right after the dice stop.
            </div>
          </div>
        </div>
      )}
      {/* Mobile Menu Buttons */}
      {isMobile && (
        <>
          <button
            onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            style={{
              position: 'fixed',
              top: '10px',
              left: '10px',
              zIndex: 1001,
              background: '#2f3136',
              border: '2px solid #e94560',
              color: '#e94560',
              padding: '10px',
              borderRadius: '8px',
              cursor: 'pointer',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px'
            }}
          >
            {leftSidebarOpen ? '✕' : '☰'}
          </button>
          <button
            onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
            style={{
              position: 'fixed',
              top: '10px',
              right: '10px',
              zIndex: 1001,
              background: '#2f3136',
              border: '2px solid #e94560',
              color: '#e94560',
              padding: '10px',
              borderRadius: '8px',
              cursor: 'pointer',
              minWidth: '44px',
              minHeight: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px'
            }}
          >
            {rightSidebarOpen ? '✕' : '👤'}
          </button>
        </>
      )}

      {/* Sidebar Overlay for Mobile */}
      {isMobile && (leftSidebarOpen || rightSidebarOpen) && (
        <div
          onClick={() => {
            setLeftSidebarOpen(false);
            setRightSidebarOpen(false);
          }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            zIndex: 999
          }}
        />
      )}

      {/* Left Sidebar - Locations/Channels */}
      <div style={{
        width: isMobile ? '280px' : '240px',
        background: '#16213e',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '2px solid #2a2a4e',
        position: isMobile ? 'fixed' : 'relative',
        left: isMobile ? (leftSidebarOpen ? '0' : '-280px') : 'auto',
        top: isMobile ? '0' : 'auto',
        bottom: isMobile ? '0' : 'auto',
        zIndex: 1000,
        transition: 'left 0.3s ease',
        height: isMobile ? '100vh' : '100%',
        maxHeight: '100vh',
        minHeight: 0,
        flexShrink: 0,
        overflow: 'hidden'
      }}>
        {/* Campaign Header */}
        <div style={{
          padding: '15px',
          borderBottom: '2px solid #2a2a4e',
          color: '#e94560',
          fontWeight: 'bold',
          fontSize: '16px',
          fontFamily: 'Cinzel, serif'
        }}>
          🎲 {selectedCampaign?.name}
        </div>

        {/* Locations/Channels */}
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '10px 0' }}>
          <div style={{
            padding: '5px 15px',
            color: '#8b8b9f',
            fontSize: '12px',
            fontWeight: '600',
            textTransform: 'uppercase',
            marginTop: '10px',
            fontFamily: 'Cinzel, serif',
            letterSpacing: '0.05em'
          }}>
            Locations
          </div>
          {locations.map(loc => (
            <div
              key={loc.id}
              onClick={() => changeLocation(loc)}
              style={{
                padding: '8px 15px',
                margin: '2px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
                color: currentLocation?.id === loc.id ? '#e0e0e0' : '#b5b5c3',
                background: currentLocation?.id === loc.id ? 'rgba(233, 69, 96, 0.15)' : 'transparent',
                border: currentLocation?.id === loc.id ? '1px solid rgba(233, 69, 96, 0.35)' : '1px solid transparent',
                fontSize: '15px',
                fontFamily: 'Crimson Text, serif',
                transition: 'all 0.15s',
                opacity: loc.is_open === false || loc.is_open === 0 ? 0.75 : 1,
              }}
              onMouseOver={(e) => {
                if (currentLocation?.id !== loc.id) {
                  e.currentTarget.style.background = 'rgba(139, 139, 159, 0.08)';
                  e.currentTarget.style.color = '#dcddde';
                }
              }}
              onMouseOut={(e) => {
                if (currentLocation?.id !== loc.id) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#b5b5c3';
                }
              }}
            >
              {(loc.is_open === false || loc.is_open === 0 ? '🚫 ' : '')}
              {loc.name}
            </div>
          ))}
        </div>

        {/* User Info at Bottom */}
        <div style={{
          padding: '10px',
          background: '#0f1729',
          borderTop: '2px solid #2a2a4e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
        }}>
          <div style={{ color: '#b5b5c3', fontSize: '14px', fontWeight: '500', fontFamily: 'Crimson Text, serif', minWidth: 0 }}>
            <i className="fas fa-user" style={{ marginRight: '6px', color: '#8b8b9f' }} />
            {user?.username}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: '6px', flexShrink: 0 }}>
            {canHideRollToOthers && (
              <button
                type="button"
                onClick={() => navigateTo('profile')}
                style={{
                  padding: '5px 10px',
                  background: 'rgba(157, 78, 221, 0.12)',
                  color: '#d8b4fe',
                  border: '1px solid rgba(124, 58, 237, 0.45)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '11px',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                Profile
              </button>
            )}
            <button
              type="button"
              onClick={handleLeaveCampaign}
              style={{
                padding: '5px 10px',
                background: 'rgba(233, 69, 96, 0.15)',
                color: '#e94560',
                border: '1px solid rgba(233, 69, 96, 0.4)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px',
                fontFamily: 'Cinzel, serif'
              }}
            >
              🚪 Exit
            </button>
          </div>
        </div>
      </div>

      {/* Main Chat Area with Campaign Theme */}
      <GothicBox theme={campaignTheme} style={{
        flex: 1,
        minWidth: 0,
        minHeight: 0,
        maxHeight: '100vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative'
      }}>
        {/* Channel Header */}
        <div style={{
          flexShrink: 0,
          minHeight: '52px',
          borderBottom: '2px solid #2a2a4e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 20px',
          background: '#16213e',
          fontFamily: 'Cinzel, serif'
        }}>
          <span style={{ color: '#e94560', fontSize: '17px', fontWeight: '600' }}>
            <i className="fas fa-comments" style={{ marginRight: '10px', opacity: 0.9 }} />
            {currentLocation?.name || 'Select a location'}
          </span>
          <span style={{
            fontSize: '11px',
            color: '#8b8b9f',
            background: '#0f1729',
            padding: '4px 10px',
            borderRadius: '4px',
            border: '1px solid #2a2a4e',
            fontFamily: 'Crimson Text, serif'
          }}>
            {campaignTheme || 'gothic'}
          </span>
        </div>

        {/* Pinned Topic / Room Description */}
        {currentLocation?.description && currentLocation.description.trim() && (
          <div style={{
            flexShrink: 0,
            padding: '12px 20px',
            background: '#0f1729',
            borderBottom: '2px solid #2a2a4e',
            color: '#b5b5c3',
            fontSize: '14px',
            lineHeight: '1.5',
            fontFamily: 'Crimson Text, serif'
          }}>
            <span style={{ color: '#e94560', marginRight: '8px' }}><i className="fas fa-thumbtack" /></span>
            {currentLocation.description}
          </div>
        )}

        {/* Messages Area — Dark Conclave style (matches GothicShowcase) */}
        <div
          ref={chatMessagesScrollRef}
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            overflowX: 'hidden',
            overscrollBehavior: 'contain',
            WebkitOverflowScrolling: 'touch',
            padding: '16px 20px',
            background: '#0f1729',
            borderLeft: 'none',
            borderRight: 'none'
          }}
        >
          <div style={{
            background: '#0f1729',
            border: '2px solid #2a2a4e',
            borderRadius: '8px',
            padding: '16px',
            minHeight: '120px'
          }}>
          {messages.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '40px 20px',
              color: '#8b8b9f',
              fontFamily: 'Crimson Text, serif'
            }}>
              <div style={{ fontSize: '40px', marginBottom: '10px', opacity: 0.7 }}><i className="fas fa-moon" /></div>
              <div style={{ fontSize: '17px', fontWeight: '600', marginBottom: '8px', color: '#b5b5c3', fontFamily: 'Cinzel, serif' }}>
                No whispers yet
              </div>
              <div style={{ fontSize: '15px' }}>
                Start the conversation in {currentLocation?.name}!
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const mk = (msg.ai_message_kind || '').toLowerCase();
              // Marker messages should never appear in the chat list.
              if (mk.startsWith('dice_animation:') || mk.startsWith('dice_animation_hidden:')) {
                return null;
              }
              // Dice-roll final reveal is controlled by pendingDiceAnimations.
              if (mk.startsWith('dice_roll:') || mk.startsWith('dice_roll_hidden:')) {
                const parts = mk.split(':');
                const animationId = parts.length >= 2 ? parts[1] : null;
                const id = animationId ? String(animationId) : null;
                const revealAtMs = id ? diceMarkerRevealAtById[id] : null;
                if (
                  id &&
                  (pendingDiceAnimations[id] ||
                    (revealAtMs != null && Date.now() < revealAtMs))
                ) {
                  return null;
                }
              }

              const line = getChatMessagePresentation(msg);
              const isAI = msg.role === 'assistant';
              const subLabel = line.subLabel;

              return (
              <div key={msg.id || idx} style={{ marginBottom: '15px' }}>
                {firstUnreadMessageId && msg.id === firstUnreadMessageId && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    margin: '10px 0 16px',
                    color: '#e94560',
                    fontSize: '11px',
                    fontWeight: '700',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    fontFamily: 'Cinzel, serif'
                  }}>
                    <div style={{ flex: 1, height: '1px', background: 'rgba(233, 69, 96, 0.45)' }} />
                    Unread messages
                    <div style={{ flex: 1, height: '1px', background: 'rgba(233, 69, 96, 0.45)' }} />
                  </div>
                )}
                <div style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start'
                }}>
                  {!isAI && (() => {
                    const inOocRoom =
                      String(currentLocation?.type || '').toLowerCase() === 'ooc';
                    const avatarUrl =
                      inOocRoom && msg.player_avatar_url
                        ? msg.player_avatar_url
                        : msg.character_portrait_url;
                    return (
                      <div style={{ paddingTop: '4px' }}>
                        <MessageCharacterAvatar url={avatarUrl} size={40} />
                      </div>
                    );
                  })()}
                  <div style={{
                    flex: 1,
                    minWidth: 0,
                    padding: '12px',
                    background: line.bg,
                    borderLeft: `3px solid ${line.border}`,
                    borderRadius: '4px'
                  }}>
                    <div style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'center',
                      justifyContent: 'flex-start',
                      gap: '8px',
                      marginBottom: '6px',
                      fontWeight: 'bold',
                      color: line.nameColor,
                      fontFamily: 'Cinzel, serif',
                      fontSize: '14px',
                    }}>
                      <span>
                        <i className={`fas ${line.icon}`} style={{ marginRight: '8px' }} />
                        {line.label}
                      </span>
                      {subLabel && (
                        <span style={{ fontWeight: '500', color: '#8b8b9f', fontSize: '12px' }}>
                          {subLabel}
                        </span>
                      )}
                      <span
                        title={msg.created_at ? formatDateTimeTooltip(msg.created_at, user?.display_timezone || null) : undefined}
                        style={{ color: '#8b8b9f', fontSize: '12px', fontWeight: '500', fontFamily: 'Crimson Text, serif' }}
                      >
                        {formatMessageTime(msg.created_at, chatNow, user?.display_timezone || null)}
                      </span>
                    </div>
                    <div
                      id={msg.id ? `msg-${msg.id}` : undefined}
                      style={{
                        color: '#d0d0d0',
                        fontFamily: 'Crimson Text, serif',
                        fontSize: '16px',
                        lineHeight: 1.55,
                        fontStyle: line.italic ? 'italic' : 'normal'
                      }}
                    >
                      {renderMessageContent(msg.content)}
                    </div>
                  </div>
                </div>
              </div>
              );
            })
          )}
          {loading && (
            <div style={{ textAlign: 'center', color: '#9d4edd', padding: '20px', fontFamily: 'Cinzel, serif' }}>
              <div><i className="fas fa-scroll" style={{ marginRight: '8px' }} />The storyteller ponders...</div>
            </div>
          )}
          </div>
        </div>

        {/* Input Area */}
        <div style={{ flexShrink: 0, padding: '20px', background: '#16213e', borderTop: '2px solid #2a2a4e' }}>
          {firstUnreadMessageId && (
            <div style={{
              marginBottom: '10px',
              display: 'flex',
              gap: '10px',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ color: '#e94560', fontSize: '12px', fontFamily: 'Crimson Text, serif' }}>
                {locationReadState?.first_unread_at
                  ? `You have unread messages since ${formatDateTimeInZone(locationReadState.first_unread_at, user?.display_timezone || null)}`
                  : 'You have unread messages'}
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => jumpToMessage(firstUnreadMessageId)}
                  style={{
                    padding: '6px 10px',
                    background: '#0f1729',
                    color: '#b5b5c3',
                    border: '1px solid #2a2a4e',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontFamily: 'Cinzel, serif'
                  }}
                >
                  Jump to first unread
                </button>
                <button
                  type="button"
                  onClick={markLocationRead}
                  style={{
                    padding: '6px 10px',
                    background: 'rgba(157, 78, 221, 0.2)',
                    color: '#d8b4fe',
                    border: '1px solid rgba(157, 78, 221, 0.45)',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    fontSize: '12px',
                    fontFamily: 'Cinzel, serif'
                  }}
                >
                  Mark as read
                </button>
              </div>
            </div>
          )}
          <form onSubmit={handleSendMessage}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                ref={chatInputRef}
                type="text"
                name="message"
                placeholder="Whisper to the darkness..."
                disabled={loading}
                autoFocus
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  background: '#0f1729',
                  border: '2px solid #2a2a4e',
                  borderRadius: '8px',
                  color: '#e0e0e0',
                  fontSize: '16px',
                  outline: 'none',
                  fontFamily: 'Crimson Text, serif'
                }}
              />
              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '12px 24px',
                  background: loading ? '#4a4a5e' : '#e94560',
                  color: 'white',
                  border: '2px solid rgba(233, 69, 96, 0.5)',
                  borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: '600',
                  fontSize: '15px',
                  fontFamily: 'Cinzel, serif',
                  boxShadow: loading ? 'none' : '0 4px 15px rgba(233, 69, 96, 0.25)'
                }}
              >
                {loading ? 'Sending...' : <><i className="fas fa-paper-plane" style={{ marginRight: '8px' }} />Send</>}
              </button>
            </div>
          </form>

          {error && (
            <div style={{
              marginTop: '10px',
              padding: '12px',
              background: 'rgba(233, 69, 96, 0.12)',
              color: '#e94560',
              borderRadius: '6px',
              fontSize: '14px',
              border: '1px solid rgba(233, 69, 96, 0.35)',
              fontFamily: 'Crimson Text, serif'
            }}>
              ⚠️ {error}
            </div>
          )}
        </div>
      </GothicBox>

      {/* Right Sidebar - Character Info */}
      <div style={{
        width: isMobile ? '280px' : '280px',
        background: '#16213e',
        borderLeft: '2px solid #2a2a4e',
        padding: '20px',
        position: isMobile ? 'fixed' : 'relative',
        right: isMobile ? (rightSidebarOpen ? '0' : '-280px') : 'auto',
        top: isMobile ? '0' : 'auto',
        bottom: isMobile ? '0' : 'auto',
        zIndex: 1000,
        transition: 'right 0.3s ease',
        height: isMobile ? '100vh' : '100%',
        maxHeight: '100vh',
        minHeight: 0,
        flexShrink: 0,
        overflowY: 'auto',
        overscrollBehavior: 'contain'
      }}>
        <h3 style={{ color: '#e94560', marginBottom: '15px', fontSize: '16px', fontWeight: '600', fontFamily: 'Cinzel, serif' }}>
          <i className="fas fa-id-card" style={{ marginRight: '8px' }} />
          Character Info
        </h3>
        
        {campaignCharacters.length > 1 && (
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', color: '#8b8b9f', fontSize: '12px', marginBottom: '6px', fontFamily: 'Cinzel, serif' }}>
              Active character
            </label>
            <select
              value={character?.id ?? ''}
              onChange={(e) => {
                const id = parseInt(e.target.value, 10);
                const next = campaignCharacters.find((c) => c.id === id) || null;
                setCharacter(next);
                if (selectedCampaign?.id && currentLocation?.id) {
                  loadMessages(selectedCampaign.id, currentLocation.id, { characterForRead: next });
                }
              }}
              style={{
                width: '100%',
                padding: '8px 10px',
                background: '#0f1729',
                color: '#b5b5c3',
                border: '1px solid #2a2a4e',
                borderRadius: '6px',
                fontSize: '13px',
                fontFamily: 'Crimson Text, serif',
              }}
            >
              {campaignCharacters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {character ? (
          <div>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', marginBottom: '12px' }}>
              <MessageCharacterAvatar url={character.portrait_url} size={56} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#b5b5c3', fontSize: '16px', fontWeight: '600', fontFamily: 'Cinzel, serif' }}>
                  {character.name}
                </div>
                <label style={{
                  display: 'inline-block',
                  marginTop: '8px',
                  padding: '6px 10px',
                  background: 'rgba(157, 78, 221, 0.15)',
                  color: '#d8b4fe',
                  border: '1px solid rgba(157, 78, 221, 0.35)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  fontFamily: 'Cinzel, serif',
                }}>
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      e.target.value = '';
                      if (!f || !character?.id) return;
                      if (f.size > 350000) {
                        showError('Image is too large (max ~350KB).');
                        return;
                      }
                      const reader = new FileReader();
                      reader.onload = async () => {
                        const dataUrl = reader.result;
                        if (typeof dataUrl !== 'string') return;
                        try {
                          const res = await fetch(`${API_URL}/characters/${character.id}`, {
                            method: 'PUT',
                            headers: {
                              Authorization: `Bearer ${token}`,
                              'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ portrait_url: dataUrl }),
                          });
                          if (!res.ok) {
                            const err = await res.json().catch(() => ({}));
                            showError(err.error || 'Could not save portrait.');
                            return;
                          }
                          const body = await res.json();
                          const updated = body.character;
                          if (updated) {
                            setCharacter(updated);
                            setCampaignCharacters((prev) =>
                              prev.map((c) => (c.id === updated.id ? { ...c, ...updated } : c))
                            );
                            showSuccess('Portrait updated.');
                          }
                        } catch (err) {
                          showError(err.message || 'Could not save portrait.');
                        }
                      };
                      reader.readAsDataURL(f);
                    }}
                  />
                  <i className="fas fa-image" style={{ marginRight: '6px' }} />
                  Portrait
                </label>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ color: '#8b8b9f', fontSize: '14px', lineHeight: '1.5', fontFamily: 'Crimson Text, serif' }}>
            <p>No character in this campaign.</p>
            <p style={{ marginTop: '10px' }}>
              Create a character (API or tools) to play in-character and set a portrait here.
            </p>
          </div>
        )}

        <div style={{ marginTop: '30px', paddingTop: '20px', borderTop: '2px solid #2a2a4e' }}>
          <h4 style={{ color: '#b5b5c3', marginBottom: '10px', fontSize: '14px', fontWeight: '600', fontFamily: 'Cinzel, serif' }}>
            <i className="fas fa-bolt" style={{ marginRight: '6px', color: '#9d4edd' }} />
            Quick Actions
          </h4>
          <button
            type="button"
            onClick={() => setShowRollModal(true)}
            style={{
              width: '100%',
              padding: '8px',
              background: '#0f1729',
              color: '#b5b5c3',
              border: '1px solid #2a2a4e',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '13px',
              marginBottom: '8px',
              fontFamily: 'Cinzel, serif'
            }}
          >
            🎲 Roll Dice
          </button>
          {user?.role === 'admin' && (
            <button
              type="button"
              onClick={() => {
                const f = currentLocation?.dice_leniency_floor;
                setAdminDiceFloorDraft(
                  f !== undefined && f !== null && f !== '' ? String(f) : ''
                );
                setShowAdminDiceRulesModal(true);
              }}
              style={{
                width: '100%',
                padding: '8px',
                background: 'rgba(157, 78, 221, 0.12)',
                color: '#d8b4fe',
                border: '1px solid rgba(124, 58, 237, 0.45)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '13px',
                marginBottom: '8px',
                fontFamily: 'Cinzel, serif',
              }}
            >
              Admin Dice Rules
            </button>
          )}
          <button style={{
            width: '100%',
            padding: '8px',
            background: '#0f1729',
            color: '#b5b5c3',
            border: '1px solid #2a2a4e',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px',
            marginBottom: '8px',
            fontFamily: 'Cinzel, serif'
          }}>
            📚 Search Rules
          </button>
          <button style={{
            width: '100%',
            padding: '8px',
            background: '#0f1729',
            color: '#b5b5c3',
            border: '1px solid #2a2a4e',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '13px',
            fontFamily: 'Cinzel, serif'
          }}>
            👤 View Character
          </button>
        </div>
      </div>

      {showRollModal && (
        <div
          role="presentation"
          onClick={() =>
            !rollSubmitting && !showDiceHistoryModal && setShowRollModal(false)
          }
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.75)',
            zIndex: 2000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="roll-dice-title"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '420px', width: '100%' }}
          >
            <GothicBox theme="none" style={{ background: '#16213e', padding: '22px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'space-between',
                  gap: '12px',
                  marginBottom: '14px',
                }}
              >
                <h3
                  id="roll-dice-title"
                  style={{
                    color: '#e94560',
                    fontSize: '17px',
                    margin: 0,
                    flex: 1,
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  <i className="fas fa-dice" style={{ marginRight: '8px' }} />
                  Roll dice (Storyteller)
                </h3>
                {user?.role === 'admin' && (
                  <button
                    type="button"
                    disabled={rollSubmitting}
                    onClick={() => openDiceHistory()}
                    style={{
                      flexShrink: 0,
                      padding: '6px 10px',
                      fontSize: '11px',
                      fontFamily: 'Cinzel, serif',
                      background: '#0f1729',
                      color: '#d8b4fe',
                      border: '1px solid #6b21a8',
                      borderRadius: '6px',
                      cursor: rollSubmitting ? 'not-allowed' : 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    History
                  </button>
                )}
              </div>
              <p style={{ color: '#8b8b9f', fontSize: '13px', marginBottom: '16px', fontFamily: 'Crimson Text, serif', lineHeight: 1.5 }}>
                Old World of Darkness style: pool of <strong>d10</strong>, difficulty (target number) usually 6–9.
                Each die ≥ difficulty is a success; <strong>1s cancel</strong> successes. Optional: specialty (10s = 2 successes).
                See <code style={{ color: '#d8b4fe' }}>docs/dice-old-wod.md</code> for details.
              </p>
              <label style={{ display: 'block', color: '#b5b5c3', fontSize: '12px', marginBottom: '6px', fontFamily: 'Cinzel, serif' }}>
                Dice pool
              </label>
              <input
                type="text"
                value={rollPoolInput}
                onChange={(e) => setRollPoolInput(e.target.value)}
                placeholder="e.g. 5 or 4+3 or 7-1"
                disabled={rollSubmitting}
                style={{
                  width: '100%',
                  marginBottom: '12px',
                  padding: '10px 12px',
                  background: '#0f1729',
                  border: '1px solid #2a2a4e',
                  borderRadius: '6px',
                  color: '#e0e0e0',
                  fontSize: '15px',
                  fontFamily: 'Crimson Text, serif',
                }}
              />
              <label style={{ display: 'block', color: '#b5b5c3', fontSize: '12px', marginBottom: '6px', fontFamily: 'Cinzel, serif' }}>
                Difficulty (target number, 2–10)
              </label>
              <select
                value={rollDifficulty}
                onChange={(e) => setRollDifficulty(Number(e.target.value))}
                disabled={rollSubmitting}
                style={{
                  width: '100%',
                  marginBottom: '12px',
                  padding: '10px 12px',
                  background: '#0f1729',
                  border: '1px solid #2a2a4e',
                  borderRadius: '6px',
                  color: '#e0e0e0',
                  fontSize: '15px',
                  fontFamily: 'Crimson Text, serif',
                }}
              >
                {[2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                    {n === 6 ? ' (common default)' : ''}
                  </option>
                ))}
              </select>
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  color: '#b5b5c3',
                  fontSize: '13px',
                  marginBottom: '12px',
                  cursor: rollSubmitting ? 'default' : 'pointer',
                  fontFamily: 'Crimson Text, serif',
                }}
              >
                <input
                  type="checkbox"
                  checked={rollSpecialty}
                  onChange={(e) => setRollSpecialty(e.target.checked)}
                  disabled={rollSubmitting}
                />
                Specialty (10s count as 2 successes)
              </label>
              {canHideRollToOthers && (
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    color: '#b5b5c3',
                    fontSize: '13px',
                    marginBottom: '14px',
                    cursor: rollSubmitting ? 'default' : 'pointer',
                    fontFamily: 'Crimson Text, serif',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={rollHideOthers}
                    onChange={(e) => setRollHideOthers(e.target.checked)}
                    disabled={rollSubmitting}
                  />
                  Hide roll to others (admin/storyteller only)
                </label>
              )}
              <label style={{ display: 'block', color: '#b5b5c3', fontSize: '12px', marginBottom: '6px', fontFamily: 'Cinzel, serif' }}>
                Reason / what you’re rolling for (optional)
              </label>
              <textarea
                value={rollReason}
                onChange={(e) => setRollReason(e.target.value)}
                placeholder="e.g. Brawl attack, soak, Perception + Alertness…"
                disabled={rollSubmitting}
                rows={3}
                style={{
                  width: '100%',
                  marginBottom: '16px',
                  padding: '10px 12px',
                  background: '#0f1729',
                  border: '1px solid #2a2a4e',
                  borderRadius: '6px',
                  color: '#e0e0e0',
                  fontSize: '14px',
                  resize: 'vertical',
                  fontFamily: 'Crimson Text, serif',
                }}
              />
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  disabled={rollSubmitting}
                  onClick={closeRollModal}
                  style={{
                    padding: '10px 16px',
                    background: '#0f1729',
                    color: '#b5b5c3',
                    border: '1px solid #2a2a4e',
                    borderRadius: '6px',
                    cursor: rollSubmitting ? 'not-allowed' : 'pointer',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={rollSubmitting}
                  onClick={() => submitSidebarRoll()}
                  style={{
                    padding: '10px 16px',
                    background: rollSubmitting ? '#4a4a5e' : '#e94560',
                    color: 'white',
                    border: '1px solid rgba(233, 69, 96, 0.5)',
                    borderRadius: '6px',
                    cursor: rollSubmitting ? 'not-allowed' : 'pointer',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  {rollSubmitting ? 'Rolling…' : 'Roll & post'}
                </button>
              </div>
            </GothicBox>
          </div>
        </div>
      )}

      {showAdminDiceRulesModal && (
        <div
          role="presentation"
          onClick={() => !adminDiceSaving && setShowAdminDiceRulesModal(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.75)',
            zIndex: 2050,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-dice-rules-title"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '420px', width: '100%' }}
          >
            <GothicBox theme="none" style={{ background: '#16213e', padding: '22px' }}>
              <h3
                id="admin-dice-rules-title"
                style={{
                  color: '#e94560',
                  fontSize: '17px',
                  margin: '0 0 12px 0',
                  fontFamily: 'Cinzel, serif',
                }}
              >
                Admin Dice Rules
              </h3>
              <p style={{ color: '#8b8b9f', fontSize: '13px', marginBottom: '14px', lineHeight: 1.5, fontFamily: 'Crimson Text, serif' }}>
                Applies only to <strong style={{ color: '#d0d0d0' }}>{currentLocation?.name || 'this room'}</strong>.
                Floor <strong>2–10</strong>: no 1s; with 2+ dice, one die is always ≥ floor. Matches{' '}
                <code style={{ color: '#d8b4fe' }}>/ai dice-diff</code> for this location.
              </p>
              <label style={{ display: 'block', color: '#b5b5c3', fontSize: '12px', marginBottom: '6px', fontFamily: 'Cinzel, serif' }}>
                Leniency floor (2–10)
              </label>
              <input
                type="number"
                min={2}
                max={10}
                value={adminDiceFloorDraft}
                onChange={(e) => setAdminDiceFloorDraft(e.target.value)}
                placeholder="e.g. 7"
                disabled={adminDiceSaving}
                style={{
                  width: '100%',
                  marginBottom: '14px',
                  padding: '10px 12px',
                  background: '#0f1729',
                  border: '1px solid #2a2a4e',
                  borderRadius: '6px',
                  color: '#e0e0e0',
                  fontSize: '15px',
                  fontFamily: 'Crimson Text, serif',
                }}
              />
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  disabled={adminDiceSaving}
                  onClick={() => saveAdminDiceLeniency({ restore: true })}
                  style={{
                    padding: '10px 14px',
                    background: '#0f1729',
                    color: '#94a3b8',
                    border: '1px solid #475569',
                    borderRadius: '6px',
                    cursor: adminDiceSaving ? 'not-allowed' : 'pointer',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  Restore normal
                </button>
                <button
                  type="button"
                  disabled={adminDiceSaving}
                  onClick={() => setShowAdminDiceRulesModal(false)}
                  style={{
                    padding: '10px 14px',
                    background: '#0f1729',
                    color: '#b5b5c3',
                    border: '1px solid #2a2a4e',
                    borderRadius: '6px',
                    cursor: adminDiceSaving ? 'not-allowed' : 'pointer',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={adminDiceSaving}
                  onClick={() => saveAdminDiceLeniency()}
                  style={{
                    padding: '10px 16px',
                    background: adminDiceSaving ? '#4a4a5e' : '#9d4edd',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: adminDiceSaving ? 'not-allowed' : 'pointer',
                    fontFamily: 'Cinzel, serif',
                  }}
                >
                  {adminDiceSaving ? 'Saving…' : 'Save'}
                </button>
              </div>
            </GothicBox>
          </div>
        </div>
      )}

      {showDiceHistoryModal && (
        <div
          role="presentation"
          onClick={() => !diceHistoryLoading && setShowDiceHistoryModal(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.82)',
            zIndex: 2100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="dice-history-title"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '520px', width: '100%', maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}
          >
            <GothicBox theme="none" style={{ background: '#16213e', padding: '20px', display: 'flex', flexDirection: 'column', maxHeight: '80vh' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', gap: '12px' }}>
                <h3
                  id="dice-history-title"
                  style={{ color: '#e94560', fontSize: '16px', margin: 0, fontFamily: 'Cinzel, serif' }}
                >
                  Dice roll history — this room
                </h3>
                <button
                  type="button"
                  disabled={diceHistoryLoading}
                  onClick={() => setShowDiceHistoryModal(false)}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    fontFamily: 'Cinzel, serif',
                    background: '#0f1729',
                    color: '#b5b5c3',
                    border: '1px solid #2a2a4e',
                    borderRadius: '6px',
                    cursor: diceHistoryLoading ? 'not-allowed' : 'pointer',
                  }}
                >
                  Close
                </button>
              </div>
              <p style={{ color: '#8b8b9f', fontSize: '12px', margin: '0 0 12px', fontFamily: 'Crimson Text, serif' }}>
                All Storyteller rolls stored for <strong>{currentLocation?.name || 'this location'}</strong> in this campaign (admin only).
              </p>
              {diceHistoryError && (
                <div style={{ color: '#f87171', fontSize: '13px', marginBottom: '10px', fontFamily: 'Crimson Text, serif' }}>
                  {diceHistoryError}
                </div>
              )}
              {diceHistoryLoading && (
                <div style={{ color: '#b5b5c3', fontSize: '14px', fontFamily: 'Crimson Text, serif' }}>Loading…</div>
              )}
              {!diceHistoryLoading && !diceHistoryError && diceHistoryRows.length === 0 && (
                <div style={{ color: '#8b8b9f', fontSize: '14px', fontFamily: 'Crimson Text, serif' }}>No rolls recorded in this room yet.</div>
              )}
              {!diceHistoryLoading && diceHistoryRows.length > 0 && (
                <div
                  style={{
                    overflowY: 'auto',
                    flex: 1,
                    minHeight: 0,
                    border: '1px solid #2a2a4e',
                    borderRadius: '8px',
                    background: '#0f1729',
                    padding: '10px',
                  }}
                >
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                    {diceHistoryRows.map((r) => {
                      const who =
                        [r.username, r.character_name].filter(Boolean).join(' · ') || `user #${r.user_id}`;
                      const diceStr = Array.isArray(r.results) ? r.results.join(', ') : String(r.results ?? '');
                      const tag = r.is_botch ? ' · BOTCH' : r.is_critical ? ' · critical' : '';
                      return (
                        <li
                          key={r.id}
                          style={{
                            borderBottom: '1px solid #1e293b',
                            padding: '10px 4px',
                            fontSize: '13px',
                            color: '#d0d0e0',
                            fontFamily: 'Crimson Text, serif',
                            lineHeight: 1.45,
                          }}
                        >
                          <div style={{ color: '#94a3b8', fontSize: '11px', marginBottom: '4px' }}>
                            {formatMessageTime(r.rolled_at, chatNow, user?.display_timezone || null)}
                          </div>
                          <div>
                            <strong style={{ color: '#e2e8f0' }}>{who}</strong>
                            {r.action_description ? ` — ${r.action_description}` : ''}
                          </div>
                          <div style={{ marginTop: '4px', color: '#b5b5c3' }}>
                            Pool {r.dice_pool}, diff {r.difficulty}
                            {r.modifiers?.specialty ? ', specialty' : ''}
                            {' → '}[{diceStr}] → <strong>{r.successes}</strong> successes{tag}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </GothicBox>
          </div>
        </div>
      )}
    </div>
    );
  };

  // Main render
  
  // Show Gothic Showcase if requested
  if (showGothicShowcase) {
    return (
      <GothicShowcase
        onBack={() => {
          // Gothic showcase is opened via `showShowcase(true)` which pushes a history state.
          // Prefer going back in history to restore the previous page (login/dashboard/etc).
          if (window.history.state?.showGothicShowcase) {
            window.history.back();
          } else {
            showShowcase(false);
          }
        }}
      />
    );
  }
  
  return (
    <div className="App">
      <GothicPageLoadingOverlay visible={pageOverlay.visible} label={pageOverlay.label} />
      {!token && renderLogin()}
      {token && currentPage === 'dashboard' && renderDashboard()}
      {token && currentPage === 'selectCharacter' && renderSelectCharacter()}
      {token && currentPage === 'playerProfile' && renderPlayerProfile()}
      {token && currentPage === 'characterCreate' && renderCharacterCreate()}
      {token && currentPage === 'profile' && renderProfile()}
      {token && currentPage === 'createCampaign' && renderCreateCampaign()}
      {token && currentPage === 'campaignDetails' && renderCampaignDetails()}
      {token && currentPage === 'chat' && renderChat()}
      
      {/* Delete Campaign Confirmation Modal */}
      {showDeleteConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          animation: 'fadeIn 0.3s ease-out',
          padding: '20px'
        }}>
          <GothicBox theme="vampire" style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '15px',
            maxWidth: '550px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 0 40px rgba(233, 69, 96, 0.8)',
            border: '3px solid #e94560',
            position: 'relative'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>💀</div>
            <h2 style={{ 
              color: '#e94560', 
              marginBottom: '20px', 
              fontFamily: 'Cinzel, serif', 
              fontSize: '28px',
              textShadow: '0 0 10px rgba(233, 69, 96, 0.5)'
            }}>
              ⚠️ DELETE CAMPAIGN
            </h2>
            <div style={{
              background: 'rgba(220, 53, 69, 0.1)',
              border: '2px solid #dc3545',
              borderRadius: '10px',
              padding: '20px',
              marginBottom: '25px',
              textAlign: 'left'
            }}>
              <p style={{ 
                color: '#ff6b6b', 
                marginBottom: '15px', 
                lineHeight: '1.6',
                fontFamily: 'Crimson Text, serif',
                fontSize: '16px',
                fontWeight: 'bold'
              }}>
                You are about to permanently delete:
              </p>
              <p style={{ 
                color: '#d0d0e0', 
                marginBottom: '10px',
                fontFamily: 'Cinzel, serif',
                fontSize: '18px',
                textAlign: 'center',
                padding: '10px',
                background: 'rgba(233, 69, 96, 0.2)',
                borderRadius: '5px'
              }}>
                "{selectedCampaign?.name}"
              </p>
              <ul style={{ 
                color: '#ff6b6b', 
                marginBottom: '15px', 
                lineHeight: '1.8',
                fontFamily: 'Crimson Text, serif',
                fontSize: '15px',
                paddingLeft: '20px'
              }}>
                <li>All locations and rooms</li>
                <li>All characters and their data</li>
                <li>All messages and chat history</li>
                <li>All dice rolls and logs</li>
                <li>All campaign progress</li>
              </ul>
              <p style={{ 
                color: '#ff4444', 
                marginTop: '15px',
                fontFamily: 'Cinzel, serif',
                fontSize: '14px',
                fontWeight: 'bold',
                textAlign: 'center',
                textTransform: 'uppercase',
                letterSpacing: '1px'
              }}>
                ⚠️ THIS CANNOT BE UNDONE ⚠️
              </p>
            </div>
            
            <div style={{ marginBottom: '25px' }}>
              <label style={{ 
                color: '#b5b5c3', 
                display: 'block', 
                marginBottom: '10px',
                fontFamily: 'Crimson Text, serif',
                fontSize: '15px'
              }}>
                Type <strong style={{ color: '#e94560' }}>CONFIRM</strong> to proceed:
              </label>
              <input
                type="text"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="Type CONFIRM here"
                style={{
                  width: '100%',
                  padding: '12px',
                  background: '#0f1729',
                  border: '2px solid ' + (deleteConfirmText === 'CONFIRM' ? '#4ade80' : '#2a2a4e'),
                  borderRadius: '8px',
                  color: '#d0d0e0',
                  fontSize: '16px',
                  fontFamily: 'monospace',
                  textAlign: 'center',
                  textTransform: 'uppercase',
                  letterSpacing: '2px',
                  transition: 'all 0.3s'
                }}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setDeleteConfirmText('');
                }}
                style={{
                  padding: '14px 30px',
                  background: '#40444b',
                  color: '#dcddde',
                  border: '2px solid #6c757d',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => { 
                  e.target.style.background = '#6c757d'; 
                  e.target.style.color = 'white'; 
                }}
                onMouseOut={(e) => { 
                  e.target.style.background = '#40444b'; 
                  e.target.style.color = '#dcddde'; 
                }}
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (deleteConfirmText !== 'CONFIRM') return;
                  
                  try {
                    const response = await fetch(`${API_URL}/campaigns/${selectedCampaign.id}`, {
                      method: 'DELETE',
                      headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    if (response.ok) {
                      setShowDeleteConfirm(false);
                      setDeleteConfirmText('');
                      await fetchCampaigns(undefined, { forActiveCharacter: true });
                      setCurrentPage('dashboard');
                      showSuccess('✅ Campaign deleted successfully!');
                    } else {
                      const data = await response.json();
                      showError('❌ Failed to delete: ' + (data.error || 'Unknown error'));
                    }
                  } catch (error) {
                    showError('❌ Error deleting campaign: ' + error.message);
                  }
                }}
                disabled={deleteConfirmText !== 'CONFIRM'}
                style={{
                  padding: '14px 30px',
                  background: deleteConfirmText === 'CONFIRM' 
                    ? 'linear-gradient(135deg, #dc3545 0%, #8b0000 100%)' 
                    : '#555',
                  color: deleteConfirmText === 'CONFIRM' ? 'white' : '#888',
                  border: deleteConfirmText === 'CONFIRM' ? '2px solid #dc3545' : '2px solid #555',
                  borderRadius: '8px',
                  cursor: deleteConfirmText === 'CONFIRM' ? 'pointer' : 'not-allowed',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  boxShadow: deleteConfirmText === 'CONFIRM' 
                    ? '0 4px 20px rgba(220, 53, 69, 0.6)' 
                    : 'none',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => {
                  if (deleteConfirmText === 'CONFIRM') {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 30px rgba(220, 53, 69, 0.8)';
                  }
                }}
                onMouseOut={(e) => {
                  if (deleteConfirmText === 'CONFIRM') {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 4px 20px rgba(220, 53, 69, 0.6)';
                  }
                }}
              >
                {deleteConfirmText === 'CONFIRM' ? '🗑️ Delete Forever' : '🔒 Locked'}
              </button>
            </div>
          </GothicBox>
        </div>
      )}

      {/* Location Delete Confirmation Modal */}
      {showLocationDeleteConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 3000,
          animation: 'fadeIn 0.3s ease-out',
          padding: '20px'
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '15px',
            maxWidth: '500px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 0 40px rgba(233, 69, 96, 0.8)',
            border: '3px solid #e94560'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>🗑️</div>
            <h2 style={{ 
              color: '#e94560', 
              marginBottom: '20px', 
              fontFamily: 'Cinzel, serif', 
              fontSize: '24px'
            }}>
              Delete Location?
            </h2>
            <p style={{ 
              color: '#d0d0e0', 
              marginBottom: '30px', 
              lineHeight: '1.6',
              fontFamily: 'Crimson Text, serif',
              fontSize: '16px'
            }}>
              Are you sure you want to delete this location?
              <br />
              <strong style={{ color: '#ff6b6b' }}>
                This will also delete all messages in this location.
              </strong>
              <br />
              This action cannot be undone.
            </p>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '15px' }}>
              <button
                onClick={() => {
                  setShowLocationDeleteConfirm(false);
                  setLocationToDelete(null);
                }}
                style={{
                  padding: '14px 30px',
                  background: '#40444b',
                  color: '#dcddde',
                  border: '2px solid #6c757d',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => { 
                  e.target.style.background = '#5a5e66'; 
                  e.target.style.color = 'white'; 
                }}
                onMouseOut={(e) => { 
                  e.target.style.background = '#40444b'; 
                  e.target.style.color = '#dcddde'; 
                }}
              >
                Cancel
              </button>
              <button
                onClick={executeDeleteLocation}
                disabled={loading}
                style={{
                  padding: '14px 30px',
                  background: loading ? '#6c757d' : '#dc3545',
                  color: 'white',
                  border: loading ? '2px solid #6c757d' : '2px solid #dc3545',
                  borderRadius: '8px',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                  fontSize: '16px',
                  fontFamily: 'Cinzel, serif',
                  transition: 'all 0.2s',
                  minWidth: '140px'
                }}
                onMouseOver={(e) => {
                  if (!loading) {
                    e.target.style.transform = 'translateY(-2px)';
                    e.target.style.boxShadow = '0 6px 30px rgba(220, 53, 69, 0.8)';
                  }
                }}
                onMouseOut={(e) => {
                  if (!loading) {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = 'none';
                  }
                }}
              >
                {loading ? '⏳ Deleting...' : '🗑️ Delete Location'}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Location Suggestions Modal */}
      {showLocationSuggestions && newCampaignData && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          overflowY: 'auto'
        }}>
          <div style={{
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <LocationSuggestions
              campaignId={newCampaignData.id}
              settingDescription={newCampaignData.description}
              onComplete={async () => {
                // Check if we're adding to an existing campaign or new campaign
                if (selectedCampaign && selectedCampaign.id === newCampaignData.id) {
                  // Adding to existing campaign - return to location manager
                  await handleLocationSuggestionsComplete();
                } else {
                  // New campaign - return to dashboard
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  await fetchCampaigns(undefined, { forActiveCharacter: true });
                  setCurrentPage('dashboard');
                }
              }}
              onSkip={async () => {
                // Check if we're adding to an existing campaign or new campaign
                if (selectedCampaign && selectedCampaign.id === newCampaignData.id) {
                  // Adding to existing campaign - return to location manager
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  setShowLocationManager(true);
                } else {
                  // New campaign - return to dashboard
                  setShowLocationSuggestions(false);
                  setNewCampaignData(null);
                  await fetchCampaigns(undefined, { forActiveCharacter: true });
                  setCurrentPage('dashboard');
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Location Manager Modal */}
      {showLocationManager && selectedCampaign && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.85)',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '20px',
          overflowY: 'auto'
        }}>
          <div style={{
            background: '#16213e',
            borderRadius: '15px',
            maxWidth: '800px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            border: '2px solid #e94560',
            boxShadow: '0 0 30px rgba(233, 69, 96, 0.5)'
          }}>
            {/* Header */}
            <div style={{
              background: 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
              padding: '20px',
              borderTopLeftRadius: '13px',
              borderTopRightRadius: '13px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <h2 style={{ color: 'white', margin: 0, fontFamily: 'Cinzel, serif', fontSize: '24px' }}>
                🗺️ Manage Locations
              </h2>
              <button
                onClick={() => setShowLocationManager(false)}
                style={{
                  background: 'rgba(255, 255, 255, 0.2)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '50%',
                  width: '40px',
                  height: '40px',
                  cursor: 'pointer',
                  fontSize: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                ✕
              </button>
            </div>

            {/* Content */}
            <div style={{ padding: '30px' }}>
              {/* Add Locations Button */}
              <div style={{ marginBottom: '30px', textAlign: 'center' }}>
                <button
                  onClick={handleAddLocationsWithAI}
                  disabled={loading}
                  style={{
                    padding: '15px 30px',
                    background: 'linear-gradient(135deg, #9d4edd 0%, #5a0099 100%)',
                    color: 'white',
                    border: '2px solid #9d4edd',
                    borderRadius: '10px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontSize: '18px',
                    fontWeight: 'bold',
                    fontFamily: 'Cinzel, serif',
                    boxShadow: '0 4px 15px rgba(157, 78, 221, 0.4)',
                    transition: 'all 0.3s'
                  }}
                  onMouseOver={(e) => !loading && (e.target.style.boxShadow = '0 6px 25px rgba(157, 78, 221, 0.6)')}
                  onMouseOut={(e) => !loading && (e.target.style.boxShadow = '0 4px 15px rgba(157, 78, 221, 0.4)')}
                >
                  ✨ Add New Locations (AI Suggestions)
                </button>
                <div style={{
                  marginTop: '10px',
                  color: '#9d4edd',
                  fontSize: '14px',
                  fontFamily: 'Crimson Text, serif'
                }}>
                  AI will suggest thematic locations based on your campaign setting
                </div>
              </div>

              {/* Current Locations */}
              <h3 style={{ color: '#e94560', marginBottom: '20px', fontFamily: 'Cinzel, serif' }}>
                Current Locations ({campaignLocations.length})
              </h3>

              {campaignLocations.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  padding: '40px',
                  color: '#8b8b9f',
                  fontFamily: 'Crimson Text, serif',
                  fontSize: '16px'
                }}>
                  No locations found. Click "Add New Locations" to create some!
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                  {campaignLocations.map((location) => (
                    <div
                      key={location.id}
                      style={{
                        background: '#0f1729',
                        padding: '20px',
                        borderRadius: '10px',
                        border: '2px solid #2a2a4e',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        transition: 'all 0.2s'
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{
                          color: '#e94560',
                          fontSize: '18px',
                          fontWeight: 'bold',
                          marginBottom: '5px',
                          fontFamily: 'Cinzel, serif'
                        }}>
                          {location.name}
                        </div>
                        <div style={{
                          color: '#9d4edd',
                          fontSize: '14px',
                          marginBottom: '8px',
                          fontFamily: 'Crimson Text, serif',
                          textTransform: 'capitalize'
                        }}>
                          Type: {location.type}
                        </div>
                        {location.description && (
                          <div style={{
                            color: '#b5b5c3',
                            fontSize: '14px',
                            fontFamily: 'Crimson Text, serif',
                            lineHeight: '1.6'
                          }}>
                            {location.description}
                          </div>
                        )}
                        {canEditLocationAccess && location.type !== 'ooc' && (
                          <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #2a2a4e' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#b5b5c3', cursor: 'pointer', fontFamily: 'Crimson Text, serif', fontSize: '14px' }}>
                              <input
                                type="checkbox"
                                checked={
                                  locEdits[location.id]?.is_open
                                  ?? (location.is_open !== false && location.is_open !== 0)
                                }
                                onChange={(e) => {
                                  const checked = e.target.checked;
                                  setLocEdits((prev) => ({
                                    ...prev,
                                    [location.id]: {
                                      is_open: checked,
                                      closure_reason: prev[location.id]?.closure_reason || '',
                                    },
                                  }));
                                }}
                              />
                              Open to players (unchecked = 🚫 closed — scene paused)
                            </label>
                            {locEdits[location.id] && locEdits[location.id].is_open === false && (
                              <textarea
                                value={locEdits[location.id].closure_reason || ''}
                                onChange={(e) => setLocEdits((prev) => ({
                                  ...prev,
                                  [location.id]: {
                                    ...prev[location.id],
                                    closure_reason: e.target.value,
                                  },
                                }))}
                                placeholder="Optional reason for players (e.g. “Elysium under repair — check back next session”)"
                                rows={2}
                                style={{
                                  width: '100%',
                                  marginTop: '10px',
                                  padding: '8px',
                                  borderRadius: '6px',
                                  border: '1px solid #2a2a4e',
                                  background: '#0f1729',
                                  color: '#e0e0e0',
                                  fontFamily: 'Crimson Text, serif',
                                  fontSize: '14px',
                                  resize: 'vertical',
                                }}
                              />
                            )}
                            <button
                              type="button"
                              onClick={() => saveLocationAccess(location.id)}
                              disabled={loading}
                              style={{
                                marginTop: '10px',
                                padding: '8px 14px',
                                background: '#2d6a4f',
                                color: 'white',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: loading ? 'not-allowed' : 'pointer',
                                fontFamily: 'Cinzel, serif',
                                fontSize: '13px',
                                fontWeight: '600',
                              }}
                            >
                              Save access
                            </button>
                          </div>
                        )}
                        {canEditLocationAccess && location.type === 'ooc' && (
                          <div style={{ marginTop: '10px', color: '#8b8b9f', fontSize: '13px', fontFamily: 'Crimson Text, serif' }}>
                            The OOC lobby cannot be closed to players.
                          </div>
                        )}
                      </div>
                      <div style={{ marginLeft: '20px', display: 'flex', gap: '10px', flexShrink: 0 }}>
                        {location.type !== 'ooc' && (
                          <button
                            onClick={() => handleDeleteLocation(location.id)}
                            disabled={loading}
                            style={{
                              padding: '8px 16px',
                              background: '#dc3545',
                              color: 'white',
                              border: 'none',
                              borderRadius: '5px',
                              cursor: loading ? 'not-allowed' : 'pointer',
                              fontSize: '14px',
                              fontWeight: '600',
                              fontFamily: 'Cinzel, serif'
                            }}
                          >
                            🗑️ Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {token && currentPage === 'admin' && (
        <div style={{ minHeight: '100vh', background: '#0f0f1e', display: 'flex', flexDirection: 'column' }}>
          {renderAppPageHeader({ title: 'Admin panel' })}
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <AdminPage token={token} user={user} displayTimezone={user?.display_timezone || null} />
          </div>
        </div>
      )}

      {closedRoomModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.82)',
            zIndex: 2400,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setClosedRoomModal(null)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="closed-room-title"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#16213e',
              borderRadius: '14px',
              maxWidth: '440px',
              width: '100%',
              border: '2px solid #9d4edd',
              boxShadow: '0 0 28px rgba(157, 78, 221, 0.35)',
              padding: '24px',
            }}
          >
            <h2
              id="closed-room-title"
              style={{
                margin: '0 0 12px 0',
                color: '#e94560',
                fontFamily: 'Cinzel, serif',
                fontSize: '20px',
              }}
            >
              {closedRoomModal.title}
            </h2>
            <p style={{ color: '#e0e0e0', fontFamily: 'Crimson Text, serif', fontSize: '16px', lineHeight: 1.5, margin: '0 0 12px 0' }}>
              {closedRoomModal.lead}
            </p>
            <p style={{ color: '#9d4edd', fontFamily: 'Crimson Text, serif', fontSize: '15px', fontStyle: 'italic', margin: '0 0 20px 0' }}>
              {closedRoomModal.flavor}
            </p>
            <button
              type="button"
              onClick={() => setClosedRoomModal(null)}
              style={{
                padding: '10px 20px',
                background: 'linear-gradient(135deg, #9d4edd 0%, #5a0099 100%)',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer',
                fontFamily: 'Cinzel, serif',
                fontWeight: '600',
              }}
            >
              Understood
            </button>
          </div>
        </div>
      )}

      {/* Custom Exit Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showExitConfirm}
        title="⚠️ Leave Campaign?"
        message={`You are currently in ${currentLocation?.name || 'the location'}.\n\nYour character will be marked as having left this location.\n\nAre you sure you want to exit?`}
        onConfirm={confirmLeaveCampaign}
        onCancel={cancelLeaveCampaign}
        confirmText="Yes, Leave"
        cancelText="Stay Here"
      />
      
      {/* Toast Notifications */}
      <ToastContainer />
    </div>
  );
}

export default SimpleApp;
