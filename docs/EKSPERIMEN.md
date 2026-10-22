# Laporan Eksperimen Aktual

Dihasilkan oleh `ml/src/train.py` (seed 42, AutoGluon 1.6.3, Python 3.12.3, preset `medium_quality`, time_limit 600 dtk, waktu training 75.3 dtk). Semua angka berasal dari file di `ml/results/`.

## Data
- Dataset 2.111 baris × 17 kolom; 0 nilai kosong; 24 duplikat eksak dibuang sebelum split → **2087** baris.
- 7 kelas relatif seimbang (272–351 baris sebelum dedup).
- **Kebocoran:** aturan ambang BMI cocok 95,2% dengan label; `Height`/`Weight` dikeluarkan dari fitur (14 fitur tersisa).
- ~77% sintetis (SMOTE) menurut UCI; heuristik nilai bulat menandai 513 baris kemungkinan asli.

## Split
Stratified 80:20 → pengembangan 1669, test **418** (ceil(0,2·2087)). Pengembangan dipecah stratified 80:20 → fit 1335, validasi 334. Overlap `source_row_id` = 0. 1 baris test memiliki fitur identik dengan baris pengembangan (label berbeda/sama) — dilaporkan, tidak dihapus.

## Kandidat AutoGluon dan Macro F1 validasi
| Model | Macro F1 validasi | Waktu fit (dtk) |
|---|---|---|
| WeightedEnsemble_L2 | 0.8985 | 61.8 |
| LightGBMXT | 0.8913 | 4.1 |
| RandomForestGini | 0.8873 | 0.8 |
| RandomForestEntr | 0.8852 | 0.7 |
| XGBoost | 0.8744 | 2.8 |
| CatBoost | 0.8676 | 54.0 |
| LightGBM | 0.8607 | 3.4 |
| LightGBMLarge | 0.8550 | 5.5 |
| ExtraTreesEntr | 0.8543 | 0.7 |
| ExtraTreesGini | 0.8536 | 0.7 |

Model terpilih: **WeightedEnsemble_L2** (otomatis oleh AutoGluon dari skor validasi `f1_macro` tertinggi). KNN dan model jaringan saraf tidak termasuk kandidat pada konfigurasi/lingkungan ini (tanpa PyTorch).

## Evaluasi final (test set, satu kali)
| Metrik | Nilai |
|---|---|
| Accuracy | 0.8708 |
| Precision macro | 0.8714 |
| Recall macro | 0.8688 |
| **Macro F1** | **0.8692** |

| Kelas | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Insufficient_Weight | 0.907 | 0.925 | 0.916 | 53 |
| Normal_Weight | 0.698 | 0.772 | 0.733 | 57 |
| Obesity_Type_I | 0.845 | 0.857 | 0.851 | 70 |
| Obesity_Type_II | 0.921 | 0.967 | 0.943 | 60 |
| Obesity_Type_III | 1.000 | 0.985 | 0.992 | 65 |
| Overweight_Level_I | 0.882 | 0.818 | 0.849 | 55 |
| Overweight_Level_II | 0.846 | 0.759 | 0.800 | 58 |

Confusion matrix: `ml/results/confusion_matrix.png` / `.csv`. Semua kelas menerima prediksi (tidak ada kelas tanpa prediksi); `zero_division=0` dipakai untuk kasus tersebut.

## Dampak kebocoran label (eksperimen pembanding)
Dengan `Height`+`Weight` sebagai fitur (hanya referensi, `ml/results_reference_with_height_weight/`, time_limit 300 dtk): accuracy 0.9593, Macro F1 **0.9580** vs **0.8692** tanpa keduanya. Selisih ±8.9 poin itu mencerminkan informasi BMI yang secara definisi membentuk label, bukan kemampuan model mempelajari kebiasaan hidup. Model referensi tidak dipakai di aplikasi.

## Analisis sensitivitas (indikatif)
Pada 103 baris test yang kemungkinan asli (bukan SMOTE; heuristik): accuracy 0.670, Macro F1 0.535. Subset ini sangat timpang (didominasi Normal_Weight) sehingga hanya indikatif; skor yang lebih rendah di sini sejalan dengan kekhawatiran bahwa skor seluruh test set optimistis, tetapi tidak membuktikannya.

## Keterbatasan dan bias
- Dataset sebagian besar sintetis dan berasal dari Meksiko, Peru, Kolombia (usia 14–61, mayoritas muda): generalisasi ke populasi lain tidak terjamin.
- Baris SMOTE yang mirip dapat tersebar di fit/validasi/test → skor optimistis.
- Satu split & satu seed; tidak ada interval kepercayaan. Hasil dapat berubah antar run/versi library.
- Skala ordinal (FCVC, NCP, dll.) berasal dari kuesioner dan bukan ukuran klinis.
- Tidak ada refit pada seluruh data pengembangan (agar model deployment = model yang dievaluasi).

## Reproduksibilitas
Training dijalankan ulang pada salinan terpisah dengan perintah yang sama (`--time-limit 600`, seed 42, mesin/versi library yang sama): split train/validasi/test **identik byte-per-byte**, leaderboard validasi, metrik test, dan 418 prediksi test **identik**. Hasil ini hanya menjamin reproduksi pada lingkungan yang sama; CPU/versi library/`--time-limit` yang berbeda dapat memberi hasil berbeda.

## Catatan artefak model
Setelah evaluasi, model dasar yang tidak dipakai WeightedEnsemble_L2 (bobot: LightGBMXT 0,444; CatBoost 0,222; ExtraTreesEntr 0,222; XGBoost 0,111) dibuang dari folder model untuk mengecilkan ukuran distribusi; prediksi identik dengan yang dievaluasi (diuji di `tests/test_ml_pipeline.py`). Leaderboard penuh tetap di `leaderboard_validation.csv`. Daftar versi paket ada di `environment_versions.txt` (bukan `pip freeze` penuh karena venv pengujian tidak memiliki pip).
