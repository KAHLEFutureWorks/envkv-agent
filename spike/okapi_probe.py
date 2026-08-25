"""Ausführbarer Beleg für OAuth, Katalogsuche und optionalen WLTP-Abruf."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .okapi import OkapiClient, OkapiError


def _data(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise OkapiError("Die Katalogantwort hat nicht das erwartete data-Format.")
    return [entry for entry in payload["data"] if isinstance(entry, dict)]


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _first_string(entry: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _find_country(entries: list[dict[str, Any]], expected: str) -> dict[str, Any]:
    expected_normalised = _normalise(expected)
    for entry in entries:
        code = _first_string(entry, "code", "countryCode")
        if code and _normalise(code) == expected_normalised:
            return entry
    raise OkapiError(f"Im OKAPI-Katalog wurde kein Eintrag für {expected!r} gefunden.")


def _find_volkswagen_brand(entries: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    volkswagen = next(
        (brand for brand in entries if (_first_string(brand, "code") or "").upper() == "VW"),
        None,
    )
    if volkswagen is None:
        volkswagen = next(
            (
                brand
                for brand in entries
                if _normalise(_first_string(brand, "description", "name") or "")
                in {"volkswagen", "volkswagen pkw"}
            ),
            None,
        )
    brand_id = _first_string(volkswagen or {}, "id", "brand_id")
    if volkswagen is None or brand_id is None:
        raise OkapiError("Im gewählten Markt wurde keine Volkswagen-Marke gefunden.")
    return volkswagen, brand_id


def _find_brand(entries: list[dict[str, Any]], query: str) -> tuple[dict[str, Any], str]:
    aliases = {
        "VOLKSWAGEN": {"VW", "VOLKSWAGEN", "VOLKSWAGEN PKW"},
        "AUDI": {"AU", "AUDI"},
        "SEAT": {"SE", "SEAT"},
        "SKODA": {"SK", "SKODA", "ŠKODA"},
        "ŠKODA": {"SK", "SKODA", "ŠKODA"},
        "CUPRA": {"CU", "CUPRA"},
        "VOLKSWAGEN NUTZFAHRZEUGE": {"VN", "VOLKSWAGEN COMMERCIAL VEHICLES", "VOLKSWAGEN NUTZFAHRZEUGE"},
        "VW NUTZFAHRZEUGE": {"VN", "VOLKSWAGEN COMMERCIAL VEHICLES", "VOLKSWAGEN NUTZFAHRZEUGE"},
    }
    query_normalised = _normalise(query).upper()
    accepted = aliases.get(query_normalised, {query_normalised})
    brand = next(
        (
            entry for entry in entries
            if (_first_string(entry, "code") or "").upper() in accepted
            or _normalise(_first_string(entry, "description", "name") or "").upper() in accepted
        ),
        None,
    )
    brand_id = _first_string(brand or {}, "id", "brand_id")
    if brand is None or brand_id is None:
        raise OkapiError(f"Im gewählten Markt wurde die Marke {query!r} nicht gefunden.")
    return brand, brand_id


def _contains_string_value(entry: dict[str, Any], query: str) -> bool:
    query_normalised = query.casefold()
    return any(query_normalised in value.casefold() for value in entry.values() if isinstance(value, str))


def _matches_description(entry: dict[str, Any], query: str) -> bool:
    description = _first_string(entry, "description", "name") or ""
    return _normalise(query) in _normalise(description)


def _model_year(entry: dict[str, Any]) -> str | None:
    value = _first_string(entry, "modelyear_code", "model_year")
    if value and ":" in value:
        return value.rsplit(":", 1)[1]
    return value


def _load_configuration(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise OkapiError("Die angegebene Konfigurationsdatei kann nicht gelesen werden.") from error
    except json.JSONDecodeError as error:
        raise OkapiError("Die Konfigurationsdatei enthält kein gültiges JSON.") from error
    if not isinstance(payload, dict):
        raise OkapiError("Die OKAPI-Konfiguration muss ein JSON-Objekt sein.")
    for required in ("brand_id", "model_id", "options"):
        if required not in payload:
            raise OkapiError(f"In der Konfiguration fehlt {required}.")
    return payload


def _id_configuration(base_configuration: dict[str, Any]) -> dict[str, Any]:
    brand_id = _first_string(base_configuration, "brand_id")
    model_id = _first_string(base_configuration, "model_id")
    options = base_configuration.get("options")
    if brand_id is None or model_id is None or not isinstance(options, list):
        raise OkapiError("Die OKAPI-Basiskonfiguration ist unvollständig.")
    option_ids = [
        {"id": option["id"]}
        for option in options
        if isinstance(option, dict) and isinstance(option.get("id"), str)
    ]
    if not option_ids:
        raise OkapiError("Die OKAPI-Basiskonfiguration enthält keine technischen Optionen.")
    return {"brand_id": brand_id, "model_id": model_id, "options": option_ids}


def _wltp_value(
    values: list[Any],
    *,
    value_type: str,
    phase: str,
    fuel_type: str = "ELECTRICAL",
    energy_management_type: str | None = None,
) -> dict[str, Any]:
    matches = [
        value
        for value in values
        if isinstance(value, dict)
        and value.get("value_type") == value_type
        and value.get("phase") == phase
        and value.get("fuel_type") == fuel_type
        and (
            energy_management_type is None
            or value.get("energy_management_type") == energy_management_type
        )
        and isinstance(value.get("value"), (int, float))
    ]
    if len(matches) != 1:
        raise OkapiError(
            f"Der WLTP-Datensatz enthält keinen eindeutigen Wert für {value_type}/{phase}."
        )
    return matches[0]


def extract_verified_wltp(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise OkapiError("Die WLTP-Antwort hat nicht das erwartete Objektformat.")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise OkapiError("Die WLTP-Antwort enthält nicht genau einen Datensatz.")
    metadata = data[0].get("wltp_metadata")
    values = data[0].get("wltp_value")
    if (
        not isinstance(metadata, dict)
        or metadata.get("status") != 200
        or not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], dict)
    ):
        raise OkapiError("Der WLTP-Datensatz ist nicht erfolgreich oder nicht eindeutig.")

    vehicle = values[0]
    interpolations = vehicle.get("interpolations")
    energy_efficiency = vehicle.get("energy_efficiency")
    if not isinstance(interpolations, list) or not isinstance(energy_efficiency, dict):
        raise OkapiError("Im WLTP-Datensatz fehlen Verbrauchs- oder Effizienzwerte.")

    engine_type = vehicle.get("engine_type")
    fuel_types = vehicle.get("fuel_types")
    co2_class = energy_efficiency.get("class_wltp")
    if not isinstance(co2_class, str) or not co2_class:
        raise OkapiError("Im WLTP-Datensatz fehlt die CO₂-Klasse.")

    result: dict[str, Any] = {
        "engine_type": engine_type,
        "fuel_types": fuel_types,
        "co2_class": co2_class,
        "data_version": vehicle.get("data_version"),
    }

    def phase_values(fuel_type: str, unit: str, energy_management_type: str | None = None) -> dict[str, float]:
        factor = 0.1 if unit == "Wh/km" else 1.0
        return {
            phase.lower(): round(float(value["value"]) * factor, 1)
            for phase in ("LOW", "MEDIUM", "HIGH", "EXTRA_HIGH", "CITY")
            for value in interpolations
            if isinstance(value, dict)
            and value.get("value_type") == "CONSUMPTION"
            and value.get("fuel_type") == fuel_type
            and value.get("phase") == phase
            and value.get("unit") == unit
            and (energy_management_type is None or value.get("energy_management_type") == energy_management_type)
            and isinstance(value.get("value"), (int, float))
        }
    if engine_type == "PEV" and fuel_types == ["ELECTRICAL"]:
        consumption = _wltp_value(interpolations, value_type="CONSUMPTION", phase="COMBINED")
        combined_range = _wltp_value(interpolations, value_type="RANGE", phase="COMBINED")
        co2 = _wltp_value(interpolations, value_type="CO2", phase="COMBINED")
        if consumption.get("unit") != "Wh/km":
            raise OkapiError("Der kombinierte Stromverbrauch besitzt nicht die erwartete Einheit Wh/km.")
        if combined_range.get("unit") != "km" or co2.get("unit") != "g/km":
            raise OkapiError("Reichweite oder CO₂-Wert besitzt eine unerwartete Einheit.")
        consumption_kwh_100km = float(consumption["value"]) / 10
        result.update({
            "combined_kwh_100km": round(consumption_kwh_100km, 1),
            "combined_kwh_100km_raw": consumption_kwh_100km,
            "co2_g_km": round(float(co2["value"]), 1),
            "electric_range_km": round(float(combined_range["value"])),
            "electric_range_km_raw": float(combined_range["value"]),
            "phase_kwh_100km": phase_values("ELECTRICAL", "Wh/km"),
        })
        return result

    if engine_type in {"ICE", "NOVC_HEV"} and isinstance(fuel_types, list) and len(fuel_types) == 1:
        fuel_type = fuel_types[0]
        consumption = _wltp_value(
            interpolations, value_type="CONSUMPTION", phase="COMBINED", fuel_type=fuel_type
        )
        co2 = _wltp_value(interpolations, value_type="CO2", phase="COMBINED", fuel_type=fuel_type)
        if consumption.get("unit") != "l/100km" or co2.get("unit") != "g/km":
            raise OkapiError("Kraftstoffverbrauch oder CO₂-Wert besitzt eine unerwartete Einheit.")
        result.update({
            "combined_l_100km": round(float(consumption["value"]), 1),
            "combined_l_100km_raw": float(consumption["value"]),
            "co2_g_km": round(float(co2["value"]), 1),
            "phase_l_100km": phase_values(fuel_type, "l/100km"),
        })
        return result

    if engine_type == "OVC_HEV" and isinstance(fuel_types, list) and "ELECTRICAL" in fuel_types:
        combustion_fuels = [fuel for fuel in fuel_types if fuel != "ELECTRICAL"]
        if len(combustion_fuels) != 1:
            raise OkapiError("Der Plug-in-Hybrid besitzt keinen eindeutigen Kraftstofftyp.")
        fuel_type = combustion_fuels[0]
        electricity = _wltp_value(
            interpolations, value_type="CONSUMPTION", phase="COMBINED",
            fuel_type="ELECTRICAL", energy_management_type="WEIGHTED",
        )
        electricity_pure = _wltp_value(
            interpolations, value_type="CONSUMPTION", phase="COMBINED",
            fuel_type="ELECTRICAL", energy_management_type="PURE",
        )
        fuel = _wltp_value(
            interpolations, value_type="CONSUMPTION", phase="COMBINED",
            fuel_type=fuel_type, energy_management_type="WEIGHTED",
        )
        fuel_discharged = _wltp_value(
            interpolations, value_type="CONSUMPTION", phase="COMBINED",
            fuel_type=fuel_type, energy_management_type="SUSTAINING",
        )
        co2 = _wltp_value(
            interpolations, value_type="CO2", phase="COMBINED",
            fuel_type=fuel_type, energy_management_type="WEIGHTED",
        )
        combined_range = _wltp_value(
            interpolations, value_type="RANGE", phase="COMBINED",
            fuel_type="ELECTRICAL", energy_management_type="ALL_ELECTRIC_RANGE",
        )
        if electricity.get("unit") != "Wh/km" or electricity_pure.get("unit") != "Wh/km" or fuel.get("unit") != "l/100km":
            raise OkapiError("Der gewichtete Plug-in-Hybrid-Verbrauch besitzt eine unerwartete Einheit.")
        if fuel_discharged.get("unit") != "l/100km" or co2.get("unit") != "g/km" or combined_range.get("unit") != "km":
            raise OkapiError("Ergänzende Plug-in-Hybrid-Werte besitzen eine unerwartete Einheit.")
        energy_efficiency_2 = vehicle.get("energy_efficiency_2")
        discharged_class = (
            energy_efficiency_2.get("class_wltp")
            if isinstance(energy_efficiency_2, dict) else None
        )
        electricity_kwh_100km = float(electricity["value"]) / 10
        electricity_pure_kwh_100km = float(electricity_pure["value"]) / 10
        result.update({
            "weighted_kwh_100km": round(electricity_kwh_100km, 1),
            "weighted_kwh_100km_raw": electricity_kwh_100km,
            "pure_electric_kwh_100km": round(electricity_pure_kwh_100km, 1),
            "pure_electric_kwh_100km_raw": electricity_pure_kwh_100km,
            "weighted_l_100km": round(float(fuel["value"]), 1),
            "weighted_l_100km_raw": float(fuel["value"]),
            "discharged_l_100km": round(float(fuel_discharged["value"]), 1),
            "discharged_l_100km_raw": float(fuel_discharged["value"]),
            "co2_g_km": round(float(co2["value"]), 1),
            "co2_class_discharged": discharged_class,
            "electric_range_km": round(float(combined_range["value"])),
            "electric_range_km_raw": float(combined_range["value"]),
            "phase_l_100km": phase_values(fuel_type, "l/100km", "SUSTAINING"),
            "phase_kwh_100km": phase_values("ELECTRICAL", "Wh/km", "PURE"),
        })
        return result

    raise OkapiError(f"Die OKAPI-Antriebsart {engine_type!r} wird noch nicht unterstützt.")


def fetch_wltp_for_result(
    client: OkapiClient,
    market: str,
    result: dict[str, Any],
) -> None:
    candidates = [
        candidate
        for model in result.get("models", [])
        if isinstance(model, dict)
        for candidate in model.get("types", [])
        if isinstance(candidate, dict)
    ]
    package_free = [candidate for candidate in candidates if not candidate.get("extensions")]
    if len(candidates) == 1:
        selected = candidates[0]
    elif len(package_free) == 1:
        selected = package_free[0]
    else:
        raise OkapiError(
            "Für den automatischen WLTP-Abruf muss genau ein eindeutiger Typkandidat vorhanden sein."
        )
    type_id = _first_string(selected, "id")
    modelyear_code = _first_string(selected, "modelyear_code")
    brand = result.get("brand")
    brand_id = _first_string(brand, "id") if isinstance(brand, dict) else None
    if type_id is None or modelyear_code is None or brand_id is None:
        raise OkapiError("Dem ausgewählten Typ fehlen technische IDs für die Basiskonfiguration.")

    base_configurations = _data(
        client.base_configuration(market, brand_id, type_id, modelyear_code)
    )
    if len(base_configurations) != 1:
        raise OkapiError("OKAPI hat keine eindeutige Basiskonfiguration für Typ und Modelljahr geliefert.")
    configuration = _id_configuration(base_configurations[0])
    check_result = client.check(market, configuration)
    if not isinstance(check_result, dict):
        raise OkapiError("Die Check-Antwort hat nicht das erwartete Objektformat.")

    result["selected_type"] = selected
    result["configuration"] = configuration
    result["configuration_check"] = check_result
    if check_result.get("buildable") is True and check_result.get("distinct") is True:
        wltp = client.wltp(market, configuration)
        result["wltp"] = wltp
        try:
            result["verified_values"] = extract_verified_wltp(wltp)
        except OkapiError as error:
            result["normalization_status"] = "not_yet_supported"
            result["normalization_message"] = str(error)
    else:
        result["wltp"] = {
            "status": "not_requested",
            "reason": "Konfiguration ist nicht eindeutig und baubar.",
        }


def fetch_order_for_result(client: OkapiClient, market: str, result: dict[str, Any]) -> None:
    if "configuration" not in result:
        fetch_wltp_for_result(client, market, result)
    configuration = result.get("configuration")
    if not isinstance(configuration, dict):
        raise OkapiError("Für den Abruf der technischen Daten fehlt eine eindeutige Konfiguration.")
    result["order"] = client.order(market, configuration)


def run_probe(
    client: OkapiClient,
    market: str,
    model_query: str,
    type_query: str | None,
    brand_query: str = "Volkswagen",
    type_id: str | None = None,
) -> dict[str, Any]:
    countries = _data(client.countries())
    _find_country(countries, market)

    volkswagen, brand_id = _find_brand(_data(client.brands(market)), brand_query)

    models = _data(client.models(market, brand_id))
    matching_models = [
        model
        for model in models
        if model_query.casefold() in (_first_string(model, "description", "name") or "").casefold()
        and isinstance(model.get("id"), str)
    ]
    if not matching_models:
        raise OkapiError(f"Für {model_query!r} wurde bei {brand_query} kein Modell gefunden.")

    model_results: list[dict[str, Any]] = []
    for model in matching_models:
        types = _data(client.model_types(market, model["id"]))
        if type_id:
            types = [item for item in types if _first_string(item, "id") == type_id]
        elif type_query:
            types = [
                item
                for item in types
                if _matches_description(item, type_query)
            ]
        model_results.append(
            {
                "id": model["id"],
                "name": _first_string(model, "description", "name"),
                "code": model.get("code"),
                "types": [
                    {
                        "id": item.get("id"),
                        "name": _first_string(item, "description", "name"),
                        "model_year": _model_year(item),
                        "modelyear_code": item.get("modelyear_code"),
                        "code": item.get("code"),
                        "basetype_code": item.get("basetype_code"),
                        "shortener_code": item.get("shortener_code"),
                        "extensions": [
                            {
                                "code": extension.get("code"),
                                "description": extension.get("description"),
                            }
                            for extension in item.get("extensions", [])
                            if isinstance(extension, dict)
                        ],
                    }
                    for item in types
                ],
            }
        )

    return {
        "retrieved_at": datetime.now(UTC).isoformat(),
        "market": market,
        "brand": {
            "id": brand_id,
            "name": _first_string(volkswagen, "description", "name"),
        },
        "models": model_results,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", default=os.getenv("VW_MARKET", "DE"), help="OKAPI-Markt, Standard DE")
    parser.add_argument("--brand", default="Volkswagen", help="Konzernmarke, z. B. Volkswagen, Škoda, Audi oder CUPRA")
    parser.add_argument("--model", help="Teil des gesuchten Modellnamens, z. B. ID.5")
    parser.add_argument("--type-query", help="optionaler Teil der Typbezeichnung")
    parser.add_argument("--type-id", help="exakte technische Typ-ID für einen eindeutigen Diagnoseabruf")
    parser.add_argument("--configuration", type=Path, help="vollständige technische OKAPI-Konfiguration als JSON")
    parser.add_argument(
        "--fetch-wltp",
        action="store_true",
        help="wählt genau einen paketlosen Typ, prüft die Basiskonfiguration und ruft WLTP ab",
    )
    parser.add_argument(
        "--fetch-order",
        action="store_true",
        help="ruft für den eindeutigen Typ zusätzliche technische Daten und Attribute ab",
    )
    parser.add_argument(
        "--list-countries",
        action="store_true",
        help="gibt nur die für diese Zugangsdaten verfügbaren OKAPI-Märkte aus",
    )
    parser.add_argument(
        "--list-brands",
        action="store_true",
        help="zeigt Feldnamen und drei Markenbeispiele für den gewählten Markt",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="zeigt das Modellschema und Treffer für den Suchtext aus --model",
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="zeigt das Typenschema und Treffer für --type-query beim gewählten Modell",
    )
    args = parser.parse_args()

    try:
        client = OkapiClient(os.getenv("VW_CLIENT_ID", ""), os.getenv("VW_CLIENT_SECRET", ""))
        if args.list_countries:
            countries = _data(client.countries())
            result = {
                "countries": [
                    {
                        "code": _first_string(country, "code", "countryCode"),
                        "name": _first_string(country, "description", "name"),
                    }
                    for country in countries
                ]
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.list_brands:
            market = args.market.upper()
            _find_country(_data(client.countries()), market)
            brands = _data(client.brands(market))
            result = {
                "market": market,
                "schema_fields": sorted({key for brand in brands for key in brand}),
                "samples": brands[:3],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.list_models:
            market = args.market.upper()
            _find_country(_data(client.countries()), market)
            _, brand_id = _find_brand(_data(client.brands(market)), args.brand)
            models = _data(client.models(market, brand_id))
            result = {
                "market": market,
                "schema_fields": sorted({key for model in models for key in model}),
                "samples": models[:3],
                "matching_samples": [
                    model for model in models if args.model and _contains_string_value(model, args.model)
                ],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.list_types:
            if not args.model:
                raise OkapiError("Für --list-types muss --model angegeben werden.")
            market = args.market.upper()
            _find_country(_data(client.countries()), market)
            _, brand_id = _find_brand(_data(client.brands(market)), args.brand)
            models = [
                model
                for model in _data(client.models(market, brand_id))
                if args.model.casefold()
                in (_first_string(model, "description", "name") or "").casefold()
                and isinstance(model.get("id"), str)
            ]
            if not models:
                raise OkapiError(f"Für {args.model!r} wurde bei {args.brand} kein Modell gefunden.")
            type_groups = []
            for model in models:
                types = _data(client.model_types(market, model["id"]))
                type_groups.append(
                    {
                        "model": {
                            "id": model["id"],
                            "description": _first_string(model, "description", "name"),
                        },
                        "schema_fields": sorted({key for item in types for key in item}),
                        "samples": types[:3],
                        "matching_samples": [
                            item
                            for item in types
                            if args.type_query and _contains_string_value(item, args.type_query)
                        ],
                    }
                )
            print(json.dumps({"market": market, "models": type_groups}, ensure_ascii=False, indent=2))
            return 0
        if not args.model:
            raise OkapiError("Bitte --model angeben oder einen der Listenmodi verwenden.")
        result = run_probe(
            client,
            args.market.upper(),
            args.model,
            args.type_query,
            args.brand,
            args.type_id,
        )
        if args.fetch_wltp:
            fetch_wltp_for_result(client, args.market.upper(), result)
        if args.fetch_order:
            fetch_order_for_result(client, args.market.upper(), result)
        if args.configuration:
            configuration = _load_configuration(args.configuration)
            check_result = client.check(args.market.upper(), configuration)
            if not isinstance(check_result, dict):
                raise OkapiError("Die Check-Antwort hat nicht das erwartete Objektformat.")
            result["configuration_check"] = check_result
            if check_result.get("buildable") is True and check_result.get("distinct") is True:
                result["wltp"] = client.wltp(args.market.upper(), configuration)
            else:
                result["wltp"] = {"status": "not_requested", "reason": "Konfiguration ist nicht eindeutig und baubar."}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OkapiError) as error:
        print(f"OKAPI-Spike nicht erfolgreich: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
