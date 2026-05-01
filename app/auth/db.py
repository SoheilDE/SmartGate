import secrets
import time

import bcrypt
import psycopg2

from app.config.settings import settings


def _conn():
    return psycopg2.connect(settings.database_url)


def init_auth_tables() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username      TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at    DOUBLE PRECISION NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key        TEXT PRIMARY KEY,
                    username   TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
                    expires_at DOUBLE PRECISION NOT NULL
                )
            """)


def create_user(username: str, password: str) -> bool:
    """Returns False if username already exists."""
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s)",
                    (username, hashed, time.time()),
                )
        return True
    except psycopg2.errors.UniqueViolation:
        return False


def verify_user(username: str, password: str) -> bool:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row[0].encode())


def issue_api_key(username: str) -> str:
    """Revoke existing keys for this user, generate a fresh 24h key."""
    key = f"sk-sg-{secrets.token_urlsafe(32)}"
    expires_at = time.time() + 86400  # 24 hours
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM api_keys WHERE username = %s", (username,))
            cur.execute(
                "INSERT INTO api_keys (key, username, expires_at) VALUES (%s, %s, %s)",
                (key, username, expires_at),
            )
    return key


def resolve_key(key: str) -> str | None:
    """Return username if key exists and is not expired, else None."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, expires_at FROM api_keys WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
    if not row:
        return None
    username, expires_at = row
    if time.time() > expires_at:
        return None
    return username


def purge_expired_keys() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM api_keys WHERE expires_at < %s", (time.time(),))
