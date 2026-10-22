import React, { useState } from 'react';
import { Eye, EyeOff, LogIn, UserPlus, ShieldCheck } from 'lucide-react';
import { api } from '../services/api.js';

const USERNAME_RE = /^[A-Za-z0-9_.-]{3,30}$/;
const EMAIL_RE = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;

export function validateRegister({ username, email, password }) {
  const e = [];
  if (!USERNAME_RE.test(username.trim())) e.push('Username 3–30 karakter: huruf, angka, titik, garis bawah, atau strip.');
  if (!EMAIL_RE.test(email.trim())) e.push('Format email tidak valid.');
  if (password.length < 8 || password.length > 128 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) e.push('Password 8–128 karakter dan mengandung huruf serta angka.');
  else if (username.trim() && password.toLowerCase().includes(username.trim().toLowerCase())) e.push('Password tidak boleh mengandung username.');
  return e;
}

export default function AuthPage({ notice, onLoggedIn }) {
  const [mode, setMode] = useState('login');
  const [f, setF] = useState({ identifier: '', username: '', email: '', password: '' });
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState([]);
  const [info, setInfo] = useState('');
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));
  const isLogin = mode === 'login';

  const submit = async e => {
    e.preventDefault();
    setInfo('');
    const problems = isLogin
      ? [!f.identifier.trim() && 'Username atau email wajib diisi.', !f.password && 'Password wajib diisi.'].filter(Boolean)
      : validateRegister(f);
    setErrors(problems);
    if (problems.length) return;
    setBusy(true);
    try {
      if (!isLogin) {
        await api.register({ username: f.username.trim(), email: f.email.trim(), password: f.password });
        const r = await api.login({ identifier: f.username.trim(), password: f.password });
        onLoggedIn(r.user);
      } else {
        const r = await api.login({ identifier: f.identifier.trim(), password: f.password });
        onLoggedIn(r.user);
      }
    } catch (err) { setErrors([err.message]); } finally { setBusy(false); }
  };

  const switchMode = m => { setMode(m); setErrors([]); setInfo(''); };
  return (
    <div className="auth-wrap">
      <form className="form-card auth-card" onSubmit={submit} noValidate>
        <div className="auth-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={isLogin} className={isLogin ? 'on' : ''} onClick={() => switchMode('login')}><LogIn size={15} /> Masuk</button>
          <button type="button" role="tab" aria-selected={!isLogin} className={!isLogin ? 'on' : ''} onClick={() => switchMode('register')}><UserPlus size={15} /> Daftar</button>
        </div>
        <h2>{isLogin ? 'Masuk ke ObesiCheck' : 'Buat akun baru'}</h2>
        {notice && <div className="notice"><ShieldCheck size={20} /><p>{notice}</p></div>}
        {isLogin ? (
          <label className="field"><span>Username atau email</span>
            <input name="identifier" autoComplete="username" value={f.identifier} onChange={e => set('identifier', e.target.value)} maxLength={254} /></label>
        ) : (<>
          <label className="field"><span>Username</span>
            <input name="username" autoComplete="username" value={f.username} onChange={e => set('username', e.target.value)} maxLength={30} /></label>
          <label className="field"><span>Email</span>
            <input name="email" type="email" autoComplete="email" value={f.email} onChange={e => set('email', e.target.value)} maxLength={254} /></label>
        </>)}
        <label className="field"><span>Password</span>
          <span className="pw-row">
            <input name="password" type={show ? 'text' : 'password'} autoComplete={isLogin ? 'current-password' : 'new-password'} value={f.password} onChange={e => set('password', e.target.value)} maxLength={128} />
            <button type="button" className="icon-button" aria-label={show ? 'Sembunyikan password' : 'Tampilkan password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={16} /> : <Eye size={16} />}</button>
          </span>
          {!isLogin && <small className="helper">Minimal 8 karakter, mengandung huruf dan angka. Jangan memakai password yang sama dengan layanan lain.</small>}
        </label>
        {errors.length > 0 && <div className="error-msg" role="alert">{errors.map(m => <div key={m}>{m}</div>)}</div>}
        {info && <div className="notice"><p>{info}</p></div>}
        <button className="btn primary" disabled={busy}>{busy ? 'Memproses...' : isLogin ? 'Masuk' : 'Daftar dan masuk'}</button>
        <p className="helper">Jangan memasukkan data identitas yang tidak perlu. Akun hanya dipakai untuk memisahkan riwayat estimasi Anda.</p>
      </form>
    </div>
  );
}
