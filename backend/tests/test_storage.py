from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.storage import SQLiteStore, technical_cache_key


class SQLiteStoreTests(unittest.TestCase):
    def test_cache_is_keyed_by_canonical_technical_configuration_and_expires(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            first = {"model_id": "id5", "options": [{"id": "b"}, {"id": "a"}]}
            same = {"options": [{"id": "b"}, {"id": "a"}], "model_id": "id5"}
            cache_key = technical_cache_key(first)
            self.assertEqual(cache_key, technical_cache_key(same))
            now = datetime(2026, 8, 20, 10, tzinfo=UTC)
            store.put_cache(cache_key, {"verified": True}, ttl_seconds=60, now=now)
            self.assertEqual({"verified": True}, store.get_cache(cache_key, now=now))
            self.assertIsNone(store.get_cache(cache_key, now=now + timedelta(seconds=61)))

    def test_audit_requires_and_persists_traceability_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            audit_id = store.write_audit(
                {
                    "timestamp": "2026-08-20T12:15:36+02:00",
                    "user_input": "ID.5 Pure 140 kW",
                    "parsed_vehicle": {"model": "ID.5"},
                    "matched_vehicle": {"type_code": "TYPE:E392JM"},
                    "model_id": "model-id",
                    "model_year": 2027,
                    "match_confidence": 1.0,
                    "wltp_raw": {"data_version": "3"},
                    "generated_output": "Verbrauchstext",
                    "source": {"provider": "Volkswagen OKAPI"},
                }
            )
            self.assertGreater(audit_id, 0)

    def test_vehicle_class_approval_is_auditable_and_removes_pending_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            store.record_vehicle_class_request("type-1", "Volkswagen", "T-Cross Style")
            self.assertEqual("type-1", store.list_pending_vehicle_classes()[0]["type_id"])
            store.approve_vehicle_class("type-1", "M1", "CoC 0.4", "jan.oltmanns")
            approval = store.get_vehicle_class_approval("type-1")
            self.assertIsNotNone(approval)
            self.assertEqual("M1", approval["vehicle_class"])
            self.assertEqual([], store.list_pending_vehicle_classes())


if __name__ == "__main__":
    unittest.main()
