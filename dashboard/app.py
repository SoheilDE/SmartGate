import os
import sqlite3
import time

import pandas as pd
import streamlit as st

DB_PATH = os.getenv("METRICS_DB_PATH", "./metrics.db")

st.set_page_config(page_title="SmartGate Dashboard", layout="wide")
st.title("SmartGate Observability Dashboard")

REFRESH_INTERVAL = 5  # seconds


@st.cache_data(ttl=REFRESH_INTERVAL)
def load_data() -> pd.DataFrame:
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM requests ORDER BY ts DESC LIMIT 1000", conn
    )
    conn.close()
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["ts"], unit="s")
    return df


df = load_data()

if df.empty:
    st.info("No requests recorded yet. Send some requests through SmartGate to see telemetry.")
    st.stop()

# ── Top-level KPIs ────────────────────────────────────────────────────────────
total = len(df)
cache_hits = df["cache_hit"].sum()
hit_ratio = cache_hits / total if total else 0
fallbacks = df["fallback"].sum()
avg_latency = df["latency_ms"].mean()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Requests", f"{total:,}")
col2.metric("Cache Hit Ratio", f"{hit_ratio:.1%}")
col3.metric("Avg Latency", f"{avg_latency:.0f} ms")
col4.metric("Fallbacks", f"{int(fallbacks):,}")

st.divider()

# ── Per-model latency ─────────────────────────────────────────────────────────
st.subheader("Avg Latency by Model")
latency_by_model = (
    df[df["cache_hit"] == 0]
    .groupby("model")["latency_ms"]
    .mean()
    .reset_index()
    .rename(columns={"latency_ms": "avg_latency_ms"})
)
st.bar_chart(latency_by_model.set_index("model"))

# ── Token usage over time ─────────────────────────────────────────────────────
st.subheader("Token Usage Over Time")
df_sorted = df.sort_values("datetime")
df_sorted["total_tokens"] = df_sorted["prompt_tokens"] + df_sorted["completion_tokens"]
token_ts = df_sorted.set_index("datetime")[["prompt_tokens", "completion_tokens"]]
st.line_chart(token_ts)

# ── Request volume over time ──────────────────────────────────────────────────
st.subheader("Request Volume (1-minute buckets)")
df_sorted["minute"] = df_sorted["datetime"].dt.floor("min")
volume = df_sorted.groupby("minute").size().reset_index(name="requests")
st.line_chart(volume.set_index("minute"))

# ── Cache hit vs miss ─────────────────────────────────────────────────────────
st.subheader("Cache Hit vs Miss")
cache_counts = df["cache_hit"].map({1: "HIT", 0: "MISS"}).value_counts().reset_index()
cache_counts.columns = ["result", "count"]
st.bar_chart(cache_counts.set_index("result"))

# ── Recent requests table ─────────────────────────────────────────────────────
st.subheader("Recent Requests")
display_cols = ["datetime", "model", "latency_ms", "prompt_tokens", "completion_tokens", "cache_hit", "fallback"]
st.dataframe(df[display_cols].head(50), use_container_width=True)

st.caption(f"Auto-refreshes every {REFRESH_INTERVAL}s. Last loaded: {time.strftime('%H:%M:%S')}")
st.rerun() if st.button("Refresh now") else None
