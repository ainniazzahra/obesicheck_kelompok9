"""Pembacaan, validasi, dan audit dataset."""
import numpy as np
import pandas as pd
from config import ALL_COLUMNS, TARGET, CATEGORICAL, NUMERIC_RANGES, ORDINAL_SCALE_COLUMNS, DATA_PATH


def load_raw(path=DATA_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {path}")
    df = pd.read_csv(path)
    df.insert(0, "source_row_id", np.arange(len(df)))  # identitas baris sumber untuk uji overlap
    return df


def validate_schema(df: pd.DataFrame) -> dict:
    """Validasi skema, tipe, nilai kosong, kategori dan rentang. Melempar ValueError bila fatal."""
    cols = [c for c in df.columns if c != "source_row_id"]
    if cols != ALL_COLUMNS:
        raise ValueError(f"Skema dataset tidak sesuai. Hilang={set(ALL_COLUMNS)-set(cols)}; Lebih={set(cols)-set(ALL_COLUMNS)}")
    problems = []
    missing = df[ALL_COLUMNS].isna().sum()
    if missing.sum():
        problems.append(f"Nilai kosong: {missing[missing > 0].to_dict()}")
    for col, allowed in CATEGORICAL.items():
        bad = sorted(set(df[col].dropna().unique()) - set(allowed))
        if bad:
            problems.append(f"Kategori tidak dikenal di {col}: {bad}")
    for col, (lo, hi) in NUMERIC_RANGES.items():
        if not pd.api.types.is_numeric_dtype(df[col]):
            problems.append(f"Kolom {col} bukan numerik")
            continue
        n_bad = int(((df[col] < lo) | (df[col] > hi)).sum())
        if n_bad:
            problems.append(f"{n_bad} nilai {col} di luar rentang [{lo}, {hi}]")
    if df[TARGET].isna().any() or df[TARGET].nunique() < 2:
        problems.append("Target kosong atau hanya memiliki satu kelas")
    if problems:
        raise ValueError("Validasi dataset gagal: " + " | ".join(problems))
    return {"missing_values": missing.to_dict(), "problems": problems}


def likely_original_mask(df: pd.DataFrame) -> pd.Series:
    """Heuristik: baris asli survei memiliki skala ordinal & usia bulat dan tinggi 2 desimal;
    baris hasil SMOTE umumnya berisi pecahan. Hanya untuk analisis sensitivitas, BUKAN pelabelan pasti."""
    ints = df[ORDINAL_SCALE_COLUMNS].apply(lambda s: np.isclose(s % 1, 0)).all(axis=1)
    age_int = np.isclose(df["Age"] % 1, 0)
    height_2dp = np.isclose((df["Height"] * 100) % 1, 0, atol=1e-6) | np.isclose((df["Height"] * 100) % 1, 1, atol=1e-6)
    return ints & age_int & height_2dp


def bmi_rule_label(bmi: pd.Series) -> pd.Series:
    """Kelas dari ambang BMI WHO (Overweight I/II digabung) untuk menguji kebocoran label."""
    return pd.Series(np.select([bmi < 18.5, bmi < 25, bmi < 30, bmi < 35, bmi < 40],
                               ["Insufficient_Weight", "Normal_Weight", "Overweight", "Obesity_Type_I", "Obesity_Type_II"],
                               default="Obesity_Type_III"), index=bmi.index)
