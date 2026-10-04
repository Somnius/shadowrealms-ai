// Admin Laya labelling + evaluation (backend/routes/laya_eval.py). Kept out of utils/api.js on purpose.
import { authFetch } from '../../app/http';

const BASE = '/api/admin/laya';

const auth = (token, json) => ({
  Authorization: `Bearer ${token}`,
  ...(json ? { 'Content-Type': 'application/json' } : {}),
});

export const layaApi = {
  listMessages: (token, { status, campaignId, language, page, perPage }) => {
    const q = new URLSearchParams();
    if (status) q.set('status', status);
    if (campaignId) q.set('campaign_id', String(campaignId));
    if (language) q.set('language', language);
    if (page) q.set('page', String(page));
    if (perPage) q.set('per_page', String(perPage));
    return authFetch(`${BASE}/messages?${q.toString()}`, { headers: auth(token) });
  },

  setLabel: (token, messageId, label) =>
    authFetch(`${BASE}/labels/${encodeURIComponent(messageId)}`, {
      method: 'PUT',
      headers: auth(token, true),
      body: JSON.stringify(label),
    }),

  clearLabel: (token, messageId) =>
    authFetch(`${BASE}/labels/${encodeURIComponent(messageId)}`, { method: 'DELETE', headers: auth(token) }),

  runEvaluation: (token) => authFetch(`${BASE}/evaluate`, { method: 'POST', headers: auth(token) }),

  getReport: (token, id) => authFetch(`${BASE}/report${id ? `?id=${encodeURIComponent(id)}` : ''}`, { headers: auth(token) }),
};

export default layaApi;
