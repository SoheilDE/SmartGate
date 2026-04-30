import json
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.cache import semantic_cache
from app.config import gateway_config
from app.config.settings import settings
from app.fallback.validator import validate
from app.routing.model_router import select_model
from app.telemetry.metrics import RequestRecord, init_db, record


@asynccontextmanager
async def lifespan(app: FastAPI):
    gateway_config.load(settings.gateway_config_path)
    semantic_cache.init_collection()
    init_db()
    yield


app = FastAPI(title="SmartGate", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/instrumentator-metrics")

_admin_key_header = APIKeyHeader(name="X-Admin-Api-Key", auto_error=False)


def require_admin(key: str = Security(_admin_key_header)):
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY is not configured")
    if key != expected:
        raise HTTPException(status_code=401, detail="Invalid admin API key")


# ── Observability ─────────────────────────────────────────────────────────────

@app.get("/metrics")
def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Admin config endpoints ────────────────────────────────────────────────────

@app.get("/admin/config", dependencies=[Depends(require_admin)])
def get_config():
    return gateway_config.get()


@app.put("/admin/config", dependencies=[Depends(require_admin)])
async def update_config(request: Request):
    body = await request.json()
    gateway_config.update(body)
    return {"status": "updated", "config": gateway_config.get()}


@app.post("/admin/config/reload", dependencies=[Depends(require_admin)])
def reload_config():
    gateway_config.reload()
    return {"status": "reloaded", "config": gateway_config.get()}


# ── OpenAI-compatible endpoints ───────────────────────────────────────────────

@app.get("/v1/models")
def list_models():
    fast = gateway_config.fast_model()
    powerful = gateway_config.powerful_model()
    models = [
        {"id": fast.get("model"), "object": "model", "owned_by": "smartgate", "tier": "fast"},
        {"id": powerful.get("model"), "object": "model", "owned_by": "smartgate", "tier": "powerful"},
    ]
    # Deduplicate in case both tiers point to the same model
    seen = set()
    unique = []
    for m in models:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)
    return {"object": "list", "data": unique}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    payload = await request.json()
    messages = payload.get("messages", [])
    if not messages:
        raise HTTPException(status_code=422, detail="messages field is required")

    stream = payload.get("stream", False)
    prompt = " ".join(
        m.get("content", "") for m in messages if m.get("role") == "user"
    )
    t_start = time.perf_counter()
    fallback_used = False

    # ── 1. Semantic cache ────────────────────────────────────────────────────
    if gateway_config.feature_enabled("semantic_cache"):
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
            if stream:
                return StreamingResponse(
                    _stream_from_cache(response_body),
                    media_type="text/event-stream",
                    headers={"X-Cache": "HIT", "X-Model-Used": "cache"},
                )
            return JSONResponse(
                content=response_body,
                headers={"X-Cache": "HIT", "X-Model-Used": "cache"},
            )

    # ── 2. Model routing ─────────────────────────────────────────────────────
    if gateway_config.feature_enabled("model_routing"):
        model_cfg, complexity, routing_reason = select_model(prompt, messages)
    else:
        model_cfg, complexity, routing_reason = select_model(prompt, messages, force_powerful=True)

    # ── Streaming path ───────────────────────────────────────────────────────
    if stream:
        return StreamingResponse(
            _stream_llm(payload, model_cfg, prompt, t_start, complexity),
            media_type="text/event-stream",
            headers={
                "X-Cache": "MISS",
                "X-Model-Used": model_cfg.model,
                "X-Complexity-Score": str(complexity),
                "X-Routing-Reason": routing_reason,
            },
        )

    # ── Non-streaming path ───────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        # ── 3. Forward request ───────────────────────────────────────────────
        response_data = await _call_llm(payload, model_cfg, client)

        # ── 4. Fallback ──────────────────────────────────────────────────────
        if gateway_config.feature_enabled("fallback") and not validate(response_data):
            fallback_cfg, _, _ = select_model(prompt, messages, force_powerful=True)
            response_data = await _call_llm(payload, fallback_cfg, client)
            model_cfg = fallback_cfg
            fallback_used = True

    latency_ms = (time.perf_counter() - t_start) * 1000
    usage = response_data.get("usage", {})

    # ── 5. Store in cache ────────────────────────────────────────────────────
    if gateway_config.feature_enabled("semantic_cache"):
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
            "X-Routing-Reason": routing_reason,
            "X-Fallback": str(fallback_used),
        },
    )


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


async def _stream_from_cache(response_body: dict):
    """Emit a cached complete response as a single SSE chunk so stream clients work."""
    content = (
        response_body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    chunk = {
        "id": "smartgate-cache",
        "object": "chat.completion.chunk",
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
    }
    yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


async def _stream_llm(payload: dict, model_cfg, prompt: str, t_start: float, complexity: float):
    """Forward SSE chunks from upstream LLM, then cache + record telemetry when done."""
    headers = {
        "Authorization": f"Bearer {model_cfg.api_key}",
        "Content-Type": "application/json",
    }
    body = {**payload, "model": model_cfg.model}

    accumulated_content = ""
    prompt_tokens = 0
    completion_tokens = 0

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{model_cfg.base_url}/chat/completions",
            json=body,
            headers=headers,
            timeout=120.0,
        ) as response:
            if response.status_code != 200:
                error_body = await response.aread()
                yield f"data: {json.dumps({'error': error_body.decode()})}\n\n"
                return

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data == "[DONE]":
                        yield "data: [DONE]\n\n"
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        accumulated_content += delta.get("content", "")
                        usage = chunk.get("usage", {})
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens", 0)
                            completion_tokens = usage.get("completion_tokens", 0)
                    except json.JSONDecodeError:
                        pass
                yield f"{line}\n\n"

    # Post-stream: store assembled response in cache and record telemetry
    latency_ms = (time.perf_counter() - t_start) * 1000

    if gateway_config.feature_enabled("semantic_cache") and accumulated_content:
        cached_response = {
            "choices": [
                {"message": {"role": "assistant", "content": accumulated_content}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
        semantic_cache.store(prompt, json.dumps(cached_response))

    record(RequestRecord(
        model=model_cfg.model,
        latency_ms=latency_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cache_hit=False,
        fallback=False,
    ))
