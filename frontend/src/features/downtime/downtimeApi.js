/**
 * Downtime routes (backend/routes/downtime.py). Each takes the useApi() function and resolves to
 * its { ok, status, data }; refusals carry data.code (see downtimeErrors.js).
 */
const base = (cid) => `/campaigns/${cid}/downtime`;

export const downtimeApi = {
  // Everyone: the player view, plus is_storyteller.
  view: (api, cid) => api(base(cid)),
  createProject: (api, cid, { title, goal, parent_id }) =>
    api(`${base(cid)}/projects`, { method: 'POST', body: { title, goal, parent_id: parent_id || null } }),
  declarePhase: (api, cid, projectId, action) =>
    api(`${base(cid)}/projects/${projectId}/phases`, { method: 'POST', body: { action } }),
  rollPhase: (api, cid, phaseId, body) => api(`${base(cid)}/phases/${phaseId}/roll`, { method: 'POST', body }),

  // Storyteller.
  rounds: (api, cid) => api(`${base(cid)}/rounds`),
  openRound: (api, cid, title) => api(`${base(cid)}/rounds`, { method: 'POST', body: { title } }),
  closeRound: (api, cid, roundId) => api(`${base(cid)}/rounds/${roundId}/resolve`, { method: 'POST', body: {} }),
  reopenRound: (api, cid, roundId) => api(`${base(cid)}/rounds/${roundId}/reopen`, { method: 'POST', body: {} }),
  releaseRound: (api, cid, roundId, force = false) =>
    api(`${base(cid)}/rounds/${roundId}/release`, { method: 'POST', body: { force } }),
  inbox: (api, cid, { roundId, unresolved } = {}) => {
    const q = [];
    if (roundId) q.push(`round_id=${roundId}`);
    if (unresolved) q.push('unresolved=1');
    return api(`${base(cid)}/inbox${q.length ? `?${q.join('&')}` : ''}`);
  },
  setupPhase: (api, cid, phaseId, body) => api(`${base(cid)}/phases/${phaseId}/setup`, { method: 'PUT', body }),
  resolvePhase: (api, cid, phaseId, body) => api(`${base(cid)}/phases/${phaseId}/resolve`, { method: 'POST', body }),
  setProjectStatus: (api, cid, projectId, status) =>
    api(`${base(cid)}/projects/${projectId}`, { method: 'PATCH', body: { status } }),
  addIndicator: (api, cid, projectId, body) =>
    api(`${base(cid)}/projects/${projectId}/indicators`, { method: 'POST', body }),
  editIndicator: (api, cid, id, body) => api(`${base(cid)}/indicators/${id}`, { method: 'PATCH', body }),
  deleteIndicator: (api, cid, id) => api(`${base(cid)}/indicators/${id}`, { method: 'DELETE' }),
  variables: (api, cid) => api(`${base(cid)}/variables`),
  addVariable: (api, cid, body) => api(`${base(cid)}/variables`, { method: 'POST', body }),
  editVariable: (api, cid, id, body) => api(`${base(cid)}/variables/${id}`, { method: 'PATCH', body }),
  deleteVariable: (api, cid, id) => api(`${base(cid)}/variables/${id}`, { method: 'DELETE' }),
  changes: (api, cid) => api(`${base(cid)}/changes`),
};
