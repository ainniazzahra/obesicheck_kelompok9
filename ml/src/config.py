"""Konfigurasi eksperimen ObesiCheck (satu sumber kebenaran untuk training dan audit)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "ml" / "data" / "ObesityDataSet_raw_and_data_sinthetic.csv"
MODEL_DIR = ROOT / "ml" / "models" / "ObesiCheckPredictor"
RESULTS_DIR = ROOT / "ml" / "results"
REFERENCE_MODEL_DIR = ROOT / "ml" / "models_reference" / "WithHeightWeight"
REFERENCE_RESULTS_DIR = ROOT / "ml" / "results_reference_with_height_weight"

TARGET = "NObeyesdad"
RANDOM_SEED = 42
TEST_SIZE = 0.20          # 80:20 stratified split (test disimpan terpisah)
VALIDATION_SIZE = 0.20    # porsi dari 80% data pengembangan -> validasi internal (64/16 dari total)
EVAL_METRIC = "f1_macro"  # metrik utama pemilihan model
DEFAULT_PRESET = "medium_quality"
DEFAULT_TIME_LIMIT = 600

# Skema dataset sumber (urutan kolom persis seperti file).
ALL_COLUMNS = ["Gender", "Age", "Height", "Weight", "family_history_with_overweight", "FAVC", "FCVC",
               "NCP", "CAEC", "SMOKE", "CH2O", "SCC", "FAF", "TUE", "CALC", "MTRANS", TARGET]

# Height & Weight membentuk BMI, dan label dataset didefinisikan dari BMI -> kebocoran label.
LEAKAGE_COLUMNS = ["Height", "Weight"]
FEATURES = [c for c in ALL_COLUMNS if c not in LEAKAGE_COLUMNS + [TARGET]]
FEATURES_WITH_ANTHROPOMETRY = [c for c in ALL_COLUMNS if c != TARGET]

CATEGORICAL = {
    "Gender": ["Female", "Male"],
    "family_history_with_overweight": ["yes", "no"],
    "FAVC": ["yes", "no"],
    "CAEC": ["no", "Sometimes", "Frequently", "Always"],
    "SMOKE": ["yes", "no"],
    "SCC": ["yes", "no"],
    "CALC": ["no", "Sometimes", "Frequently", "Always"],
    "MTRANS": ["Public_Transportation", "Automobile", "Walking", "Motorbike", "Bike"],
}
NUMERIC_RANGES = {  # rentang valid (min, max) yang juga dipakai skema API
    "Age": (14, 100), "Height": (1.2, 2.3), "Weight": (25, 300),
    "FCVC": (1, 3), "NCP": (1, 4), "CH2O": (1, 3), "FAF": (0, 3), "TUE": (0, 2),
}
ORDINAL_SCALE_COLUMNS = ["FCVC", "NCP", "CH2O", "FAF", "TUE"]
