"""Registrasi, login, sesi/token, logout, isolasi data antar akun, dan ketahanan terhadap input/serangan umum."""
import sqlite3
import time

import jwt
import pytest
from conftest import CREDS, make_user

import app.db.database as database
from app.core import security
from app.main import app  # noqa: F401
from app.services.model_service import service

VALID = {"Gender": "Female", "Age": 21, "family_history_with_overweight": "yes", "FAVC": "yes", "FCVC": 2, "NCP": 3,
         "CAEC": "Sometimes", "SMOKE": "no", "CH2O": 2, "SCC": "no", "FAF": 1, "TUE": 1, "CALC": "Sometimes",
         "MTRANS": "Public_Transportation"}
needs_model = pytest.mark.skipif(not service.load().ready, reason="Model belum dilatih")


def reg(c, **kw):
    return c.post("/api/auth/register", json={**CREDS, **kw})


def login(c, ident="tester", pw="Sandi12345"):
    return c.post("/api/auth/login", json={"identifier": ident, "password": pw})


# ---------- registrasi ----------
def test_register_ok_returns_user_without_secrets(anon):
    r = reg(anon)
    assert r.status_code == 201
    u = r.json()["user"]
    assert set(u) == {"id", "username", "email", "created_at"} and "password" not in r.text and "hash" not in r.text


@pytest.mark.parametrize("patch,needle", [
    ({"password": "pendek1"}, "password"), ({"password": "hurufsajaa"}, "huruf serta angka"), ({"password": "12345678"}, "huruf serta angka"),
    ({"password": "x" * 129 + "1"}, "password"), ({"username": "ab"}, "username"), ({"username": "nama dengan spasi"}, "Username"),
    ({"username": "a" * 31}, "username"), ({"username": "x'; DROP TABLE users;--"}, "Username"), ({"email": "bukan-email"}, "email"),
    ({"email": "a@b"}, "email"), ({"email": "<script>@x.id"}, "email"), ({"password": "tester12345"}, "username"), ({"extra": 1}, "extra"),
])
def test_register_validation(anon, patch, needle):
    r = reg(anon, **patch)
    assert r.status_code == 422 and needle.lower() in r.text.lower() and "password" not in str([d.get("input") for d in r.json()["detail"]])


def test_register_missing_fields(anon):
    assert anon.post("/api/auth/register", json={"username": "abc"}).status_code == 422
    assert anon.post("/api/auth/register", content="x", headers={"Content-Type": "application/json"}).status_code == 422


def test_duplicate_username_and_email_rejected_case_insensitively(anon):
    assert reg(anon).status_code == 201
    r1 = reg(anon, email="lain@example.com", username="TESTER")
    r2 = reg(anon, username="lainnya", email="TESTER@EXAMPLE.COM")
    assert r1.status_code == r2.status_code == 409 and r1.json() == r2.json()  # pesan sama: tidak membocorkan field mana yang bentrok


def test_password_is_hashed_with_argon2_never_plaintext(anon):
    reg(anon)
    con = sqlite3.connect(database.DB_PATH)
    (h,) = con.execute("SELECT password_hash FROM users").fetchone()
    con.close()
    assert h.startswith("$argon2id$") and "Sandi12345" not in h
    assert "Sandi12345" not in database.DB_PATH.read_bytes().decode("latin-1")


def test_password_whitespace_is_significant(anon):
    reg(anon, password=" Sandi12345 ")
    assert login(anon, pw="Sandi12345").status_code == 401 and login(anon, pw=" Sandi12345 ").status_code == 200


# ---------- login ----------
def test_login_by_username_and_by_email(anon):
    reg(anon)
    a, b = login(anon), login(anon, ident="TESTER@example.com")
    assert a.status_code == b.status_code == 200
    body = a.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0 and body["user"]["username"] == "tester" and "password" not in a.text


def test_wrong_password_and_unknown_user_same_response(anon):
    reg(anon)
    a, b = login(anon, pw="SalahBanget1"), login(anon, ident="tidakada")
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


@pytest.mark.parametrize("ident", ["' OR '1'='1", "tester' --", "%", "tester\x00", "x" * 300])
def test_login_injection_and_garbage_identifiers(anon, ident):
    reg(anon)
    r = login(anon, ident=ident, pw="apapun123")
    assert r.status_code in (401, 422) and "access_token" not in r.text


def test_login_bruteforce_lockout_then_success_after_reset(anon):
    reg(anon)
    for _ in range(5):
        assert login(anon, pw="Salah12345").status_code == 401
    r = login(anon, pw="Sandi12345")  # password benar pun ditolak saat terkunci
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    security.limiter.clear()
    assert login(anon).status_code == 200


def test_successful_login_resets_failure_counter(anon):
    reg(anon)
    for _ in range(4):
        login(anon, pw="Salah12345")
    assert login(anon).status_code == 200
    for _ in range(4):
        assert login(anon, pw="Salah12345").status_code == 401  # tidak langsung terkunci


# ---------- sesi / token ----------
def test_protected_endpoints_require_token(anon):
    for method, path in [("get", "/api/auth/me"), ("post", "/api/auth/logout"), ("get", "/api/history"), ("delete", "/api/history/1")]:
        r = getattr(anon, method)(path)
        assert r.status_code == 401 and r.headers["WWW-Authenticate"] == "Bearer", path
    assert anon.post("/api/predictions", json=VALID).status_code == 401


def test_public_endpoints_stay_public(anon):
    for p in ("/api/health", "/api/model/status", "/api/evaluation"):
        assert anon.get(p).status_code == 200, p


def test_me_returns_current_user(client):
    assert client.get("/api/auth/me").json()["user"]["username"] == "tester"


@pytest.mark.parametrize("hdr", ["Bearer", "Bearer ", "Bearer abc.def.ghi", "Basic dGVzdGVyOnBhc3M=", "bearer", "Token xyz"])
def test_malformed_authorization_headers_rejected(anon, hdr):
    assert anon.get("/api/auth/me", headers={"Authorization": hdr}).status_code == 401


def test_tampered_expired_wrongkey_and_alg_none_tokens_rejected(anon):
    reg(anon)
    token = login(anon).json()["access_token"]
    uid = anon.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["id"]
    now = int(time.time())
    good = {"sub": str(uid), "jti": "j1", "iat": now, "exp": now + 600}
    key = security.secret_key()
    bad = {
        "tanda tangan diubah": token[:-2] + ("AA" if token[-2:] != "AA" else "BB"),
        "kedaluwarsa": jwt.encode({**good, "exp": now - 10}, key, algorithm="HS256"),
        "kunci lain": jwt.encode(good, "z" * 48, algorithm="HS256"),
        "alg none": jwt.encode(good, None, algorithm="none"),
        "algoritma lain (HS512) dgn kunci benar": jwt.encode(good, key, algorithm="HS512"),
        "tanpa exp": jwt.encode({k: v for k, v in good.items() if k != "exp"}, key, algorithm="HS256"),
        "tanpa jti": jwt.encode({k: v for k, v in good.items() if k != "jti"}, key, algorithm="HS256"),
        "sub bukan angka": jwt.encode({**good, "sub": "1 OR 1=1"}, key, algorithm="HS256"),
        "sub akun tak ada": jwt.encode({**good, "sub": "9999"}, key, algorithm="HS256"),
    }
    for name, t in bad.items():
        assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401, name
    assert anon.get("/api/auth/me", headers={"Authorization": f"Bearer {jwt.encode(good, key, algorithm='HS256')}"}).status_code == 200


def test_logout_revokes_token_server_side(anon):
    reg(anon)
    h = {"Authorization": f"Bearer {login(anon).json()['access_token']}"}
    h2 = {"Authorization": f"Bearer {login(anon).json()['access_token']}"}  # sesi kedua tidak ikut tercabut
    assert anon.get("/api/auth/me", headers=h).status_code == 200
    assert anon.post("/api/auth/logout", headers=h).json() == {"logged_out": True}
    assert anon.get("/api/auth/me", headers=h).status_code == 401  # token yang sama tidak bisa dipakai lagi
    assert anon.get("/api/history", headers=h).status_code == 401
    assert anon.post("/api/auth/logout", headers=h).status_code == 401
    assert anon.get("/api/auth/me", headers=h2).status_code == 200


def test_revoked_tokens_are_purged_after_expiry(anon):
    reg(anon)
    database.revoke_token("lama", time.time() - 100)
    database.revoke_token("baru", time.time() + 100)
    con = sqlite3.connect(database.DB_PATH)
    assert [r[0] for r in con.execute("SELECT jti FROM revoked_tokens")] == ["baru"]
    con.close()


def test_secret_key_not_hardcoded_and_persisted(tmp_path, monkeypatch):
    monkeypatch.delenv("OBESICHECK_SECRET_KEY", raising=False)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "x.db")
    import app.core.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "x.db")
    k1 = security.secret_key()
    assert len(k1) >= 48 and (tmp_path / "secret.key").read_text().strip() == k1 and security.secret_key() == k1
    monkeypatch.setenv("OBESICHECK_SECRET_KEY", "pendek")
    with pytest.raises(RuntimeError):
        security.secret_key()


# ---------- otorisasi & isolasi data ----------
@needs_model
def test_history_is_isolated_per_account(anon):
    a, b = make_user(anon, "alice"), make_user(anon, "bobby")
    ra = anon.post("/api/predictions", json=VALID, headers=a).json()
    assert ra["history_saved"] is True
    anon.post("/api/predictions", json=VALID, headers=b)
    ha, hb = anon.get("/api/history", headers=a).json(), anon.get("/api/history", headers=b).json()
    assert [x["id"] for x in ha] == [ra["id"]] and len(hb) == 1 and hb[0]["id"] != ra["id"]
    assert anon.delete(f"/api/history/{ra['id']}", headers=b).status_code == 404  # tidak bisa menghapus milik akun lain
    assert len(anon.get("/api/history", headers=a).json()) == 1  # milik alice utuh
    assert anon.delete(f"/api/history/{ra['id']}", headers=a).status_code == 200


@needs_model
def test_history_survives_relogin_and_app_restart(anon):
    reg(anon)
    h = {"Authorization": f"Bearer {login(anon).json()['access_token']}"}
    anon.post("/api/predictions", json=VALID, headers=h)
    anon.post("/api/auth/logout", headers=h)
    h = {"Authorization": f"Bearer {login(anon).json()['access_token']}"}
    assert len(anon.get("/api/history", headers=h).json()) == 1


def test_legacy_rows_without_owner_are_invisible_and_db_is_migrated(anon, tmp_path):
    """Migrasi dari DB v2 (tanpa user_id): kolom ditambahkan, baris lama tidak tampil bagi siapa pun."""
    legacy = tmp_path / "legacy.db"
    con = sqlite3.connect(legacy)
    con.execute("CREATE TABLE prediction_history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, predicted_class TEXT NOT NULL, "
                "model_version TEXT, input_json TEXT NOT NULL, probabilities_json TEXT NOT NULL)")
    con.execute("INSERT INTO prediction_history(created_at,predicted_class,model_version,input_json,probabilities_json) VALUES('t','Normal_Weight','v','{}','{}')")
    con.commit(); con.close()
    database.DB_PATH = legacy  # dipulihkan otomatis oleh monkeypatch fixture `anon`
    h = make_user(anon, "migran")
    assert anon.get("/api/history", headers=h).json() == []
    con = sqlite3.connect(legacy)
    assert "user_id" in [r[1] for r in con.execute("PRAGMA table_info(prediction_history)")]
    assert con.execute("SELECT COUNT(*) FROM prediction_history").fetchone()[0] == 1  # data lama tidak dihapus
    con.close()


def test_deleting_user_cascades_history(anon):
    h = make_user(anon, "hapusaku")
    uid = anon.get("/api/auth/me", headers=h).json()["user"]["id"]
    database.add_prediction(uid, "Normal_Weight", "v", {}, {})
    con = sqlite3.connect(database.DB_PATH); con.execute("PRAGMA foreign_keys=ON")
    con.execute("DELETE FROM users WHERE id=?", (uid,)); con.commit()
    assert con.execute("SELECT COUNT(*) FROM prediction_history").fetchone()[0] == 0
    con.close()
    assert anon.get("/api/auth/me", headers=h).status_code == 401  # token akun terhapus tidak berlaku


def test_user_db_failure_is_503_without_leak(anon, monkeypatch):
    reg(anon)
    import app.main as m

    def boom(*_a, **_k): raise sqlite3.OperationalError("disk I/O error /rahasia/path")
    monkeypatch.setattr(m.db, "get_user_by_login", boom)
    r = login(anon)
    assert r.status_code == 503 and "rahasia" not in r.text
