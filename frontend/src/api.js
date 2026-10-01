/**
 * API client for the Dataset Request Desk backend.
 * Handles auth token injection and error normalization.
 */

const API_BASE = '/api';

function getToken() {
  return localStorage.getItem('token');
}

async function request(method, path, { body, isFormData } = {}) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (body && !isFormData) {
    headers['Content-Type'] = 'application/json';
  }

  const opts = { method, headers };
  if (body) {
    opts.body = isFormData ? body : JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, opts);

  if (res.status === 204) return null;

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message = data?.detail || `Request failed (${res.status})`;
    throw new Error(message);
  }

  return data;
}

const api = {
  // Auth
  login: (username, password) =>
    request('POST', '/auth/login', { body: { username, password } }),

  // Users
  getMe: () => request('GET', '/users/me'),
  listUsers: () => request('GET', '/users'),
  createUser: (data) => request('POST', '/users', { body: data }),
  updateUser: (id, data) => request('PATCH', `/users/${id}`, { body: data }),

  // Episodes
  listEpisodes: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.task_name) qs.set('task_name', params.task_name);
    if (params.quality) qs.set('quality', params.quality);
    if (params.available_only) qs.set('available_only', 'true');
    if (params.limit) qs.set('limit', params.limit);
    if (params.offset) qs.set('offset', params.offset);
    const query = qs.toString();
    return request('GET', `/episodes${query ? '?' + query : ''}`);
  },
  listTaskNames: () => request('GET', '/episodes/task-names'),
  importCSV: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('POST', '/episodes/import', { body: formData, isFormData: true });
  },

  // Requests
  listRequests: (status) => {
    const qs = status ? `?status=${status}` : '';
    return request('GET', `/requests${qs}`);
  },
  getRequest: (id) => request('GET', `/requests/${id}`),
  createRequest: (data) => request('POST', '/requests', { body: data }),
  transitionStatus: (id, status, notes) =>
    request('PATCH', `/requests/${id}/status`, { body: { status, notes } }),
  getHistory: (id) => request('GET', `/requests/${id}/history`),

  // Assignments
  listAssignments: (requestId) =>
    request('GET', `/requests/${requestId}/assignments`),
  assignEpisodes: (requestId, episodeIds) =>
    request('POST', `/requests/${requestId}/assignments`, {
      body: { episode_ids: episodeIds },
    }),
  removeAssignment: (requestId, assignmentId) =>
    request('DELETE', `/requests/${requestId}/assignments/${assignmentId}`),

  // Analytics
  getAnalytics: (startDate, endDate) =>
    request('GET', `/analytics?start_date=${startDate}&end_date=${endDate}`),

  // Health
  health: () => request('GET', '/health'),
};

export default api;
