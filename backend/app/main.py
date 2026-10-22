import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pandas as pd
import jwt
from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import CORS_ORIGINS, RESULTS_DIR
from app.core.security import TOKEN_TTL_SECONDS, create_token, decode_token, hash_password, limiter, verify_password
from app.db import database as db
from app.db.database import DuplicateUser, add_prediction, delete_history, get_history, init_db
from app.schemas.auth import LoginInput, RegisterInput
from app.schemas.prediction import MODEL_FIELDS, PredictionInput
from app.services.bmi import bmi_info
from app.services.model_service import ModelUnavailable, service
from app.services.recommendations import recommendations

log = logging.getLogger("obesicheck")
DISCLAIMER = "Hasil merupakan estimasi berbasis dataset, bukan diagnosis medis."


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    service.load()  # model dimuat sekali saat startup, bukan per permintaan
    yield


app = FastAPI(title="ObesiCheck API", version="2.0.0", lifespan=lifespan,
              description="API estimasi tingkat obesitas (AutoGluon Tabular) berbasis dataset; bukan diagnosis medis.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization"])


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    """422 yang aman di-serialisasi: tidak memantulkan input mentah (mis. NaN tidak valid sebagai JSON)."""
    errors = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "")).removeprefix("Value error, "), "type": e.get("type")}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Kesalahan tidak tertangani", exc_info=exc)  # detail hanya di log server
    return JSONResponse(status_code=500, content={"detail": "Terjadi kesalahan internal pada server."})


bearer = HTTPBearer(auto_error=False)
AUTH_REQUIRED = HTTPException(status_code=401, detail="Autentikasi diperlukan atau sesi tidak valid. Silakan masuk kembali.",
                              headers={"WWW-Authenticate": "Bearer"})


def _claims(creds: HTTPAuthorizationCredentials | None) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AUTH_REQUIRED
    try:
        claims = decode_token(creds.credentials)
        if not str(claims["sub"]).isdigit():
            raise AUTH_REQUIRED
        if db.is_revoked(claims["jti"]):
            raise AUTH_REQUIRED
    except jwt.PyJWTError:
        raise AUTH_REQUIRED from None
    except sqlite3.Error:
        log.exception("Gagal memeriksa sesi")
        raise HTTPException(status_code=503, detail="Database pengguna tidak dapat diakses.") from None
    return claims


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    claims = _claims(creds)
    try:
        user = db.get_user(int(claims["sub"]))
    except sqlite3.Error:
        log.exception("Gagal membaca pengguna")
        raise HTTPException(status_code=503, detail="Database pengguna tidak dapat diakses.") from None
    if user is None:  # akun sudah tidak ada
        raise AUTH_REQUIRED
    return {**user, "_claims": claims}


def public_user(u: dict) -> dict:
    return {k: u[k] for k in ("id", "username", "email", "created_at")}


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterInput):
    try:
        user = db.create_user(payload.username, payload.email, hash_password(payload.password))
    except DuplicateUser:
        raise HTTPException(status_code=409, detail="Username atau email sudah terdaftar.") from None
    except sqlite3.Error:
        log.exception("Registrasi gagal")
        raise HTTPException(status_code=503, detail="Database pengguna tidak dapat diakses.") from None
    return {"user": public_user(user)}


@app.post("/api/auth/login")
def login(payload: LoginInput, request: Request):
    ident = payload.identifier.lower()
    ip = request.client.host if request.client else "unknown"
    keys = (f"user:{ident}", f"ip:{ip}")
    wait = limiter.retry_after(*keys)
    if wait:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan masuk. Coba lagi nanti.", headers={"Retry-After": str(wait)})
    try:
        user = db.get_user_by_login(payload.identifier)
    except sqlite3.Error:
        log.exception("Login gagal membaca pengguna")
        raise HTTPException(status_code=503, detail="Database pengguna tidak dapat diakses.") from None
    if not verify_password(user["password_hash"] if user else None, payload.password):
        limiter.fail(*keys)
        raise HTTPException(status_code=401, detail="Username/email atau password salah.")  # pesan sama untuk akun tak ada / password salah
    limiter.reset(keys[0])
    token, _, _ = create_token(user["id"])
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_TTL_SECONDS, "user": public_user(user)}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user)}


@app.post("/api/auth/logout")
def logout(user: dict = Depends(current_user)):
    try:
        db.revoke_token(user["_claims"]["jti"], user["_claims"]["exp"])
    except sqlite3.Error:
        log.exception("Logout gagal mencabut token")
        raise HTTPException(status_code=503, detail="Database pengguna tidak dapat diakses.") from None
    return {"logged_out": True}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "ObesiCheck API", "model_loaded": service.ready}


@app.get("/api/model/status")
def model_status():
    return service.status()


def _read_json(name):
    p = RESULTS_DIR / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.exception("File hasil rusak: %s", name)
        return None


@app.get("/api/evaluation")
def evaluation():
    metrics = _read_json("metrics.json")
    if metrics is None:
        return {"available": False, "message": "Metrik evaluasi belum tersedia atau tidak dapat dibaca. Latih model terlebih dahulu."}
    manifest, config = _read_json("split_manifest.json") or {}, _read_json("experiment_config.json") or {}
    lb_path = RESULTS_DIR / "leaderboard_validation.csv"
    leaderboard = []
    if lb_path.exists():
        try:
            lb = pd.read_csv(lb_path)
            leaderboard = lb[["model", "score_val", "fit_time"]].rename(columns={"score_val": "validation_macro_f1"}).round(4).to_dict("records")
        except Exception:
            log.exception("Leaderboard tidak dapat dibaca")
    return {"available": True, "model_loaded": service.ready,
            "metrics_match_loaded_model": service.ready and service.info.get("model_version") == config.get("model_version"), **metrics, "leaderboard_validation": leaderboard,
            "split": {k: manifest.get(k) for k in ("rows_original", "exact_duplicate_rows_removed", "rows_after_dedup",
                                                    "train_fit_rows", "validation_rows", "test_rows", "class_distribution")},
            "experiment": {k: config.get(k) for k in ("model_version", "features", "eval_metric", "validation_strategy",
                                                      "autogluon_preset", "autogluon_time_limit_seconds", "random_seed")}}


@app.post("/api/predictions")
def create_prediction(payload: PredictionInput, user: dict = Depends(current_user)):
    data = payload.model_dump()
    try:
        pred, probs = service.predict({k: data[k] for k in MODEL_FIELDS})
    except ModelUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except Exception:
        log.exception("Prediksi gagal")
        raise HTTPException(status_code=500, detail="Prediksi gagal diproses. Periksa log server.") from None
    recs = recommendations(data)
    version = service.info.get("model_version")
    stored = {k: data[k] for k in MODEL_FIELDS}  # data BMI opsional tidak disimpan
    try:
        rid, created = add_prediction(user["id"], pred, version, stored, probs)
        history_saved = True
    except sqlite3.Error:  # prediksi sudah berhasil; kegagalan riwayat dilaporkan terang-terangan, bukan disembunyikan
        log.exception("Riwayat gagal disimpan")
        rid, created, history_saved = None, datetime.now(timezone.utc).isoformat(), False
    return {"id": rid, "history_saved": history_saved, "created_at": created, "predicted_class": pred, "probabilities": probs,
            "model_version": version, "bmi_indicator": bmi_info(data["Height"], data["Weight"], data["Age"]),
            "recommendations": recs, "disclaimer": DISCLAIMER}


HISTORY_ERROR = "Database riwayat tidak dapat diakses. Periksa izin dan lokasi file database."


@app.get("/api/history")
def history(user: dict = Depends(current_user)):
    try:
        return get_history(user["id"])
    except sqlite3.Error:
        log.exception("Gagal membaca riwayat")
        raise HTTPException(status_code=503, detail=HISTORY_ERROR) from None


@app.delete("/api/history/{record_id}")
def remove_history(record_id: int = Path(ge=1, le=2**63 - 1), user: dict = Depends(current_user)):
    try:
        deleted = delete_history(record_id, user["id"])
    except sqlite3.Error:
        log.exception("Gagal menghapus riwayat")
        raise HTTPException(status_code=503, detail=HISTORY_ERROR) from None
    if not deleted:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan")  # juga untuk riwayat milik akun lain
    return {"deleted": True, "id": record_id}
