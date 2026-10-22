import test from 'node:test';
import assert from 'node:assert/strict';
import { assertPrediction, assertEvaluation, assertHistory, assertStatus } from '../src/contract.js';

const ok = () => ({ predicted_class: 'Normal_Weight', probabilities: { Normal_Weight: 0.7, Obesity_Type_I: 0.3 }, created_at: '2026-10-20T00:00:00+00:00',
  recommendations: [{ code: 'c', topic: 't', title: 'x', reason: 'r', steps: ['a'], source: 's', source_url: 'https://who.int' }] });

test('respons prediksi valid diterima', () => assert.doesNotThrow(() => assertPrediction(ok())));
for (const [name, mut] of Object.entries({
  'objek kosong': () => ({}), 'tanpa probabilities': r => { delete r.probabilities; return r; },
  'kelas tidak ada di probabilities': r => { r.predicted_class = 'Alien'; return r; },
  'probabilitas > 1': r => { r.probabilities.Normal_Weight = 1.7; return r; },
  'jumlah probabilitas bukan 1': r => { r.probabilities.Obesity_Type_I = 0.9; return r; },
  'steps hilang': r => { delete r.recommendations[0].steps; return r; },
  'source_url bukan https': r => { r.recommendations[0].source_url = 'javascript:alert(1)'; return r; },
  'recommendations bukan array': r => { r.recommendations = null; return r; },
  'created_at tidak valid': r => { r.created_at = 'bukan tanggal'; return r; },
})) test(`respons prediksi ditolak: ${name}`, () => assert.throws(() => assertPrediction(mut(ok())), /tidak sesuai kontrak/));

test('evaluasi: tidak tersedia diterima, matriks tidak persegi ditolak', () => {
  assert.doesNotThrow(() => assertEvaluation({ available: false, message: 'x' }));
  assert.throws(() => assertEvaluation({ available: true, labels: ['a', 'b'], confusion_matrix: [[1, 2]], classification_report: {}, accuracy: 1, macro_precision: 1, macro_recall: 1, macro_f1: 1 }));
});
test('status & history', () => {
  assert.doesNotThrow(() => assertStatus({ trained: false }));
  assert.throws(() => assertStatus({}));
  assert.doesNotThrow(() => assertHistory([]));
  assert.throws(() => assertHistory({ a: 1 }));
});

import { assertLogin, assertUser } from '../src/contract.js';
const user = { id: 1, username: 'ani', email: 'ani@x.id', created_at: '2026-10-20T00:00:00+00:00' };
test('auth: login valid diterima; kontrak rusak ditolak', () => {
  assert.doesNotThrow(() => assertLogin({ user, access_token: 'a.b.c', token_type: 'bearer' }));
  assert.throws(() => assertLogin({ user, access_token: 'bukan-jwt', token_type: 'bearer' }), /tidak sesuai kontrak/);
  assert.throws(() => assertLogin({ user, token_type: 'bearer' }), /tidak sesuai kontrak/);
  assert.throws(() => assertLogin({ access_token: 'a.b.c', token_type: 'bearer' }), /tidak sesuai kontrak/);
  assert.throws(() => assertUser({ user: { ...user, id: '1' } }), /tidak sesuai kontrak/);
  assert.throws(() => assertUser(null), /tidak sesuai kontrak/);
});
