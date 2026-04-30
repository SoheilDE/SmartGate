import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass

from prometheus_client import Counter, Histogram

from app.config.settings import settings

# ── Prometheus metrics ────────────────────────────────────────────────────────

requests_total = Counter(
    "smartgate_requests_total",
    "Total requests processed",
    ["model", "cache_hit"],
)

latency_seconds = Histogram(
    "smartgate_latency_seconds",
    "Request latency in seconds",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

tokens_total = Counter(
    "smartgate_tokens_total",
    "Total tokens consumed",
    ["model", "type"],  # type = prompt | completion
)

fallbacks_total = Counter(
    "smartgate_fallbacks_total",
    "Total fallback retries triggered",
    ["model"],
)

# ── SQLite journal ────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(settings.metrics_db_path, check_same_thread=False)


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL    NOT NULL,
                model       TEXT    NOT NULL,
                latency_ms  REAL    NOT NULL,
                prompt_tokens    INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                cache_hit   INTEGER NOT NULL DEFAULT 0,
                fallback    INTEGER NOT NULL DEFAULT 0
            )
        """)


@dataclass
class RequestRecord:
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cache_hit: bool
    fallback: bool


def record(r: RequestRecord) -> None:
    # Prometheus
    requests_total.labels(model=r.model, cache_hit=str(r.cache_hit)).inc()
    latency_seconds.labels(model=r.model).observe(r.latency_ms / 1000)
    tokens_total.labels(model=r.model, type="prompt").inc(r.prompt_tokens)
    tokens_total.labels(model=r.model, type="completion").inc(r.completion_tokens)
    if r.fallback:
        fallbacks_total.labels(model=r.model).inc()

    # SQLite
    with _conn() as conn:
        conn.execute(
            """INSERT INTO requests
               (ts, model, latency_ms, prompt_tokens, completion_tokens, cache_hit, fallback)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                time.time(),
                r.model,
                r.latency_ms,
                r.prompt_tokens,
                r.completion_tokens,
                int(r.cache_hit),
                int(r.fallback),
            ),
        )
