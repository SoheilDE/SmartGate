import time
from dataclasses import dataclass

import psycopg2
import psycopg2.extras
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

# ── PostgreSQL journal ────────────────────────────────────────────────────────

def _conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(settings.database_url)


def init_db() -> None:
    from app.auth.db import init_auth_tables
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id                SERIAL PRIMARY KEY,
                    ts                DOUBLE PRECISION NOT NULL,
                    model             TEXT             NOT NULL,
                    latency_ms        DOUBLE PRECISION NOT NULL,
                    prompt_tokens     INTEGER          NOT NULL DEFAULT 0,
                    completion_tokens INTEGER          NOT NULL DEFAULT 0,
                    cache_hit         BOOLEAN          NOT NULL DEFAULT FALSE,
                    fallback          BOOLEAN          NOT NULL DEFAULT FALSE
                )
            """)
    init_auth_tables()


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

    # PostgreSQL
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO requests
                   (ts, model, latency_ms, prompt_tokens, completion_tokens, cache_hit, fallback)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    time.time(),
                    r.model,
                    r.latency_ms,
                    r.prompt_tokens,
                    r.completion_tokens,
                    r.cache_hit,
                    r.fallback,
                ),
            )
