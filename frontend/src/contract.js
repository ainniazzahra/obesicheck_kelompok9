// Validasi kontrak respons API di sisi klien: respons yang tidak sesuai ditolak, tidak ditampilkan sebagai hasil.
const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const bad = what => { throw new Error(`Respons server tidak sesuai kontrak (${what}). Hasil tidak ditampilkan.`); };

export function assertPrediction(r) {
  if (!isObj(r)) bad('bukan objek');
  if (typeof r.predicted_class !== 'string' || !r.predicted_class) bad('predicted_class');
  if (!isObj(r.probabilities)) bad('probabilities');
  const vals = Object.values(r.probabilities);
  if (!vals.length || !vals.every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1)) bad('nilai probabilitas');
  if (!(r.predicted_class in r.probabilities)) bad('predicted_class tidak ada di probabilities');
  if (Math.abs(vals.reduce((a, b) => a + b, 0) - 1) > 0.01) bad('jumlah probabilitas bukan 1');
  if (typeof r.created_at !== 'string' || Number.isNaN(Date.parse(r.created_at))) bad('created_at');
  if (!Array.isArray(r.recommendations)) bad('recommendations');
  for (const x of r.recommendations) {
    if (!isObj(x) || ![x.code, x.topic, x.title, x.reason, x.source, x.source_url].every(t => typeof t === 'string') ||
        !Array.isArray(x.steps) || !x.steps.every(t => typeof t === 'string')) bad('item recommendations');
    if (!/^https:\/\//.test(x.source_url)) bad('source_url');
  }
  return r;
}

export function assertEvaluation(r) {
  if (!isObj(r) || typeof r.available !== 'boolean') bad('evaluation.available');
  if (r.available) {
    const n = Array.isArray(r.labels) ? r.labels.length : -1;
    if (n < 2 || !Array.isArray(r.confusion_matrix) || r.confusion_matrix.length !== n || !r.confusion_matrix.every(row => Array.isArray(row) && row.length === n)) bad('confusion_matrix');
    if (!isObj(r.classification_report) || !r.labels.every(l => isObj(r.classification_report[l]))) bad('classification_report');
    if (!['accuracy', 'macro_precision', 'macro_recall', 'macro_f1'].every(k => typeof r[k] === 'number')) bad('metrik');
  }
  return r;
}

export function assertStatus(r) {
  if (!isObj(r) || typeof r.trained !== 'boolean') bad('model/status');
  return r;
}

export function assertHistory(r) {
  if (!Array.isArray(r) || !r.every(h => isObj(h) && Number.isInteger(h.id) && typeof h.predicted_class === 'string' && typeof h.created_at === 'string')) bad('history');
  return r;
}

export function assertUser(r) {
  const u = r && r.user;
  if (!isObj(u) || !Number.isInteger(u.id) || typeof u.username !== 'string' || typeof u.email !== 'string' || typeof u.created_at !== 'string') bad('user');
  return r;
}

export function assertLogin(r) {
  assertUser(r);
  if (typeof r.access_token !== 'string' || r.access_token.split('.').length !== 3 || String(r.token_type).toLowerCase() !== 'bearer') bad('token');
  return r;
}
