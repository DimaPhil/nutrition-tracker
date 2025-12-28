"""Simple cache abstractions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Cache(Protocol):
    """Cache interface for simple key-value data."""

    def get(self, key: str) -> object | None:
        """Return a cached value if present and not expired."""

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        """Store a cached value with a TTL in seconds."""


@dataclass
class _CacheEntry:
    value: object
    expires_at: datetime


@dataclass
class InMemoryCache(Cache):
    """In-memory cache implementation for MVP."""

    _entries: dict[str, _CacheEntry]

    def __init__(self) -> None:
        self._entries = {}

    def get(self, key: str) -> object | None:
        """Return a cached value if it hasn't expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if datetime.now(tz=UTC) >= entry.expires_at:
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        """Store a cached value with a TTL."""
        expires_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)
        self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
