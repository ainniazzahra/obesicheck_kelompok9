import React, { useEffect, useState } from 'react';
import { Activity, BookOpen, ChartNoAxesCombined, ClipboardList, HeartPulse, House, History, UserRound, ShieldCheck,
         ArrowRight, CheckCircle2, AlertCircle, ExternalLink, Trash2, LogIn, LogOut } from 'lucide-react';
import { api, session, setUnauthorizedHandler } from './services/api.js';
import { labelMap, initialForm, validateForm, buildPayload } from './constants.js';
import Field from './components/Field.jsx';
import { Feature, Stat } from './components/Cards.jsx';
import AuthPage from './components/AuthPage.jsx';

const nav = [['Beranda', House], ['Dashboard', ChartNoAxesCombined], ['Prediksi Risiko', HeartPulse], ['Evaluasi Model', ChartNoAxesCombined], ['Riwayat', History], ['Profil', UserRound]];
const pct = v => (typeof v === 'number' ? (v * 100).toFixed(1) + '%' : '-');
const PROTECTED = ['Prediksi Risiko', 'Hasil Prediksi', 'Riwayat', 'Profil'];  // memerlukan login
const cmd = 'python ml/src/train.py --time-limit 600';

export default function App() {
  const [page, setPage] = useState('Beranda');
  const [model, setModel] = useState(null);
  const [evalData, setEvalData] = useState(null);
  const [result, setResult] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState([]);
  const [edu, setEdu] = useState(false);

  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(!session.get());
  const [authNotice, setAuthNotice] = useState('');

  // Semua data milik akun dibersihkan saat keluar/sesi berakhir agar tidak terlihat oleh pengguna berikutnya.
  const resetPrivate = () => { setResult(null); setHistory([]); setForm(initialForm); setEdu(false); setErrors([]); };
  const loadHistory = () => api.history().then(setHistory).catch(() => setHistory([]));
  const refresh = () => {
    api.status().then(setModel).catch(e => setModel({ trained: false, message: e.message }));
    api.evaluation().then(setEvalData).catch(e => setEvalData({ available: false, message: e.message }));
    if (session.get()) loadHistory();
  };

  useEffect(() => {
    setUnauthorizedHandler(() => { resetPrivate(); setUser(null); setAuthNotice('Sesi Anda berakhir atau tidak valid. Silakan masuk kembali.'); setPage(p => (PROTECTED.includes(p) ? p : 'Masuk')); });
    api.status().then(setModel).catch(e => setModel({ trained: false, message: e.message }));
    api.evaluation().then(setEvalData).catch(e => setEvalData({ available: false, message: e.message }));
    if (session.get()) {
      api.me().then(r => { setUser(r.user); loadHistory(); }).catch(() => { session.set(null); }).finally(() => setAuthReady(true));
    }
  }, []);

  const view = !user && PROTECTED.includes(page) ? 'Masuk' : page;  // halaman privat tanpa login -> formulir masuk
  const onLoggedIn = u => { setUser(u); setAuthNotice(''); loadHistory(); if (page === 'Masuk') setPage('Prediksi Risiko'); };
  const logout = async () => {
    try { await api.logout(); } catch { /* sesi lokal tetap dibersihkan */ }
    resetPrivate(); setUser(null); setAuthNotice(''); setPage('Beranda');
  };

  const change = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const submit = async e => {
    e.preventDefault();
    const problems = validateForm(form);
    setErrors(problems);
    if (problems.length) return;
    setBusy(true); setEdu(false);
    try {
      const r = await api.predict(buildPayload(form));
      setResult(r); setPage('Hasil Prediksi');
      api.history().then(setHistory).catch(() => {});
    } catch (err) { setErrors([err.message]); } finally { setBusy(false); }
  };

  const f = (k, label, extra = {}) => <Field k={k} label={label} value={form[k]} onChange={change} {...extra} />;
  const probs = result ? Object.entries(result.probabilities || {}).sort((a, b) => b[1] - a[1]) : [];

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-icon"><HeartPulse size={24} /></div><div><b>ObesiCheck</b><small>HEALTH INSIGHT PLATFORM</small></div></div>
        <div className="nav-label">MENU UTAMA</div>
        {nav.map(([n, I]) => <button key={n} aria-label={n} title={n} aria-current={view === n ? 'page' : undefined} className={`nav-item ${view === n ? 'active' : ''}`} onClick={() => { setPage(n); setErrors([]); setAuthNotice(!user && PROTECTED.includes(n) ? 'Masuk atau daftar untuk menggunakan fitur ini.' : ''); }}><I size={18} /><span>{n}</span></button>)}
        {!user && <button className="nav-item" aria-label="Masuk" title="Masuk" onClick={() => { setPage('Masuk'); setAuthNotice(''); }}><LogIn size={18} /><span>Masuk / Daftar</span></button>}
        <div className="side-note"><ShieldCheck size={18} /><div><b>Privasi & edukasi</b><p>Hasil bersifat informatif, bukan diagnosis medis.</p></div></div>
        {user && <div className="user-chip"><small>Masuk sebagai</small><b title={user.email}>{user.username}</b><button className="btn secondary" onClick={logout}><LogOut size={15} /> Keluar</button></div>}
        <div className="side-footer">ObesiCheck · Versi {model?.model_version ? 'model ' + model.model_version : 'pengembangan'}</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div><span className="eyebrow">SISTEM ESTIMASI BERBASIS DATA</span><h1>{view}</h1></div>
          <div className="status-pill"><span className={`dot ${model?.trained ? 'on' : ''}`}></span>{model?.trained ? 'Model tersedia' : 'Model belum tersedia'}</div>
        </header>

        {view === 'Masuk' && (authReady ? <AuthPage notice={authNotice} onLoggedIn={onLoggedIn} /> : <div className="empty"><p>Memeriksa sesi...</p></div>)}

        {view === 'Beranda' && <>
          <section className="hero">
            <div className="hero-copy"><span className="hero-kicker">KENALI POLA KESEHATANMU</span><h2>Langkah kecil untuk<br />memahami pola hidup.</h2>
              <p>Kenali kategori estimasi berdasarkan kebiasaan makan dan kondisi fisik, lalu pelajari langkah gaya hidup yang relevan untuk dicoba.</p>
              <button className="btn light" onClick={() => setPage('Prediksi Risiko')}>Mulai estimasi <ArrowRight size={17} /></button></div>
            <div className="hero-art"><div className="orb"><HeartPulse size={78} /></div><div className="float-card"><CheckCircle2 size={18} /><span>Insight yang mudah dipahami</span></div></div>
          </section>
          <div className="section-heading"><div><h2>Dirancang untuk membantu memahami</h2><p>Fokus pada informasi yang jelas dan dapat ditindaklanjuti.</p></div></div>
          <div className="feature-grid">
            <Feature icon={<Activity />} title="Estimasi berbasis data" desc="Model AutoGluon Tabular memperkirakan kategori dari kebiasaan hidup (tanpa tinggi/berat badan) sesuai dataset." />
            <Feature icon={<BookOpen />} title="Edukasi berbasis aturan" desc="Materi dipilih oleh aturan terdokumentasi dari kebiasaan yang Anda laporkan; bukan keluaran model ML." />
            <Feature icon={<ShieldCheck />} title="Transparan dan informatif" desc="Metrik evaluasi, leaderboard, dan sumber tepercaya ditampilkan apa adanya." />
          </div>
          <div className="notice"><AlertCircle size={20} /><p>ObesiCheck merupakan alat edukasi dan estimasi berbasis dataset, bukan alat diagnosis atau pengganti konsultasi tenaga kesehatan.</p></div>
        </>}

        {view === 'Dashboard' && <>
          <div className="section-heading"><div><h2>Ringkasan sistem</h2><p>Informasi berasal dari artefak hasil training; metrik hanya tampil setelah training dijalankan.</p></div></div>
          <div className="stats-grid">
            <Stat title="Status model" value={model?.trained ? 'Siap' : 'Belum siap'} note={model?.trained ? 'Artefak berhasil dimuat' : 'Jalankan pipeline training'} />
            <Stat title="Model terpilih" value={model?.best_model || '-'} note="Dipilih AutoGluon (Macro F1 validasi)" />
            <Stat title="Kategori target" value={model?.classes?.length ?? '-'} note="Dari artefak model" />
            <Stat title="Riwayat Anda (100 terbaru)" value={user ? history.length : '-'} note={user ? 'Milik akun ini' : 'Masuk untuk melihat'} />
          </div>
          <div className="panel"><h3>Status model</h3><p>{model?.message || 'Memeriksa model...'}</p>
            {model?.trained && <><p>Versi: {model.model_version}</p><p>Fitur input model ({model.features?.length}): {model.features?.join(', ')}</p></>}
            {!model?.trained && <code>{cmd}</code>}</div>
        </>}

        {view === 'Prediksi Risiko' && <>
          <div className="intro-card"><span className="icon-box"><ClipboardList /></span><div><h2>Formulir kebiasaan dan kondisi fisik</h2><p>Isi sesuai kebiasaan yang paling mendekati kondisi Anda. Data ini dipakai untuk estimasi dan memilih materi edukasi yang relevan.</p></div></div>
          {!model?.trained && <div className="notice"><AlertCircle size={20} /><p>{model?.message || 'Model belum tersedia.'} Prediksi baru dapat dilakukan setelah model AutoGluon dilatih dan backend dijalankan.</p></div>}
          <form className="form-card" onSubmit={submit} noValidate>
            <div className="form-section"><h3>Informasi dasar</h3><div className="form-grid">
              {f('Gender', 'Jenis kelamin', { opts: ['Female', 'Male'] })}
              {f('Age', 'Usia (tahun)', { type: 'number', min: 14, max: 100 })}
              {f('family_history_with_overweight', 'Riwayat keluarga dengan overweight', { opts: ['yes', 'no'] })}
            </div></div>
            <div className="form-section"><h3>Kebiasaan makan</h3><div className="form-grid">
              {f('FAVC', 'Sering mengonsumsi makanan tinggi kalori?', { opts: ['yes', 'no'] })}
              {f('FCVC', 'Frekuensi konsumsi sayur (skala dataset)', { opts: [1, 2, 3] })}
              {f('NCP', 'Jumlah makan utama (skala dataset)', { opts: [1, 2, 3, 4] })}
              {f('CAEC', 'Makan di antara waktu makan', { opts: ['no', 'Sometimes', 'Frequently', 'Always'] })}
              {f('SCC', 'Memantau asupan kalori?', { opts: ['yes', 'no'] })}
            </div><p className="helper">Skala 1–3/1–4 mengikuti kode dataset sumber, bukan ukuran klinis. Pilih nilai yang paling mendekati.</p></div>
            <div className="form-section"><h3>Aktivitas dan kebiasaan lain</h3><div className="form-grid">
              {f('CH2O', 'Konsumsi air (skala dataset)', { opts: [1, 2, 3] })}
              {f('FAF', 'Aktivitas fisik (skala dataset)', { opts: [0, 1, 2, 3] })}
              {f('TUE', 'Waktu penggunaan teknologi (skala dataset)', { opts: [0, 1, 2] })}
              {f('SMOKE', 'Merokok', { opts: ['no', 'yes'] })}
              {f('CALC', 'Konsumsi alkohol (kategori dataset)', { opts: ['no', 'Sometimes', 'Frequently', 'Always'] })}
              {f('MTRANS', 'Transportasi utama', { opts: ['Public_Transportation', 'Automobile', 'Walking', 'Motorbike', 'Bike'] })}
            </div></div>
            <div className="form-section"><h3>Indikator BMI (opsional)</h3><div className="form-grid">
              {f('Height', 'Tinggi badan (meter)', { type: 'number', min: 1.2, max: 2.3, step: 0.01, required: false })}
              {f('Weight', 'Berat badan (kg)', { type: 'number', min: 25, max: 300, step: 0.5, required: false })}
            </div><p className="helper">Tinggi dan berat <b>tidak dikirim ke model ML</b>. Label pada dataset dibentuk dari BMI, sehingga memakainya sebagai fitur akan membocorkan jawaban. Keduanya hanya dipakai untuk menghitung BMI dengan rumus baku.</p></div>
            {errors.length > 0 && <div className="error-msg" role="alert">{errors.map(m => <div key={m}>{m}</div>)}</div>}
            <div className="form-actions"><span>Data tidak memerlukan nama atau nomor identitas.</span>
              <button className="btn primary" disabled={busy}>{busy ? 'Memproses...' : 'Lihat hasil estimasi'} <ArrowRight size={17} /></button></div>
          </form>
        </>}

        {view === 'Hasil Prediksi' && result && <>
          <div className="result-hero"><div><span className="hero-kicker">HASIL ESTIMASI MODEL</span><h2>{labelMap[result.predicted_class] || result.predicted_class}</h2><p>Kategori keluaran model AutoGluon berdasarkan kebiasaan yang Anda masukkan.</p></div><div className="result-icon"><HeartPulse size={46} /></div></div>
          <div className="notice"><AlertCircle size={20} /><p>{result.disclaimer} Model dilatih pada dataset yang sebagian besar sintetis dan tanpa tinggi/berat badan; interpretasikan dengan hati-hati.</p></div>
          {result.history_saved === false && <div className="notice"><AlertCircle size={20} /><p>Hasil prediksi berhasil, tetapi gagal disimpan ke riwayat (database tidak dapat diakses). Periksa log backend.</p></div>}
          <div className="panel"><h3>Probabilitas per kelas</h3>
            {probs.map(([k, v]) => <div key={k} style={{ margin: '10px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>{labelMap[k] || k}</span><b>{pct(v)}</b></div>
              <div style={{ background: '#f4e6ea', borderRadius: 6, height: 8 }}><div style={{ width: `${v * 100}%`, background: 'var(--wine2)', height: 8, borderRadius: 6 }} /></div></div>)}
          </div>
          {result.bmi_indicator && <div className="panel"><h3>Indikator BMI (terpisah dari model)</h3>
            <p>BMI: <b>{result.bmi_indicator.bmi}</b>{result.bmi_indicator.who_adult_category && <> — kategori dewasa WHO: <b>{result.bmi_indicator.who_adult_category}</b></>}</p>
            <p className="helper">{result.bmi_indicator.note || result.bmi_indicator.source}</p></div>}
          <div className="panel result-panel"><div><h3>Ringkasan</h3><p>Versi model: {result.model_version || 'Tidak tersedia'}</p><p>Waktu: {new Date(result.created_at).toLocaleString('id-ID')}</p></div>
            <button className="btn primary" onClick={() => setEdu(!edu)}><BookOpen size={18} />{edu ? 'Tutup materi edukasi' : 'Pelajari langkah yang bisa saya terapkan'}</button></div>
          {edu && <div className="education-wrap"><div className="section-heading"><div><h2>Materi yang relevan untuk Anda</h2><p>Dipilih oleh aturan terdokumentasi dari kebiasaan pada formulir (bukan keluaran model ML dan bukan dari kategori estimasi).</p></div></div>
            {result.recommendations?.length ? result.recommendations.map((r, i) => <article className="edu-card" key={r.code}><div className="edu-index">{String(i + 1).padStart(2, '0')}</div><div className="edu-content"><span className="tag">{r.topic}</span><h3>{r.title}</h3><p className="reason"><b>Mengapa materi ini muncul?</b> {r.reason}</p><h4>Langkah praktis yang bisa dicoba</h4><ul>{r.steps.map(s => <li key={s}>{s}</li>)}</ul><a href={r.source_url} target="_blank" rel="noreferrer">{r.source} <ExternalLink size={14} /></a></div></article>) : <p>Tidak ada materi yang cocok berdasarkan aturan saat ini.</p>}
            <p className="helper">Materi bersifat edukasi umum. Sesuaikan dengan kondisi, kemampuan, akses makanan, dan anjuran tenaga kesehatan.</p></div>}
          <button className="btn secondary" onClick={() => setPage('Prediksi Risiko')}>Buat estimasi baru</button>
        </>}
        {view === 'Hasil Prediksi' && !result && <div className="empty"><HeartPulse size={36} /><h2>Belum ada hasil prediksi</h2><p>Isi formulir terlebih dahulu untuk melihat hasil dan materi edukasi.</p><button className="btn primary" onClick={() => setPage('Prediksi Risiko')}>Buka formulir</button></div>}

        {view === 'Evaluasi Model' && <>
          <div className="section-heading"><div><h2>Evaluasi model</h2><p>Pemilihan model memakai Macro F1 pada validasi; metrik di bawah dihitung satu kali pada test set 20% yang terpisah.</p></div><button className="btn secondary" onClick={refresh}>Muat ulang</button></div>
          {evalData?.available && (!evalData.model_loaded || evalData.metrics_match_loaded_model === false) && <div className="notice"><AlertCircle size={20} /><p>Peringatan: metrik di bawah berasal dari berkas hasil training, tetapi {evalData.model_loaded ? 'versinya tidak sama dengan model yang sedang dimuat backend' : 'tidak ada model yang sedang dimuat backend'}. Latih ulang atau periksa artefak.</p></div>}
          {!evalData?.available ? <div className="empty"><ChartNoAxesCombined size={36} /><h3>Metrik belum tersedia</h3><p>{evalData?.message || 'Jalankan training AutoGluon terlebih dahulu.'}</p><code>{cmd}</code></div> : <>
            <div className="stats-grid">{[['Accuracy', evalData.accuracy], ['Macro precision', evalData.macro_precision], ['Macro recall', evalData.macro_recall], ['Macro F1', evalData.macro_f1]].map(([k, v]) => <Stat key={k} title={k} value={pct(v)} note={`Test set (${evalData.test_rows} baris)`} />)}</div>
            <div className="panel"><h3>Confusion matrix</h3><p>Baris = label aktual, kolom = prediksi.</p><div className="table-wrap"><table><thead><tr><th>Aktual / Prediksi</th>{evalData.labels.map(l => <th key={l}>{labelMap[l] || l}</th>)}</tr></thead><tbody>{evalData.confusion_matrix.map((row, i) => <tr key={evalData.labels[i]}><th>{labelMap[evalData.labels[i]] || evalData.labels[i]}</th>{row.map((v, j) => <td key={j} style={i === j ? { fontWeight: 800, background: '#fbeff2' } : undefined}>{v}</td>)}</tr>)}</tbody></table></div></div>
            <div className="panel"><h3>Laporan per kelas</h3><div className="table-wrap"><table><thead><tr><th>Kelas</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead><tbody>{evalData.labels.map(l => { const r = evalData.classification_report[l]; return <tr key={l}><th>{labelMap[l] || l}</th><td>{pct(r.precision)}</td><td>{pct(r.recall)}</td><td>{pct(r['f1-score'])}</td><td>{r.support}</td></tr>; })}</tbody></table></div></div>
            <div className="panel"><h3>Leaderboard validasi (Macro F1)</h3><p>Kandidat yang benar-benar dilatih AutoGluon. Model terpilih: <b>{evalData.best_model}</b>.</p><div className="table-wrap"><table><thead><tr><th>Model</th><th>Macro F1 validasi</th><th>Waktu fit (dtk)</th></tr></thead><tbody>{evalData.leaderboard_validation?.map(m => <tr key={m.model}><th>{m.model}</th><td>{pct(m.validation_macro_f1)}</td><td>{m.fit_time}</td></tr>)}</tbody></table></div></div>
            <p className="helper">Split stratified 80:20 setelah penghapusan {evalData.split?.exact_duplicate_rows_removed} baris duplikat eksak. Height/Weight dikeluarkan dari fitur karena label dataset dibentuk dari BMI. Dataset ± 77% sintetis (SMOTE) sehingga baris serupa dapat muncul di training dan test; angka ini kemungkinan lebih optimistis dari performa pada populasi nyata.</p>
          </>}
        </>}

        {view === 'Riwayat' && <>
          <div className="section-heading"><div><h2>Riwayat estimasi</h2><p>Hanya riwayat milik akun Anda yang ditampilkan.</p></div><button className="btn secondary" onClick={() => api.history().then(setHistory).catch(e => setErrors([e.message]))}>Muat ulang</button></div>
          {errors.length > 0 && <div className="error-msg">{errors.join('; ')}</div>}
          {history.length === 0 ? <div className="empty"><History size={36} /><h3>Belum ada riwayat</h3><p>Riwayat akan tampil setelah prediksi berhasil dilakukan.</p></div> :
            <div className="table-wrap"><table><thead><tr><th>Waktu</th><th>Kategori estimasi</th><th>Versi model</th><th></th></tr></thead><tbody>{history.map(h => <tr key={h.id}><td>{new Date(h.created_at).toLocaleString('id-ID')}</td><td>{labelMap[h.predicted_class] || h.predicted_class}</td><td>{h.model_version || '-'}</td><td><button className="icon-button" title="Hapus riwayat" onClick={() => api.deleteHistory(h.id).then(() => api.history().then(setHistory)).catch(e => setErrors([e.message]))}><Trash2 size={16} /></button></td></tr>)}</tbody></table></div>}
        </>}

        {view === 'Profil' && user && <div className="profile-card"><div className="profile-avatar"><UserRound size={32} /></div><h2>{user.username}</h2><p>Akun ObesiCheck</p>
          <div className="profile-row"><span>Username</span><b>{user.username}</b></div>
          <div className="profile-row"><span>Email</span><b>{user.email}</b></div>
          <div className="profile-row"><span>Terdaftar</span><b>{new Date(user.created_at).toLocaleDateString('id-ID')}</b></div>
          <div className="notice"><ShieldCheck size={20} /><p>Jangan masukkan nama, alamat, atau identitas pribadi pada formulir. Riwayat Anda terpisah dari akun lain dan hanya dapat dibaca setelah masuk.</p></div>
          <button className="btn secondary" onClick={logout}><LogOut size={16} /> Keluar</button>
          <h3>Informasi aplikasi</h3><p>Frontend React + Vite · Backend FastAPI · AutoGluon Tabular · SQLite</p></div>}

        <footer>ObesiCheck · Estimasi edukatif berbasis data · Bukan alat diagnosis medis</footer>
      </main>
    </div>
  );
}