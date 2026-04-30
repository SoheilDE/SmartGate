import re

# ── Task intent patterns ──────────────────────────────────────────────────────
_SIMPLE_PATTERNS = [
    r"\b(what is|what are|what was|what were)\b",
    r"\b(who is|who are|who was|who were)\b",
    r"\b(when (is|was|did|does))\b",
    r"\bwhere (is|are|was|were)\b",
    r"\bdefine\b",
    r"\bspell\b",
    r"\btranslate\b",
    r"\bconvert\b",
]

_COMPLEX_PATTERNS = [
    r"\bexplain\b",
    r"\banalyze\b|\banalyse\b",
    r"\bcompare\b",
    r"\bdebug\b",
    r"\bimplement\b",
    r"\bdesign\b",
    r"\barchitect\b",
    r"\boptimize\b|\boptimise\b",
    r"\brefactor\b",
    r"\bevaluate\b",
    r"\bdiagnose\b",
    r"\btroubleshoot\b",
    r"\bwrite (a |an )?(function|class|module|script|program|algorithm|service|api|library)\b",
    r"\bhow (does|do|would|can|should)\b",
    r"\bwhy\b",
    r"\bpros and cons\b",
    r"\btradeoffs?\b",
    r"\bstep[- ]by[- ]step\b",
    r"\bwalk (me )?through\b",
    r"\bdeep dive\b",
    r"\bin detail\b",
    r"\bwhat (would|could|should|might)\b",
]

# ── Code signals ──────────────────────────────────────────────────────────────
_CODE_BLOCK_RE = re.compile(r"```")
_CODE_KEYWORDS = [
    "function", "class", "method", "variable", "loop", "recursion",
    "algorithm", "api", "endpoint", "query", "schema", "async", "await",
    "exception", "stack trace", "stacktrace", "bug", "error", "test",
]

# ── Technical domain vocabulary ───────────────────────────────────────────────
_TECHNICAL_TERMS = [
    "distributed", "concurrent", "architecture", "cryptograph", "neural",
    "machine learning", "kubernetes", "microservice", "scalab",
    "throughput", "latency", "fault toleran", "consensus", "replication",
    "sharding", "transaction", "oauth", "authentication", "authorization",
    "encryption", "ssl", "tls", "websocket", "graphql", "race condition",
    "deadlock", "cache invalidat", "load balanc", "circuit breaker",
]

# ── Brevity / simplicity signals (push score down) ────────────────────────────
_BREVITY_RE = re.compile(
    r"\b(briefly|in one sentence|in one word|yes or no|tl;?dr|"
    r"quick(ly)?|short answer|simple answer|just (say|tell me|give me))\b"
)

# ── Constraint / requirement density (each adds complexity) ──────────────────
_CONSTRAINT_RE = re.compile(
    r"\b(must|make sure|ensure|require[sd]?|need to|important|critical|"
    r"also|additionally|furthermore|as well|and also)\b"
)

_TOKEN_CEILING = 600


def score(prompt: str) -> float:
    text = prompt.lower()
    tokens = text.split()

    # ── Signal 1: Task intent (0.0 – 0.75) ───────────────────────────────────
    simple_hits = sum(1 for p in _SIMPLE_PATTERNS if re.search(p, text))
    complex_hits = sum(1 for p in _COMPLEX_PATTERNS if re.search(p, text))

    if complex_hits > 0 and simple_hits == 0:
        task_score = min(0.35 + (complex_hits - 1) * 0.08, 0.75)
    elif complex_hits > 0 and simple_hits > 0:
        # Mixed signals — partial credit
        task_score = 0.25
    elif simple_hits > 0:
        task_score = max(0.0, 0.15 - simple_hits * 0.05)
    else:
        task_score = 0.15  # unknown intent

    # ── Signal 2: Code complexity (0.0 – 0.35) ───────────────────────────────
    has_code_block = bool(_CODE_BLOCK_RE.search(prompt))
    code_kw_hits = sum(1 for kw in _CODE_KEYWORDS if kw in text)

    if has_code_block:
        code_score = 0.35
    elif code_kw_hits >= 3:
        code_score = 0.20
    elif code_kw_hits >= 1:
        code_score = 0.10
    else:
        code_score = 0.0

    # ── Signal 3: Technical domain density (0.0 – 0.25) ─────────────────────
    tech_hits = sum(1 for t in _TECHNICAL_TERMS if t in text)
    tech_score = min(tech_hits * 0.08, 0.25)

    # ── Signal 4: Constraint / requirement density (0.0 – 0.20) ─────────────
    constraint_hits = len(_CONSTRAINT_RE.findall(text))
    constraint_score = min(constraint_hits * 0.05, 0.20)

    # ── Signal 5: Length (low weight, 0.0 – 0.12) ────────────────────────────
    length_score = min(len(tokens) / _TOKEN_CEILING, 1.0) * 0.12

    # ── Brevity penalty ───────────────────────────────────────────────────────
    brevity_penalty = 0.30 if _BREVITY_RE.search(text) else 0.0

    raw = task_score + code_score + tech_score + constraint_score + length_score - brevity_penalty
    return round(max(0.0, min(raw, 1.0)), 4)
