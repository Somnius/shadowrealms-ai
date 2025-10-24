// API utility functions
const API_URL = '/api';

export const api = {
  // Auth
  login: (credentials) => 
    fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials)
    }),
  
  register: (userData) =>
    fetch(`${API_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData)
    }),
  
  // Campaigns
  getCampaigns: (token) =>
    fetch(`${API_URL}/campaigns/`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  createCampaign: (token, campaignData) =>
    fetch(`${API_URL}/campaigns`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(campaignData)
    }),
  
  // AI Chat
  sendMessage: (token, messageData) =>
    fetch(`${API_URL}/ai/chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(messageData)
    }),
  
  // Admin
  getAllUsers: (token) =>
    fetch(`${API_URL}/admin/users`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  updateUser: (token, userId, userData) =>
    fetch(`${API_URL}/admin/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(userData)
    }),
  
  resetUserPassword: (token, userId, password) =>
    fetch(`${API_URL}/admin/users/${userId}/reset-password`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ new_password: password })
    }),
  
  banUser: (token, userId, banData) =>
    fetch(`${API_URL}/admin/users/${userId}/ban`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(banData)
    }),
  
  unbanUser: (token, userId) =>
    fetch(`${API_URL}/admin/users/${userId}/unban`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  getUserCharacters: (token, userId) =>
    fetch(`${API_URL}/admin/users/${userId}/characters`, {
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  convertCharacterToNPC: (token, characterId) =>
    fetch(`${API_URL}/admin/characters/${characterId}/convert-to-npc`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` }
    }),
  
  killCharacter: (token, characterId, deathType) =>
    fetch(`${API_URL}/admin/characters/${characterId}/kill`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ death_type: deathType })
    }),
  
  getModerationLog: (token, limit = 50) =>
    fetch(`${API_URL}/admin/moderation-log?limit=${limit}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
};

