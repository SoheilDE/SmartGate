import asyncio
import time
from collections import deque

from app.config import gateway_config

_windows: dict[str, deque] = {}
_lock = asyncio.Lock()


async def check(ip: str) -> tuple[bool, int, int]:
    """Sliding-window rate check. Returns (allowed, limit_rph, remaining)."""
    cfg = gateway_config.rate_limit_config()
    if not cfg.get("enabled", False):
        return True, 0, 0

    limit: int = cfg.get("per_ip", {}).get(ip) or cfg.get("default_rph", 1000)
    now = time.monotonic()

    async with _lock:
        dq = _windows.setdefault(ip, deque())
        while dq and now - dq[0] > 3600.0:
            dq.popleft()
        if len(dq) >= limit:
            return False, limit, 0
        dq.append(now)
        return True, limit, limit - len(dq)
