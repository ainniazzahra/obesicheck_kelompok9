import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "ml" / "src"))

CREDS = {"username": "tester", "email": "tester@example.com", "password": "Sandi12345"}


def make_user(c, username, password="Sandi12345"):  # noqa: S107 (kata sandi uji)
    """Daftarkan akun lalu masuk; kembalikan header Authorization."""
    r = c.post("/api/auth/register", json={"username": username, "email": f"{username}@example.com", "password": password})
    assert r.status_code == 201, r.text
    r = c.post("/api/auth/login", json={"identifier": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def anon(tmp_path, monkeypatch):
    """Klien tanpa login dengan DB sementara terpisah (tidak menyentuh data pengguna)."""
    from fastapi.testclient import TestClient

    import app.db.database as database
    from app.core.security import limiter
    from app.main import app
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("OBESICHECK_SECRET_KEY", "k" * 48)
    limiter.clear()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    limiter.clear()


@pytest.fixture()
def client(anon):
    """Klien yang sudah login sebagai 'tester'."""
    anon.headers.update(make_user(anon, "tester"))
    return anon
