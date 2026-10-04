// API utility functions (fetch with the session rules of app/http.js: refresh on expiry, etc.)
import { authFetch } from '../app/http';

const API_URL = '/api';

export const api = {
  // Auth
  login: (credentials) => 
    authFetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials)
    }),
  
  register: (userData) =>
    authFetch(`${API_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    }),
  
  // Campaigns
  getCampaigns: (token) =>
    authFetch(`${API_URL}/campaigns/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  createCampaign: (token, campaignData) =>
    authFetch(`${API_URL}/campaigns`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(campaignData)
    }),

  discoverCampaigns: (token) =>
    authFetch(`${API_URL}/campaigns/discover`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  joinCampaign: (token, campaignId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/join`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    }),

  detachCampaign: (token, campaignId, payload = {}) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/detach`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }),

  addCampaignMember: (token, campaignId, userId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/members`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ user_id: userId }),
    }),

  setMyPlayingCharacter: (token, campaignId, characterId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/my-playing-character`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ character_id: characterId }),
    }),

  setPlayerPlayingCharacter: (token, campaignId, targetUserId, characterId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/players/${targetUserId}/playing-character`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ character_id: characterId }),
    }),

  updateCampaign: (token, campaignId, payload) =>
    authFetch(`${API_URL}/campaigns/${campaignId}`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }),

  getCampaign: (token, campaignId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  getCampaignStats: (token, campaignId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}/stats`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  deleteCampaign: (token, campaignId) =>
    authFetch(`${API_URL}/campaigns/${campaignId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    }),
  
  // AI Chat
  sendMessage: (token, messageData) =>
    authFetch(`${API_URL}/ai/chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(messageData)
    }),
  
  // Admin
  getAllUsers: (token) =>
    authFetch(`${API_URL}/admin/users`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),

  /** All campaigns (admin picker — not scoped to caller's membership). */
  listAdminCampaigns: (token) =>
    authFetch(`${API_URL}/admin/campaigns`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  /** Chronicles a user is in (roster + campaigns they created without a roster row). */
  getAdminUserCampaignMemberships: (token, userId) =>
    authFetch(`${API_URL}/admin/users/${userId}/campaign-memberships`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  
  updateUser: (token, userId, userData) =>
    authFetch(`${API_URL}/admin/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(userData)
    }),
  
  resetUserPassword: (token, userId, password) =>
    authFetch(`${API_URL}/admin/users/${userId}/reset-password`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ new_password: password })
    }),
  
  banUser: (token, userId, banData) =>
    authFetch(`${API_URL}/admin/users/${userId}/ban`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(banData)
    }),
  
  unbanUser: (token, userId) =>
    authFetch(`${API_URL}/admin/users/${userId}/unban`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }),

  /** Remove user + all their characters; location chat rows kept (reassigned to archive account). */
  deleteUserAccountPreserveChats: (token, userId) =>
    authFetch(`${API_URL}/admin/users/${userId}/delete-account`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ confirm: true }),
    }),
  
  getUserCharacters: (token, userId) =>
    authFetch(`${API_URL}/admin/users/${userId}/characters`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),

  getUserDebug: (token, userId) =>
    authFetch(`${API_URL}/admin/users/${userId}/debug`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  patchCharacterPlayStatus: (token, characterId, payload) =>
    authFetch(`${API_URL}/admin/characters/${characterId}/play-status`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }),

  adminUserCampaignMembership: (token, userId, campaignId, action) =>
    authFetch(`${API_URL}/admin/users/${userId}/campaigns/${campaignId}/membership`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ action }),
    }),
  
  convertCharacterToNPC: (token, characterId) =>
    authFetch(`${API_URL}/admin/characters/${characterId}/convert-to-npc`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  killCharacter: (token, characterId, deathType) =>
    authFetch(`${API_URL}/admin/characters/${characterId}/kill`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ death_type: deathType })
    }),
  
  getModerationLog: (token, limit = 50) =>
    authFetch(`${API_URL}/admin/moderation-log?limit=${limit}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),

  listInvites: (token) =>
    authFetch(`${API_URL}/admin/invites`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),

  createInvite: (token, payload) =>
    authFetch(`${API_URL}/admin/invites`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }),

  listDowntimeRequests: (token, status) => {
    const q = status ? `?status=${encodeURIComponent(status)}` : '';
    return authFetch(`${API_URL}/admin/downtime-requests${q}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  },

  resolveDowntimeRequest: (token, requestId, payload) =>
    authFetch(`${API_URL}/admin/downtime-requests/${requestId}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }),

  getAiSettings: (token) =>
    authFetch(`${API_URL}/admin/ai-settings`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  putAiSettings: (token, payload) =>
    authFetch(`${API_URL}/admin/ai-settings`, {
      method: 'PUT',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }),

  listLmStudioModels: (token) =>
    authFetch(`${API_URL}/admin/lm-studio/models`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  // Phase 2: AI roles/providers, write-only API keys (returned masked), classifier, embeddings
  getAiProviders: (token) =>
    authFetch(`${API_URL}/admin/ai-providers`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  putAiProviders: (token, payload) =>
    authFetch(`${API_URL}/admin/ai-providers`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  testAiProvider: (token, provider, model) =>
    authFetch(`${API_URL}/admin/ai-providers/test`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model }),
    }),

  testClassifier: (token, provider, text) =>
    authFetch(`${API_URL}/admin/classifier/test`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, text }),
    }),

  getEmbeddings: (token) =>
    authFetch(`${API_URL}/admin/embeddings`, {
      headers: { Authorization: `Bearer ${token}` },
    }),

  reembed: (token, force = false) =>
    authFetch(`${API_URL}/admin/embeddings/reembed`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ force }),
    }),
};

