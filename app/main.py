import json
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.cache import semantic_cache
from app.config.settings import settings
from app.fallback.validator import validate
from app.routing.model_router import select_model
from app.telemetry.metrics import RequestRecord, init_db, record


@asynccontextmanager
async def lifespan(app: FastAPI):
    semantic_cache.init_collection()
    init_db()
    yield


app = FastAPI(title="SmartGate", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/instrumentator-metrics")


@app.get("/metrics")
def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "ok"}


async def _call_llm(payload: dict, model_cfg, client: httpx.AsyncClient) -> dict:
    headers = {
        "Authorization": f"Bearer {model_cfg.api_key}",
        "Content-Type": "application/json",
    }
    body = {**payload, "model": model_cfg.model}
    resp = await client.post(
        f"{model_cfg.base_url}/chat/completions",
        json=body,
        headers=headers,
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=422, detail="messages field is required")

    # Extract the latest user turn as the prompt for caching/scoring
    prompt = " ".join(
        m.get("content", "") for m in messages if m.get("role") == "user"
    )

    t_start = time.perf_counter()
    fallback_used = False

    # ── 1. Semantic cache lookup ─────────────────────────────────────────────
    cached = semantic_cache.lookup(prompt)
    if cached:
        latency_ms = (time.perf_counter() - t_start) * 1000
        response_body = json.loads(cached)
        usage = response_body.get("usage", {})
        record(RequestRecord(
            model="cache",
            latency_ms=latency_ms,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cache_hit=True,
            fallback=False,
        ))
        return JSONResponse(
            content=response_body,
            headers={"X-Cache": "HIT", "X-Model-Used": "cache"},
        )

    # ── 2. Complexity scoring + model selection ──────────────────────────────
    model_cfg, complexity = select_model(prompt)

    async with httpx.AsyncClient() as client:
        # ── 3. Forward request ───────────────────────────────────────────────
        response_data = await _call_llm(payload, model_cfg, client)

        # ── 4. Fallback if response is invalid ───────────────────────────────
        if not validate(response_data):
            from app.routing.model_router import select_model as _select
            fallback_cfg, _ = _select(prompt, force_powerful=True)
            response_data = await _call_llm(payload, fallback_cfg, client)
            model_cfg = fallback_cfg
            fallback_used = True

    latency_ms = (time.perf_counter() - t_start) * 1000
    usage = response_data.get("usage", {})

    # ── 5. Store in cache ────────────────────────────────────────────────────
    semantic_cache.store(prompt, json.dumps(response_data))

    # ── 6. Record telemetry ──────────────────────────────────────────────────
    record(RequestRecord(
        model=model_cfg.model,
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cache_hit=False,
        fallback=fallback_used,
    ))

    return JSONResponse(
        content=response_data,
        headers={
            "X-Cache": "MISS",
            "X-Model-Used": model_cfg.model,
            "X-Complexity-Score": str(complexity),
            "X-Fallback": str(fallback_used),
        },
    )
