// Nama field harus identik dengan skema API (backend/app/schemas/prediction.py) dan fitur training.
export const labelMap = {
  Insufficient_Weight: 'Berat badan kurang', Normal_Weight: 'Berat badan normal',
  Overweight_Level_I: 'Kelebihan berat badan tingkat I', Overweight_Level_II: 'Kelebihan berat badan tingkat II',
  Obesity_Type_I: 'Obesitas tipe I', Obesity_Type_II: 'Obesitas tipe II', Obesity_Type_III: 'Obesitas tipe III',
};
export const optionLabels = {
  Female: 'Perempuan', Male: 'Laki-laki', yes: 'Ya', no: 'Tidak', Sometimes: 'Kadang-kadang', Frequently: 'Sering', Always: 'Selalu',
  Public_Transportation: 'Transportasi umum', Automobile: 'Mobil', Walking: 'Berjalan kaki', Motorbike: 'Sepeda motor', Bike: 'Sepeda',
};
export const initialForm = {
  Gender: 'Female', Age: '21', family_history_with_overweight: 'yes', FAVC: 'yes', FCVC: 2, NCP: 3, CAEC: 'Sometimes',
  SMOKE: 'no', CH2O: 2, SCC: 'no', FAF: 1, TUE: 1, CALC: 'Sometimes', MTRANS: 'Public_Transportation', Height: '', Weight: '',
};
export const numericLimits = { Age: [14, 100, 'Usia'], Height: [1.2, 2.3, 'Tinggi badan'], Weight: [25, 300, 'Berat badan'] };

export function validateForm(f) {
  const errors = [];
  for (const [k, [lo, hi, name]] of Object.entries(numericLimits)) {
    const raw = String(f[k]).trim();
    if (raw === '') { if (k === 'Age') errors.push('Usia wajib diisi.'); continue; }  // Height/Weight opsional
    const v = Number(raw);
    if (!Number.isFinite(v) || v < lo || v > hi) errors.push(`${name} harus berada pada rentang ${lo}–${hi}.`);
  }
  const hasH = String(f.Height).trim() !== '', hasW = String(f.Weight).trim() !== '';
  if (hasH !== hasW) errors.push('Isi tinggi dan berat badan bersamaan, atau kosongkan keduanya.');
  return errors;
}

export function buildPayload(f) {
  const p = { ...f };
  for (const k of ['Age', 'FCVC', 'NCP', 'CH2O', 'FAF', 'TUE']) p[k] = Number(f[k]);
  for (const k of ['Height', 'Weight']) { if (String(f[k]).trim() === '') delete p[k]; else p[k] = Number(f[k]); }
  return p;
}
