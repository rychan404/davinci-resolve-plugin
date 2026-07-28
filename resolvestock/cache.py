"""SQLite response cache. The default 24-hour TTL satisfies Pixabay terms."""

from __future__ import annotations
import hashlib, json, sqlite3, time
from pathlib import Path

DAY_SECONDS = 86400
SECRET_PARAMS = frozenset({"key", "api_key", "apikey", "token", "access_token"})


def make_key(url: str, params: dict) -> str:
    safe = {
        key: value
        for key, value in sorted(params.items())
        if key.lower() not in SECRET_PARAMS
    }
    return hashlib.sha256(
        json.dumps([url, safe], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class ResponseCache:
    def __init__(self, db_path: Path, ttl_seconds: int = DAY_SECONDS):
        self.db_path, self.ttl_seconds = Path(db_path), ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS responses ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, stored_at REAL NOT NULL)"
        )
        self._connection.commit()

    def get(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value, stored_at FROM responses WHERE key = ?", (key,)
        ).fetchone()
        if row is None or time.time() - row[1] > self.ttl_seconds:
            return None
        return row[0]

    def set(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO responses VALUES (?, ?, ?)",
            (key, value, time.time()),
        )
        self._connection.commit()

    def purge_expired(self) -> int:
        cursor = self._connection.execute(
            "DELETE FROM responses WHERE stored_at < ?",
            (time.time() - self.ttl_seconds,),
        )
        self._connection.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._connection.close()
