import React from 'react';
import { optionLabels } from '../constants.js';

// Didefinisikan di luar App agar input tidak di-remount (kehilangan fokus) pada setiap ketikan.
export default function Field({ label, k, value, onChange, opts, type = 'select', min, max, step, required = true, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {type === 'number' ? (
        <input type="number" inputMode="decimal" value={value} min={min} max={max} step={step || 1} required={required}
               onChange={e => onChange(k, e.target.value)} />
      ) : (
        <select value={value} onChange={e => onChange(k, typeof opts[0] === 'number' ? Number(e.target.value) : e.target.value)}>
          {opts.map(o => <option key={o} value={o}>{typeof o === 'string' ? (optionLabels[o] || o) : o}</option>)}
        </select>
      )}
      {hint && <small className="helper">{hint}</small>}
    </label>
  );
}
