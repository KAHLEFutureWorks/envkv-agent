from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any


MONEY_QUANTUM = Decimal("0.01")
CONSUMPTION_QUANTUM = Decimal("0.1")

# § 3d KraftStG: Die Befreiung gilt bei einer Erstzulassung bis zum 31.12.2030
# für zehn Jahre, längstens bis zum 31.12.2035.
EV_TAX_EXEMPTION_LAST_REGISTRATION = date(2030, 12, 31)
EV_TAX_EXEMPTION_LATEST_END = date(2035, 12, 31)
EV_TAX_EXEMPTION_YEARS = 10


class PowertrainType(StrEnum):
    BATTERY_ELECTRIC = "battery_electric"
    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    PLUG_IN_HYBRID = "plug_in_hybrid"
    FUEL_CELL = "fuel_cell"


class UsageContext(StrEnum):
    ADVERTISING = "advertising"
    SOCIAL_MEDIA = "social_media"
    ONLINE_OFFER = "online_offer"
    LEASING_OFFER = "leasing_offer"


class ComplianceProfileIncomplete(ValueError):
    """Für den gewünschten Einsatz fehlen rechtlich erforderliche Herstellerwerte."""


@dataclass(frozen=True)
class VehicleIdentity:
    brand: str
    model: str
    trim: str
    power_kw: int
    power_ps: int | None
    # Der Katalog nennt auch gebrochene Kapazitaeten wie 19,7 kWh; der Wert wird
    # deshalb als Decimal uebernommen und nicht gerundet.
    battery_kwh: Decimal | None
    transmission: str
    model_id: str
    model_year: int
    type_id: str
    type_code: str
    engine_displacement_cc: int | None = None
    vehicle_class: str = "M1"


@dataclass(frozen=True)
class ConsumptionValues:
    combined_kwh_100km: Decimal | None
    co2_g_km: Decimal
    co2_class: str
    electric_range_km: int | None
    combined_l_100km: Decimal | None = None
    discharged_l_100km: Decimal | None = None
    co2_class_discharged: str | None = None
    fuel_type: str | None = None
    phase_kwh_100km: dict[str, Decimal] | None = None
    phase_l_100km: dict[str, Decimal] | None = None
    pure_electric_kwh_100km: Decimal | None = None


@dataclass(frozen=True)
class EnergyCostConfiguration:
    electricity_price_eur_kwh: Decimal
    electricity_reference_year: int
    annual_distance_km: int
    petrol_price_eur_l: Decimal = Decimal("1.796")
    diesel_price_eur_l: Decimal = Decimal("1.649")
    fuel_reference_year: int = 2024
    co2_price_low_eur_t: Decimal = Decimal("60")
    co2_price_medium_eur_t: Decimal = Decimal("142.5")
    co2_price_high_eur_t: Decimal = Decimal("220")
    co2_cost_period_years: int = 10
    co2_cost_period_start_year: int = 2027
    price_profile_id: str = ""
    price_profile_valid_from: str = ""
    price_profile_valid_until: str = ""
    energy_price_source_url: str = ""
    co2_price_source_url: str = ""


@dataclass(frozen=True)
class EnergyCosts:
    annual_cost_eur: Decimal
    annual_distance_km: int
    electricity_price_eur_kwh: Decimal
    fuel_price_eur_l: Decimal | None
    reference_year: int
    electricity_reference_year: int
    fuel_reference_year: int
    annual_vehicle_tax_eur: Decimal
    co2_cost_low_eur: Decimal
    co2_cost_medium_eur: Decimal
    co2_cost_high_eur: Decimal
    co2_cost_period_years: int
    co2_cost_period_start_year: int
    co2_price_low_eur_t: Decimal
    co2_price_medium_eur_t: Decimal
    co2_price_high_eur_t: Decimal
    price_profile_id: str = ""
    price_profile_valid_from: str = ""
    price_profile_valid_until: str = ""
    energy_price_source_url: str = ""
    co2_price_source_url: str = ""


@dataclass(frozen=True)
class SourceReference:
    provider: str
    model_id: str
    model_year: int
    type_id: str
    type_code: str
    retrieved_at: str
    data_version: str | None = None


@dataclass(frozen=True)
class VerifiedVehicleData:
    vehicle: VehicleIdentity
    consumption: ConsumptionValues
    source: SourceReference
    raw_wltp: dict[str, Any]
    confidence: Decimal = Decimal("1.0")
    powertrain: PowertrainType = PowertrainType.BATTERY_ELECTRIC
    annual_vehicle_tax_eur: Decimal | None = None
    tax_data_verified: bool = False


CO2_CLASS_SCALE = "ABCDEFG"


@dataclass(frozen=True)
class ConsumptionRangeGroup:
    """Spanne einer Antriebsart über alle zusammengefassten Varianten eines Modells."""

    powertrain: PowertrainType
    variant_count: int
    type_codes: tuple[str, ...]
    co2_g_km: tuple[Decimal, Decimal]
    co2_class_best: str
    co2_class_worst: str
    combined_l_100km: tuple[Decimal, Decimal] | None = None
    combined_kwh_100km: tuple[Decimal, Decimal] | None = None
    discharged_l_100km: tuple[Decimal, Decimal] | None = None
    co2_class_discharged_best: str | None = None
    co2_class_discharged_worst: str | None = None


@dataclass(frozen=True)
class VerifiedModelRange:
    """Gesetzliche Min-/Max-Angaben für die Werbung mit einem ganzen Modell."""

    brand: str
    model_family: str
    groups: tuple[ConsumptionRangeGroup, ...]
    model_ids: tuple[str, ...]
    model_years: tuple[int, ...]
    type_ids: tuple[str, ...]
    provider: str
    retrieved_at: str


def _span(values: list[Decimal | None]) -> tuple[Decimal, Decimal] | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    if len(present) != len(values):
        raise ComplianceProfileIncomplete(
            "Für die Modellspanne fehlt bei mindestens einer Variante ein Pflichtwert."
        )
    return min(present), max(present)


def _class_span(classes: list[str | None]) -> tuple[str, str] | None:
    present = [item for item in classes if item]
    if not present:
        return None
    if len(present) != len(classes) or any(item not in CO2_CLASS_SCALE for item in present):
        raise ComplianceProfileIncomplete(
            "Für die Modellspanne fehlt bei mindestens einer Variante die CO₂-Klasse."
        )
    ordered = sorted(present, key=CO2_CLASS_SCALE.index)
    return ordered[0], ordered[-1]


def build_model_range_group(
    powertrain: PowertrainType, variants: list[tuple[str, ConsumptionValues]]
) -> ConsumptionRangeGroup:
    """Fasst die Varianten einer Antriebsart zu einer gesetzlichen Spanne zusammen.

    Nach Anlage 4 sind jeweils niedrigster und höchster Wert sowie günstigste und
    ungünstigste CO₂-Klasse anzugeben. Fehlt bei einer Variante ein Pflichtwert,
    ist die Spanne unvollständig und darf nicht ausgegeben werden.
    """
    if not variants:
        raise ComplianceProfileIncomplete("Die Modellspanne enthält keine Varianten.")
    consumptions = [consumption for _, consumption in variants]
    co2 = _span([declared_co2_g_km(item.co2_g_km) for item in consumptions])
    combined_classes = _class_span([item.co2_class for item in consumptions])
    if co2 is None or combined_classes is None:
        raise ComplianceProfileIncomplete("Die Modellspanne besitzt keine vollständigen CO₂-Angaben.")

    electricity = _span([item.combined_kwh_100km for item in consumptions])
    fuel = _span([item.combined_l_100km for item in consumptions])
    discharged = _span([item.discharged_l_100km for item in consumptions])
    discharged_classes = _class_span([item.co2_class_discharged for item in consumptions])

    if powertrain == PowertrainType.BATTERY_ELECTRIC and electricity is None:
        raise ComplianceProfileIncomplete("Der kombinierte Stromverbrauch fehlt für die Modellspanne.")
    if powertrain == PowertrainType.PLUG_IN_HYBRID and (
        electricity is None or fuel is None or discharged is None or discharged_classes is None
    ):
        raise ComplianceProfileIncomplete(
            "Die Pflichtwerte des Plug-in-Hybrids fehlen für die Modellspanne."
        )
    if powertrain in {PowertrainType.PETROL, PowertrainType.DIESEL, PowertrainType.HYBRID} and fuel is None:
        raise ComplianceProfileIncomplete("Der kombinierte Kraftstoffverbrauch fehlt für die Modellspanne.")

    return ConsumptionRangeGroup(
        powertrain=powertrain,
        variant_count=len(variants),
        type_codes=tuple(sorted(type_code for type_code, _ in variants)),
        co2_g_km=co2,
        co2_class_best=combined_classes[0],
        co2_class_worst=combined_classes[1],
        combined_l_100km=fuel,
        combined_kwh_100km=electricity,
        discharged_l_100km=discharged,
        co2_class_discharged_best=discharged_classes[0] if discharged_classes else None,
        co2_class_discharged_worst=discharged_classes[1] if discharged_classes else None,
    )


def _de_span(span: tuple[Decimal, Decimal], places: str) -> str:
    low, high = _de_decimal(span[0], places), _de_decimal(span[1], places)
    return low if low == high else f"{low} bis {high}"


def _de_class_span(best: str, worst: str) -> tuple[str, str]:
    return ("CO₂-Klasse", best) if best == worst else ("CO₂-Klassen", f"{best} bis {worst}")


_RANGE_POWERTRAIN_LABELS = {
    PowertrainType.BATTERY_ELECTRIC: "Rein elektrisch",
    PowertrainType.PETROL: "Benzin",
    PowertrainType.DIESEL: "Diesel",
    PowertrainType.HYBRID: "Hybrid ohne externe Aufladung",
    PowertrainType.PLUG_IN_HYBRID: "Plug-in-Hybrid",
}


def render_model_range_text(
    data: VerifiedModelRange, usage_context: UsageContext = UsageContext.ADVERTISING
) -> str:
    """Pflichtblock nach Anlage 4 für die Werbung mit einem Modell mehrerer Varianten."""
    if usage_context in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}:
        raise ComplianceProfileIncomplete(
            "Ein konkretes Online- oder Leasingangebot benötigt eine einzelne Variante, "
            "keine Modellspanne."
        )
    if not data.groups:
        raise ComplianceProfileIncomplete("Die Modellspanne enthält keine Antriebsart.")

    blocks: list[str] = []
    for group in data.groups:
        label, value = _de_class_span(group.co2_class_best, group.co2_class_worst)
        if group.powertrain == PowertrainType.BATTERY_ELECTRIC:
            body = (
                f"Energieverbrauch kombiniert: {_de_span(group.combined_kwh_100km, '0.1')} kWh/100 km; "
                f"CO₂-Emissionen kombiniert: {_de_span(group.co2_g_km, '1')} g/km; "
                f"{label}: {value}."
            )
        elif group.powertrain == PowertrainType.PLUG_IN_HYBRID:
            discharged_label, discharged_value = _de_class_span(
                group.co2_class_discharged_best or "", group.co2_class_discharged_worst or ""
            )
            body = (
                f"Energieverbrauch gewichtet kombiniert: {_de_span(group.combined_l_100km, '0.1')} l/100 km "
                f"und {_de_span(group.combined_kwh_100km, '0.1')} kWh/100 km; "
                f"Kraftstoffverbrauch bei entladener Batterie kombiniert: "
                f"{_de_span(group.discharged_l_100km, '0.1')} l/100 km; "
                f"CO₂-Emissionen gewichtet kombiniert: {_de_span(group.co2_g_km, '1')} g/km; "
                f"CO₂-Klassen: {value} (gewichtet kombiniert), "
                f"{discharged_value} (bei entladener Batterie)."
            )
        else:
            body = (
                f"Energieverbrauch kombiniert: {_de_span(group.combined_l_100km, '0.1')} l/100 km; "
                f"CO₂-Emissionen kombiniert: {_de_span(group.co2_g_km, '1')} g/km; "
                f"{label}: {value}."
            )
        prefix = (
            f"{_RANGE_POWERTRAIN_LABELS[group.powertrain]}: " if len(data.groups) > 1 else ""
        )
        blocks.append(f"{prefix}{body}")

    title = f"{data.brand} {data.model_family}".strip()
    intro = (
        "Angaben für alle derzeit angebotenen Varianten dieses Modells "
        f"({sum(group.variant_count for group in data.groups)} Varianten)."
    )
    return f"{title}\n\n{intro}\n\n" + "\n\n".join(blocks)


def declared_co2_g_km(co2_g_km: Decimal) -> Decimal:
    """Der auszuweisende CO₂-Wert in ganzen Gramm je Kilometer.

    OKAPI liefert den interpolierten Rohwert mit Nachkommastelle. Auszuweisen und
    für die CO₂-Kosten zu verwenden ist der ganzzahlige Wert; die Labels von
    Volkswagen für dieselben Fahrzeuge weisen ihn ebenso aus.
    """
    return co2_g_km.to_integral_value(rounding=ROUND_HALF_UP)


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        # Der 29. Februar besitzt im Zieljahr keine Entsprechung.
        return value.replace(year=value.year + years, month=2, day=28)


def electric_vehicle_tax_exemption(first_registration: date) -> dict[str, Any]:
    """Leitet die Steuerbefreiung eines Elektrofahrzeugs aus § 3d KraftStG ab.

    Der Anlage-1-Hinweis verlangt den Text „befristet steuerbefreit" zusammen mit
    dem Ende der Befristung. Das Ende wird deshalb aus dem Zulassungsdatum
    berechnet und nicht als fester Wert hinterlegt.
    """
    if first_registration > EV_TAX_EXEMPTION_LAST_REGISTRATION:
        raise ComplianceProfileIncomplete(
            "Für eine Erstzulassung nach dem "
            f"{EV_TAX_EXEMPTION_LAST_REGISTRATION.strftime('%d.%m.%Y')} greift die Steuerbefreiung "
            "nach § 3d KraftStG nicht mehr. Die Kraftfahrzeugsteuer muss dann aus bestätigten "
            "technischen Daten ermittelt werden."
        )
    exemption_end = min(
        _add_years(first_registration, EV_TAX_EXEMPTION_YEARS) - timedelta(days=1),
        EV_TAX_EXEMPTION_LATEST_END,
    )
    return {
        "status": "temporarily_exempt",
        "text": "Befristet steuerbefreit",
        "first_registration": first_registration.isoformat(),
        "first_registration_is_assumed": True,
        "exemption_end": exemption_end.isoformat(),
        "legal_basis": "§ 3d KraftStG",
        "footnote": (
            "Befristet steuerbefreit: Die Befreiung nach § 3d KraftStG gilt bei einer Erstzulassung "
            f"bis zum {EV_TAX_EXEMPTION_LAST_REGISTRATION.strftime('%d.%m.%Y')} für zehn Jahre, "
            f"längstens bis zum {EV_TAX_EXEMPTION_LATEST_END.strftime('%d.%m.%Y')}. Bei einer "
            f"Erstzulassung am {first_registration.strftime('%d.%m.%Y')} endet die Befreiung am "
            f"{exemption_end.strftime('%d.%m.%Y')}."
        ),
    }


def calculate_vehicle_tax(powertrain: PowertrainType, displacement_cc: int | None, co2_g_km: Decimal) -> Decimal | None:
    if powertrain == PowertrainType.BATTERY_ELECTRIC:
        return Decimal("0.00")
    if displacement_cc is None:
        return None
    hundreds = (displacement_cc + 99) // 100
    base = Decimal(hundreds) * (Decimal("9.50") if powertrain == PowertrainType.DIESEL else Decimal("2.00"))
    remaining = max(0, int(co2_g_km.to_integral_value(rounding=ROUND_HALF_UP)) - 95)
    co2_tax = Decimal("0")
    for width, rate in ((20, "2.00"), (20, "2.20"), (20, "2.50"), (20, "2.90"), (20, "3.40"), (10**9, "4.00")):
        amount = min(remaining, width)
        co2_tax += Decimal(amount) * Decimal(rate)
        remaining -= amount
        if remaining <= 0:
            break
    return (base + co2_tax).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_energy_costs(
    consumption: ConsumptionValues,
    config: EnergyCostConfiguration,
) -> EnergyCosts:
    if consumption.combined_kwh_100km is not None and consumption.combined_kwh_100km < 0:
        raise ValueError("Der kombinierte Verbrauch darf nicht negativ sein.")
    if config.annual_distance_km <= 0:
        raise ValueError("Die Jahresfahrleistung muss größer als null sein.")
    if config.electricity_price_eur_kwh < 0:
        raise ValueError("Der Strompreis darf nicht negativ sein.")
    annual_electricity = (
        (consumption.combined_kwh_100km or Decimal("0"))
        * Decimal(config.annual_distance_km) / Decimal(100)
    )
    fuel_price = None
    if consumption.combined_l_100km is not None:
        fuel_price = config.diesel_price_eur_l if consumption.fuel_type == "DIESEL" else config.petrol_price_eur_l
    annual_fuel = (
        (consumption.combined_l_100km or Decimal("0"))
        * Decimal(config.annual_distance_km) / Decimal(100)
    )
    annual_cost = (
        annual_electricity * config.electricity_price_eur_kwh
        + annual_fuel * (fuel_price or Decimal("0"))
    ).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    co2_tonnes = (
        declared_co2_g_km(consumption.co2_g_km)
        * Decimal(config.annual_distance_km)
        * Decimal(config.co2_cost_period_years)
        / Decimal("1000000")
    )
    return EnergyCosts(
        annual_cost_eur=annual_cost,
        annual_distance_km=config.annual_distance_km,
        electricity_price_eur_kwh=config.electricity_price_eur_kwh,
        fuel_price_eur_l=fuel_price,
        reference_year=max(config.electricity_reference_year, config.fuel_reference_year),
        electricity_reference_year=config.electricity_reference_year,
        fuel_reference_year=config.fuel_reference_year,
        annual_vehicle_tax_eur=Decimal("0.00"),
        co2_cost_low_eur=(co2_tonnes * config.co2_price_low_eur_t).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
        co2_cost_medium_eur=(co2_tonnes * config.co2_price_medium_eur_t).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
        co2_cost_high_eur=(co2_tonnes * config.co2_price_high_eur_t).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
        co2_cost_period_years=config.co2_cost_period_years,
        co2_cost_period_start_year=config.co2_cost_period_start_year,
        co2_price_low_eur_t=config.co2_price_low_eur_t,
        co2_price_medium_eur_t=config.co2_price_medium_eur_t,
        co2_price_high_eur_t=config.co2_price_high_eur_t,
        price_profile_id=config.price_profile_id,
        price_profile_valid_from=config.price_profile_valid_from,
        price_profile_valid_until=config.price_profile_valid_until,
        energy_price_source_url=config.energy_price_source_url,
        co2_price_source_url=config.co2_price_source_url,
    )


def _de_decimal(value: Decimal, places: str) -> str:
    return format(value.quantize(Decimal(places), rounding=ROUND_HALF_UP), "f").replace(".", ",")


def validate_compliance_profile(data: VerifiedVehicleData, usage_context: UsageContext) -> None:
    consumption = data.consumption
    if consumption.co2_g_km < 0 or consumption.co2_class not in set("ABCDEFG"):
        raise ComplianceProfileIncomplete("CO₂-Emissionen oder CO₂-Klasse sind nicht vollständig bestätigt.")
    if data.powertrain == PowertrainType.BATTERY_ELECTRIC:
        if consumption.combined_kwh_100km is None:
            raise ComplianceProfileIncomplete("Der kombinierte Stromverbrauch fehlt.")
    elif data.powertrain == PowertrainType.PLUG_IN_HYBRID:
        if any(value is None for value in (
            consumption.combined_l_100km,
            consumption.combined_kwh_100km,
            consumption.discharged_l_100km,
            consumption.co2_class_discharged,
        )):
            raise ComplianceProfileIncomplete("Die Pflichtwerte des Plug-in-Hybrids sind nicht vollständig bestätigt.")
        if consumption.co2_class_discharged not in set("ABCDEFG"):
            raise ComplianceProfileIncomplete("Die CO₂-Klasse bei entladener Batterie fehlt.")
    elif consumption.combined_l_100km is None:
        raise ComplianceProfileIncomplete("Der kombinierte Kraftstoffverbrauch fehlt.")

    if usage_context not in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}:
        return
    if data.annual_vehicle_tax_eur is None:
        raise ComplianceProfileIncomplete("Für dieses Fahrzeug fehlt die bestätigte Kraftfahrzeugsteuer.")
    if data.powertrain != PowertrainType.BATTERY_ELECTRIC and not data.tax_data_verified:
        raise ComplianceProfileIncomplete("Die Kraftfahrzeugsteuer basiert noch nicht auf bestätigten technischen Daten.")
    required_phases = {"low", "medium", "high", "extra_high"}
    if data.powertrain == PowertrainType.BATTERY_ELECTRIC:
        if consumption.electric_range_km is None or not required_phases.issubset(consumption.phase_kwh_100km or {}):
            raise ComplianceProfileIncomplete("Reichweite oder phasenspezifische Stromverbräuche fehlen für das Datenblatt.")
    elif data.powertrain == PowertrainType.PLUG_IN_HYBRID:
        if (
            consumption.electric_range_km is None
            or consumption.pure_electric_kwh_100km is None
            or not required_phases.issubset(consumption.phase_kwh_100km or {})
            or not required_phases.issubset(consumption.phase_l_100km or {})
        ):
            raise ComplianceProfileIncomplete("Die ergänzenden Plug-in-Hybrid-Werte fehlen für das Datenblatt.")
    elif not required_phases.issubset(consumption.phase_l_100km or {}):
        raise ComplianceProfileIncomplete("Die phasenspezifischen Kraftstoffverbräuche fehlen für das Datenblatt.")


def render_compliance_text(
    data: VerifiedVehicleData,
    costs: EnergyCosts,
    usage_context: UsageContext = UsageContext.ADVERTISING,
) -> str:
    validate_compliance_profile(data, usage_context)
    vehicle = data.vehicle
    consumption = data.consumption
    ps_text = f" ({vehicle.power_ps} PS)" if vehicle.power_ps is not None else ""
    battery_text = f" {vehicle.battery_kwh} kWh" if vehicle.battery_kwh is not None else ""
    title = (
        f"{vehicle.model} {vehicle.trim} {vehicle.power_kw} kW{ps_text}"
        f"{battery_text} {vehicle.transmission}"
    )

    if data.powertrain == PowertrainType.BATTERY_ELECTRIC:
        consumption_text = (
            f"Energieverbrauch kombiniert: {_de_decimal(consumption.combined_kwh_100km, '0.1')} kWh/100 km; "
            f"CO₂-Emissionen kombiniert: {_de_decimal(declared_co2_g_km(consumption.co2_g_km), '1')} g/km; "
            f"CO₂-Klasse: {consumption.co2_class}."
        )
    elif data.powertrain == PowertrainType.PLUG_IN_HYBRID:
        consumption_text = (
            f"Energieverbrauch gewichtet kombiniert: {_de_decimal(consumption.combined_l_100km, '0.1')} l/100 km "
            f"und {_de_decimal(consumption.combined_kwh_100km, '0.1')} kWh/100 km; "
            f"Kraftstoffverbrauch bei entladener Batterie kombiniert: {_de_decimal(consumption.discharged_l_100km, '0.1')} l/100 km; "
            f"CO₂-Emissionen gewichtet kombiniert: {_de_decimal(declared_co2_g_km(consumption.co2_g_km), '1')} g/km; "
            f"CO₂-Klassen: {consumption.co2_class} (gewichtet kombiniert), {consumption.co2_class_discharged} (bei entladener Batterie)."
        )
    else:
        consumption_text = (
            f"Energieverbrauch kombiniert: {_de_decimal(consumption.combined_l_100km, '0.1')} l/100 km; "
            f"CO₂-Emissionen kombiniert: {_de_decimal(declared_co2_g_km(consumption.co2_g_km), '1')} g/km; "
            f"CO₂-Klasse: {consumption.co2_class}."
        )
    return f"{title.strip()}\n\n{consumption_text}"


def build_data_sheet(
    data: VerifiedVehicleData,
    costs: EnergyCosts,
    created_at: str,
    planned_first_registration: date | None = None,
) -> dict[str, Any]:
    """Strukturierter Inhalt für den Hinweis nach Anlage 1 Pkw-EnVKV."""
    consumption = data.consumption
    if data.powertrain == PowertrainType.BATTERY_ELECTRIC:
        tax = electric_vehicle_tax_exemption(
            planned_first_registration or date.fromisoformat(created_at)
        )
    else:
        tax = {"status": "amount", "annual_eur": decimal_safe_dict(data.annual_vehicle_tax_eur)}
    tax_footnotes = [tax["footnote"]] if "footnote" in tax else []
    return {
        "document_type": "pkw_envkv_notice",
        "legal_basis": "Pkw-EnVKV Anlage 1",
        "created_at": created_at,
        "vehicle": decimal_safe_dict(data.vehicle),
        "powertrain": data.powertrain.value,
        "consumption": decimal_safe_dict(consumption),
        "declared_co2_g_km": decimal_safe_dict(declared_co2_g_km(consumption.co2_g_km)),
        "co2_classes": {
            "combined": consumption.co2_class,
            "discharged_battery": consumption.co2_class_discharged,
            "scale": ["A", "B", "C", "D", "E", "F", "G"],
        },
        "annual_energy_costs": decimal_safe_dict(costs),
        "vehicle_tax": tax,
        "co2_cost_period": (
            f"{costs.co2_cost_period_start_year}-"
            f"{costs.co2_cost_period_start_year + costs.co2_cost_period_years - 1}"
        ),
        "price_profile": {
            "id": costs.price_profile_id,
            "valid_from": costs.price_profile_valid_from,
            "valid_until": costs.price_profile_valid_until,
            "energy_price_source_url": costs.energy_price_source_url,
            "co2_price_source_url": costs.co2_price_source_url,
        },
        # Die Reihenfolge entspricht den Verweisen im Hinweis: 1) am CO₂-Wert,
        # 2) an den möglichen CO₂-Kosten, 3) an der Kraftfahrzeugsteuer.
        "footnotes": [
            "Es werden nur die CO₂-Emissionen berücksichtigt, die durch den Betrieb des Fahrzeugs entstehen. CO₂-Emissionen, die durch die Produktion und Bereitstellung des Pkw sowie des Kraftstoffs oder der Energieträger entstehen oder vermieden werden, werden bei der Ermittlung der CO₂-Emissionen gemäß WLTP nicht berücksichtigt.",
            "Aufgrund der CO₂-Bepreisung sind künftig Erhöhungen der Kraftstoffkosten möglich. Die zukünftige CO₂-Preisentwicklung ist unsicher; tatsächliche Preise können sowohl höher als auch niedriger als in den hier zugrunde gelegten Modellrechnungen ausfallen. Die CO₂-Kosten sind beim Tanken mit den Kraftstoffkosten zu bezahlen. Weitere Informationen unter www.alternativ-mobil.info.",
        ] + tax_footnotes,
        "general_notes": [
            "Die tatsächlichen Energiekosten hängen von Fahrweise, Nutzung und Energiepreisen ab.",
        ],
        "source": decimal_safe_dict(data.source),
    }


def decimal_safe_dict(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "__dataclass_fields__"):
        return {key: decimal_safe_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: decimal_safe_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        # Spannen werden als Tupel geführt; ohne diesen Zweig blieben ihre
        # Decimal-Werte unkonvertiert und wären nicht serialisierbar.
        return [decimal_safe_dict(item) for item in value]
    return value
