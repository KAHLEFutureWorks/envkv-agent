from __future__ import annotations

import tempfile
import unittest
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.app.services.volkswagen.provider import (
    ManualReviewRequired, VehicleNotEligible, VehicleNotFound, VolkswagenProvider, _brand_for_input, _is_excluded_n1_candidate,
)
from backend.app.storage import SQLiteStore


class FakeVolkswagenClient:
    def __init__(self) -> None:
        self.wltp_calls = 0

    def countries(self) -> dict[str, Any]:
        return {"data": [{"code": "DE", "description": "Germany"}]}

    def brands(self, market: str) -> dict[str, Any]:
        return {"data": [{"id": "brand-vw", "code": "VW", "description": "Volkswagen"}]}

    def models(self, market: str, brand_id: str) -> dict[str, Any]:
        return {"data": [{"id": "model-id5", "code": "MODEL:30100_30450", "description": "Der ID.5"}]}

    def model_types(self, market: str, model_id: str) -> dict[str, Any]:
        common = {
            "description": "ID.5 Pure  140 kW (190 PS) 58 kWh 1-Gang-Automatik",
            "modelyear_code": "MODELYEAR:2027",
        }
        return {
            "data": [
                {**common, "id": "type-package", "code": "TYPE:E392JM-GRB1RB1", "extensions": [{"code": "PACKET:RB1"}]},
                {**common, "id": "type-pure", "code": "TYPE:E392JM", "extensions": []},
            ]
        }

    def base_configuration(self, market: str, brand_id: str, type_id: str, modelyear_code: str) -> dict[str, Any]:
        return {
            "data": [{
                "brand_id": "brand-vw",
                "model_id": "model-id5",
                "options": [{"id": "type-option"}, {"id": "modelyear-option"}],
            }]
        }

    def check(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
        return {"buildable": True, "distinct": True}

    def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
        self.wltp_calls += 1
        return {
            "data": [{
                "wltp_metadata": {"status": 200},
                "wltp_value": [{
                    "data_version": "3",
                    "engine_type": "PEV",
                    "fuel_types": ["ELECTRICAL"],
                    "interpolations": [
                        {"value_type": "CONSUMPTION", "fuel_type": "ELECTRICAL", "phase": "COMBINED", "value": 155.448682, "unit": "Wh/km"},
                        {"value_type": "RANGE", "fuel_type": "ELECTRICAL", "phase": "COMBINED", "value": 445.796, "unit": "km"},
                        {"value_type": "CO2", "fuel_type": "ELECTRICAL", "phase": "COMBINED", "value": 0.0, "unit": "g/km"},
                    ],
                    "energy_efficiency": {"class_wltp": "A", "iso": "DE"},
                }],
            }]
        }


class VolkswagenProviderTests(unittest.TestCase):
    def test_pilot_examples_are_routed_to_the_expected_group_brand(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "pilot_vehicle_examples.json"
        examples = json.loads(fixture.read_text(encoding="utf-8"))
        for example in examples:
            with self.subTest(vehicle=example["input"]):
                brand, _ = _brand_for_input(example["input"])
                self.assertEqual(example["brand"], brand["display"])

    def test_id_polo_without_explicit_brand_is_routed_to_volkswagen(self) -> None:
        brand, query = _brand_for_input("ID. Polo Life 99 kW (135 PS) 37 kWh 1-Gang-Automatik")
        self.assertEqual("Volkswagen", brand["display"])
        self.assertEqual("id. polo life 99 kw (135 ps) 37 kwh 1-gang-automatik", query)

    def test_brandless_models_are_routed_to_their_group_catalogs(self) -> None:
        cases = (
            ("Octavia", "Škoda", "octavia"),
            ("A3", "Audi", "a3"),
            ("Arona", "SEAT", "arona"),
            ("Born", "CUPRA", "cupra born"),
        )
        for vehicle_name, display, query in cases:
            with self.subTest(vehicle_name=vehicle_name):
                brand, actual_query = _brand_for_input(vehicle_name)
                self.assertEqual(display, brand["display"])
                self.assertEqual(query, actual_query)

    def test_overlapping_seat_and_cupra_models_require_the_brand(self) -> None:
        for vehicle_name in ("Leon", "Ateca", "Leon 110 kW", "Ateca Style"):
            with self.subTest(vehicle_name=vehicle_name):
                with self.assertRaisesRegex(VehicleNotFound, "SEAT oder CUPRA"):
                    _brand_for_input(vehicle_name)

        seat, seat_query = _brand_for_input("SEAT Leon")
        cupra, cupra_query = _brand_for_input("CUPRA Leon")
        self.assertEqual(("SEAT", "leon"), (seat["display"], seat_query))
        self.assertEqual(("CUPRA", "cupra leon"), (cupra["display"], cupra_query))

    def test_cupra_uses_seat_catalog_but_keeps_cupra_identity(self) -> None:
        brand, query = _brand_for_input("CUPRA Born 140 kW (190 PS) 58 kWh")
        self.assertEqual("SE", brand["code"])
        self.assertEqual("CUPRA", brand["display"])
        self.assertEqual("cupra born 140 kw (190 ps) 58 kwh", query)

    def test_cupra_born_does_not_require_transmission_in_catalog_description(self) -> None:
        class CupraClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-seat", "code": "SE", "description": "SEAT"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-born", "description": "CUPRA Born"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-born", "code": "TYPE:BORN140",
                    "description": "CUPRA Born 140 kW (190 PS) 58 kWh",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                CupraClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            result = provider.retrieve("CUPRA Born 140 kW (190 PS) 58 kWh")

        self.assertEqual("CUPRA", result.vehicle.brand)
        self.assertEqual("Born", result.vehicle.model)
        self.assertEqual("", result.vehicle.transmission)

    def test_seat_and_cupra_are_separated_by_the_catalog_name_prefix(self) -> None:
        # SEAT und CUPRA liegen in OKAPI unter derselben Marke und werden nur
        # über den Namenszusatz unterschieden.
        class SharedCatalogClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-seat", "code": "SE", "description": "SEAT"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [
                    {"id": "model-seat-leon", "description": "SEAT Leon"},
                    {"id": "model-cupra-leon", "description": "CUPRA Leon"},
                ]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                label = "SEAT Leon" if model_id == "model-seat-leon" else "CUPRA Leon"
                return {"data": [{
                    "id": f"type-{model_id}", "code": "TYPE:LEON",
                    "description": f"{label} 1,5 l eTSI 110 kW (150 PS) 7-Gang-DSG",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            provider = VolkswagenProvider(SharedCatalogClient(), store)
            seat = provider.retrieve("Seat Leon 1,5 l eTSI 110 kW")
            cupra = provider.retrieve("CUPRA Leon 1,5 l eTSI 110 kW")

        self.assertEqual(("SEAT", "Leon"), (seat.vehicle.brand, seat.vehicle.model))
        self.assertEqual(("CUPRA", "Leon"), (cupra.vehicle.brand, cupra.vehicle.model))
        # Die Marke steht in einem eigenen Feld und darf nicht doppelt erscheinen.
        self.assertNotIn("SEAT", seat.vehicle.model)
        self.assertNotIn("CUPRA", cupra.vehicle.model)

    def test_model_name_is_found_although_the_catalog_prefixes_the_brand(self) -> None:
        class AudiClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-audi", "code": "AU", "description": "Audi"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-a3", "description": "Audi A3"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-a3", "code": "TYPE:A3",
                    "description": "Audi A3 Sportback 1,5 l TFSI 110 kW (150 PS) 7-Gang-S tronic",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(AudiClient(), SQLiteStore(Path(directory) / "envkv.sqlite3"))
            result = provider.retrieve("A3")

        self.assertEqual("Audi", result.vehicle.brand)
        self.assertEqual("A3", result.vehicle.model)

    def test_cargo_and_kasten_types_are_excluded_from_m1_v1_scope(self) -> None:
        self.assertTrue(_is_excluded_n1_candidate("VN", "ID. Buzz Cargo Pro 210 kW"))
        self.assertTrue(_is_excluded_n1_candidate("VN", "E-Transporter Kasten 210 kW"))
        self.assertTrue(_is_excluded_n1_candidate("VN", "Transporter Pritsche 110 kW"))
        self.assertTrue(_is_excluded_n1_candidate("VN", "Crafter 35 130 kW"))
        self.assertFalse(_is_excluded_n1_candidate("VN", "e-Transporter Kombi 210 kW"))
        self.assertFalse(_is_excluded_n1_candidate("VN", "Multivan Life eHybrid"))

    def test_resolves_skoda_vehicle_through_group_brand_catalog(self) -> None:
        class SkodaClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-skoda", "code": "SK", "description": "SKODA"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-enyaq", "description": "Der Enyaq"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-enyaq-60",
                    "code": "TYPE:ENYAQ60",
                    "description": "Enyaq Selection 60 (63 kWh) 150 kW 1-Gang-Automatik",
                    "modelyear_code": "MODELYEAR:2027",
                    "extensions": [],
                }]}

            def base_configuration(self, market: str, brand_id: str, type_id: str, modelyear_code: str) -> dict[str, Any]:
                return {"data": [{
                    "brand_id": "brand-skoda", "model_id": "model-enyaq",
                    "options": [{"id": "type-option"}, {"id": "modelyear-option"}],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                SkodaClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            result = provider.retrieve(
                "Škoda Enyaq Selection 60 (63 kWh) 150 kW 1-Gang-Automatik"
            )

            self.assertEqual("Škoda", result.vehicle.brand)
            self.assertEqual("Enyaq", result.vehicle.model)
            self.assertEqual("Selection 60", result.vehicle.trim)
            self.assertEqual(150, result.vehicle.power_kw)
            self.assertEqual(63, result.vehicle.battery_kwh)

    def test_prefers_exact_id7_model_over_id7_tourer(self) -> None:
        class Id7Client(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {
                    "data": [
                        {"id": "model-id7", "description": "Der ID.7"},
                        {"id": "model-id7-tourer", "description": "Der ID.7 Tourer"},
                    ]
                }

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                self.requested_model_id = model_id
                return {
                    "data": [{
                        "id": "type-id7-pro",
                        "code": "TYPE:ID7PRO",
                        "description": "ID.7 Pro 210 kW (286 PS) 77 kWh 1-Gang-Automatik",
                        "modelyear_code": "MODELYEAR:2027",
                        "extensions": [],
                    }]
                }

        with tempfile.TemporaryDirectory() as directory:
            client = Id7Client()
            provider = VolkswagenProvider(client, SQLiteStore(Path(directory) / "envkv.sqlite3"))
            vehicle = provider.retrieve("ID.7 Pro 210 kW (286 PS) 77 kWh 1-Gang-Automatik")

            self.assertEqual("model-id7", client.requested_model_id)
            self.assertEqual("ID.7", vehicle.vehicle.model)

    def test_generic_model_name_returns_types_from_the_whole_model_family(self) -> None:
        class GolfFamilyClient(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [
                    {"id": "model-golf", "description": "Der Golf"},
                    {"id": "model-golf-variant", "description": "Der Golf Variant"},
                    {"id": "model-polo", "description": "Der Polo"},
                ]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                name = "Golf Life 85 kW 6-Gang" if model_id == "model-golf" else "Golf Variant Style 110 kW 7-Gang-DSG"
                return {"data": [{
                    "id": f"type-{model_id}", "code": f"TYPE:{model_id}",
                    "description": name, "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                GolfFamilyClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            with self.assertRaises(ManualReviewRequired) as context:
                provider.retrieve("Golf")

        self.assertEqual(
            {"Golf Life 85 kW 6-Gang", "Golf Variant Style 110 kW 7-Gang-DSG"},
            {candidate["name"] for candidate in context.exception.candidates},
        )

    def test_generic_model_family_search_works_for_all_passenger_brands(self) -> None:
        cases = (
            ("A3", "AU", "Audi", ("A3", "A3 Sportback")),
            ("SEAT Leon", "SE", "SEAT", ("Leon", "Leon Sportstourer")),
            ("Octavia", "SK", "SKODA", ("Octavia", "Octavia Combi")),
            ("Born", "SE", "SEAT", ("CUPRA Born", "CUPRA Born VZ")),
        )
        for entered, brand_code, catalog_brand, model_names in cases:
            with self.subTest(entered=entered):
                class FamilyClient(FakeVolkswagenClient):
                    def brands(self, market: str) -> dict[str, Any]:
                        return {"data": [{"id": "brand", "code": brand_code, "description": catalog_brand}]}

                    def models(self, market: str, brand_id: str) -> dict[str, Any]:
                        return {"data": [
                            {"id": f"model-{index}", "description": name}
                            for index, name in enumerate(model_names)
                        ]}

                    def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                        index = int(model_id.rsplit("-", 1)[-1])
                        return {"data": [{
                            "id": f"type-{index}", "code": f"TYPE:{index}",
                            "description": f"{model_names[index]} Style 110 kW 7-Gang-DSG",
                            "modelyear_code": "MODELYEAR:2027", "extensions": [],
                        }]}

                with tempfile.TemporaryDirectory() as directory:
                    provider = VolkswagenProvider(
                        FamilyClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
                    )
                    with self.assertRaises(ManualReviewRequired) as context:
                        provider.retrieve(entered)
                self.assertEqual(2, len(context.exception.candidates))

    def test_selected_type_from_sibling_model_is_resolved(self) -> None:
        class GolfFamilyClient(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [
                    {"id": "model-golf", "description": "Der Golf"},
                    {"id": "model-golf-variant", "description": "Der Golf Variant"},
                ]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": f"type-{model_id}", "code": f"TYPE:{model_id}",
                    "description": ("Golf Life 85 kW 6-Gang" if model_id == "model-golf" else "Golf Variant Style 110 kW 7-Gang-DSG"),
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                GolfFamilyClient(), SQLiteStore(Path(directory) / "envkv.sqlite3"),
                require_vehicle_class_approval=True,
            )
            result = provider.retrieve("Golf", "type-model-golf-variant")
            self.assertEqual("type-model-golf-variant", result.vehicle.type_id)

    def test_troc_cabriolet_energy_does_not_need_individual_m1_approval(self) -> None:
        class TrocClient(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-troc-cabriolet", "description": "Das T-Roc Cabriolet"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-troc-energy-85", "code": "TYPE:TROCENERGY85",
                    "description": "T-Roc Cabriolet ENERGY 1,0 l TSI OPF 85 kW (116 PS) 6-Gang",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                TrocClient(), SQLiteStore(Path(directory) / "envkv.sqlite3"),
                require_vehicle_class_approval=True,
            )
            result = provider.retrieve("T-Roc Cabriolet ENERGY 1.0 l TSI OPF 85 kW")
            self.assertEqual("type-troc-energy-85", result.vehicle.type_id)
            self.assertEqual([], provider.store.list_pending_vehicle_classes())

    def test_retrieves_exact_package_free_type_and_caches_wltp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = FakeVolkswagenClient()
            provider = VolkswagenProvider(client, SQLiteStore(Path(directory) / "envkv.sqlite3"))

            first = provider.retrieve("ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik")
            second = provider.retrieve("ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik")

            self.assertEqual("TYPE:E392JM", first.vehicle.type_code)
            self.assertEqual(2027, first.vehicle.model_year)
            self.assertEqual("15.5", str(first.consumption.combined_kwh_100km))
            self.assertEqual(446, first.consumption.electric_range_km)
            self.assertEqual("A", first.consumption.co2_class)
            self.assertEqual(first.consumption, second.consumption)
            self.assertEqual(1, client.wltp_calls)

    def test_retrieves_petrol_vehicle_from_captured_wltp(self) -> None:
        class PetrolClient(FakeVolkswagenClient):
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "t-cross", "description": "T-Cross"}]}
            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{"id": "petrol", "code": "TYPE:D313BZ", "description": "T-Cross Style 1.0 l TSI 85 kW (116 PS) 7-Gang-Doppelkupplungsgetriebe DSG", "modelyear_code": "MODELYEAR:2027", "extensions": []}]}
            def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                payload = json.loads((Path(__file__).parents[2] / "okapi-t-cross-petrol.json").read_text(encoding="utf-8-sig"))
                return payload["wltp"]
            def order(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                payload = json.loads((Path(__file__).parents[2] / "okapi-t-cross-order.json").read_text(encoding="utf-8-sig"))
                return payload["order"]
        with tempfile.TemporaryDirectory() as directory:
            result = VolkswagenProvider(PetrolClient(), SQLiteStore(Path(directory) / "db.sqlite3")).retrieve("T-Cross Style 1.0 l TSI OPF 85 kW (116 PS) 7-Gang-Doppelkupplungsgetriebe DSG")
        self.assertEqual("petrol", result.powertrain.value)
        self.assertEqual(Decimal("5.8"), result.consumption.combined_l_100km)
        self.assertEqual(999, result.vehicle.engine_displacement_cc)
        self.assertTrue(result.tax_data_verified)

    def test_retrieves_plug_in_hybrid_with_decimal_battery(self) -> None:
        class PhevClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-vn", "code": "VN", "description": "Volkswagen Commercial Vehicles"}]}
            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "multivan", "description": "Der neue Multivan"}]}
            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{"id": "phev", "code": "TYPE:SUNGH9", "description": "Multivan Life Generation 1,5 l eHybrid OPF 4MOTION 130 kW 100 kW 19,7 kWh 6-Gang-Doppelkupplungsgetriebe", "modelyear_code": "MODELYEAR:2027", "extensions": []}]}
            def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                payload = json.loads((Path(__file__).parents[2] / "okapi-multivan-phev.json").read_text(encoding="utf-8-sig"))
                return payload["wltp"]
        with tempfile.TemporaryDirectory() as directory:
            result = VolkswagenProvider(PhevClient(), SQLiteStore(Path(directory) / "db.sqlite3")).retrieve("Multivan Life Generation 1,5 l eHybrid OPF 4MOTION 130 kW 100 kW 19,7 kWh 6-Gang-Doppelkupplungsgetriebe")
        self.assertEqual("plug_in_hybrid", result.powertrain.value)
        self.assertEqual(Decimal("19.7"), result.vehicle.battery_kwh)
        self.assertEqual(Decimal("2.8"), result.consumption.combined_l_100km)

    def test_multivan_input_may_omit_catalog_motor_label(self) -> None:
        from backend.app.services.volkswagen.provider import _type_search_text
        entered = 'Multivan Life "Generation" 1,5 l eHybrid OPF 4MOTION 130 kW 100 kW 19,7 kWh Getriebe: 6-Gang-Doppelkupplungsgetriebe Radstand: 3124 mm LÜ langer Überhang'
        catalog = 'Multivan Life "Generation" Motor: 1,5 l eHybrid OPF 4MOTION 130 kW 100 kW 19,7 kWh Getriebe: 6-Gang-Doppelkupplungsgetriebe Radstand: 3124 mm LÜ langer Überhang'
        self.assertIn(_type_search_text(entered), _type_search_text(catalog))

    def test_vehicle_class_approval_is_limited_to_commercial_vehicle_catalog(self) -> None:
        class CommercialClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-vn", "code": "VN", "description": "Volkswagen Commercial Vehicles"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-multivan", "description": "Der Multivan"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-multivan", "code": "TYPE:MULTIVAN",
                    "description": "Multivan Life 110 kW 7-Gang-Doppelkupplungsgetriebe",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            provider = VolkswagenProvider(
                CommercialClient(), store, require_vehicle_class_approval=True
            )
            result = provider.retrieve("Multivan Life 110 kW 7-Gang-Doppelkupplungsgetriebe")
            self.assertEqual("UNKNOWN", result.vehicle.vehicle_class)
            self.assertEqual("type-multivan", store.list_pending_vehicle_classes()[0]["type_id"])
            store.approve_vehicle_class("type-multivan", "N1", "CoC Feld 0.4", "tester")
            with self.assertRaises(VehicleNotEligible):
                provider.retrieve("Multivan Life 110 kW 7-Gang-Doppelkupplungsgetriebe")

    def test_commercial_vehicle_approval_is_shared_by_basetype(self) -> None:
        class CommercialClient(FakeVolkswagenClient):
            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "brand-vn", "code": "VN", "description": "Volkswagen Commercial Vehicles"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "model-caddy", "description": "Der Caddy"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-caddy-life", "code": "TYPE:CADDYLIFE", "basetype_code": "BASETYPE:CADDY15",
                    "description": "Caddy Life 85 kW 7-Gang-Doppelkupplungsgetriebe",
                    "modelyear_code": "MODELYEAR:2027", "extensions": [],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "envkv.sqlite3")
            provider = VolkswagenProvider(CommercialClient(), store, require_vehicle_class_approval=True)
            first = provider.retrieve("Caddy Life 85 kW 7-Gang-Doppelkupplungsgetriebe")
            self.assertEqual("UNKNOWN", first.vehicle.vehicle_class)
            self.assertEqual("BASETYPE:CADDY15", store.list_pending_vehicle_classes()[0]["type_id"])
            store.approve_vehicle_class("BASETYPE:CADDY15", "M1", "CoC Feld 0.4", "tester")
            approved = provider.retrieve("Caddy Life 85 kW 7-Gang-Doppelkupplungsgetriebe")
            self.assertEqual("M1", approved.vehicle.vehicle_class)

    def test_accepts_one_exact_type_with_standard_catalog_extension(self) -> None:
        class StandardPackageClient(FakeVolkswagenClient):
            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [{
                    "id": "type-pure", "code": "TYPE:E392JM",
                    "description": "ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik",
                    "modelyear_code": "MODELYEAR:2027",
                    "extensions": [{"code": "PACKET:YOR", "description": "Online-Dienste"}],
                }]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                StandardPackageClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            result = provider.retrieve("ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik")
            self.assertEqual("TYPE:E392JM", result.vehicle.type_code)

    def test_rejects_ambiguous_package_free_type(self) -> None:
        class AmbiguousClient(FakeVolkswagenClient):
            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                payload = super().model_types(market, model_id)
                payload["data"][0]["extensions"] = []
                return payload

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                AmbiguousClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            with self.assertRaises(ManualReviewRequired) as context:
                provider.retrieve("ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik")
            self.assertEqual(2, len(context.exception.candidates))
            self.assertTrue(all(candidate.get("type_id") for candidate in context.exception.candidates))

            selected = provider.retrieve(
                "ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik", "type-pure"
            )
            self.assertEqual("type-pure", selected.vehicle.type_id)

    def test_returns_all_ranked_type_candidates_without_five_item_limit(self) -> None:
        class ManyTypesClient(FakeVolkswagenClient):
            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                return {"data": [
                    {
                        "id": f"type-{index}", "code": f"TYPE:{index}",
                        "description": f"ID.5 Variante {index} 140 kW 1-Gang-Automatik",
                        "modelyear_code": "MODELYEAR:2027", "extensions": [],
                    }
                    for index in range(1, 8)
                ]}

        with tempfile.TemporaryDirectory() as directory:
            provider = VolkswagenProvider(
                ManyTypesClient(), SQLiteStore(Path(directory) / "envkv.sqlite3")
            )
            with self.assertRaises(ManualReviewRequired) as context:
                provider.retrieve("ID.5 Balance 140 kW 1-Gang-Automatik")
            self.assertEqual(7, len(context.exception.candidates))


if __name__ == "__main__":
    unittest.main()
