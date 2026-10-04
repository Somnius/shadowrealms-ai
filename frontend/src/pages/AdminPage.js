import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Badge, Button, Checkbox, EmptyState, Input, Modal, Panel, Select, Tabs, Textarea, useToast } from '../design';
import { api } from '../utils/api';
import EditionBadge from '../components/EditionBadge';
import { editionLabel } from '../rules/rulesEdition';
import { getLanguage, getLocale, t } from '../i18n';
import AiProvidersPanel from './admin/AiProvidersPanel';
import './admin/admin.css';

/** Admin sections, in tab order; each is a sub-route (/admin/<id>, overview at /admin). */
export const ADMIN_SECTIONS = ['home', 'invites', 'chronicles', 'users', 'downtime', 'moderation', 'ai'];

export const sectionLabels = () => ({
  home: t('admin:nav.home', 'Overview'),
  invites: t('admin:nav.invites', 'Invite codes'),
  chronicles: t('admin:nav.chronicles', 'All chronicles'),
  users: t('admin:nav.users', 'Users'),
  downtime: t('admin:nav.downtime', 'Downtime requests'),
  moderation: t('admin:nav.moderation', 'Moderation log'),
  ai: t('admin:nav.ai', 'AI system'),
});

const SECTION_ICONS = {
  home: 'crown',
  invites: 'key',
  chronicles: 'book',
  users: 'users',
  downtime: 'hourglass',
  moderation: 'scroll',
  ai: 'ai-sigil',
};

/** Date + time in the admin's display timezone (browser zone when unset), in the UI language. */
function formatWhen(value, timeZone) {
  if (!value) return '—';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  const opts = { year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit' };
  if (getLanguage() === 'el') opts.hourCycle = 'h23';
  else opts.hour12 = true;
  if (timeZone) opts.timeZone = timeZone;
  try {
    return new Intl.DateTimeFormat(getLocale(), opts).format(d);
  } catch (e) {
    return d.toLocaleString();
  }
}

/** Yes/No confirmation in the design-system modal (replaces the legacy ConfirmDialog here). */
function AdminConfirm({ open, title, message, confirmText, onConfirm, onCancel, busy = false }) {
  return (
    <Modal
      open={open}
      onClose={busy ? undefined : onCancel}
      title={title}
      icon="warning"
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={busy}>
            {t('admin:common.cancel', 'Cancel')}
          </Button>
          <Button variant="danger" onClick={onConfirm} loading={busy}>
            {confirmText}
          </Button>
        </>
      }
    >
      <p className="sr-admin__confirm">{message}</p>
    </Modal>
  );
}

function AdminPage({ token, user, displayTimezone = null, onAdminOpenCampaign = null }) {
  const { toast } = useToast();
  const showSuccess = (message) => toast({ tone: 'ok', title: message });
  const showError = (message) => toast({ tone: 'danger', title: message });
  const navigate = useNavigate();
  const sectionParam = (useParams()['*'] || '').split('/')[0];
  /** Section comes from the URL: /admin, /admin/invites, /admin/users, … */
  const adminSection = ADMIN_SECTIONS.includes(sectionParam) ? sectionParam : 'home';
  const setAdminSection = (id) => navigate(id === 'home' ? '/admin' : `/admin/${id}`);
  const [banType, setBanType] = useState('temporary');
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showBanModal, setShowBanModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showUnbanConfirm, setShowUnbanConfirm] = useState(false);
  const [userToUnban, setUserToUnban] = useState(null);
  const [showDeleteAccountConfirm, setShowDeleteAccountConfirm] = useState(false);
  const [userToDeleteAccount, setUserToDeleteAccount] = useState(null);
  const [deleteAccountLoading, setDeleteAccountLoading] = useState(false);
  const [moderationLog, setModerationLog] = useState([]);
  const [moderationLogLimit, setModerationLogLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [invites, setInvites] = useState([]);
  const [inviteType, setInviteType] = useState('player');
  const [inviteMaxUses, setInviteMaxUses] = useState(1);
  const [inviteDescription, setInviteDescription] = useState('');
  const [inviteCustomCode, setInviteCustomCode] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  const [downtimeRows, setDowntimeRows] = useState([]);
  const [downtimeStatusFilter, setDowntimeStatusFilter] = useState('pending');
  const [showUserCharsModal, setShowUserCharsModal] = useState(false);
  const [charsTargetUser, setCharsTargetUser] = useState(null);
  const [userCharsList, setUserCharsList] = useState([]);
  const [userCharsLoading, setUserCharsLoading] = useState(false);
  const [userCharsError, setUserCharsError] = useState(null);
  const [chroniclesList, setChroniclesList] = useState([]);
  const [chroniclesLoading, setChroniclesLoading] = useState(false);
  const [chroniclesError, setChroniclesError] = useState(null);
  const [chroniclesOpeningId, setChroniclesOpeningId] = useState(null);
  const [chronicleBusyId, setChronicleBusyId] = useState(null);
  const [chronicleEditTarget, setChronicleEditTarget] = useState(null);
  const [chEdName, setChEdName] = useState('');
  const [chEdDescription, setChEdDescription] = useState('');
  const [chEdListing, setChEdListing] = useState('private');
  const [chEdAccepting, setChEdAccepting] = useState(false);
  const [chEdMaxPlayers, setChEdMaxPlayers] = useState('');
  const [chronicleStatsTarget, setChronicleStatsTarget] = useState(null);
  const [chronicleStatsData, setChronicleStatsData] = useState(null);
  const [chronicleStatsLoading, setChronicleStatsLoading] = useState(false);
  const [chroniclePauseTarget, setChroniclePauseTarget] = useState(null);
  const [chroniclePauseReason, setChroniclePauseReason] = useState('');
  const [chronicleDeleteTarget, setChronicleDeleteTarget] = useState(null);
  const [chronicleDeleteLoading, setChronicleDeleteLoading] = useState(false);
  const [showDebugModal, setShowDebugModal] = useState(false);
  const [debugTargetUser, setDebugTargetUser] = useState(null);
  const [debugPayload, setDebugPayload] = useState(null);
  const [debugLoading, setDebugLoading] = useState(false);
  const [suspendTargetChar, setSuspendTargetChar] = useState(null);
  const [suspendReason, setSuspendReason] = useState('pending_downtime');
  const [suspendMessage, setSuspendMessage] = useState('');
  const [membershipModalUser, setMembershipModalUser] = useState(null);
  const [membershipCampaignId, setMembershipCampaignId] = useState('');
  const [membershipAction, setMembershipAction] = useState('add');
  const [adminCampaignsList, setAdminCampaignsList] = useState([]);
  const [adminCampaignsLoading, setAdminCampaignsLoading] = useState(false);
  const [adminCampaignsLoadError, setAdminCampaignsLoadError] = useState(null);
  /** True when /api/admin/campaigns failed and we used GET /api/campaigns/ instead */
  const [adminCampaignsFromFallback, setAdminCampaignsFromFallback] = useState(false);
  const [membershipTargetChronicles, setMembershipTargetChronicles] = useState([]);
  const [aiSettings, setAiSettings] = useState(null);
  const [lmOpenaiModels, setLmOpenaiModels] = useState([]);
  const [lmListError, setLmListError] = useState(null);
  const [aiSectionLoading, setAiSectionLoading] = useState(false);
  const [aiModelSelect, setAiModelSelect] = useState('');
  const [masterPromptDraft, setMasterPromptDraft] = useState('');
  const [aiSaveLoading, setAiSaveLoading] = useState(false);

  // Fetch all users on mount
  useEffect(() => {
    fetchUsers();
    fetchInvites();
  }, []);

  useEffect(() => {
    if (!token || adminSection !== 'moderation') return undefined;
    fetchModerationLog();
    return undefined;
  }, [token, adminSection, moderationLogLimit]);

  const reloadChronicles = async () => {
    if (!token) return;
    setChroniclesLoading(true);
    setChroniclesError(null);
    try {
      const r = await api.listAdminCampaigns(token);
      const data = await r.json().catch(() => null);
      if (r.ok && Array.isArray(data)) {
        setChroniclesList(data);
        setChroniclesError(null);
      } else {
        setChroniclesList([]);
        const msg =
          (data && data.error) ||
          (r.status === 404
            ? t('admin:error.campaignsApiMissing', 'Admin campaigns API not found. Restart the backend.')
            : t('admin:error.loadChronicles', 'Could not load chronicles'));
        setChroniclesError(msg);
        showError(msg);
      }
    } catch (e) {
      setChroniclesList([]);
      setChroniclesError(t('admin:error.loadChronicles', 'Could not load chronicles'));
      showError(t('admin:error.loadChronicles', 'Could not load chronicles'));
    } finally {
      setChroniclesLoading(false);
    }
  };

  useEffect(() => {
    if (adminSection !== 'chronicles' || !token) return undefined;
    reloadChronicles();
    return undefined;
  }, [adminSection, token]);

  useEffect(() => {
    if (adminSection !== 'downtime') return undefined;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.listDowntimeRequests(
          token,
          downtimeStatusFilter || undefined
        );
        if (r.ok && !cancelled) {
          const d = await r.json();
          setDowntimeRows(Array.isArray(d.requests) ? d.requests : []);
        }
      } catch (e) {
        console.error(e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [adminSection, downtimeStatusFilter, token]);

  useEffect(() => {
    if (!membershipModalUser || !token) {
      setAdminCampaignsList([]);
      setAdminCampaignsLoadError(null);
      setAdminCampaignsFromFallback(false);
      setMembershipTargetChronicles([]);
      return undefined;
    }
    let cancelled = false;
    setAdminCampaignsLoading(true);
    setAdminCampaignsLoadError(null);
    setAdminCampaignsFromFallback(false);
    (async () => {
      try {
        const r = await api.listAdminCampaigns(token);
        const data = await r.json().catch(() => null);
        if (!cancelled && r.ok && Array.isArray(data)) {
          setAdminCampaignsList(data);
          setAdminCampaignsFromFallback(false);
          return;
        }
        if (!cancelled) {
          const r2 = await api.getCampaigns(token);
          const data2 = await r2.json().catch(() => []);
          if (r2.ok && Array.isArray(data2)) {
            setAdminCampaignsList(
              data2.map((c) => ({
                id: c.id,
                name: c.name,
                game_system: c.game_system,
                rules_edition: c.rules_edition,
                status: c.status,
                created_at: c.created_at,
              }))
            );
            setAdminCampaignsFromFallback(true);
            setAdminCampaignsLoadError(null);
          } else {
            setAdminCampaignsList([]);
            const msg =
              (data && data.error) ||
              (data2 && data2.error) ||
              t('admin:error.loadCampaignsRestart', 'Could not load campaigns (restart backend to enable /api/admin/campaigns)');
            setAdminCampaignsLoadError(msg);
            showError(msg);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setAdminCampaignsList([]);
          setAdminCampaignsLoadError(t('admin:error.loadCampaigns', 'Could not load campaigns'));
        }
      } finally {
        if (!cancelled) setAdminCampaignsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [membershipModalUser, token]);

  useEffect(() => {
    if (!membershipModalUser || !token) {
      setMembershipTargetChronicles([]);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const r = await api.getAdminUserCampaignMemberships(token, membershipModalUser.id);
        const data = await r.json().catch(() => []);
        if (!cancelled && r.ok && Array.isArray(data)) {
          setMembershipTargetChronicles(data);
        } else if (!cancelled) {
          setMembershipTargetChronicles([]);
        }
      } catch (e) {
        if (!cancelled) setMembershipTargetChronicles([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [membershipModalUser, token]);

  const loadAiSection = async () => {
    if (!token) return;
    setAiSectionLoading(true);
    setLmListError(null);
    try {
      const r = await api.getAiSettings(token);
      const d = await r.json().catch(() => null);
      if (r.ok && d) {
        setAiSettings(d);
        setAiModelSelect(d.lm_studio_model || '');
        setMasterPromptDraft(d.ai_master_system_prompt || '');
      } else {
        setAiSettings(null);
        showError((d && d.error) || t('admin:error.loadAiSettings', 'Could not load AI settings'));
      }
      const r2 = await api.listLmStudioModels(token);
      const d2 = await r2.json().catch(() => null);
      if (r2.ok && d2) {
        setLmOpenaiModels(Array.isArray(d2.openai_models) ? d2.openai_models : []);
        setLmListError(d2.error || null);
      } else {
        setLmOpenaiModels([]);
        setLmListError((d2 && d2.error) || t('admin:error.listLmModels', 'Could not list LM Studio models'));
      }
    } catch (e) {
      console.error(e);
      showError(t('admin:error.loadAiSystem', 'Failed to load Ai System settings'));
    } finally {
      setAiSectionLoading(false);
    }
  };

  useEffect(() => {
    if (adminSection !== 'ai') return undefined;
    loadAiSection();
    return undefined;
  }, [adminSection, token]);

  const fetchUsers = async () => {
    try {
      const response = await api.getAllUsers(token);
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (err) {
      setError(t('admin:error.loadUsers', 'Failed to load users'));
    }
  };

  const fetchModerationLog = async () => {
    try {
      const response = await api.getModerationLog(token, moderationLogLimit);
      if (response.ok) {
        const data = await response.json();
        setModerationLog(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('Failed to load moderation log');
    }
  };

  const refreshUserCharsList = async (userId) => {
    setUserCharsLoading(true);
    setUserCharsError(null);
    try {
      const r = await api.getUserCharacters(token, userId);
      const data = await r.json().catch(() => null);
      if (r.ok && Array.isArray(data)) {
        setUserCharsList(data);
        setUserCharsError(null);
      } else {
        setUserCharsList([]);
        const msg =
          (data && typeof data === 'object' && data.error) ||
          t('admin:error.loadCharactersStatus', 'Could not load characters ({{status}})', { status: r.status });
        setUserCharsError(msg);
        showError(msg);
      }
    } catch (e) {
      setUserCharsList([]);
      setUserCharsError(t('admin:error.loadCharacters', 'Failed to load characters'));
      showError(t('admin:error.loadCharacters', 'Failed to load characters'));
    } finally {
      setUserCharsLoading(false);
    }
  };

  const openUserCharacters = async (u) => {
    setCharsTargetUser(u);
    setShowUserCharsModal(true);
    setUserCharsList([]);
    setUserCharsError(null);
    await refreshUserCharsList(u.id);
  };

  const handleOpenChronicleFromAdmin = async (c) => {
    if (!onAdminOpenCampaign || !c?.id) {
      showError(t('admin:error.openUnavailable', 'Open-in-app is not available from this screen.'));
      return;
    }
    setChroniclesOpeningId(c.id);
    try {
      await onAdminOpenCampaign({
        id: c.id,
        name: c.name,
        game_system: c.game_system,
        rules_edition: c.rules_edition,
        status: c.status,
      });
    } catch (e) {
      showError(t('admin:error.openChronicle', 'Could not open chronicle'));
    } finally {
      setChroniclesOpeningId(null);
    }
  };

  const openChronicleEdit = async (c) => {
    if (!c?.id) return;
    setChronicleBusyId(c.id);
    try {
      const r = await api.getCampaign(token, c.id);
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        showError((d && d.error) || t('admin:error.loadChronicle', 'Could not load chronicle'));
        return;
      }
      setChEdName(d.name || c.name || '');
      setChEdDescription(d.description || c.description || '');
      setChEdListing(d.listing_visibility || c.listing_visibility || 'private');
      setChEdAccepting(!!d.accepting_players);
      const mp = d.max_players != null ? d.max_players : c.max_players;
      setChEdMaxPlayers(mp != null && mp !== '' ? String(mp) : '');
      setChronicleEditTarget(c);
    } catch (e) {
      showError(t('admin:error.loadChronicle', 'Could not load chronicle'));
    } finally {
      setChronicleBusyId(null);
    }
  };

  const submitChronicleEdit = async (e) => {
    e.preventDefault();
    if (!chronicleEditTarget) return;
    const name = chEdName.trim();
    if (!name) {
      showError(t('admin:error.nameRequired', 'Name is required'));
      return;
    }
    setChronicleBusyId(chronicleEditTarget.id);
    try {
      let maxVal = null;
      if (chEdMaxPlayers !== '') {
        const n = parseInt(chEdMaxPlayers, 10);
        if (Number.isNaN(n) || n < 0) {
          showError(t('admin:error.maxPlayers', 'Max players must be a non-negative integer or empty'));
          setChronicleBusyId(null);
          return;
        }
        maxVal = n;
      }
      const r = await api.updateCampaign(token, chronicleEditTarget.id, {
        name,
        description: chEdDescription,
        listing_visibility: chEdListing,
        accepting_players: chEdAccepting,
        max_players: maxVal,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:chronicles.updated', 'Chronicle updated'));
        setChronicleEditTarget(null);
        await reloadChronicles();
      } else {
        showError(d.error || t('admin:error.updateFailed', 'Update failed'));
      }
    } catch (err) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    } finally {
      setChronicleBusyId(null);
    }
  };

  const openChronicleStats = async (c) => {
    if (!c?.id) return;
    setChronicleStatsTarget(c);
    setChronicleStatsData(null);
    setChronicleStatsLoading(true);
    try {
      const r = await api.getCampaignStats(token, c.id);
      const d = await r.json().catch(() => null);
      if (r.ok) setChronicleStatsData(d);
      else showError((d && d.error) || t('admin:error.loadStats', 'Could not load stats'));
    } catch (e) {
      showError(t('admin:error.loadStats', 'Could not load stats'));
    } finally {
      setChronicleStatsLoading(false);
    }
  };

  const submitChroniclePause = async (e) => {
    e.preventDefault();
    if (!chroniclePauseTarget) return;
    setChronicleBusyId(chroniclePauseTarget.id);
    try {
      const r = await api.updateCampaign(token, chroniclePauseTarget.id, {
        is_active: false,
        admin_inactive_reason: chroniclePauseReason.trim() || undefined,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:chronicles.pausedToast', 'Chronicle paused (hidden from discovery; rolls may be blocked until resumed)'));
        setChroniclePauseTarget(null);
        setChroniclePauseReason('');
        await reloadChronicles();
      } else {
        showError(d.error || t('admin:error.pause', 'Could not pause'));
      }
    } catch (e) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    } finally {
      setChronicleBusyId(null);
    }
  };

  const resumeChronicle = async (c) => {
    if (!c?.id) return;
    setChronicleBusyId(c.id);
    try {
      const r = await api.updateCampaign(token, c.id, { is_active: true });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:chronicles.resumed', 'Chronicle resumed'));
        await reloadChronicles();
      } else {
        showError(d.error || t('admin:error.resume', 'Could not resume'));
      }
    } catch (e) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    } finally {
      setChronicleBusyId(null);
    }
  };

  const confirmDeleteChronicle = async () => {
    if (!chronicleDeleteTarget) return;
    setChronicleDeleteLoading(true);
    setChronicleBusyId(chronicleDeleteTarget.id);
    try {
      const r = await api.deleteCampaign(token, chronicleDeleteTarget.id);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(d.message || t('admin:chronicles.deleted', 'Chronicle deleted'));
        setChronicleDeleteTarget(null);
        await reloadChronicles();
      } else {
        showError(d.error || t('admin:error.deleteFailed', 'Delete failed'));
      }
    } catch (e) {
      showError(t('admin:error.deleteFailed', 'Delete failed'));
    } finally {
      setChronicleDeleteLoading(false);
      setChronicleBusyId(null);
    }
  };

  const openUserDebug = async (u) => {
    setDebugTargetUser(u);
    setShowDebugModal(true);
    setDebugLoading(true);
    setDebugPayload(null);
    try {
      const r = await api.getUserDebug(token, u.id);
      const data = await r.json().catch(() => null);
      if (r.ok) setDebugPayload(data);
      else showError(data?.error || t('admin:error.loadDebug', 'Failed to load debug profile'));
    } catch (e) {
      showError(t('admin:error.loadDebug', 'Failed to load debug profile'));
    } finally {
      setDebugLoading(false);
    }
  };

  const submitSuspend = async (e) => {
    e.preventDefault();
    if (!suspendTargetChar) return;
    try {
      const r = await api.patchCharacterPlayStatus(token, suspendTargetChar.id, {
        suspended: true,
        reason_code: suspendReason,
        message: suspendMessage,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:users.chars.suspended', 'Character suspended'));
        setSuspendTargetChar(null);
        setSuspendMessage('');
        if (charsTargetUser) refreshUserCharsList(charsTargetUser.id);
      } else {
        showError(d.error || t('admin:error.failed', 'Failed'));
      }
    } catch (err) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    }
  };

  const clearCharacterSuspension = async (characterId) => {
    try {
      const r = await api.patchCharacterPlayStatus(token, characterId, {
        suspended: false,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:users.chars.cleared', 'Suspension cleared'));
        if (charsTargetUser) refreshUserCharsList(charsTargetUser.id);
      } else {
        showError(d.error || t('admin:error.failed', 'Failed'));
      }
    } catch (err) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    }
  };

  const submitMembershipOverride = async (e) => {
    e.preventDefault();
    if (!membershipModalUser) return;
    const cid = parseInt(membershipCampaignId, 10);
    if (!cid) {
      showError(t('admin:error.selectCampaign', 'Select a campaign'));
      return;
    }
    try {
      const r = await api.adminUserCampaignMembership(
        token,
        membershipModalUser.id,
        cid,
        membershipAction
      );
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(d.message || t('admin:users.membership.updated', 'Updated'));
        setMembershipCampaignId('');
      } else {
        showError(d.error || t('admin:error.failed', 'Failed'));
      }
    } catch (err) {
      showError(t('admin:error.requestFailed', 'Request failed'));
    }
  };

  const fetchInvites = async () => {
    try {
      const response = await api.listInvites(token);
      if (response.ok) {
        const data = await response.json();
        setInvites(Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('Failed to load invites');
    }
  };

  const handleCreateInvite = async (e) => {
    e.preventDefault();
    setInviteLoading(true);
    setError('');
    try {
      const payload = {
        type: inviteType,
        max_uses: Math.min(500, Math.max(1, parseInt(inviteMaxUses, 10) || 1)),
        description: inviteDescription.trim(),
        code: inviteCustomCode.trim() || undefined
      };
      const response = await api.createInvite(token, payload);
      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        showSuccess(t('admin:invites.created', 'Invite created: {{code}}', { code: data.invite?.code || 'OK' }));
        setInviteCustomCode('');
        fetchInvites();
      } else {
        setError(data.error || t('admin:error.createInvite', 'Failed to create invite'));
      }
    } catch (err) {
      setError(t('admin:error.connection', 'Connection error'));
    } finally {
      setInviteLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      showSuccess(t('admin:invites.copied', 'Copied to clipboard'));
    }).catch(() => {});
  };

  const handleEditUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    
    try {
      const response = await api.updateUser(token, selectedUser.id, {
        username: formData.get('username'),
        email: formData.get('email'),
        allow_multi_campaign_play: formData.get('allow_multi') === 'on',
        self_switch_playing_character: formData.get('self_switch_pc') === 'on',
      });
      
      if (response.ok) {
        showSuccess(t('admin:users.edit.done', 'User updated.'));
        setShowEditModal(false);
        fetchUsers();
      } else {
        const data = await response.json();
        setError(data.error || t('admin:error.updateUser', 'Failed to update user'));
      }
    } catch (err) {
      setError(t('admin:error.connection', 'Connection error'));
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    const newPassword = formData.get('new_password');
    
    try {
      const response = await api.resetUserPassword(token, selectedUser.id, newPassword);
      
      if (response.ok) {
        showSuccess(t('admin:users.password.done', 'Password reset.'));
        setShowPasswordModal(false);
      } else {
        const data = await response.json();
        setError(data.error || t('admin:error.resetPassword', 'Failed to reset password'));
      }
    } catch (err) {
      setError(t('admin:error.connection', 'Connection error'));
    } finally {
      setLoading(false);
    }
  };

  const handleBanUser = async (e) => {
    e.preventDefault();
    setLoading(true);
    const formData = new FormData(e.target);
    
    const banType = formData.get('ban_type');
    const banData = {
      ban_type: banType,
      ban_reason: formData.get('ban_reason')
    };
    
    if (banType === 'temporary') {
      banData.duration_hours = parseInt(formData.get('duration_hours') || 0);
      banData.duration_days = parseInt(formData.get('duration_days') || 0);
    }
    
    try {
      const response = await api.banUser(token, selectedUser.id, banData);
      
      if (response.ok) {
        showSuccess(t('admin:users.ban.done', 'User banned.'));
        setShowBanModal(false);
        fetchUsers();
        fetchModerationLog();
      } else {
        const data = await response.json();
        setError(data.error || t('admin:error.banUser', 'Failed to ban user'));
      }
    } catch (err) {
      setError(t('admin:error.connection', 'Connection error'));
    } finally {
      setLoading(false);
    }
  };

  const handleUnbanUser = (userId) => {
    setUserToUnban(userId);
    setShowUnbanConfirm(true);
  };

  const confirmDeleteAccount = async () => {
    if (!userToDeleteAccount || !token || deleteAccountLoading) return;
    if (userToDeleteAccount.id == null || userToDeleteAccount.id === '') {
      showError(t('admin:error.invalidUserId', 'Invalid user id; refresh the user list and try again.'));
      return;
    }
    setDeleteAccountLoading(true);
    try {
      const uid = userToDeleteAccount.id;
      const r = await api.deleteUserAccountPreserveChats(token, uid);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(d.message || t('admin:users.delete.done', 'Account removed; chat history preserved.'));
        setShowDeleteAccountConfirm(false);
        setUserToDeleteAccount(null);
        fetchUsers();
        fetchModerationLog();
      } else {
        const msg = d.error || t('admin:error.deleteFailed', 'Delete failed');
        if (r.status === 404 && msg === 'Not found') {
          showError(
            t('admin:error.deleteApiMissing', 'Delete API not found (404). Restart the backend so it loads the latest routes, then try again.'),
          );
        } else {
          showError(msg);
        }
      }
    } catch (e) {
      showError(t('admin:error.deleteFailed', 'Delete failed'));
    } finally {
      setDeleteAccountLoading(false);
    }
  };

  const confirmUnban = async () => {
    if (!userToUnban) return;
    
    try {
      const response = await api.unbanUser(token, userToUnban);
      
      if (response.ok) {
        showSuccess(t('admin:users.unban.done', 'User unbanned.'));
        setShowUnbanConfirm(false);
        setUserToUnban(null);
        fetchUsers();
        fetchModerationLog();
      }
    } catch (err) {
      setError(t('admin:error.unbanUser', 'Failed to unban user'));
    }
  };

  const reloadDowntime = async () => {
    const r2 = await api.listDowntimeRequests(token, downtimeStatusFilter || undefined);
    if (r2.ok) {
      const d2 = await r2.json();
      setDowntimeRows(Array.isArray(d2.requests) ? d2.requests : []);
    }
  };

  const approveDowntime = async (row) => {
    const note = window.prompt(t('admin:downtime.approvePrompt', 'Optional note to the player:'), '') || '';
    const r = await api.resolveDowntimeRequest(token, row.id, {
      status: 'approved',
      admin_reason: note.trim() || undefined,
    });
    const resBody = await r.json().catch(() => ({}));
    if (r.ok) {
      showSuccess(t('admin:downtime.approved', 'Request approved.'));
      await reloadDowntime();
    } else {
      showError(resBody.error || t('admin:downtime.approveFailed', 'Failed to approve'));
    }
  };

  const rejectDowntime = async (row) => {
    const reason = window.prompt(t('admin:downtime.rejectPrompt', 'Rejection reason (required):'), '');
    if (!reason || !reason.trim()) {
      showError(t('admin:downtime.reasonRequired', 'Reason is required to reject.'));
      return;
    }
    const r = await api.resolveDowntimeRequest(token, row.id, {
      status: 'rejected',
      admin_reason: reason.trim(),
    });
    const resBody = await r.json().catch(() => ({}));
    if (r.ok) {
      showSuccess(t('admin:downtime.rejected', 'Request rejected.'));
      await reloadDowntime();
    } else {
      showError(resBody.error || t('admin:downtime.rejectFailed', 'Failed to reject'));
    }
  };

  const saveAiSettings = async () => {
    setAiSaveLoading(true);
    try {
      const r = await api.putAiSettings(token, {
        lm_studio_model: aiModelSelect.trim(),
        ai_master_system_prompt: masterPromptDraft,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(t('admin:ai.settings.saved', 'AI settings saved.'));
        await loadAiSection();
      } else {
        showError(d.error || t('admin:error.saveFailed', 'Save failed'));
      }
    } catch (e) {
      showError(t('admin:error.saveFailed', 'Save failed'));
    } finally {
      setAiSaveLoading(false);
    }
  };

  const campaignStatusLabel = (status) => ({
    active: t('admin:chronicles.status.active', 'active'),
    inactive: t('admin:chronicles.status.inactive', 'inactive'),
    completed: t('admin:chronicles.status.completed', 'completed'),
    archived: t('admin:chronicles.status.archived', 'archived'),
  }[status] || status || '—');
  const campaignName = (c) => c.name || t('admin:common.campaignN', 'Campaign {{id}}', { id: c.id });
  const roleLabel = (role) => (role === 'admin' ? t('admin:users.role.admin', 'Admin') : role === 'helper' ? t('admin:users.role.helper', 'Helper') : t('admin:users.role.player', 'Player'));
  const downtimeFilterLabel = (f) => ({
    pending: t('admin:downtime.filter.pending', 'Pending'),
    approved: t('admin:downtime.filter.approved', 'Approved'),
    rejected: t('admin:downtime.filter.rejected', 'Rejected'),
    '': t('admin:downtime.filter.all', 'All'),
  }[f] || f);
  const logKindLabel = (kind) => ({
    admin: t('admin:moderation.kind.admin', 'staff'),
    user: t('admin:moderation.kind.user', 'user'),
    system: t('admin:moderation.kind.system', 'system'),
  }[kind] || kind);
  const suspensionLabel = (code) => ({
    pending_downtime: t('admin:users.suspend.reason.pending_downtime', 'Pending downtime'),
    pending_more_information: t('admin:users.suspend.reason.pending_more_information', 'Pending more information'),
    custom: t('admin:users.suspend.reason.custom', 'Custom (use message)'),
  }[code] || code);

  /* ---------- sections ---------- */

  const renderHome = () => (
    <div className="sr-admin__section sr-admin__home">
      <h2 className="sr-admin__title">{t('admin:home.title', 'Admin panel')}</h2>
      <p className="sr-admin__lead">
        {t('admin:home.lead', 'This area is for site administrators only. Each tab opens one tool; your changes apply to the whole site (users, invites and moderation).')}
      </p>
      <ul>
        <li><strong>{t('admin:nav.invites', 'Invite codes')}</strong> — {t('admin:home.invites', 'create and copy registration codes; track uses and optional notes.')}</li>
        <li><strong>{t('admin:nav.chronicles', 'All chronicles')}</strong> — {t('admin:home.chronicles', 'every campaign in the database; open one in the app to visit locations and chat (site admins only).')}</li>
        <li><strong>{t('admin:nav.users', 'Users')}</strong> — {t('admin:home.users', 'edit accounts, grant Helper ST privileges (multi-chronicle + self-switch PC), reset passwords, ban or unban users.')}</li>
        <li><strong>{t('admin:nav.downtime', 'Downtime requests')}</strong> — {t('admin:home.downtime', 'sheet change requests from players; approve or reject with a reason.')}</li>
        <li><strong>{t('admin:nav.moderation', 'Moderation log')}</strong> — {t('admin:home.moderation', 'recent admin actions for audit and follow-up.')}</li>
        <li><strong>{t('admin:nav.ai', 'AI system')}</strong> — {t('admin:home.ai', 'local model, global master prompt, model per role, cloud keys, classifier and embeddings.')}</li>
      </ul>
    </div>
  );

  const renderInvites = () => (
    <div className="sr-admin__section">
      <h2 className="sr-admin__title">{t('admin:invites.title', 'Invite codes (sign-up)')}</h2>
      <p className="sr-admin__lead">
        {t('admin:invites.lead', 'Create a code and send it to the player. They enter it on the Register form with username, email and password. Invalid attempts are logged; if SMTP and MAIL_ADMIN_ALERT_EMAIL are set, you get an email alert.')}
      </p>
      <Panel className="sr-admin__panel">
        <form onSubmit={handleCreateInvite} className="sr-admin__form">
          <Select label={t('admin:invites.role', 'Role granted by this code')} value={inviteType} onChange={(e) => setInviteType(e.target.value)}>
            <option value="player">{t('admin:invites.rolePlayer', 'Player')}</option>
            <option value="admin">{t('admin:invites.roleAdmin', 'Admin (use sparingly)')}</option>
          </Select>
          <Input
            type="number"
            min={1}
            max={500}
            label={t('admin:invites.maxUses', 'Max uses')}
            value={inviteMaxUses}
            onChange={(e) => setInviteMaxUses(e.target.value)}
          />
          <Input
            label={t('admin:invites.note', 'Note (optional)')}
            value={inviteDescription}
            onChange={(e) => setInviteDescription(e.target.value)}
            placeholder={t('admin:invites.notePlaceholder', 'e.g. Player: Alex — March 2026')}
          />
          <Input
            label={t('admin:invites.custom', 'Custom code (optional)')}
            value={inviteCustomCode}
            onChange={(e) => setInviteCustomCode(e.target.value)}
            placeholder={t('admin:invites.customPlaceholder', 'Leave empty to auto-generate (e.g. SR-A1B2C3-D4E5)')}
          />
          <div>
            <Button type="submit" variant="arcane" icon="plus" loading={inviteLoading} loadingLabel={t('admin:invites.creating', 'Creating…')}>
              {t('admin:invites.create', 'Create invite code')}
            </Button>
          </div>
        </form>
      </Panel>
      <Panel title={t('admin:invites.existing', 'Existing codes')} className="sr-admin__panel">
        {invites.length === 0 ? (
          <EmptyState glyph="key" title={t('admin:invites.empty', 'No invites yet. Create one above.')} />
        ) : (
          <div className="sr-admin__tablewrap">
            <table className="sr-admin__table">
              <thead>
                <tr>
                  <th>{t('admin:invites.col.code', 'Code')}</th>
                  <th>{t('admin:invites.col.type', 'Type')}</th>
                  <th>{t('admin:invites.col.uses', 'Uses')}</th>
                  <th>{t('admin:invites.col.note', 'Note')}</th>
                  <th>{t('admin:invites.col.created', 'Created')}</th>
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.code}>
                    <td>
                      <div className="sr-admin__row">
                        <Button size="sm" variant="ghost" icon="scroll" onClick={() => copyToClipboard(inv.code)}>
                          {t('admin:invites.copy', 'Copy')}
                        </Button>
                        <span className="sr-admin__mono sr-admin__strong">{inv.code}</span>
                      </div>
                    </td>
                    <td>{inv.type === 'admin' ? t('admin:invites.typeAdmin', 'admin') : inv.type === 'player' ? t('admin:invites.typePlayer', 'player') : inv.type}</td>
                    <td>{inv.uses} / {inv.max_uses}</td>
                    <td className="is-note">{inv.description || '—'}</td>
                    <td className="is-small">{formatWhen(inv.created_at, displayTimezone)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );

  const renderChronicles = () => (
    <div className="sr-admin__section">
      <h2 className="sr-admin__title">{t('admin:chronicles.title', 'All chronicles')}</h2>
      <p className="sr-admin__lead">
        {t('admin:chronicles.lead', 'Complete list from GET /api/admin/campaigns. Pause sets the chronicle inactive (players won’t see it in discovery; manual dice in that game may be blocked until you resume). Delete removes the campaign and related data — use with care.')}
      </p>
      <Panel className="sr-admin__panel">
        {chroniclesLoading ? (
          <p className="sr-admin__muted">{t('admin:chronicles.loading', 'Loading chronicles…')}</p>
        ) : chroniclesError ? (
          <p className="sr-admin__error">{chroniclesError}</p>
        ) : chroniclesList.length === 0 ? (
          <EmptyState glyph="book" title={t('admin:chronicles.emptyTitle', 'There are no campaigns in the system.')}>
            {t('admin:chronicles.emptyBody', 'When Storytellers or players create a chronicle in the app, it appears here. If you expected something, check the database and that site admins can reach /api/admin/campaigns.')}
          </EmptyState>
        ) : (
          <div className="sr-admin__tablewrap">
            <table className="sr-admin__table">
              <thead>
                <tr>
                  <th>{t('admin:chronicles.col.id', 'ID')}</th>
                  <th>{t('admin:chronicles.col.name', 'Name')}</th>
                  <th>{t('admin:chronicles.col.system', 'System')}</th>
                  <th>{t('admin:chronicles.col.state', 'State')}</th>
                  <th>{t('admin:chronicles.col.listing', 'Listing')}</th>
                  <th>{t('admin:chronicles.col.maxPlayers', 'Max players')}</th>
                  <th>{t('admin:chronicles.col.createdBy', 'Created by')}</th>
                  <th>{t('admin:chronicles.col.actions', 'Actions')}</th>
                </tr>
              </thead>
              <tbody>
                {chroniclesList.map((c) => {
                  const busy = chronicleBusyId === c.id;
                  const paused = c.is_active === false;
                  return (
                    <tr key={c.id}>
                      <td>{c.id}</td>
                      <td className="is-name">{campaignName(c)}</td>
                      <td>
                        {c.game_system || '—'} <EditionBadge campaign={c} />
                      </td>
                      <td>
                        <div className="is-small">{campaignStatusLabel(c.status)}</div>
                        {paused ? (
                          <>
                            <Badge tone="warn">{t('admin:chronicles.paused', 'Paused')}</Badge>
                            {c.admin_inactive_reason ? (
                              <div className="sr-admin__reason" title={c.admin_inactive_reason}>
                                {c.admin_inactive_reason.length > 80 ? `${c.admin_inactive_reason.slice(0, 80)}…` : c.admin_inactive_reason}
                              </div>
                            ) : null}
                          </>
                        ) : (
                          <Badge tone="ok">{t('admin:chronicles.active', 'Active')}</Badge>
                        )}
                      </td>
                      <td className="is-small">
                        {c.listing_visibility === 'listed' ? t('admin:chronicles.listed', 'listed') : t('admin:chronicles.private', 'private')}
                        {c.accepting_players ? <span className="sr-admin__ok"> · {t('admin:chronicles.openJoin', 'open join')}</span> : null}
                      </td>
                      <td>{c.max_players != null && c.max_players !== '' ? c.max_players : '—'}</td>
                      <td>
                        {c.creator_username || '—'}
                        {c.created_by != null ? <span className="sr-admin__muted"> (#{c.created_by})</span> : null}
                      </td>
                      <td>
                        <div className="sr-admin__actions sr-admin__actions--cell">
                          <Button
                            size="sm"
                            variant="arcane"
                            disabled={!onAdminOpenCampaign || chroniclesOpeningId === c.id || busy}
                            loading={chroniclesOpeningId === c.id}
                            loadingLabel={t('admin:chronicles.opening', 'Opening…')}
                            onClick={() => handleOpenChronicleFromAdmin(c)}
                          >
                            {t('admin:chronicles.open', 'Open')}
                          </Button>
                          <Button size="sm" disabled={busy} onClick={() => openChronicleEdit(c)}>{t('admin:common.edit', 'Edit')}</Button>
                          <Button size="sm" disabled={busy} onClick={() => openChronicleStats(c)}>{t('admin:chronicles.stats', 'Stats')}</Button>
                          {paused ? (
                            <Button size="sm" disabled={busy} onClick={() => resumeChronicle(c)}>{t('admin:chronicles.resume', 'Resume')}</Button>
                          ) : (
                            <Button size="sm" disabled={busy} onClick={() => { setChroniclePauseTarget(c); setChroniclePauseReason(''); }}>
                              {t('admin:chronicles.pause', 'Pause')}
                            </Button>
                          )}
                          <Button size="sm" variant="danger" disabled={busy} onClick={() => setChronicleDeleteTarget(c)}>{t('admin:common.delete', 'Delete')}</Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );

  const renderUsers = () => (
    <div className="sr-admin__section">
      <h2 className="sr-admin__title">{t('admin:users.title', 'User management')}</h2>
      <Panel className="sr-admin__panel">
        <div className="sr-admin__tablewrap">
          <table className="sr-admin__table">
            <thead>
              <tr>
                <th>{t('admin:users.col.id', 'ID')}</th>
                <th>{t('admin:users.col.username', 'Username')}</th>
                <th>{t('admin:users.col.email', 'Email')}</th>
                <th>{t('admin:users.col.role', 'Role')}</th>
                <th>{t('admin:users.col.privileges', 'Privileges')}</th>
                <th>{t('admin:users.col.status', 'Status')}</th>
                <th>{t('admin:users.col.lastLogin', 'Last login')}</th>
                <th>{t('admin:users.col.actions', 'Actions')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td className="is-name">{u.username}</td>
                  <td className="is-wrap">{u.email}</td>
                  <td>
                    <Badge tone={u.role === 'admin' ? 'blood' : 'ok'} icon={u.role === 'admin' ? 'crown' : 'user'}>{roleLabel(u.role)}</Badge>
                  </td>
                  <td>
                    {!u.allow_multi_campaign_play && !u.self_switch_playing_character ? (
                      <span className="sr-admin__muted">—</span>
                    ) : u.allow_multi_campaign_play && u.self_switch_playing_character ? (
                      <Badge tone="arcane" title={t('admin:users.priv.helperHint', 'Site-granted: multiple locked chronicles + switching the playing character without Storyteller approval')}>
                        {t('admin:users.priv.helper', 'Helper ST')}
                      </Badge>
                    ) : (
                      <div className="sr-admin__badges">
                        {u.allow_multi_campaign_play && (
                          <Badge tone="neutral" title={t('admin:users.priv.multiHint', 'May have locked characters in more than one chronicle')}>
                            {t('admin:users.priv.multi', 'Multi')}
                          </Badge>
                        )}
                        {u.self_switch_playing_character && (
                          <Badge tone="neutral" title={t('admin:users.priv.selfSwitchHint', 'May switch the active character in a chronicle without Storyteller approval')}>
                            {t('admin:users.priv.selfSwitch', 'Self-switch')}
                          </Badge>
                        )}
                      </div>
                    )}
                  </td>
                  <td>
                    {u.is_banned ? (
                      <Badge tone="danger" icon="lock-chain">
                        {u.ban_type === 'permanent' ? t('admin:users.status.permaBan', 'Permanent ban') : t('admin:users.status.tempBan', 'Temporary ban')}
                      </Badge>
                    ) : (
                      <Badge tone="ok" icon="check">{t('admin:users.status.active', 'Active')}</Badge>
                    )}
                  </td>
                  <td className="is-small">{formatWhen(u.last_login, displayTimezone)}</td>
                  <td>
                    <div className="sr-admin__actions sr-admin__actions--cell">
                      <Button size="sm" onClick={() => openUserCharacters(u)}>{t('admin:users.action.characters', 'Characters')}</Button>
                      <Button size="sm" variant="ghost" onClick={() => openUserDebug(u)}>{t('admin:users.action.debug', 'Debug')}</Button>
                      <Button size="sm" onClick={() => { setMembershipModalUser(u); setMembershipCampaignId(''); }}>
                        {t('admin:users.action.membership', 'Chronicles')}
                      </Button>
                      <Button size="sm" onClick={() => { setSelectedUser(u); setShowEditModal(true); }}>{t('admin:common.edit', 'Edit')}</Button>
                      <Button size="sm" icon="key" onClick={() => { setSelectedUser(u); setShowPasswordModal(true); }}>
                        {t('admin:users.action.resetPassword', 'Reset password')}
                      </Button>
                      {u.id === user?.id ? (
                        <span className="sr-admin__muted">{t('admin:users.you', '(you)')}</span>
                      ) : (
                        <>
                          {u.username !== 'ic_history_archive' && (
                            <Button size="sm" variant="danger" icon="trash" onClick={() => { setUserToDeleteAccount(u); setShowDeleteAccountConfirm(true); }}>
                              {t('admin:common.delete', 'Delete')}
                            </Button>
                          )}
                          {u.is_banned ? (
                            <Button size="sm" icon="check" onClick={() => handleUnbanUser(u.id)}>{t('admin:users.action.unban', 'Unban')}</Button>
                          ) : (
                            <Button size="sm" variant="danger" onClick={() => { setSelectedUser(u); setBanType('temporary'); setShowBanModal(true); }}>
                              {t('admin:users.action.ban', 'Ban')}
                            </Button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );

  const renderModeration = () => (
    <div className="sr-admin__section">
      <h2 className="sr-admin__title">{t('admin:moderation.title', 'Recent activity log')}</h2>
      <p className="sr-admin__lead">
        {t('admin:moderation.lead', 'Audit trail: staff actions (red), a user acting on their own account (green), automated or system events (blue). Rows stay visible when a user account was removed (names may show as missing).')}
      </p>
      <div className="sr-admin__row">
        <Select
          label={t('admin:moderation.rows', 'Rows')}
          fieldClassName="sr-admin__select"
          value={moderationLogLimit}
          onChange={(e) => setModerationLogLimit(Number(e.target.value))}
          options={[50, 100, 200, 500].map((n) => ({ value: n, label: String(n) }))}
        />
        <Button size="sm" icon="moon-half" onClick={() => fetchModerationLog()}>{t('admin:common.refresh', 'Refresh')}</Button>
      </div>
      <Panel className="sr-admin__panel">
        {moderationLog.length === 0 ? (
          <EmptyState glyph="scroll" title={t('admin:moderation.empty', 'No logged actions yet')} />
        ) : (
          <div className="sr-admin__log">
            {moderationLog.map((log) => {
              const kind = log.entry_kind || 'admin';
              const actor = log.admin_username || (log.admin_id != null && log.admin_id !== '' ? `#${log.admin_id}` : '—');
              const target =
                log.username ||
                (log.user_id != null && log.user_id !== '' ? t('admin:moderation.userN', 'user #{{id}}', { id: log.user_id }) : '—');
              return (
                <div key={log.id} className={`sr-admin__entry sr-admin__entry--${kind}`}>
                  <div className="sr-admin__entry-head">
                    <span className="sr-admin__entry-action" lang="en">
                      {String(log.action || '').toUpperCase()}
                      <span className="sr-admin__entry-kind">({logKindLabel(kind)})</span>
                    </span>
                    <span className="sr-admin__muted">{formatWhen(log.created_at, displayTimezone)}</span>
                  </div>
                  <div>
                    <strong className="sr-admin__strong">{actor}</strong>
                    <span className="sr-admin__muted"> → </span>
                    <strong className="sr-admin__strong">{target}</strong>
                  </div>
                  {log.details && Object.keys(log.details).length > 0 && (
                    <div className="sr-admin__entry-details">{JSON.stringify(log.details)}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );

  const renderDowntime = () => (
    <div className="sr-admin__section">
      <h2 className="sr-admin__title">{t('admin:downtime.title', 'Character downtime requests')}</h2>
      <p className="sr-admin__lead">
        {t('admin:downtime.lead', 'Players send these from their profile when their sheet is locked. Approve or reject with a short reason (required for rejections).')}
      </p>
      <div className="sr-admin__row" role="group" aria-label={t('admin:downtime.filterLabel', 'Filter by status')}>
        {['pending', 'approved', 'rejected', ''].map((f) => (
          <Button
            key={f || 'all'}
            size="sm"
            variant="ghost"
            className="sr-admin__filter"
            aria-pressed={downtimeStatusFilter === f}
            onClick={() => setDowntimeStatusFilter(f)}
          >
            {downtimeFilterLabel(f)}
          </Button>
        ))}
      </div>
      <Panel className="sr-admin__panel">
        {downtimeRows.length === 0 ? (
          <EmptyState glyph="hourglass" title={t('admin:downtime.empty', 'No requests in this filter.')} />
        ) : (
          <div className="sr-admin__log">
            {downtimeRows.map((row) => (
              <div key={row.id} className="sr-admin__entry">
                <div className="sr-admin__entry-char">
                  {row.character_name} <span className="sr-admin__muted">· @{row.player_username}</span>
                </div>
                <div className="sr-admin__muted">{row.campaign_name}</div>
                <div className="sr-admin__entry-text">{row.request_text}</div>
                <div className="sr-admin__muted">
                  {t('admin:downtime.status', 'Status:')} <strong>{downtimeFilterLabel(row.status)}</strong>
                  {row.admin_reason ? ` — ${row.admin_reason}` : ''}
                </div>
                {row.status === 'pending' && (
                  <div className="sr-admin__row sr-admin__row--spaced">
                    <Button size="sm" variant="primary" icon="check" onClick={() => approveDowntime(row)}>{t('admin:downtime.approve', 'Approve')}</Button>
                    <Button size="sm" variant="danger" icon="close" onClick={() => rejectDowntime(row)}>{t('admin:downtime.reject', 'Reject')}</Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );

  const renderAi = () => (
    <div className="sr-admin__section sr-admin__section--narrow">
      <h2 className="sr-admin__title">{t('admin:nav.ai', 'AI system')}</h2>
      <p className="sr-admin__lead">
        {t('admin:ai.lead', 'Choose which model id the backend sends to LM Studio’s OpenAI-compatible API, or leave the default to follow LM_STUDIO_MODEL in the environment and the model LM Studio reports as loaded. This is the default LM Studio model (used by the English Storyteller and fallbacks unless a role below names a model). The master system prompt is prepended to every feature-specific system prompt.')}
      </p>
      {aiSectionLoading ? (
        <p className="sr-admin__muted">{t('admin:loading', 'Loading…')}</p>
      ) : (
        <Panel title={t('admin:ai.settings.title', 'Local model and master prompt')} className="sr-admin__panel">
          {aiSettings && (
            <div className="sr-admin__kv">
              <div><strong>{t('admin:ai.settings.url', 'LM Studio URL:')}</strong> <span className="sr-admin__code">{aiSettings.lm_studio_url || '—'}</span></div>
              <div><strong>{t('admin:ai.settings.envModel', 'Env LM_STUDIO_MODEL:')}</strong> {aiSettings.env_lm_studio_model || t('admin:ai.settings.envEmpty', '(empty / auto)')}</div>
              <div>
                <strong>{t('admin:ai.settings.effective', 'Effective model id (in use):')}</strong>{' '}
                <code className="sr-admin__code">{aiSettings.effective_lm_studio_model || '—'}</code>
              </div>
            </div>
          )}
          {lmListError && (
            <p className="sr-admin__warn">
              {lmListError} — {t('admin:ai.settings.lmUnreachable', 'Is LM Studio running and reachable from the backend host?')}
            </p>
          )}
          <div className="sr-admin__row sr-admin__row--top">
            <Select
              label={t('admin:ai.settings.model', 'Chat model (OpenAI id from LM Studio)')}
              hint={t('admin:ai.settings.modelHint', 'Pick a model from the list (from GET /v1/models), or keep the default to follow whatever you load in LM Studio without pinning an id here.')}
              fieldClassName="sr-admin__grow"
              value={aiModelSelect}
              onChange={(e) => setAiModelSelect(e.target.value)}
            >
              <option value="">{t('admin:ai.settings.modelDefault', 'Default — use env + loaded model')}</option>
              {lmOpenaiModels.map((m) => (
                <option key={m.id || JSON.stringify(m)} value={m.id}>{m.id}</option>
              ))}
            </Select>
            <Button size="sm" className="sr-admin__btn-offset" onClick={() => loadAiSection()}>{t('admin:ai.settings.refresh', 'Refresh list')}</Button>
          </div>
          <Textarea
            label={t('admin:ai.settings.prompt', 'Master system prompt (global)')}
            className="sr-admin__textarea-mono"
            value={masterPromptDraft}
            onChange={(e) => setMasterPromptDraft(e.target.value)}
            rows={12}
            placeholder={t('admin:ai.settings.promptPlaceholder', 'Optional. Applied before each feature-specific system prompt (chat, locations, moderation…). Describe the assistant’s tone, safety rules and setting.')}
          />
          <div>
            <Button variant="primary" loading={aiSaveLoading} loadingLabel={t('admin:common.saving', 'Saving…')} onClick={saveAiSettings}>
              {t('admin:ai.settings.save', 'Save AI settings')}
            </Button>
          </div>
        </Panel>
      )}
      <AiProvidersPanel token={token} lmModels={lmOpenaiModels} showSuccess={showSuccess} showError={showError} />
    </div>
  );

  const RENDER = {
    home: renderHome,
    invites: renderInvites,
    chronicles: renderChronicles,
    users: renderUsers,
    downtime: renderDowntime,
    moderation: renderModeration,
    ai: renderAi,
  };
  const labels = sectionLabels();
  const membershipDisabled = adminCampaignsLoading || !!adminCampaignsLoadError || adminCampaignsList.length === 0;

  return (
    <div className="sr-admin">
      <Tabs
        className="sr-admin__tabs"
        label={t('admin:nav.label', 'Admin sections')}
        value={adminSection}
        onChange={setAdminSection}
        tabs={ADMIN_SECTIONS.map((id) => ({
          id,
          label: labels[id],
          icon: SECTION_ICONS[id],
          content: id === adminSection ? RENDER[id]() : null,
        }))}
      />

      {/* Edit user */}
      <Modal open={showEditModal && !!selectedUser} onClose={() => setShowEditModal(false)} title={t('admin:users.edit.title', 'Edit user')} icon="user">
        {selectedUser ? (
          <form onSubmit={handleEditUser} className="sr-admin__form sr-admin__form--modal">
            <Input name="username" label={t('admin:users.col.username', 'Username')} defaultValue={selectedUser.username} />
            <Input type="email" name="email" label={t('admin:users.col.email', 'Email')} defaultValue={selectedUser.email} />
            <Checkbox
              name="allow_multi"
              defaultChecked={!!selectedUser.allow_multi_campaign_play}
              label={t('admin:users.edit.multi', 'Multiple chronicles at once (locked sheets in more than one campaign). Without this, joining a second locked chronicle is blocked.')}
            />
            <Checkbox
              name="self_switch_pc"
              defaultChecked={!!selectedUser.self_switch_playing_character}
              label={t('admin:users.edit.selfSwitch', 'Self-switch playing character (trusted player): change which character is active in a chronicle without Storyteller approval. Other chronicles are unchanged; characters are still switched per chronicle.')}
            />
            <div className="sr-admin__actions">
              <Button variant="ghost" onClick={() => setShowEditModal(false)}>{t('admin:common.cancel', 'Cancel')}</Button>
              <Button type="submit" variant="primary" loading={loading} loadingLabel={t('admin:common.saving', 'Saving…')}>
                {t('admin:common.saveChanges', 'Save changes')}
              </Button>
            </div>
          </form>
        ) : null}
      </Modal>

      {/* Reset password */}
      <Modal
        open={showPasswordModal && !!selectedUser}
        onClose={() => setShowPasswordModal(false)}
        title={selectedUser ? t('admin:users.password.title', 'Reset password for {{name}}', { name: selectedUser.username }) : ''}
        icon="key"
        size="sm"
      >
        <form onSubmit={handleResetPassword} className="sr-admin__form sr-admin__form--modal">
          <Input
            type="password"
            name="new_password"
            required
            minLength={8}
            autoComplete="new-password"
            label={t('admin:users.password.new', 'New password')}
            placeholder={t('admin:users.password.min', 'At least 8 characters')}
          />
          <div className="sr-admin__actions">
            <Button variant="ghost" onClick={() => setShowPasswordModal(false)}>{t('admin:common.cancel', 'Cancel')}</Button>
            <Button type="submit" variant="primary" loading={loading} loadingLabel={t('admin:users.password.busy', 'Resetting…')}>
              {t('admin:users.password.submit', 'Reset password')}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Ban */}
      <Modal
        open={showBanModal && !!selectedUser}
        onClose={() => setShowBanModal(false)}
        title={selectedUser ? t('admin:users.ban.title', 'Ban {{name}}', { name: selectedUser.username }) : ''}
        icon="lock-chain"
      >
        <form onSubmit={handleBanUser} className="sr-admin__form sr-admin__form--modal">
          <Select name="ban_type" required label={t('admin:users.ban.type', 'Ban type')} value={banType} onChange={(e) => setBanType(e.target.value)}>
            <option value="temporary">{t('admin:users.ban.temporary', 'Temporary')}</option>
            <option value="permanent">{t('admin:users.ban.permanent', 'Permanent')}</option>
          </Select>
          {banType === 'temporary' ? (
            <div className="sr-admin__grid2">
              <Input type="number" name="duration_days" min="0" defaultValue="0" label={t('admin:users.ban.days', 'Days')} />
              <Input type="number" name="duration_hours" min="0" defaultValue="0" label={t('admin:users.ban.hours', 'Hours')} />
            </div>
          ) : null}
          <Textarea
            name="ban_reason"
            required
            rows={3}
            label={t('admin:users.ban.reason', 'Reason')}
            placeholder={t('admin:users.ban.reasonPlaceholder', 'Explain why this user is being banned…')}
          />
          <div className="sr-admin__actions">
            <Button variant="ghost" onClick={() => setShowBanModal(false)}>{t('admin:common.cancel', 'Cancel')}</Button>
            <Button type="submit" variant="danger" loading={loading} loadingLabel={t('admin:users.ban.busy', 'Banning…')}>
              {t('admin:users.ban.submit', 'Ban user')}
            </Button>
          </div>
        </form>
      </Modal>

      {/* A user's characters */}
      <Modal
        open={showUserCharsModal && !!charsTargetUser}
        onClose={() => { setShowUserCharsModal(false); setCharsTargetUser(null); setSuspendTargetChar(null); }}
        title={charsTargetUser ? t('admin:users.chars.title', 'Characters — {{name}}', { name: charsTargetUser.username }) : ''}
        icon="users"
        size="lg"
      >
        {userCharsLoading ? (
          <p className="sr-admin__muted">{t('admin:loading', 'Loading…')}</p>
        ) : userCharsError ? (
          <p className="sr-admin__error">{userCharsError}</p>
        ) : userCharsList.length === 0 ? (
          <p className="sr-admin__muted">{t('admin:users.chars.none', 'No characters')}</p>
        ) : (
          <div className="sr-admin__tablewrap">
            <table className="sr-admin__table">
              <thead>
                <tr>
                  <th>{t('admin:users.chars.col.id', 'ID')}</th>
                  <th>{t('admin:users.chars.col.name', 'Name')}</th>
                  <th>{t('admin:users.chars.col.campaign', 'Chronicle')}</th>
                  <th>{t('admin:users.chars.col.locked', 'Locked')}</th>
                  <th>{t('admin:users.chars.col.suspended', 'Suspended')}</th>
                  <th><span className="sr-visually-hidden">{t('admin:users.col.actions', 'Actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {userCharsList.map((ch) => (
                  <tr key={ch.id}>
                    <td>{ch.id}</td>
                    <td className="is-name">{ch.name}</td>
                    <td>{ch.campaign_id}</td>
                    <td>{ch.sheet_locked ? t('admin:common.yes', 'Yes') : t('admin:common.no', 'No')}</td>
                    <td>{ch.play_suspended ? (suspensionLabel(ch.play_suspension_reason_code) || t('admin:common.yes', 'Yes')) : '—'}</td>
                    <td>
                      {ch.play_suspended ? (
                        <Button size="sm" onClick={() => clearCharacterSuspension(ch.id)}>{t('admin:users.chars.clear', 'Clear hold')}</Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => { setSuspendTargetChar(ch); setSuspendReason('pending_downtime'); setSuspendMessage(''); }}
                        >
                          {t('admin:users.chars.suspend', 'Suspend')}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>

      {/* Suspend a character */}
      <Modal
        open={!!suspendTargetChar}
        onClose={() => setSuspendTargetChar(null)}
        title={suspendTargetChar ? t('admin:users.suspend.title', 'Suspend play — {{name}}', { name: suspendTargetChar.name }) : ''}
        icon="lock-chain"
        size="sm"
      >
        <form onSubmit={submitSuspend} className="sr-admin__form sr-admin__form--modal">
          <Select label={t('admin:users.suspend.reasonLabel', 'Reason')} value={suspendReason} onChange={(e) => setSuspendReason(e.target.value)}>
            <option value="pending_downtime">{suspensionLabel('pending_downtime')}</option>
            <option value="pending_more_information">{suspensionLabel('pending_more_information')}</option>
            <option value="custom">{suspensionLabel('custom')}</option>
          </Select>
          <Textarea
            label={t('admin:users.suspend.message', 'Message to the player')}
            value={suspendMessage}
            onChange={(e) => setSuspendMessage(e.target.value)}
            rows={4}
            placeholder={t('admin:users.suspend.messagePlaceholder', 'Shown when they try to use this character in play.')}
          />
          <div className="sr-admin__actions">
            <Button variant="ghost" onClick={() => setSuspendTargetChar(null)}>{t('admin:common.cancel', 'Cancel')}</Button>
            <Button type="submit" variant="danger">{t('admin:users.suspend.confirm', 'Suspend')}</Button>
          </div>
        </form>
      </Modal>

      {/* Debug profile */}
      <Modal
        open={showDebugModal && !!debugTargetUser}
        onClose={() => { setShowDebugModal(false); setDebugTargetUser(null); setDebugPayload(null); }}
        title={debugTargetUser ? t('admin:users.debug.title', 'Debug profile — {{name}} (id {{id}})', { name: debugTargetUser.username, id: debugTargetUser.id }) : ''}
        icon="eye"
        size="lg"
      >
        {debugLoading ? (
          <p className="sr-admin__muted">{t('admin:loading', 'Loading…')}</p>
        ) : debugPayload ? (
          <pre className="sr-admin__pre">{JSON.stringify(debugPayload, null, 2)}</pre>
        ) : null}
      </Modal>

      {/* Chronicle membership */}
      <Modal
        open={!!membershipModalUser}
        onClose={() => { setMembershipModalUser(null); setMembershipCampaignId(''); setMembershipTargetChronicles([]); setAdminCampaignsFromFallback(false); }}
        title={membershipModalUser ? t('admin:users.membership.title', 'Chronicle membership — {{name}}', { name: membershipModalUser.username }) : ''}
        icon="book"
      >
        <div className="sr-admin__section">
          <div>
            <strong className="sr-admin__strong">{t('admin:users.membership.current', 'This user’s chronicles')}</strong>
            {membershipTargetChronicles.length === 0 ? (
              <p className="sr-admin__muted">
                {adminCampaignsLoading
                  ? t('admin:loading', 'Loading…')
                  : t('admin:users.membership.none', 'None listed (no roster row and not the sole creator of an orphan chronicle).')}
              </p>
            ) : (
              <ul className="sr-admin__list">
                {membershipTargetChronicles.map((c) => (
                  <li key={`${c.id}-${c.via || 'm'}`}>
                    <strong className="sr-admin__strong">{campaignName(c)}</strong>
                    {' · '}
                    {c.game_system || '—'} <EditionBadge campaign={c} /> · {c.member_role || t('admin:users.membership.member', 'member')}
                    {c.via === 'created_by_only' ? (
                      <span className="sr-admin__warn"> {t('admin:users.membership.creatorOnly', '(creator only — use Add below to write a roster row)')}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <form onSubmit={submitMembershipOverride} className="sr-admin__form sr-admin__form--modal">
            {adminCampaignsLoading ? (
              <p className="sr-admin__muted">{t('admin:users.membership.loadingCampaigns', 'Loading chronicles…')}</p>
            ) : adminCampaignsLoadError ? (
              <p className="sr-admin__error">{adminCampaignsLoadError}</p>
            ) : adminCampaignsList.length === 0 ? (
              <p className="sr-admin__muted">{t('admin:users.membership.noCampaigns', 'No chronicles in the database yet. Create one first.')}</p>
            ) : (
              <Select
                label={t('admin:users.membership.campaign', 'Chronicle')}
                value={membershipCampaignId}
                onChange={(e) => setMembershipCampaignId(e.target.value)}
                required
              >
                <option value="">{t('admin:users.membership.select', '— Select a chronicle —')}</option>
                {adminCampaignsList.map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {campaignName(c)} · {c.game_system || '—'}
                    {c.rules_edition != null && String(c.game_system || '').toLowerCase() === 'vampire' ? ` ${editionLabel(c)}` : ''}{' '}
                    (id {c.id})
                  </option>
                ))}
              </Select>
            )}
            {adminCampaignsFromFallback && adminCampaignsList.length > 0 ? (
              <p className="sr-admin__warn">
                {t('admin:users.membership.fallback', 'Full admin list unavailable (old backend?). Showing your chronicles only. Restart the backend so GET /api/admin/campaigns loads.')}
              </p>
            ) : null}
            <Select label={t('admin:users.membership.action', 'Action')} value={membershipAction} onChange={(e) => setMembershipAction(e.target.value)}>
              <option value="add">{t('admin:users.membership.add', 'Add to the roster (campaign_players)')}</option>
              <option value="remove">{t('admin:users.membership.remove', 'Remove from the roster (campaign_players)')}</option>
            </Select>
            <div className="sr-admin__actions">
              <Button
                variant="ghost"
                onClick={() => { setMembershipModalUser(null); setMembershipCampaignId(''); setMembershipTargetChronicles([]); setAdminCampaignsFromFallback(false); }}
              >
                {t('admin:common.cancel', 'Cancel')}
              </Button>
              <Button type="submit" variant="primary" disabled={membershipDisabled}>{t('admin:common.apply', 'Apply')}</Button>
            </div>
          </form>
        </div>
      </Modal>

      {/* Edit chronicle */}
      <Modal
        open={!!chronicleEditTarget}
        onClose={() => setChronicleEditTarget(null)}
        title={t('admin:chronicles.edit.title', 'Edit chronicle')}
        description={chronicleEditTarget ? `${chronicleEditTarget.name} (id ${chronicleEditTarget.id})` : undefined}
        icon="book"
      >
        <form onSubmit={submitChronicleEdit} className="sr-admin__form sr-admin__form--modal">
          <Input label={t('admin:chronicles.col.name', 'Name')} value={chEdName} onChange={(e) => setChEdName(e.target.value)} required />
          <Textarea label={t('admin:chronicles.edit.description', 'Description')} value={chEdDescription} onChange={(e) => setChEdDescription(e.target.value)} rows={4} />
          <Select label={t('admin:chronicles.edit.listing', 'Listing visibility')} value={chEdListing} onChange={(e) => setChEdListing(e.target.value)}>
            <option value="private">{t('admin:chronicles.private', 'private')}</option>
            <option value="listed">{t('admin:chronicles.listed', 'listed')}</option>
          </Select>
          <Checkbox
            label={t('admin:chronicles.edit.accepting', 'Accepting new players')}
            checked={chEdAccepting}
            onChange={(e) => setChEdAccepting(e.target.checked)}
          />
          <Input
            type="number"
            min={0}
            label={t('admin:chronicles.edit.maxPlayers', 'Max players (empty = no limit)')}
            value={chEdMaxPlayers}
            onChange={(e) => setChEdMaxPlayers(e.target.value)}
            placeholder={t('admin:chronicles.edit.maxPlaceholder', 'e.g. 6')}
          />
          <div className="sr-admin__actions">
            <Button variant="ghost" onClick={() => setChronicleEditTarget(null)}>{t('admin:common.cancel', 'Cancel')}</Button>
            <Button type="submit" variant="primary" disabled={!!chronicleBusyId}>{t('admin:common.save', 'Save')}</Button>
          </div>
        </form>
      </Modal>

      {/* Chronicle stats */}
      <Modal
        open={!!chronicleStatsTarget}
        onClose={() => { setChronicleStatsTarget(null); setChronicleStatsData(null); }}
        title={chronicleStatsTarget ? t('admin:chronicles.statsTitle', 'Stats — {{name}} (id {{id}})', { name: chronicleStatsTarget.name, id: chronicleStatsTarget.id }) : ''}
        icon="hourglass"
        size="sm"
      >
        {chronicleStatsLoading ? (
          <p className="sr-admin__muted">{t('admin:loading', 'Loading…')}</p>
        ) : chronicleStatsData ? (
          <dl className="sr-admin__stats">
            <dt>{t('admin:chronicles.stat.players', 'Active players')}</dt><dd>{chronicleStatsData.active_players}</dd>
            <dt>{t('admin:chronicles.stat.characters', 'Characters')}</dt><dd>{chronicleStatsData.characters}</dd>
            <dt>{t('admin:chronicles.stat.locations', 'Locations')}</dt><dd>{chronicleStatsData.locations}</dd>
            <dt>{t('admin:chronicles.stat.messages', 'Story messages')}</dt><dd>{chronicleStatsData.messages}</dd>
          </dl>
        ) : (
          <p className="sr-admin__muted">{t('admin:common.noData', 'No data')}</p>
        )}
      </Modal>

      {/* Pause chronicle */}
      <Modal
        open={!!chroniclePauseTarget}
        onClose={() => { setChroniclePauseTarget(null); setChroniclePauseReason(''); }}
        title={t('admin:chronicles.pauseTitle', 'Pause chronicle?')}
        icon="moon-new"
      >
        {chroniclePauseTarget ? (
          <form onSubmit={submitChroniclePause} className="sr-admin__form sr-admin__form--modal">
            <p className="sr-admin__lead">
              {t('admin:chronicles.pauseBody', '“{{name}}” will be marked inactive: it disappears from discovery and join lists, and manual dice that need an active chronicle may fail until you resume it.', { name: chroniclePauseTarget.name })}
            </p>
            <Textarea
              label={t('admin:chronicles.pauseReason', 'Reason (optional, visible to staff in this list)')}
              value={chroniclePauseReason}
              onChange={(e) => setChroniclePauseReason(e.target.value)}
              rows={3}
              placeholder={t('admin:chronicles.pausePlaceholder', 'e.g. on hiatus until March, content review…')}
            />
            <div className="sr-admin__actions">
              <Button variant="ghost" onClick={() => { setChroniclePauseTarget(null); setChroniclePauseReason(''); }}>{t('admin:common.cancel', 'Cancel')}</Button>
              <Button type="submit" variant="danger" disabled={!!chronicleBusyId}>{t('admin:chronicles.pause', 'Pause')}</Button>
            </div>
          </form>
        ) : null}
      </Modal>

      <AdminConfirm
        open={!!chronicleDeleteTarget}
        title={t('admin:chronicles.deleteTitle', 'Delete chronicle permanently?')}
        message={
          chronicleDeleteTarget
            ? t('admin:chronicles.deleteBody', 'Delete “{{name}}” (id {{id}}) and all related locations, messages and data?\n\nThis cannot be undone.', { name: chronicleDeleteTarget.name, id: chronicleDeleteTarget.id })
            : ''
        }
        confirmText={t('admin:chronicles.deleteConfirm', 'Yes, delete')}
        busy={chronicleDeleteLoading}
        onConfirm={confirmDeleteChronicle}
        onCancel={() => { if (!chronicleDeleteLoading) setChronicleDeleteTarget(null); }}
      />

      <AdminConfirm
        open={showUnbanConfirm}
        title={t('admin:users.unban.title', 'Unban user?')}
        message={t('admin:users.unban.body', 'They immediately regain full access to the site.')}
        confirmText={t('admin:users.unban.confirm', 'Yes, unban')}
        onConfirm={confirmUnban}
        onCancel={() => { setShowUnbanConfirm(false); setUserToUnban(null); }}
      />

      <AdminConfirm
        open={showDeleteAccountConfirm}
        title={t('admin:users.delete.title', 'Delete account permanently?')}
        message={
          userToDeleteAccount
            ? t('admin:users.delete.body', 'Delete “{{name}}” and ALL of their characters?\n\nIn-character chat lines stay in the chronicle but show as posted by the system archive account (the text is unchanged). Their dice rolls may also move to that archive account. Chronicles they created are transferred to you.', { name: userToDeleteAccount.username })
            : ''
        }
        confirmText={t('admin:users.delete.confirm', 'Yes, delete account')}
        busy={deleteAccountLoading}
        onConfirm={confirmDeleteAccount}
        onCancel={() => { setShowDeleteAccountConfirm(false); setUserToDeleteAccount(null); }}
      />

      {error && (
        <div className="sr-admin__banner" role="alert">
          <span className="sr-admin__grow">{error}</span>
          <Button size="sm" variant="ghost" icon="close" onClick={() => setError('')}>
            {t('admin:common.dismiss', 'Dismiss')}
          </Button>
        </div>
      )}
    </div>
  );
}

export default AdminPage;
