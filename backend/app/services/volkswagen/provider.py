from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from backend.app.domain.envkv import (
    ConsumptionValues,
    VerifiedModelRange,
    build_model_range_group,
    PowertrainType,
    SourceReference,
    VehicleIdentity,
    VerifiedVehicleData,
    calculate_vehicle_tax,
)
from backend.app.storage import SQLiteStore, technical_cache_key
from spike.okapi import OkapiError
from spike.okapi_probe import extract_verified_wltp


class VehicleNotFound(ValueError):
    """Der übergebene Fahrzeugtext lässt sich keinem Fahrzeug zuordnen."""


class ManualReviewRequired(ValueError):
    """OKAPI liefert keine eindeutig automatisch verwendbare Konfiguration."""

    def __init__(self, message: str, candidates: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.candidates = candidates or []


class VehicleNotEligible(ValueError):
    """Das Fahrzeug liegt außerhalb des freigegebenen V1-Anwendungsbereichs."""


class VolkswagenClient(Protocol):
    def countries(self) -> dict[str, Any] | list[Any]: ...
    def brands(self, market: str) -> dict[str, Any] | list[Any]: ...
    def models(self, market: str, brand_id: str) -> dict[str, Any] | list[Any]: ...
    def model_types(self, market: str, model_id: str) -> dict[str, Any] | list[Any]: ...
    def base_configuration(self, market: str, brand_id: str, type_id: str, modelyear_code: str) -> dict[str, Any] | list[Any]: ...
    def check(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]: ...
    def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]: ...
    def order(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]: ...


_SUPPORTED_BRANDS = (
    {"code": "VN", "display": "Volkswagen Nutzfahrzeuge", "aliases": ("volkswagen nutzfahrzeuge", "vw nutzfahrzeuge"), "catalog": ("volkswagen commercial vehicles", "volkswagen nutzfahrzeuge")},
    {"code": "VW", "display": "Volkswagen", "aliases": ("volkswagen", "vw"), "catalog": ("volkswagen", "volkswagen pkw")},
    {"code": "AU", "display": "Audi", "aliases": ("audi",), "catalog": ("audi",)},
    {"code": "SE", "display": "SEAT", "aliases": ("seat",), "catalog": ("seat",)},
    {"code": "SK", "display": "Škoda", "aliases": ("skoda", "škoda"), "catalog": ("skoda", "škoda")},
    {"code": "SE", "display": "CUPRA", "aliases": ("cupra",), "catalog": ("seat",)},
)


def _data(payload: dict[str, Any] | list[Any], label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise OkapiError(f"Die {label} hat nicht das erwartete Datenformat.")
    return [entry for entry in payload["data"] if isinstance(entry, dict)]


def _text(entry: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _normalise(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(without_marks.split())


# Volkswagen fuehrt seine Modelle im Katalog mit Artikel: "Der Grand California".
_ARTICLE = re.compile(r"^(?:der|die|das)\s+(?:neue[rs]?\s+)?", re.IGNORECASE)


def _without_article(value: str) -> str:
    return _ARTICLE.sub("", value)


def _catalog_model_name(value: str) -> str:
    return _without_article(_normalise(value))


def _catalog_model_display(value: str) -> str:
    return _without_article(value.strip())


# Mehrere Konzernmarken teilen sich einen OKAPI-Katalog. SEAT und CUPRA liegen
# beide unter der Marke "SE" und werden dort ausschließlich über den Namenszusatz
# unterschieden. Der Zusatz wird deshalb beim Vergleich abgetrennt und getrennt
# ausgewertet, statt ihn als Teil des Modellnamens zu behandeln.
_SUBBRAND_PREFIXES = (
    "volkswagen nutzfahrzeuge", "volkswagen", "vw", "cupra", "seat", "audi", "skoda",
)


def _split_catalog_name(value: str) -> tuple[str | None, str]:
    name = _catalog_model_name(value)
    for prefix in _SUBBRAND_PREFIXES:
        if name == prefix:
            return prefix, ""
        if name.startswith(f"{prefix} "):
            return prefix, name[len(prefix):].strip()
    return None, name


def _strip_subbrand_display(value: str) -> str:
    display = _catalog_model_display(value)
    for prefix in _SUBBRAND_PREFIXES:
        if _normalise(display).startswith(f"{prefix} "):
            return display[len(prefix):].strip()
    return display


def _subbrand_matches(brand_definition: dict[str, Any], subbrand: str | None) -> bool:
    own = _normalise(brand_definition["display"])
    if subbrand is None:
        # Ein Eintrag ohne Zusatz gehört der Stammmarke des Katalogs. CUPRA teilt
        # sich den Katalog mit SEAT und muss deshalb ausdrücklich benannt sein.
        return brand_definition["display"] != "CUPRA"
    return subbrand == own or (own == "volkswagen" and subbrand == "vw")


# Modellfamilien, die ihre Marke selbst tragen. "Grand California" muss vor
# "California" stehen, sonst greift der laengere Name nie.
_IMPLICIT_MODELS = (
    ("Volkswagen Nutzfahrzeuge", ("id. buzz", "e-transporter", "transporter", "multivan", "caddy", "grand california", "california", "caravelle", "crafter")),
    ("Volkswagen", ("t-cross", "t-roc", "golf", "tiguan", "passat", "tayron", "touareg", "polo", "id. cross", "id. polo")),
    ("Audi", ("a1", "a3", "a4", "a5", "a6", "a7", "a8", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "e-tron", "e-tron gt")),
    ("SEAT", ("arona", "ateca", "ibiza", "leon", "tarraco")),
    ("Škoda", ("elroq", "enyaq", "epiq", "fabia", "kamiq", "karoq", "kodiaq", "octavia", "peaq", "scala", "superb")),
    ("CUPRA", ("born", "formentor", "raval", "tavascan", "terramar")),
)


def _implicit_brand(query: str) -> str | None:
    """Die Marke, die sich allein aus dem Modellnamen ergibt."""
    for display, model_names in _IMPLICIT_MODELS:
        if any(query == name or query.startswith(f"{name} ") for name in model_names):
            return display
    return None


def _brand_for_input(vehicle_name: str) -> tuple[dict[str, Any], str]:
    normalised = _normalise(vehicle_name)
    for definition in _SUPPORTED_BRANDS:
        for alias in definition["aliases"]:
            alias_normalised = _normalise(alias)
            if normalised == alias_normalised or normalised.startswith(f"{alias_normalised} "):
                remaining = normalised[len(alias_normalised):].strip()
                if definition["display"] == "CUPRA":
                    remaining = f"cupra {remaining}"
                # "VW" ist im Alltag der Name fuer beide Kataloge. Ein Multivan
                # oder Grand California liegt aber ausschliesslich bei
                # Volkswagen Nutzfahrzeuge und waere im Pkw-Katalog nie zu
                # finden. Der Modellname entscheidet deshalb ueber den Katalog.
                if (
                    definition["display"] == "Volkswagen"
                    and _implicit_brand(_without_article(remaining)) == "Volkswagen Nutzfahrzeuge"
                ):
                    definition = next(
                        item for item in _SUPPORTED_BRANDS
                        if item["display"] == "Volkswagen Nutzfahrzeuge"
                    )
                return definition, remaining
    if re.search(r"\bid\.\d+\b", normalised):
        volkswagen = next(item for item in _SUPPORTED_BRANDS if item["code"] == "VW")
        return volkswagen, normalised
    query_without_article = _without_article(normalised)
    overlapping_models = ("ateca", "leon")
    if any(
        query_without_article == model
        or query_without_article.startswith(f"{model} ")
        for model in overlapping_models
    ):
        raise VehicleNotFound(
            "Dieses Modell gibt es bei SEAT oder CUPRA. Bitte die gewünschte Marke mit angeben."
        )
    display = _implicit_brand(query_without_article)
    if display is not None:
        definition = next(item for item in _SUPPORTED_BRANDS if item["display"] == display)
        query = f"cupra {query_without_article}" if display == "CUPRA" else query_without_article
        return definition, query
    raise VehicleNotFound("Die Fahrzeugmarke fehlt oder wird noch nicht unterstützt.")


def _parse_identity(description: str, model_name: str) -> dict[str, Any]:
    power = re.search(r"\b(\d+)\s*kW\b", description, re.IGNORECASE)
    battery = re.search(r"\b(\d+(?:[,.]\d+)?)\s*kWh\b", description, re.IGNORECASE)
    ps = re.search(r"\((\d+)\s*PS\)", description, re.IGNORECASE)
    transmission = re.search(r"\b\d+-Gang-[\wÄÖÜäöüß-]+", description, re.IGNORECASE)
    displacement = re.search(r"\b(\d+(?:[,.]\d+)?)\s*l\b", description, re.IGNORECASE)
    if power is None:
        raise ManualReviewRequired("Die Fahrzeugbezeichnung konnte nicht sicher zerlegt werden.")
    remainder = re.sub(rf"^{re.escape(model_name)}\s+", "", description.strip(), flags=re.IGNORECASE)
    for pattern in (
        r"\(\d+\s*kWh\)", r"\b\d+\s*kWh\b", r"\b\d+\s*kW\b",
        r"\(\d+\s*PS\)", re.escape(transmission.group(0)) if transmission else r"(?!)",
    ):
        remainder = re.sub(pattern, " ", remainder, flags=re.IGNORECASE)
    return {
        "trim": " ".join(remainder.split()).strip(" -"),
        "power_kw": int(power.group(1)),
        "power_ps": int(ps.group(1)) if ps else None,
        "battery_kwh": Decimal(battery.group(1).replace(",", ".")) if battery else None,
        "transmission": transmission.group(0) if transmission else "",
        "engine_displacement_cc": int(Decimal(displacement.group(1).replace(",", ".")) * 1000) if displacement else None,
    }


def _is_excluded_n1_candidate(brand_code: str, type_description: str) -> bool:
    normalised = f" {_normalise(type_description)} "
    return brand_code == "VN" and any(
        marker in normalised
        for marker in (
            " cargo ", " kasten", " transporter kasten", " pritsche",
            " fahrgestell", " crafter ",
        )
    )


def _type_search_text(value: str) -> str:
    value = _normalise(value).replace(",", ".")
    value = re.sub(r"(?<=\d)\s+(?=kw\b|kwh\b|ps\b)", "", value)
    value = re.sub(r"\b(?:opf|eu6|motor|getriebe)\b\s*:? ?", "", value)
    return " ".join(value.split())


def _is_general_model_query(value: str) -> bool:
    return len(value.split()) <= 3 and re.search(
        r"\b(?:kw|kwh|ps|tsi|tdi|tfsi|hybrid|diesel|benzin)\b", value
    ) is None


def _id_configuration(base: dict[str, Any]) -> dict[str, Any]:
    brand_id = _text(base, "brand_id")
    model_id = _text(base, "model_id")
    options = base.get("options")
    if brand_id is None or model_id is None or not isinstance(options, list):
        raise ManualReviewRequired("Die Basiskonfiguration ist unvollständig.")
    option_ids = [
        {"id": option["id"]}
        for option in options
        if isinstance(option, dict) and isinstance(option.get("id"), str)
    ]
    if not option_ids:
        raise ManualReviewRequired("Die Basiskonfiguration enthält keine technischen Optionen.")
    return {"brand_id": brand_id, "model_id": model_id, "options": option_ids}


def _technical_number(payload: dict[str, Any], attribute_id: str) -> int | None:
    additional = payload.get("additional_data")
    attributes = additional.get("technical_attributes") if isinstance(additional, dict) else None
    if not isinstance(attributes, list):
        return None
    matches = [
        item.get("number_value")
        for item in attributes
        if isinstance(item, dict)
        and item.get("category") == attribute_id
        and isinstance(item.get("number_value"), (int, float))
    ]
    return int(matches[0]) if len(matches) == 1 else None


def _powertrain_for(values: dict[str, Any]) -> PowertrainType:
    engine_type = values.get("engine_type")
    fuel_types = values.get("fuel_types") or []
    if engine_type == "PEV":
        return PowertrainType.BATTERY_ELECTRIC
    if engine_type == "OVC_HEV":
        return PowertrainType.PLUG_IN_HYBRID
    if engine_type == "NOVC_HEV":
        return PowertrainType.HYBRID
    if engine_type == "ICE" and fuel_types == ["DIESEL"]:
        return PowertrainType.DIESEL
    if engine_type == "ICE":
        return PowertrainType.PETROL
    raise ManualReviewRequired("Die Antriebsart wird noch nicht automatisch unterstützt.")


def _consumption_for(values: dict[str, Any]) -> ConsumptionValues:
    fuel_types = values.get("fuel_types") or []
    return ConsumptionValues(
        combined_kwh_100km=Decimal(str(values.get("combined_kwh_100km", values.get("weighted_kwh_100km")))) if values.get("combined_kwh_100km", values.get("weighted_kwh_100km")) is not None else None,
        co2_g_km=Decimal(str(values["co2_g_km"])),
        co2_class=str(values["co2_class"]),
        electric_range_km=int(values["electric_range_km"]) if values.get("electric_range_km") is not None else None,
        combined_l_100km=Decimal(str(values.get("combined_l_100km", values.get("weighted_l_100km")))) if values.get("combined_l_100km", values.get("weighted_l_100km")) is not None else None,
        discharged_l_100km=Decimal(str(values["discharged_l_100km"])) if values.get("discharged_l_100km") is not None else None,
        co2_class_discharged=values.get("co2_class_discharged"),
        fuel_type=next((fuel for fuel in fuel_types if fuel != "ELECTRICAL"), None),
        phase_kwh_100km={key: Decimal(str(value)) for key, value in values.get("phase_kwh_100km", {}).items()} or None,
        phase_l_100km={key: Decimal(str(value)) for key, value in values.get("phase_l_100km", {}).items()} or None,
        pure_electric_kwh_100km=Decimal(str(values["pure_electric_kwh_100km"])) if values.get("pure_electric_kwh_100km") is not None else None,
    )


class VolkswagenProvider:
    def __init__(
        self,
        client: VolkswagenClient,
        store: SQLiteStore,
        *,
        market: str = "DE",
        cache_ttl_seconds: int = 86_400,
        require_vehicle_class_approval: bool = False,
    ) -> None:
        self.client = client
        self.store = store
        self.market = market.upper()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.require_vehicle_class_approval = require_vehicle_class_approval

    def _resolve_family(self, vehicle_name: str) -> tuple[dict[str, Any], str, list[dict[str, Any]], str]:
        """Ermittelt Marke, Modellfamilie und den bereinigten Suchtext."""
        brand_definition, vehicle_query = _brand_for_input(vehicle_name)

        countries = _data(self.client.countries(), "Marktliste")
        if not any((_text(item, "code", "countryCode") or "").upper() == self.market for item in countries):
            raise OkapiError("Der konfigurierte Markt ist bei Volkswagen nicht verfügbar.")

        brands = _data(self.client.brands(self.market), "Markenliste")
        brand = next(
            (
                item for item in brands
                if (_text(item, "code") or "").upper() == brand_definition["code"]
                or _normalise(_text(item, "description", "name") or "") in {
                    _normalise(name) for name in brand_definition["catalog"]
                }
            ),
            None,
        )
        brand_id = _text(brand or {}, "id", "brand_id")
        if brand is None or brand_id is None:
            raise OkapiError("Die gewählte Konzernmarke ist im Markt nicht verfügbar.")

        models = _data(self.client.models(self.market, brand_id), "Modellliste")
        # Der Namenszusatz der Untermarke wird abgetrennt, damit "SEAT Leon" und
        # "CUPRA Leon" im gemeinsamen Katalog sauber auseinandergehalten werden
        # und ein Modellname ohne Markenzusatz trotzdem gefunden wird.
        _, query_name = _split_catalog_name(vehicle_query)
        catalog_names: dict[str, str] = {}
        compatible_models: list[dict[str, Any]] = []
        for item in models:
            if not isinstance(item.get("id"), str):
                continue
            subbrand, bare_name = _split_catalog_name(_text(item, "description", "name") or "")
            if not _subbrand_matches(brand_definition, subbrand):
                continue
            catalog_names[item["id"]] = bare_name
            compatible_models.append(item)
        models = compatible_models

        general_family_query = _is_general_model_query(query_name)
        matching_models = [
            item
            for item in models
            if (
                query_name == catalog_names[item["id"]]
                or query_name.startswith(f"{catalog_names[item['id']]} ")
                or (
                    general_family_query
                    and catalog_names[item["id"]].startswith(f"{query_name} ")
                )
            )
        ]
        exact_models = [item for item in matching_models if query_name == catalog_names[item["id"]]]
        if exact_models:
            family_name = catalog_names[exact_models[0]["id"]]
            selected_models = [
                item for item in models
                if (
                    catalog_names[item["id"]] == family_name
                    or catalog_names[item["id"]].startswith(f"{family_name} ")
                )
            ]
        elif matching_models and general_family_query:
            selected_models = matching_models
        elif matching_models:
            longest_name = max(len(catalog_names[item["id"]]) for item in matching_models)
            selected_models = [
                item for item in matching_models
                if len(catalog_names[item["id"]]) == longest_name
            ]
        else:
            selected_models = []
        if not selected_models:
            raise VehicleNotFound("Das Volkswagen-Modell wurde nicht eindeutig gefunden.")
        if len(selected_models) > 1 and not exact_models and not general_family_query:
            raise ManualReviewRequired(
                "Mehrere Volkswagen-Modelle passen zur Eingabe.",
                [{"name": _text(item, "description", "name") or "Volkswagen-Modell"} for item in selected_models],
            )
        return brand_definition, brand_id, selected_models, vehicle_query

    def _family_types(self, selected_models: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        """Listet jeden technischen Typ der Modellfamilie mit seinem Modell."""
        return [
            (model_item, item)
            for model_item in selected_models
            for item in _data(self.client.model_types(self.market, model_item["id"]), "Typenliste")
        ]

    def _verified_wltp(
        self, brand_id: str, type_id: str, modelyear_code: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
        """Holt die bestätigten WLTP-Werte genau eines eindeutig baubaren Typs."""
        bases = _data(
            self.client.base_configuration(self.market, brand_id, type_id, modelyear_code),
            "Basiskonfiguration",
        )
        if len(bases) != 1:
            raise ManualReviewRequired("Volkswagen liefert keine eindeutige Basiskonfiguration.")
        configuration = _id_configuration(bases[0])
        cache_key = technical_cache_key(configuration)
        wltp = self.store.get_cache(cache_key)
        if wltp is None:
            check = self.client.check(self.market, configuration)
            if not isinstance(check, dict) or check.get("buildable") is not True or check.get("distinct") is not True:
                raise ManualReviewRequired("Die Basiskonfiguration ist nicht eindeutig baubar.")
            raw_wltp = self.client.wltp(self.market, configuration)
            if not isinstance(raw_wltp, dict):
                raise OkapiError("Volkswagen hat keine verwendbare WLTP-Antwort geliefert.")
            extract_verified_wltp(raw_wltp)
            self.store.put_cache(cache_key, raw_wltp, ttl_seconds=self.cache_ttl_seconds)
            wltp = raw_wltp
        return extract_verified_wltp(wltp), wltp, configuration, cache_key

    def retrieve_model_range(self, vehicle_name: str) -> VerifiedModelRange:
        """Ermittelt die gesetzliche Spanne über alle Varianten einer Modellfamilie.

        Die Spanne gilt nach Anlage 4 nur dann, wenn sie den vollständigen aktuell
        angebotenen Variantenbestand abbildet. Lässt sich auch nur eine Variante
        nicht bestätigen, wird deshalb keine Spanne ausgegeben, sondern die
        manuelle Prüfung mit Nennung der betroffenen Typen verlangt.
        """
        brand_definition, brand_id, selected_models, vehicle_query = self._resolve_family(vehicle_name)
        model_types = self._family_types(selected_models)
        # Die Spanne muss denselben Variantenbestand abbilden, den die Eingabe
        # anspricht. Bei "Golf ENERGY" ist das die ENERGY-Linie, bei "Golf" die
        # gesamte Familie. Ohne diesen Filter würden fremde Ausstattungslinien
        # mitgerechnet und die Spanne wäre sachlich falsch.
        input_normalised = _type_search_text(vehicle_query)
        matching = [
            pair for pair in model_types
            if input_normalised in _type_search_text(_text(pair[1], "description", "name") or "")
        ]
        model_types = matching or model_types

        by_powertrain: dict[PowertrainType, list[tuple[str, ConsumptionValues]]] = {}
        model_ids: set[str] = set()
        model_years: set[int] = set()
        type_ids: list[str] = []
        excluded = 0
        unresolved: list[dict[str, Any]] = []

        for model_item, type_entry in model_types:
            description = _text(type_entry, "description", "name") or ""
            type_id = _text(type_entry, "id")
            type_code = _text(type_entry, "code")
            modelyear_code = _text(type_entry, "modelyear_code")
            # Nutzfahrzeugausführungen sind keine Pkw und gehören nicht in eine
            # Pkw-EnVKV-Spanne. Sie werden übergangen, nicht als Fehler gewertet.
            if _is_excluded_n1_candidate(brand_definition["code"], description):
                excluded += 1
                continue
            if type_id is None or type_code is None or modelyear_code is None:
                unresolved.append({"name": description, "reason": "Technische Zuordnungsdaten fehlen."})
                continue
            if self.require_vehicle_class_approval and brand_definition["code"] == "VN":
                approval_key = _text(type_entry, "basetype_code") or type_id
                approval = self.store.get_vehicle_class_approval(approval_key)
                if approval is not None and approval["vehicle_class"] == "N1":
                    excluded += 1
                    continue
                if approval is None:
                    self.store.record_vehicle_class_request(
                        approval_key, brand_definition["display"], description
                    )
            model_year_text = modelyear_code.rsplit(":", 1)[-1]
            try:
                values, _wltp, _configuration, _cache_key = self._verified_wltp(
                    brand_id, type_id, modelyear_code
                )
                powertrain = _powertrain_for(values)
                consumption = _consumption_for(values)
            except ManualReviewRequired as error:
                # Fachliche Gründe machen die Spanne dauerhaft unvollständig und
                # gehören in die Prüfliste. Ein vorübergehender Transportfehler
                # darf dagegen nicht als "nicht bestätigbar" erscheinen, sondern
                # muss als solcher gemeldet werden, damit der Abruf wiederholbar
                # bleibt.
                unresolved.append({"type_id": type_id, "name": description, "reason": str(error)})
                continue
            by_powertrain.setdefault(powertrain, []).append((type_code, consumption))
            model_ids.add(str(model_item["id"]))
            type_ids.append(type_id)
            if model_year_text.isdigit():
                model_years.add(int(model_year_text))

        if unresolved:
            confirmed = sum(len(variants) for variants in by_powertrain.values())
            raise ManualReviewRequired(
                f"Die Modellspanne ist unvollständig: {confirmed} von "
                f"{confirmed + len(unresolved)} Varianten konnten bestätigt werden. Eine "
                "gesetzliche Spanne darf nur aus dem vollständigen Variantenbestand gebildet "
                "werden.",
                unresolved,
            )
        if not by_powertrain:
            raise VehicleNotEligible(
                "Für dieses Modell wurde keine Variante gefunden, die unter die Pkw-EnVKV fällt."
                if excluded
                else "Für dieses Modell wurde keine verwendbare Variante gefunden."
            )

        groups = tuple(
            build_model_range_group(powertrain, variants)
            for powertrain, variants in sorted(by_powertrain.items(), key=lambda item: item[0].value)
        )
        family = _strip_subbrand_display(_text(selected_models[0], "description", "name") or "")
        return VerifiedModelRange(
            brand=brand_definition["display"],
            model_family=family,
            groups=groups,
            model_ids=tuple(sorted(model_ids)),
            model_years=tuple(sorted(model_years)),
            type_ids=tuple(type_ids),
            provider="Volkswagen OKAPI",
            retrieved_at=datetime.now(UTC).isoformat(),
        )

    def retrieve(self, vehicle_name: str, selected_type_id: str | None = None) -> VerifiedVehicleData:
        brand_definition, brand_id, selected_models, vehicle_query = self._resolve_family(vehicle_name)
        model_types = self._family_types(selected_models)
        types = [item for _, item in model_types]
        input_normalised = _type_search_text(vehicle_query)
        matching_model_types = [
            (model_item, item)
            for model_item, item in model_types
            if input_normalised in _type_search_text(_text(item, "description", "name") or "")
        ]
        matching_types = [item for _, item in matching_model_types]
        if selected_type_id is not None:
            selected_candidates = [
                (model_item, item) for model_item, item in model_types
                if _text(item, "id") == selected_type_id
            ]
            if len(selected_candidates) != 1:
                raise ManualReviewRequired("Der ausgewählte Fahrzeugtyp ist nicht mehr verfügbar.")
            model, selected = selected_candidates[0]
        elif len(matching_types) == 1:
            selected = matching_types[0]
            model = matching_model_types[0][0]
        else:
            package_free = [pair for pair in matching_model_types if not pair[1].get("extensions")]
            if len(package_free) == 1:
                model, selected = package_free[0]
            else:
                input_tokens = set(input_normalised.split())
                pool = matching_model_types or model_types
                ranked = sorted(
                    pool,
                    key=lambda pair: len(input_tokens & set(_type_search_text(_text(pair[1], "description", "name") or "").split())),
                    reverse=True,
                )
                raise ManualReviewRequired(
                    "Der Fahrzeugtyp ist nicht eindeutig oder enthält ein Ausstattungspaket.",
                    [
                        {
                            "type_id": _text(item, "id"),
                            "name": _text(item, "description", "name") or "Volkswagen-Fahrzeugtyp",
                            "model_year": (_text(item, "modelyear_code", "model_year") or "").rsplit(":", 1)[-1],
                        }
                        for _, item in ranked if _text(item, "id")
                    ],
                )

        type_id = _text(selected, "id")
        type_code = _text(selected, "code")
        approval_key = _text(selected, "basetype_code") or type_id
        modelyear_code = _text(selected, "modelyear_code")
        type_description = _text(selected, "description", "name") or ""
        if _is_excluded_n1_candidate(brand_definition["code"], type_description):
            raise VehicleNotEligible(
                "Dieses Fahrzeug ist eindeutig eine Nutzfahrzeugausführung. Eine Kennzeichnung nach der Pkw-EnVKV ist dafür nicht erforderlich."
            )
        if type_id is None or type_code is None or modelyear_code is None:
            raise ManualReviewRequired("Dem Fahrzeugtyp fehlen technische Zuordnungsdaten.")
        vehicle_class = "M1"
        if self.require_vehicle_class_approval and brand_definition["code"] == "VN":
            approval = self.store.get_vehicle_class_approval(approval_key)
            if approval is None:
                self.store.record_vehicle_class_request(
                    approval_key, brand_definition["display"], type_description
                )
                vehicle_class = "UNKNOWN"
            else:
                vehicle_class = approval["vehicle_class"]
            if vehicle_class == "N1":
                raise VehicleNotEligible(
                    "Dieses Fahrzeug ist als N1 eingestuft. Eine Kennzeichnung nach der Pkw-EnVKV ist dafür nicht erforderlich."
                )
        catalog_model_display = _catalog_model_display(_text(model, "description", "name") or "")
        parsed_type = _parse_identity(_normalise_display(type_description), catalog_model_display)
        # Die Marke steht im Datenblatt in einem eigenen Feld. Ein Namenszusatz
        # wie "SEAT" oder "CUPRA" darf deshalb nicht zusätzlich in der
        # Handelsbezeichnung erscheinen.
        model_display = _strip_subbrand_display(catalog_model_display)

        values, wltp, configuration, cache_key = self._verified_wltp(brand_id, type_id, modelyear_code)
        order_data: dict[str, Any] | None = None
        order_method = getattr(self.client, "order", None)
        if callable(order_method):
            order_cache_key = f"{cache_key}:order"
            order_data = self.store.get_cache(order_cache_key)
            if order_data is None:
                raw_order = order_method(self.market, configuration)
                if not isinstance(raw_order, dict):
                    raise OkapiError("Volkswagen hat keine verwendbaren technischen Daten geliefert.")
                self.store.put_cache(
                    order_cache_key, raw_order, ttl_seconds=self.cache_ttl_seconds
                )
                order_data = raw_order
        technical_displacement_cc = _technical_number(order_data or {}, "3.2.1.3.99")
        fuel_types = values.get("fuel_types") or []
        powertrain = _powertrain_for(values)
        model_year_text = modelyear_code.rsplit(":", 1)[-1]
        if not model_year_text.isdigit():
            raise ManualReviewRequired("Das Modelljahr ist nicht eindeutig.")
        now = datetime.now(UTC).isoformat()
        return VerifiedVehicleData(
            vehicle=VehicleIdentity(
                brand=brand_definition["display"],
                model=model_display,
                trim=parsed_type["trim"],
                power_kw=parsed_type["power_kw"],
                power_ps=parsed_type["power_ps"],
                battery_kwh=parsed_type["battery_kwh"],
                transmission=parsed_type["transmission"],
                model_id=model["id"],
                model_year=int(model_year_text),
                type_id=type_id,
                type_code=type_code,
                engine_displacement_cc=technical_displacement_cc,
                vehicle_class=vehicle_class,
            ),
            consumption=_consumption_for(values),
            source=SourceReference(
                provider="Volkswagen OKAPI",
                model_id=model["id"],
                model_year=int(model_year_text),
                type_id=type_id,
                type_code=type_code,
                retrieved_at=now,
                data_version=str(values["data_version"]) if values.get("data_version") is not None else None,
            ),
            raw_wltp=wltp,
            powertrain=powertrain,
            annual_vehicle_tax_eur=calculate_vehicle_tax(
                powertrain, technical_displacement_cc, Decimal(str(values["co2_g_km"]))
            ),
            tax_data_verified=(
                powertrain == PowertrainType.BATTERY_ELECTRIC
                or technical_displacement_cc is not None
            ),
        )


def _normalise_display(value: str) -> str:
    return " ".join(value.split())
