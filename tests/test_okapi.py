from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from typing import Any

from spike.okapi import OkapiClient, OkapiError
from spike import okapi_probe
from spike.okapi_probe import extract_verified_wltp, fetch_wltp_for_result, run_probe


class FakeResponse:
    def __init__(self, body: dict[str, Any] | list[Any]) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class OkapiClientTests(unittest.TestCase):
    def test_normalizes_captured_wltp_examples_for_all_supported_powertrains(self) -> None:
        project_root = Path(__file__).parent.parent
        cases = {
            "okapi-cupra-born-electric.json": ("PEV", "combined_kwh_100km", 14.2),
            "okapi-enyaq-electric.json": ("PEV", "combined_kwh_100km", 15.0),
            "okapi-karoq-diesel.json": ("ICE", "combined_l_100km", 5.6),
            "okapi-t-cross-petrol.json": ("ICE", "combined_l_100km", 5.8),
            "okapi-t-roc-mildhybrid.json": ("NOVC_HEV", "combined_l_100km", 5.5),
            "okapi-multivan-phev.json": ("OVC_HEV", "weighted_l_100km", 2.8),
        }
        for filename, (engine_type, field, expected) in cases.items():
            with self.subTest(filename=filename):
                captured = json.loads((project_root / filename).read_text(encoding="utf-8-sig"))
                values = extract_verified_wltp(captured["wltp"])
                self.assertEqual(engine_type, values["engine_type"])
                self.assertEqual(expected, values[field])

        multivan = json.loads(
            (project_root / "okapi-multivan-phev.json").read_text(encoding="utf-8-sig")
        )
        phev = extract_verified_wltp(multivan["wltp"])
        self.assertEqual(15.8, phev["weighted_kwh_100km"])
        self.assertEqual(24.2, phev["pure_electric_kwh_100km"])
        self.assertEqual(7.6, phev["discharged_l_100km"])
        self.assertEqual(63.7, phev["co2_g_km"])
        self.assertEqual("B", phev["co2_class"])
        self.assertEqual("F", phev["co2_class_discharged"])
        self.assertEqual(90, phev["electric_range_km"])
        self.assertEqual(9.1, phev["phase_l_100km"]["low"])
        self.assertEqual(29.3, phev["phase_kwh_100km"]["extra_high"])

        petrol = json.loads(
            (project_root / "okapi-t-cross-petrol.json").read_text(encoding="utf-8-sig")
        )
        petrol_values = extract_verified_wltp(petrol["wltp"])
        self.assertEqual(
            {"low": 7.1, "medium": 5.5, "high": 5.0, "extra_high": 6.1},
            petrol_values["phase_l_100km"],
        )

    def test_rate_limited_request_is_repeated_after_the_requested_delay(self) -> None:
        from urllib.error import HTTPError

        attempts = {"count": 0}
        waits: list[float] = []

        def transport(request: object) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise HTTPError(url, 429, "Too Many Requests", {"Retry-After": "7"}, None)
            return FakeResponse({"data": [{"code": "DE"}]})

        client = OkapiClient(
            "client", "secret", transport=transport,
            clock=lambda: 100, sleep=waits.append,
        )
        self.assertEqual({"data": [{"code": "DE"}]}, client.countries())
        self.assertEqual(3, attempts["count"])
        # Der Retry-After-Kopf des Herstellers hat Vorrang vor der eigenen Staffelung.
        self.assertEqual([7.0, 7.0], waits)

    def test_persistent_rate_limit_is_reported_and_not_retried_forever(self) -> None:
        from urllib.error import HTTPError

        attempts = {"count": 0}

        def transport(request: object) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            attempts["count"] += 1
            raise HTTPError(url, 429, "Too Many Requests", {}, None)

        client = OkapiClient(
            "client", "secret", transport=transport,
            clock=lambda: 100, sleep=lambda _seconds: None, max_retries=2,
        )
        with self.assertRaises(OkapiError) as caught:
            client.countries()
        self.assertIn("429", str(caught.exception))
        self.assertEqual(3, attempts["count"])

    def test_client_errors_are_not_retried(self) -> None:
        from urllib.error import HTTPError

        attempts = {"count": 0}

        def transport(request: object) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            attempts["count"] += 1
            raise HTTPError(url, 404, "Not Found", {}, None)

        client = OkapiClient("client", "secret", transport=transport, clock=lambda: 100, sleep=lambda _s: None)
        with self.assertRaises(OkapiError):
            client.countries()
        self.assertEqual(1, attempts["count"])

    def test_minimum_interval_spaces_out_consecutive_calls(self) -> None:
        now = {"value": 1000.0}
        waits: list[float] = []

        def transport(request: object) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            return FakeResponse({"data": []})

        def sleep(seconds: float) -> None:
            waits.append(seconds)
            now["value"] += seconds

        client = OkapiClient(
            "client", "secret", transport=transport,
            clock=lambda: now["value"], sleep=sleep, min_interval_seconds=0.5,
        )
        client.countries()
        client.countries()
        # Der Tokenabruf und die beiden Katalogaufrufe werden gleichmäßig gebremst.
        self.assertTrue(waits)
        self.assertTrue(all(abs(wait - 0.5) < 1e-9 for wait in waits), waits)

    def test_reuses_access_token_and_builds_catalog_path(self) -> None:
        requests: list[object] = []

        def transport(request: object) -> FakeResponse:
            requests.append(request)
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            return FakeResponse({"data": []})

        client = OkapiClient("client", "secret", transport=transport, clock=lambda: 100)
        client.countries()
        client.brands("DE")

        self.assertEqual(3, len(requests))
        self.assertTrue(requests[1].full_url.endswith("/v3/countries"))  # type: ignore[attr-defined]
        self.assertTrue(requests[2].full_url.endswith("/v3/catalog/DE/brands"))  # type: ignore[attr-defined]

    def test_catalog_probe_returns_only_requested_id5_type(self) -> None:
        def transport(request: object) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            if url.endswith("/oauth2/token"):
                return FakeResponse({"access_token": "token", "expires_in": 3600})
            if url.endswith("/v3/countries"):
                return FakeResponse({"data": [{"code": "DE", "description": "Germany"}]})
            if url.endswith("/catalog/DE/brands"):
                return FakeResponse(
                    {
                        "data": [
                            {"id": "vn", "description": "Volkswagen Commercial Vehicles", "code": "VN"},
                            {"id": "vw", "description": "Volkswagen", "code": "VW"},
                        ]
                    }
                )
            if url.endswith("/catalog/DE/brands/vw/models"):
                return FakeResponse({"data": [{"id": "id5", "description": "Der ID.5", "code": "id5-code"}]})
            if url.endswith("/catalog/DE/models/id5/types"):
                return FakeResponse(
                    {
                        "data": [
                            {
                                "id": "pure",
                                "description": "ID.5 Pure  140 kW",
                                "modelyear_code": "MODELYEAR:2027",
                                "code": "TYPE:P",
                                "basetype_code": "BASETYPE:E392JM",
                                "shortener_code": "SHORTENER:E00",
                                "extensions": [],
                            },
                            {
                                "id": "pro",
                                "description": "ID.5 Pro 210 kW",
                                "model_year": "2027",
                                "code": "TYPE:Q",
                            },
                        ]
                    }
                )
            self.fail(f"Unerwarteter Request: {url}")

        client = OkapiClient("client", "secret", transport=transport)
        result = run_probe(client, "DE", "ID.5", "Pure 140 kW")

        self.assertEqual("vw", result["brand"]["id"])
        self.assertEqual(["pure"], [item["id"] for item in result["models"][0]["types"]])
        self.assertEqual("2027", result["models"][0]["types"][0]["model_year"])
        self.assertEqual("BASETYPE:E392JM", result["models"][0]["types"][0]["basetype_code"])

        exact_result = run_probe(client, "DE", "ID.5", None, "Volkswagen", "pure")
        self.assertEqual(["pure"], [item["id"] for item in exact_result["models"][0]["types"]])

    def test_wltp_fetch_uses_the_single_package_free_base_configuration(self) -> None:
        class WltpClient:
            def base_configuration(
                self, market: str, brand_id: str, type_id: str, modelyear_code: str
            ) -> dict[str, Any]:
                self.base_request = (market, brand_id, type_id, modelyear_code)
                return {
                    "data": [
                        {
                            "brand_id": "vw",
                            "model_id": "id5",
                            "options": [
                                {"id": "type-option", "code": "TYPE:E392JM"},
                                {"id": "modelyear-option", "code": "MODELYEAR:2027"},
                            ],
                        }
                    ]
                }

            def check(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                self.check_request = (market, configuration)
                return {"buildable": True, "distinct": True}

            def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any]:
                self.wltp_request = (market, configuration)
                return {
                    "data": [
                        {
                            "wltp_metadata": {"status": 200},
                            "wltp_value": [
                                {
                                    "data_version": "3",
                                    "engine_type": "PEV",
                                    "fuel_types": ["ELECTRICAL"],
                                    "interpolations": [
                                        {
                                            "value_type": "CONSUMPTION",
                                            "fuel_type": "ELECTRICAL",
                                            "phase": "COMBINED",
                                            "value": 155.44868213274486,
                                            "unit": "Wh/km",
                                        },
                                        {
                                            "value_type": "RANGE",
                                            "fuel_type": "ELECTRICAL",
                                            "phase": "COMBINED",
                                            "value": 445.7961051640632,
                                            "unit": "km",
                                        },
                                        {
                                            "value_type": "CO2",
                                            "fuel_type": "ELECTRICAL",
                                            "phase": "COMBINED",
                                            "value": 0.0,
                                            "unit": "g/km",
                                        },
                                    ],
                                    "energy_efficiency": {"class_wltp": "A", "iso": "DE"},
                                }
                            ],
                        }
                    ]
                }

        client = WltpClient()
        result: dict[str, Any] = {
            "brand": {"id": "vw", "name": "Volkswagen"},
            "models": [
                {
                    "types": [
                        {
                            "id": "with-package",
                            "modelyear_code": "MODELYEAR:2027",
                            "extensions": [{"code": "PACKET:RB1"}],
                        },
                        {
                            "id": "pure",
                            "modelyear_code": "MODELYEAR:2027",
                            "extensions": [],
                        },
                    ]
                }
            ],
        }

        fetch_wltp_for_result(client, "DE", result)  # type: ignore[arg-type]

        self.assertEqual(("DE", "vw", "pure", "MODELYEAR:2027"), client.base_request)
        expected_configuration = {
            "brand_id": "vw",
            "model_id": "id5",
            "options": [{"id": "type-option"}, {"id": "modelyear-option"}],
        }
        self.assertEqual(("DE", expected_configuration), client.check_request)
        self.assertEqual(("DE", expected_configuration), client.wltp_request)
        self.assertEqual({"buildable": True, "distinct": True}, result["configuration_check"])
        self.assertEqual(15.5, result["verified_values"]["combined_kwh_100km"])
        self.assertEqual(446, result["verified_values"]["electric_range_km"])
        self.assertEqual("A", result["verified_values"]["co2_class"])

    def test_extracts_verified_values_only_from_combined_interpolations(self) -> None:
        payload = {
            "data": [
                {
                    "wltp_metadata": {"status": 200},
                    "wltp_value": [
                        {
                            "data_version": "3",
                            "engine_type": "PEV",
                            "fuel_types": ["ELECTRICAL"],
                            "interpolations": [
                                {
                                    "value_type": "RANGE",
                                    "fuel_type": "ELECTRICAL",
                                    "phase": "COMBINED",
                                    "value": 445.7961051640632,
                                    "unit": "km",
                                },
                                {
                                    "value_type": "CONSUMPTION",
                                    "fuel_type": "ELECTRICAL",
                                    "phase": "COMBINED",
                                    "value": 155.44868213274486,
                                    "unit": "Wh/km",
                                },
                                {
                                    "value_type": "CO2",
                                    "fuel_type": "ELECTRICAL",
                                    "phase": "COMBINED",
                                    "value": 0.0,
                                    "unit": "g/km",
                                },
                            ],
                            "energy_efficiency": {"class_wltp": "A"},
                        }
                    ],
                }
            ]
        }

        values = extract_verified_wltp(payload)

        self.assertAlmostEqual(15.544868213274486, values["combined_kwh_100km_raw"])
        self.assertEqual(15.5, values["combined_kwh_100km"])
        self.assertEqual(446, values["electric_range_km"])
        self.assertEqual(0.0, values["co2_g_km"])

    def test_list_countries_reports_the_actual_catalog_codes(self) -> None:
        class CountriesOnlyClient:
            def countries(self) -> dict[str, Any]:
                return {"data": [{"countryCode": "AT", "name": "Austria"}]}

        output = io.StringIO()
        with patch.object(okapi_probe, "OkapiClient", return_value=CountriesOnlyClient()):
            with patch("sys.argv", ["okapi_probe", "--list-countries"]):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(0, okapi_probe.main())

        self.assertEqual(
            {"countries": [{"code": "AT", "name": "Austria"}]},
            json.loads(output.getvalue()),
        )

    def test_list_brands_reports_schema_without_credentials(self) -> None:
        class BrandsClient:
            def countries(self) -> dict[str, Any]:
                return {"data": [{"code": "DE", "description": "Germany"}]}

            def brands(self, market: str) -> dict[str, Any]:
                self.market = market
                return {"data": [{"id": "vw", "code": "V", "description": "Volkswagen"}]}

        client = BrandsClient()
        output = io.StringIO()
        with patch.object(okapi_probe, "OkapiClient", return_value=client):
            with patch("sys.argv", ["okapi_probe", "--list-brands", "--market", "DE"]):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(0, okapi_probe.main())

        self.assertEqual("DE", client.market)
        self.assertEqual(
            {
                "market": "DE",
                "schema_fields": ["code", "description", "id"],
                "samples": [{"id": "vw", "code": "V", "description": "Volkswagen"}],
            },
            json.loads(output.getvalue()),
        )

    def test_list_models_reports_schema_and_matching_models(self) -> None:
        class ModelsClient:
            def countries(self) -> dict[str, Any]:
                return {"data": [{"code": "DE", "description": "Germany"}]}

            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "vw", "code": "V", "description": "Volkswagen"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                self.request = (market, brand_id)
                return {
                    "data": [
                        {"id": "golf", "code": "G", "description": "Golf"},
                        {"id": "id5", "code": "I5", "description": "ID.5"},
                    ]
                }

        client = ModelsClient()
        output = io.StringIO()
        with patch.object(okapi_probe, "OkapiClient", return_value=client):
            with patch("sys.argv", ["okapi_probe", "--list-models", "--model", "ID.5"]):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(0, okapi_probe.main())

        result = json.loads(output.getvalue())
        self.assertEqual(("DE", "vw"), client.request)
        self.assertEqual(["code", "description", "id"], result["schema_fields"])
        self.assertEqual(["id5"], [model["id"] for model in result["matching_samples"]])

    def test_list_types_reports_matching_type_schema(self) -> None:
        class TypesClient:
            def countries(self) -> dict[str, Any]:
                return {"data": [{"code": "DE", "description": "Germany"}]}

            def brands(self, market: str) -> dict[str, Any]:
                return {"data": [{"id": "vw", "code": "VW", "description": "Volkswagen"}]}

            def models(self, market: str, brand_id: str) -> dict[str, Any]:
                return {"data": [{"id": "id5", "code": "I5", "description": "Der ID.5"}]}

            def model_types(self, market: str, model_id: str) -> dict[str, Any]:
                self.request = (market, model_id)
                return {
                    "data": [
                        {"id": "pure", "description": "ID.5 Pure 125 kW", "modelyear_code": "MODELYEAR:2026"},
                        {"id": "pro", "description": "ID.5 Pro 210 kW", "modelyear_code": "MODELYEAR:2027"},
                    ]
                }

        client = TypesClient()
        output = io.StringIO()
        with patch.object(okapi_probe, "OkapiClient", return_value=client):
            with patch(
                "sys.argv",
                ["okapi_probe", "--list-types", "--model", "ID.5", "--type-query", "Pure"],
            ):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(0, okapi_probe.main())

        result = json.loads(output.getvalue())
        self.assertEqual(("DE", "id5"), client.request)
        self.assertEqual(["pure"], [item["id"] for item in result["models"][0]["matching_samples"]])


if __name__ == "__main__":
    unittest.main()
