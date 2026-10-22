import json

import pandas as pd
import pytest
import app.db.database as database
from app.core.config import MODEL_PATH, RESULTS_DIR
from app.schemas.prediction import MODEL_FIELDS
from app.services.model_service import service
from conftest import make_user

VALID = {"Gender": "Female", "Age": 21, "family_history_with_overweight": "yes", "FAVC": "yes", "FCVC": 2, "NCP": 3,
         "CAEC": "Sometimes", "SMOKE": "no", "CH2O": 2, "SCC": "no", "FAF": 1, "TUE": 1, "CALC": "Sometimes",
         "MTRANS": "Public_Transportation"}
needs_model = pytest.mark.skipif(not service.load().ready, reason="Integrasi model nyata memerlukan AutoGluon terpasang dan artefak model berhasil dimuat")


def test_health(anon):
    r = anon.get("/api/health"); assert r.status_code == 200 and r.json()["ok"] is True


def test_schema_matches_model_features():
    assert set(MODEL_FIELDS) == set(json.loads((RESULTS_DIR / "model_info.json").read_text())["features"])


@needs_model
def test_status_and_evaluation(client):
    s = client.get("/api/model/status").json(); assert s["trained"] and len(s["classes"]) == 7
    e = client.get("/api/evaluation").json(); assert e["available"] and e["leaderboard_validation"] and "macro_f1" in e


@needs_model
def test_valid_prediction_uses_saved_model(client):
    r = client.post("/api/predictions", json={**VALID, "Height": 1.65, "Weight": 65})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["predicted_class"] in service.info["classes"]
    assert sum(b["probabilities"].values()) == pytest.approx(1, abs=1e-4)
    assert max(b["probabilities"], key=b["probabilities"].get) == b["predicted_class"]  # pemetaan probabilitas -> label benar
    direct = service.predictor.predict(pd.DataFrame([VALID])[service.info["features"]]).iloc[0]
    assert b["predicted_class"] == direct
    assert b["bmi_indicator"]["bmi"] == pytest.approx(23.9, abs=0.1) and b["recommendations"]
    # Height/Weight tidak memengaruhi prediksi model
    r2 = client.post("/api/predictions", json={**VALID, "Height": 1.5, "Weight": 120}).json()
    assert r2["probabilities"] == b["probabilities"]


@pytest.mark.parametrize("patch", [{"Age": 5}, {"Age": "abc"}, {"Gender": "X"}, {"CAEC": "Kadang"}, {"FCVC": 9}, {"extra": 1}, {"Height": 5.0, "Weight": 60}])
def test_invalid_inputs_rejected(client, patch):
    assert client.post("/api/predictions", json={**VALID, **patch}).status_code == 422


def test_missing_field_rejected(client):
    body = {k: v for k, v in VALID.items() if k != "FAF"}
    assert client.post("/api/predictions", json=body).status_code == 422


def test_model_unavailable_returns_503_without_fallback(client, monkeypatch):
    monkeypatch.setattr(service, "predictor", None); monkeypatch.setattr(service, "error", "Model belum dilatih.")
    r = client.post("/api/predictions", json=VALID)
    assert r.status_code == 503 and "predicted_class" not in r.json()


@needs_model
def test_internal_error_does_not_leak_details(client, monkeypatch):
    class Boom:
        def predict_proba(self, *_a, **_k): raise RuntimeError("SECRET /srv/path password=hunter2")
    monkeypatch.setattr(service, "predictor", Boom())
    r = client.post("/api/predictions", json=VALID)
    assert r.status_code == 500 and "hunter2" not in r.text and "/srv/path" not in r.text


@needs_model
def test_history_crud(client):
    rid = client.post("/api/predictions", json=VALID).json()["id"]
    assert any(h["id"] == rid for h in client.get("/api/history").json())
    assert client.delete(f"/api/history/{rid}").status_code == 200
    assert client.delete(f"/api/history/{rid}").status_code == 404


# ---------- Tes regresi untuk bug hasil audit ----------
import sqlite3  # noqa: E402


@pytest.mark.parametrize("extra", [{"Height": 1.7}, {"Weight": 70}])
def test_regression_height_weight_must_be_given_together(client, extra):
    r = client.post("/api/predictions", json={**VALID, **extra})
    assert r.status_code == 422 and "bersamaan" in r.text  # sebelumnya 200 dengan BMI hilang diam-diam


def test_regression_nan_body_is_422_not_500(client):
    r = client.post("/api/predictions", content='{"Age": NaN}', headers={"Content-Type": "application/json"})
    assert r.status_code == 422  # sebelumnya 500 karena body galat memantulkan NaN


def test_validation_errors_do_not_echo_raw_input(client):
    r = client.post("/api/predictions", json={**VALID, "Gender": "<script>alert(1)</script>"})
    assert r.status_code == 422 and "<script>" not in r.text and all("input" not in d for d in r.json()["detail"])


def test_regression_numeric_string_rejected(client):
    assert client.post("/api/predictions", json={**VALID, "Age": "21"}).status_code == 422  # sebelumnya dikoersi diam-diam


def test_regression_history_id_bounds(client):
    assert client.delete("/api/history/99999999999999999999").status_code == 422  # sebelumnya 500 (OverflowError sqlite)
    assert client.delete("/api/history/0").status_code == 422
    assert client.delete("/api/history/9223372036854775807").status_code == 404


@needs_model
def test_regression_prediction_survives_history_failure(client, monkeypatch):
    import app.main as m

    def boom(*_a, **_k): raise sqlite3.OperationalError("disk I/O error /secret/path")
    monkeypatch.setattr(m, "add_prediction", boom)
    r = client.post("/api/predictions", json=VALID)
    assert r.status_code == 200 and r.json()["history_saved"] is False and r.json()["id"] is None  # sebelumnya 500
    assert "secret" not in r.text
    monkeypatch.setattr(m, "get_history", boom)
    h = client.get("/api/history")
    assert h.status_code == 503 and "secret" not in h.text


def test_regression_db_recreated_if_deleted_at_runtime(anon):
    anon.headers.update(make_user(anon, "pengguna1"))
    database.DB_PATH.unlink()
    assert anon.get("/api/history").status_code == 401  # DB baru -> akun lama tidak ada -> sesi tidak valid (sebelumnya 500 "no such table")
    anon.headers.update(make_user(anon, "pengguna1"))  # DB dibuat ulang otomatis; registrasi ulang berhasil
    assert anon.get("/api/history").status_code == 200


def test_regression_db_connections_are_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "c.db")
    made = []
    real = sqlite3.connect
    monkeypatch.setattr(database.sqlite3, "connect", lambda *a, **k: made.append(real(*a, **k)) or made[-1])
    database.init_db(); u = database.create_user("u1", "u1@x.id", "h")
    database.add_prediction(u["id"], "X", "v", {"a": 1}, {"X": 1.0}); database.get_history(u["id"]); database.delete_history(1, u["id"])
    assert len(made) == 5
    for c in made:
        with pytest.raises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")  # koneksi harus sudah tertutup


def test_regression_evaluation_tolerates_corrupt_results(client, tmp_path, monkeypatch):
    import app.main as m
    (tmp_path / "metrics.json").write_text("{broken")
    monkeypatch.setattr(m, "RESULTS_DIR", tmp_path)
    r = client.get("/api/evaluation")
    assert r.status_code == 200 and r.json()["available"] is False  # sebelumnya 500


@needs_model
def test_evaluation_reports_whether_metrics_match_loaded_model(client, monkeypatch):
    e = client.get("/api/evaluation").json()
    assert e["model_loaded"] is True and e["metrics_match_loaded_model"] is True
    monkeypatch.setattr(service, "predictor", None)
    assert client.get("/api/evaluation").json()["model_loaded"] is False
