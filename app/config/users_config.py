import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.RLock()
_users: dict[str, Any] = {}
_users_path: Path = Path("users.json")


def load(path: str = "users.json") -> None:
    global _users, _users_path
    _users_path = Path(path)
    with _lock:
        if _users_path.exists():
            _users = json.loads(_users_path.read_text())
        else:
            _users = {}
            _users_path.write_text(json.dumps(_users, indent=2))


def reload() -> None:
    load(str(_users_path))


def get() -> dict[str, Any]:
    with _lock:
        return dict(_users)


def update(new_users: dict[str, Any]) -> None:
    with _lock:
        _users.update(new_users)
        _users_path.write_text(json.dumps(_users, indent=2))


def is_allowed(username: str) -> bool:
    with _lock:
        entry = _users.get(username)
        if entry is None:
            return False
        if isinstance(entry, dict):
            return entry.get("enabled", True)
        return bool(entry)
