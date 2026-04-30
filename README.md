# SmartGate

> **Cut your LLM API bill by up to 80% — without changing a single line of application code.**

SmartGate is a drop-in reverse proxy that sits between your application and any LLM provider. It silently intercepts every request and makes three intelligent decisions: *have we answered this before? how complex is this prompt? and did the model actually give us a valid answer?* The result is faster responses, dramatically lower costs, and full visibility into where your AI budget is going.

---

## Why Companies Use SmartGate

| Pain | How SmartGate Fixes It |
|---|---|
| Paying full price for repeated or similar questions | Semantic cache returns identical answers in **<5 ms** at zero token cost |
| GPT-4 pricing on every request regardless of complexity | Complexity router sends simple prompts to cheap models automatically |
| Silent model failures going undetected | Fallback validator retries on a stronger model before the user ever sees an error |
| No visibility into AI spend by team, feature, or model | Real-time dashboard breaks down cost, latency, and cache savings |

---

## How Much Can You Save?

A typical production workload routes **~70% of prompts** to the fast tier and serves **~30% from cache**. Here's what that looks like at scale:

| Monthly Requests | Without SmartGate | With SmartGate | Estimated Saving |
|---|---|---|---|
| 100,000 | ~$300 (all GPT-4) | ~$55 | **82%** |
| 1,000,000 | ~$3,000 | ~$520 | **83%** |
| 10,000,000 | ~$30,000 | ~$5,000 | **83%** |

*Estimates based on GPT-4 vs GPT-3.5 pricing with a 30% cache hit rate. Your numbers will vary.*

---

## Architecture

```
Your App
   │
   │  POST /v1/chat/completions  (OpenAI-compatible — zero code change)
   ▼
┌─────────────────────────────────────────────────────┐
│                      SmartGate                      │
│                                                     │
│  ┌──────────────┐    HIT → return instantly ($0)   │
│  │ Semantic     │◄── embed prompt → Qdrant search  │
│  │ Cache        │                                   │
│  └──────┬───────┘    MISS ↓                        │
│         │                                           │
│  ┌──────▼───────┐                                   │
│  │ Complexity   │── simple → Fast Model (cheap)    │
│  │ Scorer       │── complex → Powerful Model        │
│  └──────┬───────┘                                   │
│         │                                           │
│  ┌──────▼───────┐                                   │
│  │ Fallback     │── valid → cache + return          │
│  │ Validator    │── invalid → retry powerful model  │
│  └──────────────┘                                   │
│                                                     │
│  Telemetry → Prometheus + SQLite → Dashboard        │
└─────────────────────────────────────────────────────┘
   │                           │
   ▼                           ▼
Fast Model                Powerful Model
(GPT-3.5 / Llama 3 /     (GPT-4 / Claude /
 any OpenAI-compatible)   any OpenAI-compatible)
```

---

## Three Layers of Cost Intelligence

### 1. Semantic Cache — Stop Paying for the Same Answer Twice
SmartGate embeds every prompt into a vector and stores it in Qdrant. Before forwarding any request, it checks whether a semantically equivalent prompt has been answered before — not just an exact string match, but *meaning*-level similarity. A user asking "how do I reset my password?" and another asking "I forgot my password, what do I do?" get the same cached answer instantly, at zero token cost.

- Cache hit response time: **< 5 ms**
- Token cost of a cache hit: **$0.00**
- Similarity threshold is configurable — tighten it for precision, loosen it for more savings

### 2. Intelligent Model Router — Right Model for the Right Job
Not every prompt needs GPT-4. A customer asking "what are your business hours?" does not need the same model as an engineer asking you to debug a distributed tracing implementation. SmartGate scores each prompt on complexity and routes automatically:

- **Fast tier**: short, factual, or conversational prompts → cheap model (e.g. GPT-3.5, Llama 3 via Ollama, or any OpenRouter model)
- **Powerful tier**: analytical, multi-step, code-generation, or detailed explanation prompts → your best model

Both tiers are fully configurable via environment variables. You can point them at OpenAI, Anthropic, OpenRouter, a local Ollama instance, or any OpenAI-compatible endpoint.

### 3. Fallback Validator — Reliability Without Manual Retries
If a model returns a malformed or empty response, SmartGate catches it before your application ever sees it and automatically retries on the powerful model. No error pages, no silent failures, no engineering time spent building retry logic.

---

## Quick Start

```bash
git clone <this-repo>
cd SmartGate
cp .env.example .env
# Fill in your model API keys and endpoints
docker compose up --build
```

Point your application at `http://localhost:8000` instead of `https://api.openai.com` — that's it. No SDK changes, no prompt changes, no application refactoring.

**Endpoints:**
- `http://localhost:8000/v1/chat/completions` — drop-in OpenAI proxy
- `http://localhost:8501` — cost & performance dashboard
- `http://localhost:8000/metrics` — Prometheus scrape endpoint

---

## Observability Dashboard

SmartGate ships with a real-time Streamlit dashboard so you always know where your AI budget is going:

- **Cache hit ratio** — what percentage of requests are being served for free
- **Per-model latency** — p50/avg breakdown by fast vs powerful tier
- **Token usage over time** — prompt vs completion tokens, by model
- **Request volume** — traffic patterns and peak usage windows
- **Fallback rate** — how often the fast tier needed escalation

---

## Response Headers

Every proxied response includes headers for debugging and observability integration:

| Header | Example | Meaning |
|---|---|---|
| `X-Cache` | `HIT` | Served from semantic cache |
| `X-Model-Used` | `gpt-3.5-turbo` | Which model handled the request |
| `X-Complexity-Score` | `0.42` | Heuristic score (0 = simple, 1 = complex) |
| `X-Fallback` | `False` | Whether fallback was triggered |

---

## Configuration

All configuration is via environment variables (copy `.env.example` to `.env`):

| Variable | Default | Description |
|---|---|---|
| `FAST_MODEL` | `gpt-3.5-turbo` | Model name for low-complexity prompts |
| `FAST_MODEL_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `FAST_MODEL_API_KEY` | — | API key for the fast model |
| `POWERFUL_MODEL` | `gpt-4` | Model name for high-complexity prompts |
| `POWERFUL_MODEL_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint |
| `POWERFUL_MODEL_API_KEY` | — | API key for the powerful model |
| `COMPLEXITY_THRESHOLD` | `0.6` | Scores at or above this go to the powerful model |
| `CACHE_SIMILARITY_THRESHOLD` | `0.92` | Cosine similarity required for a cache hit |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector store URL |
| `DATABASE_URL` | `postgresql://smartgate:smartgate@localhost:5432/smartgate` | PostgreSQL connection string for telemetry |

**Example setups:**

```bash
# Route simple prompts to a free local Llama 3 via Ollama
FAST_MODEL=llama3
FAST_MODEL_BASE_URL=http://localhost:11434/v1
FAST_MODEL_API_KEY=ollama

# Route complex prompts to GPT-4 via OpenRouter
POWERFUL_MODEL=openai/gpt-4-turbo
POWERFUL_MODEL_BASE_URL=https://openrouter.ai/api/v1
POWERFUL_MODEL_API_KEY=sk-or-...
```

---

## Development Setup

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload    # proxy on :8000
streamlit run dashboard/app.py   # dashboard on :8501
pytest tests/                    # run test suite
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Proxy server | FastAPI + HTTPX (async) |
| Semantic cache | Qdrant + sentence-transformers (`all-MiniLM-L6-v2`) |
| Metrics | Prometheus + PostgreSQL |
| Dashboard | Streamlit |
| Orchestration | Docker Compose |
