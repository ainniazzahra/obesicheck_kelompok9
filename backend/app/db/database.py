import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone

from app.core.config import DB_PATH

USERS_SCHEMA = ("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE COLLATE NOCASE, email TEXT NOT NULL UNIQUE COLLATE NOCASE, "
                "password_hash TEXT NOT NULL, created_at TEXT NOT NULL)")
HISTORY_SCHEMA = ("CREATE TABLE IF NOT EXISTS prediction_history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, "
                  "predicted_class TEXT NOT NULL, model_version TEXT, input_json TEXT NOT NULL, probabilities_json TEXT NOT NULL, "
                  "user_id INTEGER REFERENCES users(id) ON DELETE CASCADE)")
REVOKED_SCHEMA = "CREATE TABLE IF NOT EXISTS revoked_tokens (jti TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)"


@contextmanager
def connect():
    """Koneksi yang SELALU ditutup (penting di Windows agar file DB tidak terkunci), memastikan tabel ada
    (DB terhapus/belum diinisialisasi dibuat ulang) dan memigrasikan DB lama tanpa kolom user_id."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH, timeout=10)) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        with c:  # commit bila sukses, rollback bila gagal
            c.execute(USERS_SCHEMA)
            c.execute(HISTORY_SCHEMA)
            c.execute(REVOKED_SCHEMA)
            if "user_id" not in {r["name"] for r in c.execute("PRAGMA table_info(prediction_history)")}:
                # Migrasi v2 -> v3: riwayat lama tidak memiliki pemilik (NULL) sehingga tidak tampil bagi akun mana pun.
                c.execute("ALTER TABLE prediction_history ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
            yield c


def init_db():
    with connect():
        pass


# ---------- pengguna ----------
class DuplicateUser(Exception):
    pass


def create_user(username, email, password_hash):
    now = datetime.now(timezone.utc).isoformat()
    try:
        with connect() as c:
            cur = c.execute("INSERT INTO users(username,email,password_hash,created_at) VALUES(?,?,?,?)", (username, email, password_hash, now))
            return {"id": cur.lastrowid, "username": username, "email": email, "created_at": now}
    except sqlite3.IntegrityError as e:
        raise DuplicateUser from e


def get_user_by_login(identifier):
    with connect() as c:
        row = c.execute("SELECT * FROM users WHERE username=? OR email=? LIMIT 1", (identifier, identifier)).fetchone()
    return dict(row) if row else None


def get_user(user_id):
    with connect() as c:
        row = c.execute("SELECT id,username,email,created_at FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def revoke_token(jti, expires_at):
    import time
    with connect() as c:
        c.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (int(time.time()),))  # bersihkan yang sudah kedaluwarsa
        c.execute("INSERT OR IGNORE INTO revoked_tokens(jti,expires_at) VALUES(?,?)", (jti, int(expires_at)))


def is_revoked(jti):
    with connect() as c:
        return c.execute("SELECT 1 FROM revoked_tokens WHERE jti=?", (jti,)).fetchone() is not None


# ---------- riwayat (selalu dibatasi pada pemilik) ----------
def add_prediction(user_id, predicted_class, model_version, input_data, probabilities):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        cur = c.execute("INSERT INTO prediction_history(user_id,created_at,predicted_class,model_version,input_json,probabilities_json) VALUES(?,?,?,?,?,?)",
                        (user_id, now, predicted_class, model_version, json.dumps(input_data), json.dumps(probabilities)))
        return cur.lastrowid, now


def get_history(user_id):
    with connect() as c:
        rows = c.execute("SELECT id,created_at,predicted_class,model_version FROM prediction_history WHERE user_id=? ORDER BY id DESC LIMIT 100", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def delete_history(record_id, user_id):
    with connect() as c:
        return c.execute("DELETE FROM prediction_history WHERE id=? AND user_id=?", (record_id, user_id)).rowcount > 0
