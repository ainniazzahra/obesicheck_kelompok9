import { assertPrediction, assertEvaluation, assertStatus, assertHistory, assertUser, assertLogin } from '../contract.js';

const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

// Token sesi disimpan di sessionStorage (hilang saat tab ditutup). Akses storage dibungkus try/catch.
const KEY = 'obesicheck_token';
let token = null;
try { token = sessionStorage.getItem(KEY); } catch { /* storage tidak tersedia */ }
export const session = {
  get: () => token,
  set(t) { token = t; try { if (t) sessionStorage.setItem(KEY, t); else sessionStorage.removeItem(KEY); } catch { /* abaikan */ } },
};
let onUnauthorized = () => {};
export const setUnauthorizedHandler = fn => { onUnauthorized = fn; };

function formatDetail(detail) {
  if (Array.isArray(detail)) {  // galat validasi FastAPI/Pydantic (422)
    return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
  }
  return typeof detail === 'string' ? detail : 'Permintaan gagal';
}

async function request(path, options = {}) {
  let res;
  try {
    const headers = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
    res = await fetch(`${BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('Tidak dapat terhubung ke server. Pastikan backend FastAPI berjalan di ' + BASE);
  }
  const data = await res.json().catch(() => ({ detail: 'Respons server tidak dapat dibaca' }));
  if (res.status === 401 && token && !path.startsWith('/auth/login')) {  // sesi kedaluwarsa/dicabut: bersihkan dan beri tahu aplikasi
    session.set(null); onUnauthorized();
  }
  if (!res.ok) throw new Error(formatDetail(data.detail));
  return data;
}

export const api = {
  health: () => request('/health'),
  register: p => request('/auth/register', { method: 'POST', body: JSON.stringify(p) }).then(assertUser),
  login: p => request('/auth/login', { method: 'POST', body: JSON.stringify(p) }).then(assertLogin).then(r => { session.set(r.access_token); return r; }),
  me: () => request('/auth/me').then(assertUser),
  logout: async () => { try { await request('/auth/logout', { method: 'POST' }); } finally { session.set(null); } },
  status: () => request('/model/status').then(assertStatus),
  evaluation: () => request('/evaluation').then(assertEvaluation),
  predict: payload => request('/predictions', { method: 'POST', body: JSON.stringify(payload) }).then(assertPrediction),
  history: () => request('/history').then(assertHistory),
  deleteHistory: id => request(`/history/${id}`, { method: 'DELETE' }),
};
