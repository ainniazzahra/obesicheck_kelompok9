# ObesiCheck — React + FastAPI + AutoGluon Tabular (v3: dengan registrasi & login)

Aplikasi web edukasi dan estimasi **kategori tingkat obesitas** (7 kelas) dari kebiasaan makan dan kondisi fisik, memakai dataset UCI 544. **Bukan alat diagnosis medis.**

## Ringkasan perubahan metodologi (v2)
- **Kebocoran label ditemukan dan diperbaiki.** Label `NObeyesdad` didefinisikan dari BMI (= Weight/Height²); aturan ambang BMI saja cocok 95,2% dengan label. `Height` dan `Weight` **tidak lagi menjadi fitur model**. Keduanya opsional di formulir hanya untuk menghitung indikator BMI terpisah.
- Split **stratified 80:20** (setelah membuang 24 duplikat eksak); validasi internal diambil dari 80% data pengembangan; test set dievaluasi **satu kali**.
- Pemilihan model oleh AutoGluon dengan `eval_metric="f1_macro"` (Macro F1 pada validasi).
- Backend memuat artefak model yang sama dengan yang dievaluasi; tidak ada fallback.
- Hasil aktual lengkap: [`docs/EKSPERIMEN.md`](docs/EKSPERIMEN.md).

## Autentikasi (baru di v3)
- **Registrasi, login (username atau email), logout, profil** — halaman Masuk/Daftar di UI. Prediksi, riwayat, dan profil memerlukan login; Beranda, Dashboard, dan Evaluasi Model tetap publik.
- **Riwayat per akun:** setiap akun hanya melihat/menghapus riwayatnya sendiri (riwayat milik akun lain dijawab 404).
- Password di-hash **argon2id** (tidak pernah disimpan/dikirim balik sebagai teks biasa). Sesi memakai token JWT (HS256) berumur 12 jam (`OBESICHECK_TOKEN_TTL_MINUTES`); **logout mencabut token di server** (daftar pencabutan di DB), bukan hanya menghapusnya di browser.
- Kunci penandatangan: `OBESICHECK_SECRET_KEY` (≥32 karakter) atau, bila kosong, kunci acak dibuat otomatis di `backend/database/secret.key` (jangan di-commit/dibagikan; folder itu sudah di `.gitignore`). Menghapus file itu membuat semua sesi lama tidak berlaku.
- Pembatasan percobaan login: 5 gagal per akun / 20 per IP dalam 15 menit → 429 (disimpan di memori proses; reset saat server restart).
- Token disimpan di `sessionStorage` browser (hilang saat tab ditutup).
- **Migrasi dari v2:** database lama otomatis ditambah kolom `user_id`; riwayat lama tidak punya pemilik sehingga tidak tampil bagi akun mana pun (data tidak dihapus).
- **Belum ada:** reset password/verifikasi email, peran admin, login sosial, dan HTTPS (gunakan reverse proxy TLS bila dipublikasikan). Lihat Batasan.

## Struktur direktori
```
ObesiCheck/
├─ backend/            FastAPI (app/main.py, schemas, services, db), requirements*.txt
├─ frontend/           React + Vite (src/App.jsx, components, services/api.js)
├─ ml/
│  ├─ data/            ObesityDataSet_raw_and_data_sinthetic.csv
│  ├─ src/             config.py, data_utils.py, audit.py, train.py
│  ├─ models/          ObesiCheckPredictor/  (model AutoGluon final, dipakai backend)
│  ├─ results/         metrik, leaderboard, split, konfigurasi (hasil training final)
│  └─ results_reference_with_height_weight/   eksperimen pembanding (bocor label, TIDAK untuk deployment)
├─ tests/              pytest (data, split, metrik, API, BMI, rekomendasi)
└─ docs/               ARSITEKTUR.md, EKSPERIMEN.md, API.md
```

## Instalasi (Windows PowerShell)
Prasyarat: **Python 3.12** (disarankan; versi lain periksa dokumentasi AutoGluon), Node.js 18+.
Model hasil training sudah disertakan (hanya WeightedEnsemble_L2 dan 4 model dasarnya; model dasar lain yang tidak dipakai ensemble dibuang untuk mengecilkan ukuran, prediksi identik dengan yang dievaluasi — diverifikasi oleh `tests/test_ml_pipeline.py`). Training tidak wajib dijalankan ulang. Leaderboard validasi penuh ada di `ml/results/leaderboard_validation.csv`.

```powershell
# dari folder root project (ObesiCheck)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt
cd frontend; npm install; cd ..
```
Jika `Activate.ps1` ditolak: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Menjalankan
**Backend** (terminal 1, venv aktif, dari root project):
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```
Dokumentasi interaktif: http://127.0.0.1:8000/docs

**Frontend** (terminal 2):
```powershell
cd frontend
npm run dev
```
Buka http://localhost:5173. Build produksi: `npm run build`.

## Menjalankan training (opsional, mengganti model & metrik)
```powershell
# dari root project, venv aktif
python ml\src\audit.py                       # audit dataset -> ml/results/audit_report.json
python ml\src\train.py --time-limit 600      # pipeline lengkap (default seed 42)
python ml\src\train.py --with-anthropometry --time-limit 300   # pembanding bocor label; tidak untuk deployment
```
Training menimpa `ml/models/ObesiCheckPredictor` dan `ml/results/`. Hasil bergantung versi library, jumlah CPU, dan `--time-limit`, sehingga angka dapat sedikit berbeda dari laporan. Restart backend setelah training.

## Pengujian
```powershell
# dari root project, venv aktif
python -m pytest tests -q                 # 83 tes; tes integrasi model perlu AutoGluon berhasil dimuat
cd frontend; npm test; npm run build      # tes kontrak respons (13 tes) + build
```
Tes yang membutuhkan inferensi model akan berstatus SKIP bila AutoGluon belum terpasang atau artefak gagal dimuat; jangan menganggapnya sebagai validasi prediksi nyata. Pastikan output tidak memuat FAIL dan perhatikan jumlah SKIP. Catatan pengujian ZIP pada lingkungan audit ada di [`docs/RETEST_REPORT.md`](docs/RETEST_REPORT.md).

E2E browser (opsional; butuh `pip install playwright` + `playwright install chromium`, backend di :8000 dan frontend di :5173 berjalan):
```powershell
python tests\e2e\e2e_browser.py
```
Skrip ini **mendaftarkan akun uji `e2e_*`** (jalankan backend dengan `OBESICHECK_DB_PATH` khusus uji) dan menguji registrasi/login/logout, isolasi data dua akun, sesi dicabut, lockout, alur nyata, serta kondisi gagal (backend mati, 503, 422, respons melanggar kontrak, hasil lama, responsif). Laporan audit: [`docs/AUDIT.md`](docs/AUDIT.md).

## Troubleshooting Windows / PowerShell
| Gejala | Solusi |
|---|---|
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `py` tidak dikenali | Pasang Python dari python.org dengan opsi *py launcher*, atau pakai `python -m venv .venv` |
| Pemasangan AutoGluon/LightGBM gagal | Pastikan Python 3.12 64-bit dan `pip` terbaru; pasang *Microsoft Visual C++ Redistributable* |
| Model gagal dimuat dan status menyebut dependensi AutoGluon | Aktifkan `.venv`, jalankan `pip install -r backend\requirements-dev.txt`, lalu mulai ulang backend |
| Model gagal dimuat (versi berbeda) | Model terikat versi AutoGluon (1.6.x). Pasang versi dari `requirements.txt` atau latih ulang |
| Frontend: "Tidak dapat terhubung ke server" | Pastikan backend jalan di port 8000; atau atur `VITE_API_URL` di `frontend/.env` |
| Selalu diminta masuk lagi | Token ada di `sessionStorage` (hilang saat tab ditutup), kedaluwarsa 12 jam, atau `secret.key`/DB diganti |
| Login ditolak 429 | Terlalu banyak percobaan gagal; tunggu 15 menit atau restart backend |
| CORS error | Atur `OBESICHECK_CORS_ORIGINS` (lihat `backend/.env.example`) |
| Port 8000/5173 terpakai | Jalankan dengan `--port` lain dan sesuaikan `VITE_API_URL` |
| Training lambat / RAM kecil | Kurangi `--time-limit`, tutup aplikasi lain |

## Edukasi gaya hidup
Materi dipilih oleh **aturan terdokumentasi** (`backend/app/services/recommendations.py`) dari kebiasaan yang dilaporkan di formulir. Bukan keluaran model ML.

## Batasan
- ~77% dataset adalah data sintetis (SMOTE); evaluasi pada dataset ini tidak menjamin performa pada populasi nyata/lokal. Baris serupa dapat muncul di training dan test, sehingga metrik cenderung optimistis.
- Model memperkirakan kategori dari kebiasaan saja (tanpa tinggi/berat), sehingga akurasinya lebih rendah namun tidak menyesatkan akibat kebocoran label.
- Autentikasi sederhana untuk skala capstone: tanpa reset password, verifikasi email, peran admin, atau HTTPS bawaan, dan pembatas login hanya di memori satu proses. Untuk dipublikasikan ke internet: pasang di balik HTTPS, atur `OBESICHECK_SECRET_KEY`, batasi `OBESICHECK_CORS_ORIGINS`, dan tinjau ulang keamanan terlebih dahulu. Hindari memasukkan identitas pribadi.
- Model AutoGluon adalah berkas pickle yang terikat versi library/OS. Model dilatih dan diuji di Linux; memuatnya di Windows **belum diuji**. Bila gagal dimuat, API menjawab 503; latih ulang dengan `python ml\\src\\train.py`.
- Font diambil dari Google Fonts; tanpa internet, tampilan memakai font sans-serif bawaan.
- AutoGluon dipasang tanpa PyTorch pada lingkungan pengujian, jadi model jaringan saraf tidak termasuk kandidat. Pasang `autogluon.tabular[all]` bila ingin kandidat lebih luas.

## Sumber
- Dataset: https://archive.ics.uci.edu/dataset/544/
- WHO Healthy diet: https://www.who.int/news-room/fact-sheets/detail/healthy-diet · WHO Physical activity: https://www.who.int/news-room/fact-sheets/detail/physical-activity · Kemenkes RI: https://www.kemkes.go.id/
