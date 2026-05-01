import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.RLock()
_config: dict[str, Any] = {}
_config_path: Path = Path("config.json")


def _defaults() -> dict[str, Any]:
    return {
        "features": {
            "semantic_cache": True,
            "model_routing": True,
            "fallback": True,
        },
        "rate_limiting": {
            "enabled": False,
            "default_rph": 1000,
            "per_ip": {},
        },
        "routing": {
            "complexity_threshold": 0.6,
            "cache_similarity_threshold": 0.92,
            "keyword_routing": [],
            "intent_routing": {
                "conversational": "fast",
                "factual":        "fast",
                "creative":       "fast",
                "math":           "powerful",
                "analytical":     "powerful",
                "code":           "powerful",
            },
        },
        "models": {
            "fast":     {"model": "gpt-3.5-turbo", "base_url": "https://api.openai.com/v1", "api_key_env": "FAST_MODEL_API_KEY"},
            "powerful": {"model": "gpt-4",         "base_url": "https://api.openai.com/v1", "api_key_env": "POWERFUL_MODEL_API_KEY"},
        },
    }


def load(path: str = "config.json") -> None:
    global _config, _config_path
    _config_path = Path(path)
    with _lock:
        if _config_path.exists():
            _config = json.loads(_config_path.read_text())
        else:
            _config = _defaults()
            _config_path.write_text(json.dumps(_config, indent=2))


def reload() -> None:
    load(str(_config_path))


def get() -> dict[str, Any]:
    with _lock:
        return dict(_config)


def update(new_config: dict[str, Any]) -> None:
    with _lock:
        _config.update(new_config)
        _config_path.write_text(json.dumps(_config, indent=2))


# ── Convenience accessors ─────────────────────────────────────────────────────

def feature_enabled(name: str) -> bool:
    with _lock:
        return _config.get("features", {}).get(name, True)


def complexity_threshold() -> float:
    with _lock:
        return _config.get("routing", {}).get("complexity_threshold", 0.6)


def cache_similarity_threshold() -> float:
    with _lock:
        return _config.get("routing", {}).get("cache_similarity_threshold", 0.92)


def fast_model() -> dict[str, str]:
    with _lock:
        return _config.get("models", {}).get("fast", {})


def powerful_model() -> dict[str, str]:
    with _lock:
        return _config.get("models", {}).get("powerful", {})


def model_by_tier(tier: str) -> dict[str, str]:
    """Return the model config for any named tier (e.g. 'fast', 'powerful', or custom)."""
    with _lock:
        models = _config.get("models", {})
        return models.get(tier, models.get("powerful", {}))


def intent_routing() -> dict[str, str]:
    """Return the admin-configured intent → tier mapping (may be empty if not set)."""
    with _lock:
        return _config.get("routing", {}).get("intent_routing", {})


def keyword_routing() -> list[dict]:
    """Return the ordered list of keyword routing rules (may be empty if not set)."""
    with _lock:
        return _config.get("routing", {}).get("keyword_routing", [])


def rate_limit_config() -> dict:
    with _lock:
        return _config.get("rate_limiting", {"enabled": False, "default_rph": 1000, "per_ip": {}})
