from __future__ import annotations

from datetime import UTC, datetime, timedelta


class TTLCache:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[datetime, object]] = {}

    def get(self, key: str) -> object | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < datetime.now(UTC):
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._store[key] = (datetime.now(UTC) + timedelta(seconds=self.ttl), value)

    def clear(self) -> None:
        self._store.clear()
