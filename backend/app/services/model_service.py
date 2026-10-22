"""Pemuatan dan inferensi model AutoGluon hasil training. Tidak ada fallback/prediksi buatan."""
import json
import logging
import pandas as pd

from app.core.config import MODEL_PATH, RESULTS_DIR

log = logging.getLogger("obesicheck.model")


class ModelUnavailable(RuntimeError):
    """Model tidak tersedia / gagal dimuat. Pesan aman ditampilkan ke pengguna."""


class ModelService:
    def __init__(self):
        self.predictor = None
        self.info: dict = {}
        self.error: str | None = None

    def load(self):
        self.predictor, self.info, self.error = None, {}, None
        info_path = RESULTS_DIR / "model_info.json"
        if not MODEL_PATH.exists() or not info_path.exists():
            self.error = "Model belum dilatih. Jalankan: python ml/src/train.py"
            return self
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            from autogluon.tabular import TabularPredictor
            predictor = TabularPredictor.load(str(MODEL_PATH))
            if list(predictor.features()) and set(predictor.features()) != set(info["features"]):
                raise ValueError("Fitur model tidak cocok dengan model_info.json")
            if predictor.model_best != info.get("best_model"):
                raise ValueError("Model terpilih tidak cocok dengan model_info.json")
            self.predictor, self.info = predictor, info
        except ModuleNotFoundError as exc:
            log.exception("Dependensi model tidak tersedia")
            if exc.name and exc.name.split(".")[0] == "autogluon":
                self.error = (
                    "Dependensi AutoGluon belum terpasang pada lingkungan Python aktif. "
                    "Aktifkan virtual environment proyek dan instal backend\\requirements.txt."
                )
            else:
                self.error = "Dependensi model tidak lengkap. Periksa instalasi backend\\requirements.txt."
        except Exception:
            log.exception("Gagal memuat model AutoGluon")  # detail hanya di log server
            self.error = "Model ditemukan tetapi gagal dimuat. Periksa versi dependensi dan log server sebelum melatih ulang."
        return self

    @property
    def ready(self) -> bool:
        return self.predictor is not None

    def status(self) -> dict:
        return {"trained": self.ready,
                "message": "Model AutoGluon tersedia dan siap digunakan." if self.ready else self.error,
                "model_version": self.info.get("model_version"), "best_model": self.info.get("best_model"),
                "features": self.info.get("features"), "classes": self.info.get("classes"),
                "metrics": self.info.get("metrics") if self.ready else None}

    def predict(self, payload: dict) -> tuple[str, dict]:
        if not self.ready:
            raise ModelUnavailable(self.error or "Model belum tersedia.")
        feats = self.info["features"]
        row = pd.DataFrame([{f: payload[f] for f in feats}], columns=feats)  # urutan kolom = urutan training
        proba = self.predictor.predict_proba(row).iloc[0]  # kolom = label kelas
        probs = {str(k): float(v) for k, v in proba.items()}
        pred = str(proba.idxmax())  # argmax dari probabilitas yang sama -> kelas & probabilitas selalu konsisten
        return pred, probs


service = ModelService()
