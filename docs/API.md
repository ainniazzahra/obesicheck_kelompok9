# API ObesiCheck (`http://127.0.0.1:8000`, Swagger: `/docs`)

| Method | Path | Fungsi |
|---|---|---|
| POST | `/api/auth/register` | Daftar akun → 201 `{user}` (409 duplikat username/email, 422 validasi) |
| POST | `/api/auth/login` | Masuk (`identifier` = username/email) → `{access_token, token_type, expires_in, user}`; 401 salah, 429 terlalu banyak percobaan |
| GET | `/api/auth/me` | Profil akun saat ini (perlu token) |
| POST | `/api/auth/logout` | Mencabut token saat ini (perlu token) |
| GET | `/api/health` | Status layanan dan `model_loaded` |
| GET | `/api/model/status` | Status model, versi, fitur, kelas, metrik ringkas |
| GET | `/api/evaluation` | Metrik test, confusion matrix, laporan per kelas, leaderboard validasi, ringkasan split |
| POST | `/api/predictions` | **(login)** Prediksi kelas + probabilitas + indikator BMI + rekomendasi |
| GET | `/api/history` | **(login)** 100 riwayat terakhir milik akun |
| DELETE | `/api/history/{id}` | **(login)** Hapus riwayat milik akun (404 bila tidak ada/milik akun lain) |

## POST /api/predictions
Field model (wajib): `Gender` (Female/Male), `Age` 14–100, `family_history_with_overweight` (yes/no), `FAVC` (yes/no), `FCVC` 1–3, `NCP` 1–4, `CAEC` (no/Sometimes/Frequently/Always), `SMOKE` (yes/no), `CH2O` 1–3, `SCC` (yes/no), `FAF` 0–3, `TUE` 0–2, `CALC` (no/Sometimes/Frequently/Always), `MTRANS` (Public_Transportation/Automobile/Walking/Motorbike/Bike).
Opsional (tidak dikirim ke model): `Height` 1.2–2.3 m, `Weight` 25–300 kg — **harus diisi bersamaan** atau dikosongkan keduanya. Nilai numerik harus bertipe angka JSON (string seperti `"21"` ditolak).

Contoh valid:
```json
{"Gender":"Male","Age":30,"family_history_with_overweight":"yes","FAVC":"yes","FCVC":1,"NCP":3,"CAEC":"Frequently","SMOKE":"no","CH2O":1,"SCC":"no","FAF":0,"TUE":2,"CALC":"Sometimes","MTRANS":"Automobile","Height":1.75,"Weight":95}
```
Respons 200 (dipersingkat): `{"id":1,"history_saved":true,"created_at":"...","predicted_class":"Overweight_Level_II","probabilities":{"Normal_Weight":0.18,...},"model_version":"ag1.6.3-...","bmi_indicator":{"bmi":31.0,"who_adult_category":"Obesitas kelas I",...},"recommendations":[...],"disclaimer":"..."}`

Contoh tidak valid `{"Gender":"Male","Age":3}` → **422** `{"detail":[{"loc":["body","Age"],"msg":"Input should be greater than or equal to 14","type":"greater_than_equal"},{"loc":["body","FAVC"],"msg":"Field required","type":"missing"},...]}` (input mentah tidak dipantulkan).
Bila prediksi berhasil tetapi database riwayat tidak dapat ditulis → tetap **200** dengan `"history_saved":false,"id":null`; `GET/DELETE /api/history` menjawab **503** pada kegagalan DB. `{record_id}` harus 1–9223372036854775807 (di luar itu 422).

`GET /api/evaluation` memuat tambahan `model_loaded` dan `metrics_match_loaded_model` (false bila metrik berasal dari model yang berbeda/tidak sedang dimuat); berkas hasil yang rusak → `{"available":false,...}`.
Model belum ada/gagal dimuat → **503** `{"detail":"Model belum dilatih. Jalankan: python ml/src/train.py"}`. Galat internal → **500** `{"detail":"Prediksi gagal diproses. Periksa log server."}` (tanpa detail internal).

## Autentikasi
Kirim `Authorization: Bearer <access_token>` pada endpoint bertanda (login). Tanpa/dengan token tidak valid, kedaluwarsa, atau sudah di-logout → **401** `{"detail":"Autentikasi diperlukan atau sesi tidak valid. Silakan masuk kembali."}` + header `WWW-Authenticate: Bearer`.

Registrasi: `username` 3–30 karakter `[A-Za-z0-9_.-]` (unik, tanpa membedakan huruf besar/kecil), `email` valid (unik), `password` 8–128 karakter berisi huruf dan angka serta tidak memuat username. Spasi pada password dianggap bagian password.
```json
POST /api/auth/register  {"username":"ani_01","email":"ani@example.com","password":"Sandi12345"}   -> 201 {"user":{"id":1,"username":"ani_01","email":"ani@example.com","created_at":"..."}}
POST /api/auth/login     {"identifier":"ani_01","password":"Sandi12345"}   -> 200 {"access_token":"eyJ...","token_type":"bearer","expires_in":43200,"user":{...}}
```
Login salah (akun tak ada maupun password salah) selalu **401** dengan pesan sama: `Username/email atau password salah.` Pesan 409 registrasi juga sama untuk username maupun email yang bentrok (tidak membocorkan akun terdaftar).
