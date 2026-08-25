from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.domain.envkv import UsageContext
from backend.app.main import create_app
from backend.app.services.volkswagen.provider import ManualReviewRequired


def _sample_sheet() -> dict[str, object]:
    from decimal import Decimal

    from backend.app.domain.envkv import (
        ConsumptionValues, EnergyCostConfiguration, SourceReference, VehicleIdentity,
        VerifiedVehicleData, build_data_sheet, calculate_energy_costs,
    )

    consumption = ConsumptionValues(
        combined_kwh_100km=Decimal("15.5"), co2_g_km=Decimal("0"), co2_class="A",
        electric_range_km=446,
        phase_kwh_100km={"low": Decimal("11.1"), "medium": Decimal("12.2"),
                         "high": Decimal("14.1"), "extra_high": Decimal("20.4")},
    )
    verified = VerifiedVehicleData(
        vehicle=VehicleIdentity(
            brand="Volkswagen", model="ID.5", trim="Pure", power_kw=140, power_ps=190,
            battery_kwh=58, transmission="1-Gang-Automatik", model_id="model-id",
            model_year=2027, type_id="type-id", type_code="TYPE:E392JM",
        ),
        consumption=consumption,
        source=SourceReference("Volkswagen OKAPI", "model-id", 2027, "type-id", "TYPE:E392JM", "2026-08-21"),
        raw_wltp={}, annual_vehicle_tax_eur=Decimal("0"),
    )
    costs = calculate_energy_costs(consumption, EnergyCostConfiguration(
        electricity_price_eur_kwh=Decimal("0.321"), electricity_reference_year=2024,
        annual_distance_km=15_000,
    ))
    return build_data_sheet(verified, costs, "2026-08-21")


_SAMPLE_SHEET = _sample_sheet()


class ApiContractTests(unittest.TestCase):
    def _app(self, database_path: Path):
        return create_app(
            Settings(
                extension_api_key="test-extension-key",
                database_path=database_path,
            )
        )

    def test_health_is_public_and_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(self._app(Path(directory) / "envkv.sqlite3"))
            response = client.get("/api/v1/health")
            self.assertEqual(200, response.status_code)
            self.assertEqual({"status": "ok"}, response.json())

    def test_compliance_rejects_missing_api_key_with_german_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(self._app(Path(directory) / "envkv.sqlite3"))
            response = client.post(
                "/api/v1/vehicle/compliance",
                json={"vehicle_name": "ID.5 Pure 140 kW"},
            )
            self.assertEqual(401, response.status_code)
            self.assertEqual(
                "Der Zugriff auf den EnVKV-Dienst wurde nicht bestätigt.",
                response.json()["detail"],
            )

    def test_compliance_uses_injected_service_after_authentication(self) -> None:
        class FakeComplianceService:
            def create(self, vehicle_name: str, usage_context: UsageContext, selected_type_id: str | None = None) -> dict[str, object]:
                return {
                    "status": "verified",
                    "vehicle_name": vehicle_name,
                    "usage_context": usage_context.value,
                    "selected_type_id": selected_type_id,
                }

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(Path(directory) / "envkv.sqlite3")
            app.state.compliance_service = FakeComplianceService()
            client = TestClient(app)
            response = client.post(
                "/api/v1/vehicle/compliance",
                headers={"X-API-Key": "test-extension-key"},
                json={"vehicle_name": "ID.5 Pure 140 kW"},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                {
                    "status": "verified",
                    "vehicle_name": "ID.5 Pure 140 kW",
                    "usage_context": "advertising",
                    "selected_type_id": None,
                },
                response.json(),
            )

    def test_manual_vehicle_class_review_keeps_the_specific_reason(self) -> None:
        class FakeComplianceService:
            def create(self, vehicle_name: str, usage_context: UsageContext, selected_type_id: str | None = None) -> dict[str, object]:
                raise ManualReviewRequired(
                    "Die Fahrzeugklasse muss vor der ersten EnVKV-Verwendung einmalig freigegeben werden."
                )

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(Path(directory) / "envkv.sqlite3")
            app.state.compliance_service = FakeComplianceService()
            response = TestClient(app).post(
                "/api/v1/vehicle/compliance",
                headers={"X-API-Key": "test-extension-key"},
                json={"vehicle_name": "T-Roc Cabriolet ENERGY 1.0 l TSI OPF 85 kW"},
            )

        self.assertEqual(409, response.status_code)
        self.assertIn("Fahrzeugklasse", response.json()["detail"]["message"])
        self.assertEqual([], response.json()["detail"]["candidates"])

    def test_model_range_endpoint_requires_the_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(self._app(Path(directory) / "envkv.sqlite3"))
            response = client.post("/api/v1/vehicle/model-range", json={"vehicle_name": "Golf"})
            self.assertEqual(401, response.status_code)

    def test_model_range_endpoint_returns_the_verified_span(self) -> None:
        class FakeComplianceService:
            def create_model_range(self, vehicle_name: str, usage_context: UsageContext) -> dict[str, object]:
                return {"status": "verified", "result_type": "model_range",
                        "model_family": vehicle_name, "usage_context": usage_context.value}

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(Path(directory) / "envkv.sqlite3")
            app.state.compliance_service = FakeComplianceService()
            response = TestClient(app).post(
                "/api/v1/vehicle/model-range",
                headers={"X-API-Key": "test-extension-key"},
                json={"vehicle_name": "Golf", "usage_context": "social_media"},
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual("model_range", response.json()["result_type"])
            self.assertEqual("social_media", response.json()["usage_context"])

    def test_incomplete_model_range_is_reported_as_a_conflict(self) -> None:
        class FakeComplianceService:
            def create_model_range(self, vehicle_name: str, usage_context: UsageContext) -> dict[str, object]:
                raise ManualReviewRequired(
                    "Die Modellspanne ist unvollständig.",
                    [{"type_id": "type-x", "name": "Golf 1.5 TSI", "reason": "nicht eindeutig baubar"}],
                )

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(Path(directory) / "envkv.sqlite3")
            app.state.compliance_service = FakeComplianceService()
            response = TestClient(app).post(
                "/api/v1/vehicle/model-range",
                headers={"X-API-Key": "test-extension-key"},
                json={"vehicle_name": "Golf"},
            )
            self.assertEqual(409, response.status_code)
            detail = response.json()["detail"]
            self.assertIn("unvollständig", detail["message"])
            self.assertEqual("type-x", detail["candidates"][0]["type_id"])

    def test_embeddable_snippet_endpoint_returns_plain_html_text(self) -> None:
        class FakeComplianceService:
            def create(self, vehicle_name: str, usage_context: UsageContext, selected_type_id: str | None = None) -> dict[str, object]:
                return {"data_sheet": _SAMPLE_SHEET}

        with tempfile.TemporaryDirectory() as directory:
            app = self._app(Path(directory) / "envkv.sqlite3")
            app.state.compliance_service = FakeComplianceService()
            response = TestClient(app).post(
                "/api/v1/vehicle/data-sheet-snippet.html",
                headers={"X-API-Key": "test-extension-key"},
                json={"vehicle_name": "ID.5 Pure 140 kW", "usage_context": "online_offer"},
            )
            self.assertEqual(200, response.status_code)
            self.assertTrue(response.headers["content-type"].startswith("text/plain"))
            self.assertIn("kahle-envkv", response.text)
            self.assertNotIn("<!doctype", response.text.lower())

    def test_local_offer_date_follows_the_configured_timezone(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from backend.app.services.compliance import local_today

        # Kurz vor Mitternacht Ortszeit liegt UTC noch im Vortag. Das
        # Erstellungsdatum und der Profilwechsel müssen der Ortszeit folgen.
        berlin = ZoneInfo("Europe/Berlin")
        self.assertEqual(datetime.now(berlin).date(), local_today("Europe/Berlin"))
        self.assertNotEqual(local_today("Pacific/Kiritimati"), local_today("Pacific/Niue"))

    def test_retention_cleanup_is_wired_to_the_running_service(self) -> None:
        from datetime import UTC, datetime, timedelta

        from backend.app.storage import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "envkv.sqlite3"
            store = SQLiteStore(path)
            old = (datetime.now(UTC) - timedelta(days=400)).isoformat()
            store.write_audit({
                "timestamp": old, "user_input": "ID.5",
                "parsed_vehicle": {}, "matched_vehicle": {}, "model_id": "m",
                "model_year": 2027, "match_confidence": 1.0, "wltp_raw": {},
                "generated_output": "Text", "source": {},
            })
            removed = store.prune(retention_days=90)
            self.assertEqual(1, removed["audit_deleted"])

            # Der Dienst hält den Store, damit der Bereinigungslauf ihn erreicht.
            app = self._app(path)
            self.assertTrue(hasattr(app.state, "store"))


if __name__ == "__main__":
    unittest.main()
