from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator


def technical_cache_key(configuration: dict[str, Any]) -> str:
    canonical = json.dumps(configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    parsed_vehicle_json TEXT NOT NULL,
                    matched_vehicle_json TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    model_year INTEGER NOT NULL,
                    match_confidence REAL NOT NULL,
                    wltp_raw_json TEXT NOT NULL,
                    generated_output TEXT NOT NULL,
                    source_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_records(timestamp);
                CREATE TABLE IF NOT EXISTS vehicle_class_approvals (
                    type_id TEXT PRIMARY KEY,
                    vehicle_class TEXT NOT NULL CHECK(vehicle_class IN ('M1', 'N1')),
                    source_reference TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    approved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vehicle_class_requests (
                    type_id TEXT PRIMARY KEY,
                    brand TEXT NOT NULL,
                    description TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                );
                """
            )

    def record_vehicle_class_request(self, type_id: str, brand: str, description: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO vehicle_class_requests(type_id, brand, description, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(type_id) DO UPDATE SET
                    brand = excluded.brand,
                    description = excluded.description,
                    last_seen_at = excluded.last_seen_at
                """,
                (type_id, brand, description, now, now),
            )

    def approve_vehicle_class(
        self, type_id: str, vehicle_class: str, source_reference: str, approved_by: str
    ) -> None:
        if vehicle_class not in {"M1", "N1"}:
            raise ValueError("Die Fahrzeugklasse muss M1 oder N1 sein.")
        if not source_reference.strip() or not approved_by.strip():
            raise ValueError("Quelle und freigebende Person müssen angegeben werden.")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO vehicle_class_approvals(type_id, vehicle_class, source_reference, approved_by, approved_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(type_id) DO UPDATE SET
                    vehicle_class = excluded.vehicle_class,
                    source_reference = excluded.source_reference,
                    approved_by = excluded.approved_by,
                    approved_at = excluded.approved_at
                """,
                (type_id, vehicle_class, source_reference.strip(), approved_by.strip(), datetime.now(UTC).isoformat()),
            )

    def get_vehicle_class_approval(self, type_id: str) -> dict[str, str] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT type_id, vehicle_class, source_reference, approved_by, approved_at FROM vehicle_class_approvals WHERE type_id = ?",
                (type_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_pending_vehicle_classes(self) -> list[dict[str, str]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT r.type_id, r.brand, r.description, r.first_seen_at, r.last_seen_at
                FROM vehicle_class_requests r
                LEFT JOIN vehicle_class_approvals a ON a.type_id = r.type_id
                WHERE a.type_id IS NULL ORDER BY r.last_seen_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def put_cache(
        self,
        cache_key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        expires_at = current + timedelta(seconds=ttl_seconds)
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO cache_entries(cache_key, created_at, expires_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    payload_json = excluded.payload_json
                """,
                (
                    cache_key,
                    current.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )

    def get_cache(self, cache_key: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        current = now or datetime.now(UTC)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT expires_at, payload_json FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row["expires_at"]) <= current:
                connection.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
                return None
            return json.loads(row["payload_json"])

    def write_audit(self, record: dict[str, Any]) -> int:
        required = {
            "timestamp",
            "user_input",
            "parsed_vehicle",
            "matched_vehicle",
            "model_id",
            "model_year",
            "match_confidence",
            "wltp_raw",
            "generated_output",
            "source",
        }
        missing = sorted(required.difference(record))
        if missing:
            raise ValueError(f"Im Audit-Datensatz fehlen Pflichtfelder: {', '.join(missing)}")
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO audit_records(
                    timestamp, user_input, parsed_vehicle_json, matched_vehicle_json,
                    model_id, model_year, match_confidence, wltp_raw_json,
                    generated_output, source_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["timestamp"],
                    record["user_input"],
                    json.dumps(record["parsed_vehicle"], ensure_ascii=False, sort_keys=True),
                    json.dumps(record["matched_vehicle"], ensure_ascii=False, sort_keys=True),
                    record["model_id"],
                    record["model_year"],
                    record["match_confidence"],
                    json.dumps(record["wltp_raw"], ensure_ascii=False, sort_keys=True),
                    record["generated_output"],
                    json.dumps(record["source"], ensure_ascii=False, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def prune(self, *, retention_days: int, now: datetime | None = None) -> dict[str, int]:
        current = now or datetime.now(UTC)
        audit_cutoff = current - timedelta(days=retention_days)
        with self._connection() as connection:
            cache_cursor = connection.execute(
                "DELETE FROM cache_entries WHERE expires_at <= ?",
                (current.isoformat(),),
            )
            audit_cursor = connection.execute(
                "DELETE FROM audit_records WHERE timestamp < ?",
                (audit_cutoff.isoformat(),),
            )
        return {"cache_deleted": cache_cursor.rowcount, "audit_deleted": audit_cursor.rowcount}
