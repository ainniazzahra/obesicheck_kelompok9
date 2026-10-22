import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ML_DIR = ROOT / "ml"
MODEL_PATH = Path(os.getenv("OBESICHECK_MODEL_PATH", ML_DIR / "models" / "ObesiCheckPredictor"))
RESULTS_DIR = Path(os.getenv("OBESICHECK_RESULTS_DIR", ML_DIR / "results"))
DB_PATH = Path(os.getenv("OBESICHECK_DB_PATH", ROOT / "backend" / "database" / "obesicheck.db"))

CORS_ORIGINS = [o.strip() for o in os.getenv(
    "OBESICHECK_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
