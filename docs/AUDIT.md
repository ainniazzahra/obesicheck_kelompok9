# Laporan Audit ObesiCheck (v2 → v2.1) dan penambahan autentikasi (v3)

Cakupan: 107 berkas pada ZIP awal (84 substantif: kode, konfigurasi, dokumen, dataset, artefak hasil, 11 berkas model; ditambah 19 `.pyc` dan 4 berkas `.pytest_cache` yang tidak semestinya ikut). Semua kode dibaca penuh; artefak JSON/CSV diperiksa dengan skrip; kode dijalankan (pytest, probe HTTP, browser headless Chromium). **Tidak ada klaim bebas-bug absolut**; yang belum diuji tercantum di bagian "Belum diuji".

Jenis bukti: **[S]** analisis statis, **[T]** tes otomatis, **[L]** pengujian langsung (HTTP/browser).

## Bug terkonfirmasi (0 Critical, 0 High, 6 Medium, 13 Low)
| ID | Lokasi | Gejala & bukti | Sev. | Perbaikan | Retest |
|---|---|---|---|---|---|
| B1 | `schemas/prediction.py` | Height saja / Weight saja → 200, BMI hilang tanpa pesan [L] | Medium | validator "harus bersamaan" | 422 [T][L] |
| B2 | `main.py` (422) | Body `{"Age": NaN}` → **500** (body galat memantulkan NaN, tak bisa di-JSON) [L] | Medium | handler 422 yang tidak memantulkan input | 422 [T][L] |
| B4 | `db/database.py`, `main.py` | DB terhapus saat jalan → `no such table`: prediksi & riwayat **500** walau model sehat [L] | Medium | tabel dibuat ulang saat koneksi; kegagalan riwayat → 200 + `history_saved:false`, riwayat 503 | [T][L] |
| B6 | `main.py` `/evaluation` | `metrics.json` rusak → 500 [L] | Medium | dibaca aman → `available:false` | [T][L] |
| F1 | `frontend/services/api.js` | Respons `{}` ditampilkan sebagai halaman hasil kosong [L browser] | Medium | validasi kontrak (`contract.js`) → error, hasil tidak ditampilkan | E2E + 12 tes node |
| F2 | `frontend/src/App.jsx` | Rekomendasi tanpa `steps` → layar putih (tanpa error boundary) [L browser] | Medium | validasi kontrak + `ErrorBoundary` | E2E |
| B3 | `main.py` DELETE | `/api/history/99999999999999999999` → 500 (OverflowError) [L] | Low | batas `ge=1, le=2^63-1` | [T][L] |
| B5 | `database.py` | Koneksi SQLite tidak ditutup (`with conn` hanya commit) [T membuktikan] ; risiko kunci file di Windows (belum diuji di Windows) | Low | `closing()` | [T] |
| B7 | `/evaluation` | Metrik tampil "tersedia" walau model tidak dimuat [L] | Low | `model_loaded`, `metrics_match_loaded_model` + banner UI | [T] |
| B8 | schema | `"Age":"21"` dikoersi diam-diam [L] | Low | `strict=True` | [T][L] |
| B9 | handler 422 | Input mentah dipantulkan di respons [L] | Low | `input`/`ctx` dibuang | [T] |
| P1 | `model_service.py` | 2 inferensi per request (433 ms/req) [L] | Low | satu `predict_proba` + argmax (identik pada 418/418 baris test, tanpa tie) → 227 ms | [T][L] |
| F3 | `App.jsx` | Tombol navigasi mobile tanpa nama aksesibel [L browser] | Low | `aria-label`, `title` | E2E |
| F4 | Dashboard | "Riwayat tersimpan" dibatasi 100 | Low | label "Riwayat (100 terbaru)" | [L] |
| F5 | `styles.css` | Heading serif saat Google Fonts tak termuat (10 deklarasi tanpa fallback) | Low | fallback `sans-serif` | [S] |
| M1 | `ml/results/environment_freeze.txt` | Bukan `pip freeze` (venv uv tanpa pip) | Low | diganti `environment_versions.txt` + `pip_freeze.txt` bila ada pip | [T] |
| M2 | `ml/src`, `backend` | Lint: impor tak terpakai, B904, `zip` tanpa strict, tipe `Optional` [S] | Low | diperbaiki; `ruff` bersih | [S] |
| M3 | `backend/app/api/` | Paket kosong tak dipakai (tidak diimpor di mana pun) [S] | Low | dihapus | [T] |
| Z1 | ZIP | `__pycache__` dan `.pytest_cache` ikut terkemas | Low | dikecualikan + dicek | [S] |

Verifikasi regresi: 11 tes baru gagal pada kode lama dan lulus pada kode baru.

## Hasil audit alur
| Alur | Hasil |
|---|---|
| 1 Startup | Instalasi bersih dari ZIP (`npm ci`, venv), startup, muat model, backend↔frontend terhubung: BERHASIL (Linux). Windows/PowerShell: **BELUM DIUJI**. |
| 2 Autentikasi | Pada v2.1 **BELUM TERSEDIA** (riwayat global). **Ditambahkan di v3** — lihat bagian "Autentikasi (v3)" di bawah. |
| 3 Prediksi | Semua kasus uji (valid, wajib kosong, di bawah/atas batas, tipe salah, kategori tak dikenal, field hilang/tambahan, backend mati, model hilang/rusak/tidak cocok, prediksi gagal, kontrak rusak) menghasilkan penanganan yang benar; tidak ada hasil lama/hardcoded/model lain [T][L]. |
| 4 Riwayat/DB | Tambah/baca/hapus, persisten antar restart, DB terhapus saat jalan, DB tak dapat ditulis: BERHASIL setelah perbaikan. Relasi akun/otorisasi: BELUM TERSEDIA. |
| 5 Dashboard/pendukung | Dashboard, Evaluasi, Riwayat, Profil, tombol "Muat ulang", hapus riwayat berfungsi. Admin/training dari UI: BELUM TERSEDIA. |

## ML
Data valid dan dibaca; target benar; kebocoran Height/Weight dikeluarkan; dedup sebelum split; split 80:20 stratified tanpa overlap; AutoGluon nyata (log: 1.335 baris fit, 334 tuning, `f1_macro`); test hanya dipakai pada evaluasi; metrik dihitung ulang independen sama dengan `metrics.json`; model deployment = model dievaluasi (prediksi identik); label/probabilitas dipetakan dari kolom `predict_proba`; tidak ada fallback; model tidak dilatih per request. **Reproduksi training pada lingkungan sama: split, leaderboard, metrik, dan prediksi identik.** Metrik: lihat `docs/EKSPERIMEN.md`.
Ketidaksesuaian training↔deployment: tidak ditemukan; satu-satunya perbedaan (model dasar tak terpakai dibuang) tidak mengubah prediksi.

## Hasil pengujian
| No. | Pengujian | Hasil | Status |
|---|---|---|---|
| 1 | `pytest tests` (data, split, metrik, model, API, DB, BMI, rekomendasi, regresi) | 38 lulus | PASS |
| 2 | `npm test` (kontrak respons) | 12 lulus | PASS |
| 3 | `npm run build` | sukses | PASS |
| 4 | E2E browser `tests/e2e/e2e_browser.py` (33 skenario, Chromium) | awal 28 lulus/5 gagal → akhir 33/33 | PASS |
| 5 | Probe HTTP backend (input aneh, konkurensi 24 paralel, restart, DB gagal) | semua sesuai harapan setelah perbaikan | PASS |
| 6 | Skenario model: hilang, `learner.pkl` rusak, `model_info` tak cocok (2 jenis), hasil kosong/rusak | 503/`available:false`, tanpa kebocoran internal | PASS |
| 7 | `ruff` (E9,F,B,S,UP,SIM), `mypy` backend | bersih / 0 isu | PASS |
| 8 | Reproduksi training | identik | PASS |
| 9 | Windows/PowerShell, Firefox/Safari, perangkat mobile fisik | — | BELUM DIJALANKAN |
| 10 | Beban tinggi / rate limiting / uji keamanan penetrasi | — | BELUM DIJALANKAN |

## Belum selesai / belum diuji
- Tidak ada autentikasi/otorisasi dan rate limiting → jangan diekspos publik.
- Model pickle terikat versi/OS; muat di Windows belum diuji.
- Hanya Chromium yang diuji; aksesibilitas hanya diperiksa pada navigasi.
- Konkurensi: 24 request paralel konsisten, tetapi thread-safety AutoGluon tidak dibuktikan formal.
- Keterbatasan data (77% sintetis, satu split/seed) tetap berlaku untuk interpretasi metrik.

## Autentikasi (v3)
Fitur baru: registrasi, login (username/email), logout dengan pencabutan token server-side, `/auth/me`, riwayat per akun, migrasi DB v2→v3. Admin/reset password/verifikasi email: **BELUM TERSEDIA**.

| Pengujian | Hasil | Status |
|---|---|---|
| `tests/test_auth.py` (45): validasi registrasi (13 kasus invalid, termasuk injeksi/XSS), duplikat tak peka huruf, hash argon2id & tidak ada teks biasa di berkas DB, login username/email, pesan identik akun-tak-ada vs password-salah, injeksi pada login, lockout & reset, endpoint terlindungi, header Authorization rusak, token (ubah tanda tangan, kedaluwarsa, kunci lain, alg none, HS512, tanpa exp/jti, sub tak valid, akun tak ada), logout mencabut token (sesi lain tidak ikut), pembersihan token kedaluwarsa, kunci rahasia tidak hardcoded, isolasi riwayat antar akun (lihat & hapus), migrasi DB lama, cascade hapus akun, kegagalan DB → 503 tanpa kebocoran | 45 lulus | PASS |
| Uji mutasi pada kontrol keamanan (filter pemilik riwayat, cek pencabutan, daftar algoritma JWT, lockout, pesan login seragam) | 5/5 mutasi tertangkap oleh tes (satu mutasi awalnya lolos → ditambah kasus HS512 → tertangkap) | PASS |
| Temuan selama pengujian | email `<script>@x.id` lolos validasi regex awal → diperketat; tes sekarang menolaknya | diperbaiki |
| E2E browser (52 skenario, termasuk dua akun, logout, sesi dicabut, lockout, validasi form, halaman privat tanpa login) | 52 lulus (satu kegagalan sekali jalan karena race startup backend; skrip kini menunggu backend siap) | PASS |
| `npm test` kontrak (13), `npm run build`, `ruff`, `mypy` | lulus | PASS |
| Hasil total `pytest` | 83 lulus | PASS |

Belum diuji / keterbatasan: Windows, browser selain Chromium, HTTPS, beban/serangan terdistribusi (pembatas hanya di memori satu proses), reset password, pengelolaan banyak instance server (pembatas dan secret.key per instance).
