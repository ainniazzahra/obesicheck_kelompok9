# Laporan Perbaikan dan Pengujian Ulang ObesiCheck Final v3

Tanggal audit: 21 Oktober 2026. ZIP sumber: `ObesiCheck_Final_v3.zip`.

## Perbaikan yang dilakukan

1. **Tes integrasi model tidak lagi salah mengasumsikan model siap hanya karena file artefak ada.** Sebelumnya, marker `needs_model` di `tests/test_api.py` hanya memeriksa keberadaan folder model dan `model_info.json`. Akibatnya tes prediksi tetap berjalan meski paket `autogluon` tidak terpasang, lalu gagal pada setup lingkungan yang tidak lengkap. Marker kini memeriksa apakah `service.load().ready` benar-benar bernilai benar dan melewati tes inferensi dengan alasan eksplisit jika dependensi/artefak belum siap. Tes pemeriksaan kesesuaian skema fitur dengan metadata tetap dijalankan karena tidak memerlukan inferensi.
2. **Pesan kegagalan pemuatan model dibuat lebih dapat ditindaklanjuti.** `ModelService` sekarang membedakan kasus `autogluon` tidak terpasang dari kegagalan pemuatan artefak umum. Detail exception tetap hanya masuk log server, bukan dikirim ke pengguna.
3. **Panduan pengujian dan troubleshooting diperjelas.** README sekarang memperingatkan bahwa tes integrasi yang SKIP tidak membuktikan inferensi model berfungsi, dan menautkan laporan pengujian ulang.

Tidak ada perubahan terhadap algoritma, dataset, split, bobot model, atau metrik evaluasi. Karena tidak dilakukan training ulang, angka metrik ML tidak diklaim meningkat.

## Hasil pengujian pada lingkungan audit

Lingkungan saat pengujian: Python 3.13.5; paket `autogluon` tidak tersedia.

| Pengujian | Hasil | Interpretasi |
|---|---:|---|
| `python -m pytest tests -q` sebelum perbaikan marker | 75 lulus, 5 gagal, 3 skip | Lima kegagalan berasal dari tes integrasi yang mencoba memuat AutoGluon tanpa paket tersebut. |
| `python -m pytest tests -q` setelah perbaikan | **74 lulus, 9 skip, 0 gagal** | Tes yang bergantung pada model sekarang ditandai SKIP secara jujur bila runtime model tidak siap. Total 83 tes terkumpul. |
| `frontend` — `npm test` | **13 lulus, 0 gagal** | Tes kontrak frontend berhasil. |
| `frontend` — `npm run build` | **Belum berhasil diverifikasi** | `vite: not found`; proses pemasangan dependensi npm terputus/tidak lengkap dan instalasi offline tidak dapat dipenuhi dari cache. Ini masalah lingkungan instalasi, bukan bukti build berhasil. |
| Ruff lint | **Belum dijalankan** | Modul `ruff` tidak terpasang di lingkungan audit. |
| Inferensi nyata AutoGluon | **Belum terverifikasi pada lingkungan audit** | Paket AutoGluon tidak tersedia sehingga model tidak dapat dimuat. Perlu retest pada Python 3.12 dengan `backend/requirements-dev.txt`, sesuai lingkungan yang direkomendasikan proyek. |

## Apakah kualitas sistem meningkat?

- **Kualitas diagnosis masalah meningkat:** kegagalan karena dependensi hilang kini menghasilkan pesan yang lebih spesifik dan tidak mendorong pengguna melatih ulang model tanpa alasan.
- **Kualitas sinyal pengujian meningkat:** tes tidak lagi salah menyatakan kegagalan inferensi ketika prasyarat runtime model memang belum tersedia; kondisi tersebut dicatat sebagai SKIP dengan alasan eksplisit. SKIP bukan PASS.
- **Frontend contract test tetap lulus:** 13/13.
- **Peningkatan kualitas prediksi belum dibuktikan:** tidak ada training ulang atau evaluasi pada data baru. Metrik lama (accuracy 0,8708; macro F1 0,8692 pada test 418 baris) tetap sama dan masih memiliki keterbatasan dataset sintetis.
- **Build frontend dan integrasi model end-to-end masih terbuka:** wajib diuji pada lingkungan lengkap sebelum menyatakan proyek siap demo.

## Langkah retest yang wajib dilakukan di laptop proyek

Gunakan Python 3.12 64-bit, dari root `ObesiCheck`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements-dev.txt
python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

Setelah itu jalankan backend dan frontend, lalu uji registrasi, login, prediksi, probabilitas, rekomendasi, riwayat, logout, dan login ulang. Catat output aktual. Tes integrasi prediksi harus benar-benar berjalan (bukan SKIP) sebelum inferensi dinyatakan tervalidasi.
