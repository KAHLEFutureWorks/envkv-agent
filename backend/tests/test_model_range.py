from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.domain.envkv import (
    ComplianceProfileIncomplete,
    ConsumptionValues,
    PowertrainType,
    UsageContext,
    build_model_range_group,
    render_model_range_text,
)
from backend.app.services.volkswagen.provider import (
    ManualReviewRequired, VehicleNotEligible, VolkswagenProvider,
)
from backend.app.storage import SQLiteStore
from backend.tests.test_volkswagen_provider import FakeVolkswagenClient


def _petrol(fuel: str, co2: str, co2_class: str) -> ConsumptionValues:
    return ConsumptionValues(
        combined_kwh_100km=None, combined_l_100km=Decimal(fuel),
        co2_g_km=Decimal(co2), co2_class=co2_class, electric_range_km=None,
        fuel_type="PETROL",
    )


class ModelRangeAggregationTests(unittest.TestCase):
    def test_range_reports_lowest_and_highest_value_and_both_co2_classes(self) -> None:
        group = build_model_range_group(PowertrainType.PETROL, [
            ("TYPE:A", _petrol("5.4", "123.4", "C")),
            ("TYPE:B", _petrol("6.8", "154.0", "E")),
            ("TYPE:C", _petrol("5.9", "131.1", "D")),
        ])
        self.assertEqual((Decimal("5.4"), Decimal("6.8")), group.combined_l_100km)
        # CO2 wird in ganzen Gramm ausgewiesen, wie in den Labels des Herstellers.
        self.assertEqual((Decimal("123"), Decimal("154")), group.co2_g_km)
        self.assertEqual("C", group.co2_class_best)
        self.assertEqual("E", group.co2_class_worst)
        self.assertEqual(3, group.variant_count)
        self.assertEqual(("TYPE:A", "TYPE:B", "TYPE:C"), group.type_codes)

    def test_single_variant_range_does_not_render_a_pseudo_span(self) -> None:
        group = build_model_range_group(PowertrainType.PETROL, [("TYPE:A", _petrol("5.4", "123.4", "C"))])
        text = render_model_range_text(_range([group]))
        self.assertIn("Energieverbrauch kombiniert: 5,4 l/100 km", text)
        self.assertNotIn("5,4 bis 5,4", text)
        self.assertIn("CO₂-Klasse: C", text)
        self.assertNotIn("CO₂-Klassen", text)

    def test_incomplete_variant_blocks_the_whole_range(self) -> None:
        incomplete = ConsumptionValues(
            combined_kwh_100km=None, combined_l_100km=None,
            co2_g_km=Decimal("140"), co2_class="D", electric_range_km=None,
        )
        with self.assertRaises(ComplianceProfileIncomplete):
            build_model_range_group(PowertrainType.PETROL, [
                ("TYPE:A", _petrol("5.4", "123.4", "C")),
                ("TYPE:B", incomplete),
            ])

    def test_mixed_drives_are_never_merged_into_one_span(self) -> None:
        petrol = build_model_range_group(PowertrainType.PETROL, [
            ("TYPE:A", _petrol("5.4", "123.4", "C")), ("TYPE:B", _petrol("6.8", "154.0", "E")),
        ])
        electric = build_model_range_group(PowertrainType.BATTERY_ELECTRIC, [(
            "TYPE:E", ConsumptionValues(
                combined_kwh_100km=Decimal("15.5"), combined_l_100km=None,
                co2_g_km=Decimal("0"), co2_class="A", electric_range_km=446),
        )])
        text = render_model_range_text(_range([petrol, electric]))
        self.assertIn("Benzin: Energieverbrauch kombiniert: 5,4 bis 6,8 l/100 km", text)
        self.assertIn("Rein elektrisch: Energieverbrauch kombiniert: 15,5 kWh/100 km", text)
        # Liter und Kilowattstunden dürfen nicht in derselben Spanne stehen.
        self.assertNotIn("l/100 km und", text)
        self.assertIn("3 Varianten", text)

    def test_model_range_is_refused_for_a_concrete_offer(self) -> None:
        group = build_model_range_group(PowertrainType.PETROL, [("TYPE:A", _petrol("5.4", "123.4", "C"))])
        with self.assertRaises(ComplianceProfileIncomplete):
            render_model_range_text(_range([group]), UsageContext.ONLINE_OFFER)


def _range(groups: list[Any]) -> Any:
    from backend.app.domain.envkv import VerifiedModelRange
    return VerifiedModelRange(
        brand="Volkswagen", model_family="Golf", groups=tuple(groups),
        model_ids=("model-golf",), model_years=(2027,), type_ids=("t1",),
        provider="Volkswagen OKAPI", retrieved_at="2026-08-21T10:00:00+00:00",
    )


class ModelRangeProviderTests(unittest.TestCase):
    def test_range_covers_every_type_of_the_family(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            client = FakeVolkswagenClient()
            provider = VolkswagenProvider(client, SQLiteStore(Path(folder) / "db.sqlite3"))
            data = provider.retrieve_model_range("ID.5")
        self.assertEqual(1, len(data.groups))
        self.assertEqual(PowertrainType.BATTERY_ELECTRIC, data.groups[0].powertrain)
        # Beide Typen des Katalogs, auch der mit Ausstattungspaket, sind enthalten.
        self.assertEqual(2, data.groups[0].variant_count)
        self.assertEqual(("type-package", "type-pure"), tuple(sorted(data.type_ids)))
        self.assertIn("15,5 kWh/100 km", render_model_range_text(data))

    def test_range_is_limited_to_the_variants_the_input_addresses(self) -> None:
        class GolfClient(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-golf", "code": "MODEL:GOLF", "description": "Der Golf"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                common = {"modelyear_code": "MODELYEAR:2027", "extensions": []}
                return {"data": [
                    {**common, "id": "type-energy-1", "code": "TYPE:EN1",
                     "description": "Golf ENERGY 1,5 l eTSI 85 kW (116 PS) 7-Gang-DSG"},
                    {**common, "id": "type-energy-2", "code": "TYPE:EN2",
                     "description": "Golf ENERGY 2,0 l TDI 110 kW (150 PS) 7-Gang-DSG"},
                    {**common, "id": "type-gti", "code": "TYPE:GTI",
                     "description": "Golf GTI 2,0 l TSI 195 kW (265 PS) 7-Gang-DSG"},
                ]}

        with tempfile.TemporaryDirectory() as folder:
            provider = VolkswagenProvider(GolfClient(), SQLiteStore(Path(folder) / "db.sqlite3"))
            energy = provider.retrieve_model_range("Golf Energy")
            whole = provider.retrieve_model_range("Golf")
        self.assertEqual(("type-energy-1", "type-energy-2"), tuple(sorted(energy.type_ids)))
        self.assertEqual(2, sum(g.variant_count for g in energy.groups))
        # Ohne einschränkenden Zusatz umfasst die Spanne die ganze Familie.
        self.assertEqual(3, sum(g.variant_count for g in whole.groups))

    def test_unresolvable_variant_blocks_the_range_and_names_the_type(self) -> None:
        class BrokenClient(FakeVolkswagenClient):
            def check(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                return {"buildable": True, "distinct": False}

        with tempfile.TemporaryDirectory() as folder:
            provider = VolkswagenProvider(BrokenClient(), SQLiteStore(Path(folder) / "db.sqlite3"))
            with self.assertRaises(ManualReviewRequired) as caught:
                provider.retrieve_model_range("ID.5")
        self.assertTrue(caught.exception.candidates)
        self.assertIn("type-", caught.exception.candidates[0]["type_id"])


if __name__ == "__main__":
    unittest.main()
