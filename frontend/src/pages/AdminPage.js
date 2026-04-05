import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { useToast } from '../components/ToastNotification';
import ConfirmDialog from '../components/ConfirmDialog';
import { formatDateTimeInZone } from '../utils/userTimeFormat';
import '../responsive.css';

function AdminPage({ token, user, displayTimezone = null, onAdminOpenCampaign = null }) {
  // Initialize toast notification system
  const { showSuccess, showError, ToastContainer } = useToast();
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [invites, setInvites] = useState([]);
  const [inviteType, setInviteType] = useState('player');
  const [inviteMaxUses, setInviteMaxUses] = useState(1);
  const [inviteDescription, setInviteDescription] = useState('');
  const [inviteCustomCode, setInviteCustomCode] = useState('');
  const [inviteLoading, setInviteLoading] = useState(false);
  /** 'home' | 'invites' | 'users' | 'chronicles' | 'moderation' | 'downtime' */
  const [adminSection, setAdminSection] = useState('home');
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

  const adminNavSections = [
    { id: 'home', label: 'Overview' },
    { id: 'invites', label: 'Invite codes' },
    { id: 'chronicles', label: 'All chronicles' },
    { id: 'users', label: 'User management' },
    { id: 'downtime', label: 'Downtime requests' },
    { id: 'moderation', label: 'Moderation log' },
    { id: 'ai', label: 'AI & LM Studio' },
  ];

  // Fetch all users on mount
  useEffect(() => {
    fetchUsers();
    fetchModerationLog();
    fetchInvites();
  }, []);

  useEffect(() => {
    if (adminSection !== 'chronicles' || !token) return undefined;
    let cancelled = false;
    setChroniclesLoading(true);
    setChroniclesError(null);
    (async () => {
      try {
        const r = await api.listAdminCampaigns(token);
        const data = await r.json().catch(() => null);
        if (cancelled) return;
        if (r.ok && Array.isArray(data)) {
          setChroniclesList(data);
          setChroniclesError(null);
        } else {
          setChroniclesList([]);
          const msg =
            (data && data.error) ||
            (r.status === 404
              ? 'Admin campaigns API not found. Restart the backend.'
              : 'Could not load chronicles');
          setChroniclesError(msg);
          showError(msg);
        }
      } catch (e) {
        if (!cancelled) {
          setChroniclesList([]);
          setChroniclesError('Could not load chronicles');
          showError('Could not load chronicles');
        }
      } finally {
        if (!cancelled) setChroniclesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
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
              'Could not load campaigns (restart backend to enable /api/admin/campaigns)';
            setAdminCampaignsLoadError(msg);
            showError(msg);
          }
        }
      } catch (e) {
        if (!cancelled) {
          setAdminCampaignsList([]);
          setAdminCampaignsLoadError('Could not load campaigns');
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
        showError((d && d.error) || 'Could not load AI settings');
      }
      const r2 = await api.listLmStudioModels(token);
      const d2 = await r2.json().catch(() => null);
      if (r2.ok && d2) {
        setLmOpenaiModels(Array.isArray(d2.openai_models) ? d2.openai_models : []);
        setLmListError(d2.error || null);
      } else {
        setLmOpenaiModels([]);
        setLmListError((d2 && d2.error) || 'Could not list LM Studio models');
      }
    } catch (e) {
      console.error(e);
      showError('Failed to load AI / LM Studio settings');
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
      setError('Failed to load users');
    }
  };

  const fetchModerationLog = async () => {
    try {
      const response = await api.getModerationLog(token, 20);
      if (response.ok) {
        const data = await response.json();
        setModerationLog(data);
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
          `Could not load characters (${r.status})`;
        setUserCharsError(msg);
        showError(msg);
      }
    } catch (e) {
      setUserCharsList([]);
      setUserCharsError('Failed to load characters');
      showError('Failed to load characters');
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
      showError('Open-in-app is not available from this screen.');
      return;
    }
    setChroniclesOpeningId(c.id);
    try {
      await onAdminOpenCampaign({
        id: c.id,
        name: c.name,
        game_system: c.game_system,
        status: c.status,
      });
    } catch (e) {
      showError('Could not open chronicle');
    } finally {
      setChroniclesOpeningId(null);
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
      else showError(data?.error || 'Failed to load debug profile');
    } catch (e) {
      showError('Failed to load debug profile');
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
        showSuccess('Character suspended');
        setSuspendTargetChar(null);
        setSuspendMessage('');
        if (charsTargetUser) refreshUserCharsList(charsTargetUser.id);
      } else {
        showError(d.error || 'Failed');
      }
    } catch (err) {
      showError('Request failed');
    }
  };

  const clearCharacterSuspension = async (characterId) => {
    try {
      const r = await api.patchCharacterPlayStatus(token, characterId, {
        suspended: false,
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess('Suspension cleared');
        if (charsTargetUser) refreshUserCharsList(charsTargetUser.id);
      } else {
        showError(d.error || 'Failed');
      }
    } catch (err) {
      showError('Request failed');
    }
  };

  const submitMembershipOverride = async (e) => {
    e.preventDefault();
    if (!membershipModalUser) return;
    const cid = parseInt(membershipCampaignId, 10);
    if (!cid) {
      showError('Select a campaign');
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
        showSuccess(d.message || 'Updated');
        setMembershipCampaignId('');
      } else {
        showError(d.error || 'Failed');
      }
    } catch (err) {
      showError('Request failed');
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
        showSuccess(`✅ Invite created: ${data.invite?.code || 'OK'}`);
        setInviteCustomCode('');
        fetchInvites();
      } else {
        setError(data.error || 'Failed to create invite');
      }
    } catch (err) {
      setError('Connection error');
    } finally {
      setInviteLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      showSuccess('Copied to clipboard');
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
      });
      
      if (response.ok) {
        showSuccess('✅ User updated successfully!');
        setShowEditModal(false);
        fetchUsers();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to update user');
      }
    } catch (err) {
      setError('Connection error');
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
        showSuccess('✅ Password reset successfully!');
        setShowPasswordModal(false);
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to reset password');
      }
    } catch (err) {
      setError('Connection error');
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
        showSuccess('✅ User banned successfully!');
        setShowBanModal(false);
        fetchUsers();
        fetchModerationLog();
      } else {
        const data = await response.json();
        setError(data.error || 'Failed to ban user');
      }
    } catch (err) {
      setError('Connection error');
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
      showError('Invalid user id; refresh the user list and try again.');
      return;
    }
    setDeleteAccountLoading(true);
    try {
      const uid = userToDeleteAccount.id;
      const r = await api.deleteUserAccountPreserveChats(token, uid);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        showSuccess(d.message || 'Account removed; chat history preserved.');
        setShowDeleteAccountConfirm(false);
        setUserToDeleteAccount(null);
        fetchUsers();
        fetchModerationLog();
      } else {
        const msg = d.error || 'Delete failed';
        if (r.status === 404 && msg === 'Not found') {
          showError(
            'Delete API not found (404). Restart the backend so it loads the latest routes, then try again.',
          );
        } else {
          showError(msg);
        }
      }
    } catch (e) {
      showError('Delete failed');
    } finally {
      setDeleteAccountLoading(false);
    }
  };

  const confirmUnban = async () => {
    if (!userToUnban) return;
    
    try {
      const response = await api.unbanUser(token, userToUnban);
      
      if (response.ok) {
        showSuccess('✅ User unbanned successfully!');
        setShowUnbanConfirm(false);
        setUserToUnban(null);
        fetchUsers();
        fetchModerationLog();
      }
    } catch (err) {
      setError('Failed to unban user');
    }
  };

  return (
    <div style={{ minHeight: '100%', background: '#0f0f1e' }}>
      {/* Section tabs (site nav is on the parent shell) */}
      <div
        style={{
          background: 'linear-gradient(135deg, #16213e 0%, #0f1729 100%)',
          padding: '12px 20px',
          boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
          borderBottom: '2px solid #2a2a4e',
        }}
      >
        <nav
          aria-label="Admin sections"
          style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          {adminNavSections.map(({ id, label }) => {
            const active = adminSection === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setAdminSection(id)}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  border: active ? '2px solid #e94560' : '2px solid #2a2a4e',
                  background: active ? 'rgba(233, 69, 96, 0.22)' : 'rgba(15, 23, 41, 0.85)',
                  color: active ? '#fff' : '#b5b5c3',
                  cursor: 'pointer',
                  fontWeight: active ? 700 : 500,
                  fontSize: '13px',
                }}
              >
                {label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Main Content */}
      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '40px 20px' }}>

        {adminSection === 'home' && (
          <div style={{
            textAlign: 'center',
            maxWidth: '640px',
            margin: '48px auto 0',
            padding: '32px 24px',
            color: '#b5b5c3',
            lineHeight: 1.65,
          }}>
            <h2 style={{ color: '#e94560', marginTop: 0, marginBottom: '16px' }}>You are on the Admin Panel</h2>
            <p style={{ marginBottom: '20px' }}>
              This area is for site administrators only. Use the tabs above to open each tool; your changes apply to the whole site (users, invites, and moderation).
            </p>
            <ul style={{ textAlign: 'left', display: 'inline-block', margin: '0 auto', paddingLeft: '1.25rem', maxWidth: '520px' }}>
              <li style={{ marginBottom: '10px' }}><strong style={{ color: '#e0e0e0' }}>Invite codes</strong> — create and copy registration codes; track uses and optional notes.</li>
              <li style={{ marginBottom: '10px' }}><strong style={{ color: '#e0e0e0' }}>All chronicles</strong> — every campaign in the database; open one in the main app to visit locations and chat (site admins only).</li>
              <li style={{ marginBottom: '10px' }}><strong style={{ color: '#e0e0e0' }}>User management</strong> — edit accounts, reset passwords, ban or unban users.</li>
              <li style={{ marginBottom: '10px' }}><strong style={{ color: '#e0e0e0' }}>Moderation log</strong> — recent admin actions for audit and follow-up.</li>
              <li><strong style={{ color: '#e0e0e0' }}>AI &amp; LM Studio</strong> — pick the local model id, optional global master system prompt.</li>
            </ul>
          </div>
        )}

        {/* Invite codes — players use these at registration */}
        {adminSection === 'invites' && (
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '20px' }}>🎟️ Invite codes (sign-up)</h2>
          <p style={{ color: '#b5b5c3', marginBottom: '20px', lineHeight: 1.6 }}>
            Create a code and send it to the player. They enter it on the <strong>Register</strong> form with username, email, and password.
            Invalid attempts are logged; if SMTP and <code style={{ color: '#9d4edd' }}>MAIL_ADMIN_ALERT_EMAIL</code> are set, you get an email alert.
          </p>

          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '24px',
            marginBottom: '24px',
            border: '1px solid #2a2a4e',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)'
          }}>
            <form onSubmit={handleCreateInvite} style={{ display: 'grid', gap: '16px', maxWidth: '640px' }}>
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px', fontWeight: 600 }}>Role granted by this code</label>
                <select
                  value={inviteType}
                  onChange={(e) => setInviteType(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', background: '#0f1729', color: '#e0e0e0', border: '2px solid #2a2a4e' }}
                >
                  <option value="player">Player</option>
                  <option value="admin">Admin (use sparingly)</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px', fontWeight: 600 }}>Max uses</label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={inviteMaxUses}
                  onChange={(e) => setInviteMaxUses(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', background: '#0f1729', color: '#e0e0e0', border: '2px solid #2a2a4e' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px', fontWeight: 600 }}>Note (optional)</label>
                <input
                  type="text"
                  value={inviteDescription}
                  onChange={(e) => setInviteDescription(e.target.value)}
                  placeholder="e.g. Player: Alex — March 2026"
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', background: '#0f1729', color: '#e0e0e0', border: '2px solid #2a2a4e' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px', fontWeight: 600 }}>Custom code (optional)</label>
                <input
                  type="text"
                  value={inviteCustomCode}
                  onChange={(e) => setInviteCustomCode(e.target.value)}
                  placeholder="Leave empty to auto-generate (e.g. SR-A1B2C3-D4E5)"
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', background: '#0f1729', color: '#e0e0e0', border: '2px solid #2a2a4e' }}
                />
              </div>
              <button
                type="submit"
                disabled={inviteLoading}
                style={{
                  padding: '12px 20px',
                  background: inviteLoading ? '#4a4a5e' : '#9d4edd',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 'bold',
                  cursor: inviteLoading ? 'not-allowed' : 'pointer',
                  maxWidth: '280px'
                }}
              >
                {inviteLoading ? 'Creating…' : '➕ Create invite code'}
              </button>
            </form>
          </div>

          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            border: '1px solid #2a2a4e',
            overflowX: 'auto'
          }}>
            <h3 style={{ color: '#b5b5c3', marginTop: 0 }}>Existing codes</h3>
            {invites.length === 0 ? (
              <p style={{ color: '#8b8b9f' }}>No invites yet. Create one above.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #2a2a4e' }}>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Code</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Type</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Uses</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Note</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((inv) => (
                    <tr key={inv.code} style={{ borderBottom: '1px solid #2a2a4e' }}>
                      <td style={{ padding: '10px', color: '#fff', fontFamily: 'monospace' }}>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(inv.code)}
                          style={{
                            background: 'transparent',
                            border: '1px solid #667eea',
                            color: '#a5b4fc',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            cursor: 'pointer',
                            marginRight: '8px'
                          }}
                        >Copy</button>
                        {inv.code}
                      </td>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>{inv.type}</td>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>{inv.uses} / {inv.max_uses}</td>
                      <td style={{ padding: '10px', color: '#8b8b9f', maxWidth: '280px' }}>{inv.description || '—'}</td>
                      <td style={{ padding: '10px', color: '#8b8b9f', fontSize: '12px' }}>
                        {inv.created_at ? formatDateTimeInZone(inv.created_at, displayTimezone) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        )}

        {adminSection === 'chronicles' && (
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '12px' }}>All chronicles</h2>
          <p style={{ color: '#b5b5c3', marginBottom: '20px', lineHeight: 1.65, maxWidth: '720px' }}>
            Every campaign in the system (same data as <code style={{ color: '#9d4edd', fontSize: '12px' }}>GET /api/admin/campaigns</code>).
            Use <strong style={{ color: '#e0e0e0' }}>Open in app</strong> to jump into the main chronicle view, locations, and chat.
            Only users with the site admin role can open this panel.
          </p>
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            border: '1px solid #2a2a4e',
            overflowX: 'auto',
          }}
          >
            {chroniclesLoading ? (
              <p style={{ color: '#8b8b9f' }}>Loading chronicles…</p>
            ) : chroniclesError ? (
              <p style={{ color: '#f87171' }}>{chroniclesError}</p>
            ) : chroniclesList.length === 0 ? (
              <p style={{ color: '#8b8b9f' }}>No campaigns in the database.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #2a2a4e' }}>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>ID</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Name</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>System</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Status</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }}>Created by</th>
                    <th style={{ padding: '10px', textAlign: 'left', color: '#e94560' }} />
                  </tr>
                </thead>
                <tbody>
                  {chroniclesList.map((c) => (
                    <tr key={c.id} style={{ borderBottom: '1px solid #2a2a4e' }}>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>{c.id}</td>
                      <td style={{ padding: '10px', color: '#fff', fontWeight: 600 }}>
                        {c.name || `Campaign ${c.id}`}
                      </td>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>{c.game_system || '—'}</td>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>{c.status || '—'}</td>
                      <td style={{ padding: '10px', color: '#b5b5c3' }}>
                        {c.creator_username || '—'}
                        {c.created_by != null ? (
                          <span style={{ color: '#64748b' }}>{' '}(user #{c.created_by})</span>
                        ) : null}
                      </td>
                      <td style={{ padding: '10px' }}>
                        <button
                          type="button"
                          disabled={!onAdminOpenCampaign || chroniclesOpeningId === c.id}
                          onClick={() => handleOpenChronicleFromAdmin(c)}
                          style={{
                            padding: '8px 14px',
                            background:
                              !onAdminOpenCampaign || chroniclesOpeningId === c.id
                                ? '#3d3d52'
                                : '#667eea',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '6px',
                            cursor:
                              !onAdminOpenCampaign || chroniclesOpeningId === c.id
                                ? 'not-allowed'
                                : 'pointer',
                            fontWeight: 'bold',
                            fontSize: '12px',
                          }}
                        >
                          {chroniclesOpeningId === c.id ? 'Opening…' : 'Open in app'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        )}

        {/* User Management Section */}
        {adminSection === 'users' && (
        <div style={{ marginBottom: '40px' }}>
          <h2 style={{ color: '#e94560', marginBottom: '20px' }}>👥 User Management</h2>
          
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e',
            overflowX: 'auto'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #2a2a4e' }}>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>ID</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Username</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Email</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Role</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Status</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Last login</th>
                  <th style={{ padding: '12px', textAlign: 'left', color: '#e94560' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderBottom: '1px solid #2a2a4e' }}>
                    <td style={{ padding: '12px', color: '#b5b5c3' }}>{u.id}</td>
                    <td style={{ padding: '12px', color: '#fff', fontWeight: '600' }}>{u.username}</td>
                    <td style={{ padding: '12px', color: '#b5b5c3' }}>{u.email}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 12px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: '600',
                        background: u.role === 'admin' ? 'rgba(233, 69, 96, 0.2)' : 'rgba(40, 167, 69, 0.2)',
                        color: u.role === 'admin' ? '#e94560' : '#28a745',
                        border: `1px solid ${u.role === 'admin' ? '#e94560' : '#28a745'}`
                      }}>
                        {u.role === 'admin' ? '👑 Admin' : '🎮 Player'}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {u.is_banned ? (
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '600',
                          background: 'rgba(255, 68, 68, 0.2)',
                          color: '#ff4444',
                          border: '1px solid #ff4444'
                        }}>
                          🚫 {u.ban_type === 'permanent' ? 'PERMA BAN' : 'TEMP BAN'}
                        </span>
                      ) : (
                        <span style={{
                          padding: '4px 12px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          fontWeight: '600',
                          background: 'rgba(40, 167, 69, 0.2)',
                          color: '#28a745',
                          border: '1px solid #28a745'
                        }}>
                          ✅ Active
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px', color: '#8b8b9f', fontSize: '12px' }}>
                      {u.last_login
                        ? formatDateTimeInZone(u.last_login, displayTimezone)
                        : '—'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => openUserCharacters(u)}
                          style={{
                            padding: '6px 12px',
                            background: '#0ea5e9',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600',
                          }}
                        >
                          PCs
                        </button>
                        <button
                          type="button"
                          onClick={() => openUserDebug(u)}
                          style={{
                            padding: '6px 12px',
                            background: '#6366f1',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600',
                          }}
                        >
                          Debug
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setMembershipModalUser(u);
                            setMembershipCampaignId('');
                          }}
                          style={{
                            padding: '6px 12px',
                            background: '#8b5cf6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600',
                          }}
                        >
                          Campaign
                        </button>
                        <button
                          onClick={() => { setSelectedUser(u); setShowEditModal(true); }}
                          style={{
                            padding: '6px 12px',
                            background: '#667eea',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600'
                          }}
                        >
                          ✏️ Edit
                        </button>
                        <button
                          onClick={() => { setSelectedUser(u); setShowPasswordModal(true); }}
                          style={{
                            padding: '6px 12px',
                            background: '#ffa726',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '600'
                          }}
                        >
                          🔑 Reset PW
                        </button>
                        {u.id === user?.id ? (
                          <span style={{
                            padding: '6px 12px',
                            color: '#8b8b9f',
                            fontSize: '12px',
                            fontStyle: 'italic'
                          }}>
                            (You)
                          </span>
                        ) : (
                          <>
                            {u.username !== 'ic_history_archive' && (
                              <button
                                type="button"
                                onClick={() => {
                                  setUserToDeleteAccount(u);
                                  setShowDeleteAccountConfirm(true);
                                }}
                                style={{
                                  padding: '6px 12px',
                                  background: '#7f1d1d',
                                  color: 'white',
                                  border: '1px solid #991b1b',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '12px',
                                  fontWeight: '600',
                                }}
                              >
                                🗑️ Delete
                              </button>
                            )}
                            {u.is_banned ? (
                              <button
                                onClick={() => handleUnbanUser(u.id)}
                                style={{
                                  padding: '6px 12px',
                                  background: '#28a745',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '12px',
                                  fontWeight: '600',
                                }}
                              >
                                ✅ Unban
                              </button>
                            ) : (
                              <button
                                onClick={() => { setSelectedUser(u); setShowBanModal(true); }}
                                style={{
                                  padding: '6px 12px',
                                  background: '#dc3545',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer',
                                  fontSize: '12px',
                                  fontWeight: '600',
                                }}
                              >
                                🚫 Ban
                              </button>
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
        </div>
        )}

        {/* Moderation Log */}
        {adminSection === 'moderation' && (
        <div>
          <h2 style={{ color: '#e94560', marginBottom: '20px' }}>📋 Recent Moderation Log</h2>
          
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            boxShadow: '0 2px 10px rgba(0,0,0,0.5)',
            border: '1px solid #2a2a4e'
          }}>
            {moderationLog.length === 0 ? (
              <p style={{ color: '#b5b5c3', textAlign: 'center' }}>No moderation actions yet</p>
            ) : (
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {moderationLog.map(log => (
                  <div key={log.id} style={{
                    padding: '12px',
                    marginBottom: '10px',
                    background: '#0f1729',
                    borderRadius: '8px',
                    border: '1px solid #2a2a4e'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: '#e94560', fontWeight: '600' }}>
                        {log.action.toUpperCase()}
                      </span>
                      <span style={{ color: '#8b8b9f', fontSize: '12px' }}>
                        {formatDateTimeInZone(log.created_at, displayTimezone)}
                      </span>
                    </div>
                    <div style={{ color: '#b5b5c3', fontSize: '14px' }}>
                      <strong>{log.admin_username}</strong> → <strong>{log.username}</strong>
                    </div>
                    {log.details && Object.keys(log.details).length > 0 && (
                      <div style={{ color: '#8b8b9f', fontSize: '12px', marginTop: '4px' }}>
                        {JSON.stringify(log.details)}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        )}

        {adminSection === 'downtime' && (
        <div>
          <h2 style={{ color: '#e94560', marginBottom: '16px' }}>Character downtime requests</h2>
          <p style={{ color: '#8b8b9f', marginBottom: '16px', maxWidth: '720px' }}>
            Players submit these from Player Profile when their sheet is locked. Approve or reject with a short reason (required for rejections).
          </p>
          <div style={{ marginBottom: '16px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {['pending', 'approved', 'rejected', ''].map((f) => (
              <button
                key={f || 'all'}
                type="button"
                onClick={() => setDowntimeStatusFilter(f)}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  border: downtimeStatusFilter === f ? '2px solid #e94560' : '1px solid #2a2a4e',
                  background: downtimeStatusFilter === f ? 'rgba(233, 69, 96, 0.15)' : '#0f1729',
                  color: '#e0e0e0',
                  cursor: 'pointer',
                }}
              >
                {f === '' ? 'All' : f}
              </button>
            ))}
          </div>
          <div style={{
            background: '#16213e',
            borderRadius: '10px',
            padding: '20px',
            border: '1px solid #2a2a4e',
          }}>
            {downtimeRows.length === 0 ? (
              <p style={{ color: '#b5b5c3' }}>No requests in this filter.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {downtimeRows.map((row) => (
                  <div
                    key={row.id}
                    style={{
                      background: '#0f1729',
                      borderRadius: '8px',
                      padding: '14px',
                      border: '1px solid #2a2a4e',
                    }}
                  >
                    <div style={{ color: '#e94560', fontWeight: 'bold' }}>
                      {row.character_name} <span style={{ color: '#8b8b9f', fontWeight: 'normal' }}>· @{row.player_username}</span>
                    </div>
                    <div style={{ color: '#8b8b9f', fontSize: '13px' }}>{row.campaign_name}</div>
                    <div style={{ color: '#b5b5c3', marginTop: '8px', whiteSpace: 'pre-wrap' }}>{row.request_text}</div>
                    <div style={{ marginTop: '8px', color: '#94a3b8', fontSize: '12px' }}>
                      Status: <strong>{row.status}</strong>
                      {row.admin_reason ? ` — ${row.admin_reason}` : ''}
                    </div>
                    {row.status === 'pending' && (
                      <div style={{ marginTop: '12px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={async () => {
                            const note = window.prompt('Optional note to the player:', '') || '';
                            const r = await api.resolveDowntimeRequest(token, row.id, {
                              status: 'approved',
                              admin_reason: note.trim() || undefined,
                            });
                            const resBody = await r.json().catch(() => ({}));
                            if (r.ok) {
                              showSuccess('Request approved.');
                              const r2 = await api.listDowntimeRequests(token, downtimeStatusFilter || undefined);
                              if (r2.ok) {
                                const d2 = await r2.json();
                                setDowntimeRows(Array.isArray(d2.requests) ? d2.requests : []);
                              }
                            } else {
                              showError(resBody.error || 'Failed to approve');
                            }
                          }}
                          style={{
                            padding: '8px 16px',
                            background: '#15803d',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                          }}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            const reason = window.prompt('Rejection reason (required):', '');
                            if (!reason || !reason.trim()) {
                              showError('Reason is required to reject.');
                              return;
                            }
                            const r = await api.resolveDowntimeRequest(token, row.id, {
                              status: 'rejected',
                              admin_reason: reason.trim(),
                            });
                            const resBody = await r.json().catch(() => ({}));
                            if (r.ok) {
                              showSuccess('Request rejected.');
                              const r2 = await api.listDowntimeRequests(token, downtimeStatusFilter || undefined);
                              if (r2.ok) {
                                const d2 = await r2.json();
                                setDowntimeRows(Array.isArray(d2.requests) ? d2.requests : []);
                              }
                            } else {
                              showError(resBody.error || 'Failed to reject');
                            }
                          }}
                          style={{
                            padding: '8px 16px',
                            background: '#b91c1c',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: 'pointer',
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        )}

        {adminSection === 'ai' && (
        <div style={{ maxWidth: '900px', margin: '0 auto' }}>
          <h2 style={{ color: '#e94560', marginBottom: '12px' }}>AI &amp; LM Studio</h2>
          <p style={{ color: '#b5b5c3', marginBottom: '20px', lineHeight: 1.65 }}>
            Choose which model id the backend sends to LM Studio&apos;s OpenAI-compatible API, or leave default to follow{' '}
            <code style={{ color: '#9d4edd' }}>LM_STUDIO_MODEL</code> in the environment and the model LM Studio reports as loaded.
            The master system prompt is prepended to every route-specific system prompt for chat / AI features.
          </p>
          {aiSectionLoading ? (
            <p style={{ color: '#8b8b9f' }}>Loading…</p>
          ) : (
            <div style={{
              background: '#16213e',
              borderRadius: '10px',
              padding: '24px',
              border: '1px solid #2a2a4e',
              display: 'grid',
              gap: '20px',
            }}>
              {aiSettings && (
                <div style={{ color: '#94a3b8', fontSize: '14px', lineHeight: 1.6 }}>
                  <div><strong style={{ color: '#e0e0e0' }}>LM Studio URL:</strong> {aiSettings.lm_studio_url || '—'}</div>
                  <div><strong style={{ color: '#e0e0e0' }}>Env LM_STUDIO_MODEL:</strong> {aiSettings.env_lm_studio_model || '(empty / auto)'}</div>
                  <div><strong style={{ color: '#e0e0e0' }}>Effective model id (in use):</strong>{' '}
                    <code style={{ color: '#7dd3fc' }}>{aiSettings.effective_lm_studio_model || '—'}</code>
                  </div>
                </div>
              )}
              {lmListError && (
                <div style={{ color: '#ffb74d', fontSize: '14px' }}>
                  {lmListError} — Is LM Studio running and reachable from the backend host?
                </div>
              )}
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '8px', fontWeight: 600 }}>
                  Chat model (OpenAI id from LM Studio)
                </label>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <select
                    value={aiModelSelect}
                    onChange={(e) => setAiModelSelect(e.target.value)}
                    style={{
                      flex: '1 1 280px',
                      minWidth: '220px',
                      padding: '10px',
                      borderRadius: '6px',
                      background: '#0f1729',
                      color: '#e0e0e0',
                      border: '2px solid #2a2a4e',
                    }}
                  >
                    <option value="">Default — use env + loaded model resolution</option>
                    {lmOpenaiModels.map((m) => (
                      <option key={m.id || JSON.stringify(m)} value={m.id}>
                        {m.id}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => loadAiSection()}
                    style={{
                      padding: '10px 16px',
                      borderRadius: '6px',
                      border: '1px solid #2a2a4e',
                      background: '#0f1729',
                      color: '#e0e0e0',
                      cursor: 'pointer',
                    }}
                  >
                    Refresh list
                  </button>
                </div>
                <p style={{ color: '#8b8b9f', fontSize: '13px', marginTop: '8px', marginBottom: 0 }}>
                  Pick a model from the list (from GET /v1/models), or default to match whatever you load in LM Studio without pinning an id here.
                </p>
              </div>
              <div>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '8px', fontWeight: 600 }}>
                  Master system prompt (global)
                </label>
                <textarea
                  value={masterPromptDraft}
                  onChange={(e) => setMasterPromptDraft(e.target.value)}
                  rows={12}
                  placeholder="Optional. Applied before each feature-specific system prompt (e.g. chat, locations, moderation). Describe your assistant’s tone, safety, and setting."
                  style={{
                    width: '100%',
                    boxSizing: 'border-box',
                    padding: '12px',
                    borderRadius: '8px',
                    background: '#0f1729',
                    color: '#e8e8e8',
                    border: '2px solid #2a2a4e',
                    fontFamily: 'ui-monospace, monospace',
                    fontSize: '13px',
                    lineHeight: 1.5,
                  }}
                />
              </div>
              <div>
                <button
                  type="button"
                  disabled={aiSaveLoading}
                  onClick={async () => {
                    setAiSaveLoading(true);
                    try {
                      const r = await api.putAiSettings(token, {
                        lm_studio_model: aiModelSelect.trim(),
                        ai_master_system_prompt: masterPromptDraft,
                      });
                      const d = await r.json().catch(() => ({}));
                      if (r.ok) {
                        showSuccess('AI settings saved.');
                        await loadAiSection();
                      } else {
                        showError(d.error || 'Save failed');
                      }
                    } catch (e) {
                      showError('Save failed');
                    } finally {
                      setAiSaveLoading(false);
                    }
                  }}
                  style={{
                    padding: '12px 24px',
                    background: aiSaveLoading ? '#4a4a5e' : 'linear-gradient(135deg, #e94560 0%, #8b0000 100%)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: aiSaveLoading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold',
                  }}
                >
                  {aiSaveLoading ? 'Saving…' : 'Save AI settings'}
                </button>
              </div>
            </div>
          )}
        </div>
        )}
      </div>

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>✏️ Edit User</h3>
            <form onSubmit={handleEditUser}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Username:</label>
                <input
                  type="text"
                  name="username"
                  defaultValue={selectedUser.username}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Email:</label>
                <input
                  type="email"
                  name="email"
                  defaultValue={selectedUser.email}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#b5b5c3', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    name="allow_multi"
                    defaultChecked={!!selectedUser.allow_multi_campaign_play}
                  />
                  Allow multiple locked characters / campaigns (admin override)
                </label>
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#28a745',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showPasswordModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>🔑 Reset Password for {selectedUser.username}</h3>
            <form onSubmit={handleResetPassword}>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>New Password:</label>
                <input
                  type="password"
                  name="new_password"
                  required
                  minLength={8}
                  placeholder="Minimum 8 characters"
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#ffa726',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowPasswordModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Ban User Modal */}
      {showBanModal && selectedUser && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            background: '#16213e',
            padding: '30px',
            borderRadius: '10px',
            width: '90%',
            maxWidth: '500px',
            border: '2px solid #2a2a4e'
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '20px' }}>🚫 Ban {selectedUser.username}</h3>
            <form onSubmit={handleBanUser}>
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Ban Type:</label>
                <select
                  name="ban_type"
                  required
                  onChange={(e) => {
                    document.getElementById('duration-fields').style.display = 
                      e.target.value === 'temporary' ? 'block' : 'none';
                  }}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    boxSizing: 'border-box'
                  }}
                >
                  <option value="temporary">⏰ Temporary</option>
                  <option value="permanent">🔒 Permanent</option>
                </select>
              </div>
              
              <div id="duration-fields" style={{ marginBottom: '15px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Days:</label>
                    <input
                      type="number"
                      name="duration_days"
                      min="0"
                      defaultValue="0"
                      style={{
                        width: '100%',
                        padding: '10px',
                        background: '#0f1729',
                        border: '2px solid #2a2a4e',
                        borderRadius: '5px',
                        color: '#fff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Hours:</label>
                    <input
                      type="number"
                      name="duration_hours"
                      min="0"
                      defaultValue="0"
                      style={{
                        width: '100%',
                        padding: '10px',
                        background: '#0f1729',
                        border: '2px solid #2a2a4e',
                        borderRadius: '5px',
                        color: '#fff',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>
              </div>
              
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '5px' }}>Reason:</label>
                <textarea
                  name="ban_reason"
                  required
                  rows="3"
                  placeholder="Explain why this user is being banned..."
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                    fontFamily: 'inherit',
                    boxSizing: 'border-box'
                  }}
                />
              </div>
              
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: loading ? '#4a4a5e' : '#dc3545',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  {loading ? 'Banning...' : '🚫 Ban User'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowBanModal(false)}
                  style={{
                    flex: 1,
                    padding: '12px',
                    background: '#667eea',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showUserCharsModal && charsTargetUser && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#16213e', padding: '24px', borderRadius: '10px',
            width: '92%', maxWidth: '720px', maxHeight: '85vh', overflow: 'auto',
            border: '2px solid #2a2a4e',
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '16px' }}>
              Characters — {charsTargetUser.username}
            </h3>
            {userCharsLoading ? (
              <p style={{ color: '#b5b5c3' }}>Loading…</p>
            ) : userCharsError ? (
              <p style={{ color: '#f87171' }}>{userCharsError}</p>
            ) : userCharsList.length === 0 ? (
              <p style={{ color: '#b5b5c3' }}>No characters</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #2a2a4e' }}>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }}>ID</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }}>Name</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }}>Campaign</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }}>Locked</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }}>Suspended</th>
                    <th style={{ textAlign: 'left', padding: '8px', color: '#e94560' }} />
                  </tr>
                </thead>
                <tbody>
                  {userCharsList.map((ch) => (
                    <tr key={ch.id} style={{ borderBottom: '1px solid #2a2a4e' }}>
                      <td style={{ padding: '8px', color: '#b5b5c3' }}>{ch.id}</td>
                      <td style={{ padding: '8px', color: '#fff' }}>{ch.name}</td>
                      <td style={{ padding: '8px', color: '#b5b5c3' }}>{ch.campaign_id}</td>
                      <td style={{ padding: '8px', color: '#b5b5c3' }}>{ch.sheet_locked ? 'Yes' : 'No'}</td>
                      <td style={{ padding: '8px', color: '#b5b5c3' }}>
                        {ch.play_suspended ? (ch.play_suspension_reason_code || 'yes') : '—'}
                      </td>
                      <td style={{ padding: '8px' }}>
                        {ch.play_suspended ? (
                          <button
                            type="button"
                            onClick={() => clearCharacterSuspension(ch.id)}
                            style={{
                              padding: '4px 10px', background: '#28a745', color: '#fff',
                              border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
                            }}
                          >
                            Clear hold
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setSuspendTargetChar(ch);
                              setSuspendReason('pending_downtime');
                              setSuspendMessage('');
                            }}
                            style={{
                              padding: '4px 10px', background: '#dc3545', color: '#fff',
                              border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px',
                            }}
                          >
                            Suspend
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <button
              type="button"
              onClick={() => {
                setShowUserCharsModal(false);
                setCharsTargetUser(null);
                setSuspendTargetChar(null);
              }}
              style={{
                marginTop: '20px', padding: '10px 20px', background: '#667eea',
                color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer',
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {suspendTargetChar && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.9)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1100,
        }}>
          <div style={{
            background: '#16213e', padding: '24px', borderRadius: '10px',
            width: '90%', maxWidth: '440px', border: '2px solid #2a2a4e',
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '16px' }}>
              Suspend play — {suspendTargetChar.name}
            </h3>
            <form onSubmit={submitSuspend}>
              <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '8px' }}>Reason</label>
              <select
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                style={{
                  width: '100%', padding: '10px', marginBottom: '12px',
                  background: '#0f1729', border: '2px solid #2a2a4e', borderRadius: '5px', color: '#fff',
                }}
              >
                <option value="pending_downtime">Pending downtime</option>
                <option value="pending_more_information">Pending more information</option>
                <option value="custom">Custom (use message)</option>
              </select>
              <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '8px' }}>Message to player</label>
              <textarea
                value={suspendMessage}
                onChange={(e) => setSuspendMessage(e.target.value)}
                rows={4}
                style={{
                  width: '100%', padding: '10px', marginBottom: '16px', boxSizing: 'border-box',
                  background: '#0f1729', border: '2px solid #2a2a4e', borderRadius: '5px', color: '#fff',
                }}
                placeholder="Shown when they try to use this character in play."
              />
              <div style={{ display: 'flex', gap: '10px' }}>
                <button type="submit" style={{
                  flex: 1, padding: '12px', background: '#dc3545', color: '#fff',
                  border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold',
                }}
                >
                  Confirm suspend
                </button>
                <button
                  type="button"
                  onClick={() => setSuspendTargetChar(null)}
                  style={{
                    flex: 1, padding: '12px', background: '#667eea', color: '#fff',
                    border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold',
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showDebugModal && debugTargetUser && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#16213e', padding: '24px', borderRadius: '10px',
            width: '94%', maxWidth: '900px', maxHeight: '88vh', overflow: 'auto',
            border: '2px solid #2a2a4e',
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '12px' }}>
              Debug profile — {debugTargetUser.username} (id {debugTargetUser.id})
            </h3>
            {debugLoading ? (
              <p style={{ color: '#b5b5c3' }}>Loading…</p>
            ) : debugPayload ? (
              <pre style={{
                background: '#0f1729', padding: '16px', borderRadius: '8px',
                color: '#c4c4d4', fontSize: '12px', overflow: 'auto', maxHeight: '70vh',
                border: '1px solid #2a2a4e',
              }}
              >
                {JSON.stringify(debugPayload, null, 2)}
              </pre>
            ) : null}
            <button
              type="button"
              onClick={() => {
                setShowDebugModal(false);
                setDebugTargetUser(null);
                setDebugPayload(null);
              }}
              style={{
                marginTop: '16px', padding: '10px 20px', background: '#667eea',
                color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer',
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {membershipModalUser && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#16213e', padding: '24px', borderRadius: '10px',
            width: '90%', maxWidth: '420px', border: '2px solid #2a2a4e',
          }}>
            <h3 style={{ color: '#e94560', marginBottom: '16px' }}>
              Campaign membership — {membershipModalUser.username}
            </h3>
            <div style={{ marginBottom: '16px', fontSize: '13px', color: '#94a3b8' }}>
              <strong style={{ color: '#c4b5fd' }}>This user&apos;s chronicles</strong>
              {membershipTargetChronicles.length === 0 ? (
                <p style={{ margin: '8px 0 0', color: '#64748b' }}>
                  {adminCampaignsLoading ? 'Loading…' : 'None listed (no roster row and not sole creator of an orphan campaign).'}
                </p>
              ) : (
                <ul style={{ margin: '8px 0 0', paddingLeft: '18px', color: '#d1d5db' }}>
                  {membershipTargetChronicles.map((c) => (
                    <li key={`${c.id}-${c.via || 'm'}`}>
                      <strong style={{ color: '#e8e8ef' }}>{c.name || `Campaign ${c.id}`}</strong>
                      {' · '}
                      {c.game_system || '—'} · {c.member_role || 'member'}
                      {c.via === 'created_by_only' ? (
                        <span style={{ color: '#fbbf24' }}> (creator only — use Add below to write roster row)</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <form onSubmit={submitMembershipOverride}>
              <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px' }}>
                Campaign
              </label>
              {adminCampaignsLoading ? (
                <p style={{ color: '#8b8b9f', marginBottom: '12px' }}>Loading campaigns…</p>
              ) : adminCampaignsLoadError ? (
                <p style={{ color: '#f87171', marginBottom: '12px' }}>{adminCampaignsLoadError}</p>
              ) : adminCampaignsList.length === 0 ? (
                <p style={{ color: '#8b8b9f', marginBottom: '12px' }}>
                  No campaigns in the database yet. Create a campaign first.
                </p>
              ) : (
                <select
                  value={membershipCampaignId}
                  onChange={(e) => setMembershipCampaignId(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '10px',
                    marginBottom: '12px',
                    boxSizing: 'border-box',
                    background: '#0f1729',
                    border: '2px solid #2a2a4e',
                    borderRadius: '5px',
                    color: '#fff',
                  }}
                >
                  <option value="">— Select campaign —</option>
                  {adminCampaignsList.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.name || `Campaign ${c.id}`} · {c.game_system || '—'} (id {c.id})
                    </option>
                  ))}
                </select>
              )}
              {adminCampaignsFromFallback && adminCampaignsList.length > 0 ? (
                <p style={{ fontSize: '12px', color: '#fbbf24', marginBottom: '10px', lineHeight: 1.4 }}>
                  Full admin list unavailable (old backend?). Showing <strong>your</strong> chronicles only.
                  Restart the backend so <code style={{ fontSize: '11px' }}>GET /api/admin/campaigns</code> loads.
                </p>
              ) : null}
              <label style={{ display: 'block', color: '#b5b5c3', marginBottom: '6px' }}>Action</label>
              <select
                value={membershipAction}
                onChange={(e) => setMembershipAction(e.target.value)}
                style={{
                  width: '100%', padding: '10px', marginBottom: '16px',
                  background: '#0f1729', border: '2px solid #2a2a4e', borderRadius: '5px', color: '#fff',
                }}
              >
                <option value="add">Add to campaign_players</option>
                <option value="remove">Remove from campaign_players</option>
              </select>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={
                    adminCampaignsLoading ||
                    !!adminCampaignsLoadError ||
                    adminCampaignsList.length === 0
                  }
                  style={{
                    flex: 1,
                    padding: '12px',
                    background:
                      adminCampaignsLoading ||
                      adminCampaignsLoadError ||
                      adminCampaignsList.length === 0
                        ? '#3d5a40'
                        : '#28a745',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    cursor:
                      adminCampaignsLoading ||
                      adminCampaignsLoadError ||
                      adminCampaignsList.length === 0
                        ? 'not-allowed'
                        : 'pointer',
                    fontWeight: 'bold',
                  }}
                >
                  Apply
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMembershipModalUser(null);
                    setMembershipCampaignId('');
                    setMembershipTargetChronicles([]);
                    setAdminCampaignsFromFallback(false);
                  }}
                  style={{
                    flex: 1, padding: '12px', background: '#dc3545', color: '#fff',
                    border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold',
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          padding: '15px 25px',
          background: 'rgba(233, 69, 96, 0.9)',
          border: '2px solid #e94560',
          borderRadius: '8px',
          color: 'white',
          fontWeight: '500',
          zIndex: 2000
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Unban Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showUnbanConfirm}
        title="⚠️ Unban User?"
        message={`Are you sure you want to unban this user?\n\nThey will immediately regain full access to the system.`}
        onConfirm={confirmUnban}
        onCancel={() => {
          setShowUnbanConfirm(false);
          setUserToUnban(null);
        }}
        confirmText="Yes, Unban"
        cancelText="Cancel"
      />

      <ConfirmDialog
        isOpen={showDeleteAccountConfirm}
        title="⚠️ Delete account permanently?"
        message={
          userToDeleteAccount
            ? `Delete "${userToDeleteAccount.username}" and ALL of their characters?\n\n` +
              'Location in-character chat lines will stay in the chronicle, but will show as posted by the system archive account (message text is unchanged). ' +
              'Dice rolls they made may also be reassigned to that archive account. ' +
              'If they created any campaigns, ownership will be transferred to you.'
            : ''
        }
        onConfirm={confirmDeleteAccount}
        onCancel={() => {
          setShowDeleteAccountConfirm(false);
          setUserToDeleteAccount(null);
        }}
        confirmText={deleteAccountLoading ? 'Working…' : 'Yes, delete account'}
        cancelText="Cancel"
      />

      {/* Toast Notifications */}
      <ToastContainer />
    </div>
  );
}

export default AdminPage;

