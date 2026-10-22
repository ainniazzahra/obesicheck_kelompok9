# Arsitektur ObesiCheck

```
React (Vite)  --HTTP/JSON-->  FastAPI  --load sekali saat startup-->  AutoGluon TabularPredictor (ml/models/ObesiCheckPredictor)
                                 |                                       ^ dilatih oleh ml/src/train.py
                                 +--> SQLite (riwayat)                   |  artefak: ml/results/*
                                 +--> recommendations.py (aturan, bukan ML)
```

0. Pengguna mendaftar/masuk (`/api/auth/*`); frontend menyimpan token di `sessionStorage` dan mengirimnya sebagai `Authorization: Bearer`. 401 pada permintaan terautentikasi membersihkan sesi dan seluruh data privat di UI.
1. Frontend memvalidasi input (rentang, wajib) lalu memanggil `POST /api/predictions`.
2. Pydantic memvalidasi tipe, kategori, rentang; `extra="forbid"`.
3. `ModelService` memuat model **sekali** saat startup, memverifikasi fitur & model terpilih terhadap `ml/results/model_info.json`. Jika gagal: status 503 dengan pesan aman (detail hanya di log server). Tidak ada model/prediksi pengganti.
4. Kolom disusun sesuai urutan fitur training; `predict` dan `predict_proba` (kolom = label kelas) dari predictor yang sama.
5. Height/Weight (opsional) tidak masuk model; dihitung menjadi indikator BMI terpisah (`services/bmi.py`).
6. Modul rekomendasi berbasis aturan memilih materi dari jawaban gaya hidup.
7. Ringkasan riwayat (kelas, versi model) disimpan di SQLite (`backend/database/`) bersama `user_id` pemilik; seluruh kueri riwayat difilter per pemilik. Tabel: `users` (hash argon2id), `prediction_history`, `revoked_tokens` (jti token yang di-logout).

## Pipeline ML (`ml/src/train.py`)
Validasi skema → dedup eksak → split stratified 80:20 → dev dipecah stratified 80:20 (fit/validasi) → `TabularPredictor.fit(train_data=fit, tuning_data=validasi, eval_metric="f1_macro")` → leaderboard validasi → evaluasi test satu kali → simpan artefak. Tidak ada refit pada seluruh data pengembangan, sehingga model deployment = model yang dievaluasi.

## Endpoint
Lihat [API.md](API.md).
