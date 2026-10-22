"""Hash password (argon2id), token JWT bertanda tangan HS256, dan pembatasan percobaan login."""
import contextlib
import os
import secrets
import threading
import time
import uuid
from functools import lru_cache
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

import app.core.config as cfg

ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = int(os.getenv("OBESICHECK_TOKEN_TTL_MINUTES", "720")) * 60
_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("password-tiruan-untuk-menyamakan-waktu")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Selalu melakukan satu verifikasi argon2 (hash tiruan bila akun tidak ada) agar waktu respons tidak membocorkan keberadaan akun."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


@lru_cache(maxsize=8)
def _secret_from_file(path: str) -> str:
    p = Path(path)
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    p.write_text(key, encoding="utf-8")
    with contextlib.suppress(OSError):  # Windows: izin POSIX tidak berlaku
        p.chmod(0o600)
    return key


def secret_key() -> str:
    """OBESICHECK_SECRET_KEY bila diatur; jika tidak, kunci acak dibuat sekali dan disimpan di samping database (tidak ada rahasia hardcoded)."""
    env = os.getenv("OBESICHECK_SECRET_KEY")
    if env:
        if len(env) < 32:
            raise RuntimeError("OBESICHECK_SECRET_KEY minimal 32 karakter.")
        return env
    return _secret_from_file(str(cfg.DB_PATH.parent / "secret.key"))


def create_token(user_id: int) -> tuple[str, str, int]:
    now = int(time.time())
    jti = uuid.uuid4().hex
    exp = now + TOKEN_TTL_SECONDS
    token = jwt.encode({"sub": str(user_id), "jti": jti, "iat": now, "exp": exp}, secret_key(), algorithm=ALGORITHM)
    return token, jti, exp


def decode_token(token: str) -> dict:
    """Melempar jwt.PyJWTError bila tanda tangan salah, kedaluwarsa, algoritma lain (mis. 'none'), atau klaim wajib hilang."""
    return jwt.decode(token, secret_key(), algorithms=[ALGORITHM], options={"require": ["exp", "sub", "jti"]})


class LoginLimiter:
    """Pembatas sederhana dalam memori: LIMITS kegagalan per kunci dalam WINDOW detik -> terkunci. (Per proses; hilang saat restart.)"""
    LIMITS = {"user": 5, "ip": 20}  # per akun 5x, per alamat IP 20x (IP lebih longgar agar jaringan bersama tidak mudah terkunci)
    WINDOW = 15 * 60

    def __init__(self):
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = time.time() - self.WINDOW
        recent = [t for t in self._fails.get(key, []) if t > cutoff]
        if recent:
            self._fails[key] = recent
        else:
            self._fails.pop(key, None)
        return recent

    def retry_after(self, *keys: str) -> int:
        with self._lock:
            waits = [int(self.WINDOW - (time.time() - min(r))) + 1 for k in keys if len(r := self._recent(k)) >= self.LIMITS[k.split(':', 1)[0]]]
        return max(waits, default=0)

    def fail(self, *keys: str):
        with self._lock:
            for k in keys:
                self._recent(k)
                self._fails.setdefault(k, []).append(time.time())

    def reset(self, *keys: str):
        with self._lock:
            for k in keys:
                self._fails.pop(k, None)

    def clear(self):
        with self._lock:
            self._fails.clear()


limiter = LoginLimiter()
