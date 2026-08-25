from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from backend.app.domain.envkv import (
    ComplianceProfileIncomplete,
    EnergyCostConfiguration,
    UsageContext,
    VerifiedModelRange,
    VerifiedVehicleData,
    render_model_range_text,
    calculate_energy_costs,
    build_data_sheet,
    decimal_safe_dict,
    render_compliance_text,
)
from backend.app.storage import SQLiteStore
from backend.app.services.price_profiles import official_price_profile


def local_today(timezone: str = "Europe/Berlin") -> date:
    """Angebotsdatum in der Zeitzone des Betriebs.

    Das Preisprofil wechselt zu einem Kalendertag und der Hinweis nach Anlage 1
    trägt ein Erstellungsdatum. Beides muss der örtlichen Zeit folgen; in UTC
    läge der Wechsel abends um 22 oder 23 Uhr Ortszeit.
    """
    return datetime.now(ZoneInfo(timezone)).date()


class VehicleDataProvider(Protocol):
    def retrieve(self, vehicle_name: str, selected_type_id: str | None = None) -> VerifiedVehicleData: ...
    def retrieve_model_range(self, vehicle_name: str) -> VerifiedModelRange: ...


class ComplianceService:
    def __init__(
        self,
        provider: VehicleDataProvider,
        store: SQLiteStore,
        cost_config: EnergyCostConfiguration,
        cost_config_factory: Callable[[], EnergyCostConfiguration] | None = None,
        timezone: str = "Europe/Berlin",
    ) -> None:
        self.provider = provider
        self.store = store
        self.cost_config = cost_config
        self.cost_config_factory = cost_config_factory
        self.timezone = timezone

    def create(
        self,
        vehicle_name: str,
        usage_context: UsageContext = UsageContext.ADVERTISING,
        selected_type_id: str | None = None,
    ) -> dict[str, object]:
        verified = self.provider.retrieve(vehicle_name, selected_type_id)
        if (
            usage_context in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}
            and verified.vehicle.brand == "Volkswagen Nutzfahrzeuge"
            and verified.vehicle.vehicle_class != "M1"
        ):
            raise ComplianceProfileIncomplete(
                "Für ein Online- oder Leasingangebot muss dieses Fahrzeug zuerst als M1 freigegeben werden."
            )
        detailed_offer = usage_context in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}
        current_cost_config = (
            self.cost_config_factory()
            if detailed_offer and self.cost_config_factory
            else self.cost_config
        )
        costs = calculate_energy_costs(verified.consumption, current_cost_config)
        output_text = render_compliance_text(verified, costs, usage_context)
        retrieved_at = verified.source.retrieved_at
        result: dict[str, object] = {
            "status": "verified",
            "confidence": float(verified.confidence),
            "powertrain": verified.powertrain.value,
            "usage_context": usage_context.value,
            "scope": {"vehicle_status": "new", "vehicle_class": verified.vehicle.vehicle_class},
            "vehicle": decimal_safe_dict(verified.vehicle),
            "consumption": decimal_safe_dict(verified.consumption),
            "energy_costs": decimal_safe_dict(costs),
            "output_text": output_text,
            "source": decimal_safe_dict(verified.source),
        }
        if verified.vehicle.vehicle_class == "UNKNOWN":
            result["notice"] = (
                "Die Fahrzeugklasse ist noch nicht als M1 bestätigt. Der Verbrauchstext kann für Werbung "
                "und Social Media verwendet werden; Online- und Leasingangebote bleiben gesperrt."
            )
        if usage_context in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}:
            result["data_sheet"] = build_data_sheet(
                verified, costs, local_today(self.timezone).isoformat()
            )
        self.store.write_audit(_single_variant_audit(vehicle_name, verified, output_text, retrieved_at))
        return result

    def create_model_range(
        self, vehicle_name: str, usage_context: UsageContext = UsageContext.ADVERTISING
    ) -> dict[str, object]:
        """Erzeugt den Pflichtblock für die Werbung mit einem ganzen Modell."""
        if usage_context in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}:
            raise ComplianceProfileIncomplete(
                "Ein konkretes Online- oder Leasingangebot benötigt eine einzelne Variante, "
                "keine Modellspanne."
            )
        data = self.provider.retrieve_model_range(vehicle_name)
        output_text = render_model_range_text(data, usage_context)
        result: dict[str, object] = {
            "status": "verified",
            "result_type": "model_range",
            "usage_context": usage_context.value,
            "brand": data.brand,
            "model_family": data.model_family,
            "variant_count": sum(group.variant_count for group in data.groups),
            "groups": decimal_safe_dict(data.groups),
            "output_text": output_text,
            "source": {
                "provider": data.provider,
                "retrieved_at": data.retrieved_at,
                "model_years": list(data.model_years),
                "type_ids": list(data.type_ids),
            },
        }
        self.store.write_audit(_model_range_audit(vehicle_name, data, output_text))
        return result


def _single_variant_audit(
    vehicle_name: str, verified: VerifiedVehicleData, output_text: str, retrieved_at: str | None
) -> dict[str, object]:
    return {
        "timestamp": retrieved_at or datetime.now(UTC).isoformat(),
        "user_input": vehicle_name,
        "parsed_vehicle": {"vehicle_name": vehicle_name},
        "matched_vehicle": decimal_safe_dict(verified.vehicle),
        "model_id": verified.vehicle.model_id,
        "model_year": verified.vehicle.model_year,
        "match_confidence": float(verified.confidence),
        "wltp_raw": verified.raw_wltp,
        "generated_output": output_text,
        "source": decimal_safe_dict(verified.source),
    }


def _model_range_audit(vehicle_name: str, data: VerifiedModelRange, output_text: str) -> dict[str, object]:
    return {
        "timestamp": data.retrieved_at,
        "user_input": vehicle_name,
        "parsed_vehicle": {"vehicle_name": vehicle_name, "model_range": True},
        "matched_vehicle": decimal_safe_dict(data),
        "model_id": ", ".join(data.model_ids),
        "model_year": max(data.model_years) if data.model_years else 0,
        "match_confidence": 1.0,
        # Die Einzelantworten bleiben über die technischen Typen und den
        # Konfigurations-Cache nachvollziehbar. Der Rohbestand aller Varianten
        # würde den Auditsatz sonst um ein Vielfaches aufblähen.
        "wltp_raw": {"model_range_type_ids": list(data.type_ids)},
        "generated_output": output_text,
        "source": {"provider": data.provider, "retrieved_at": data.retrieved_at},
    }


def cost_config_from_settings(settings: object, offer_date: date | None = None) -> EnergyCostConfiguration:
    profile = official_price_profile(
        offer_date or local_today(getattr(settings, "timezone", "Europe/Berlin"))
    )
    config = profile.config
    return EnergyCostConfiguration(
        electricity_price_eur_kwh=config.electricity_price_eur_kwh,
        electricity_reference_year=config.electricity_reference_year,
        annual_distance_km=int(settings.annual_distance_km),
        petrol_price_eur_l=config.petrol_price_eur_l,
        diesel_price_eur_l=config.diesel_price_eur_l,
        fuel_reference_year=config.fuel_reference_year,
        co2_price_low_eur_t=config.co2_price_low_eur_t,
        co2_price_medium_eur_t=config.co2_price_medium_eur_t,
        co2_price_high_eur_t=config.co2_price_high_eur_t,
        co2_cost_period_years=config.co2_cost_period_years,
        co2_cost_period_start_year=config.co2_cost_period_start_year,
        price_profile_id=profile.profile_id,
        price_profile_valid_from=profile.valid_from.isoformat(),
        price_profile_valid_until=profile.valid_until.isoformat(),
        energy_price_source_url=profile.energy_source_url,
        co2_price_source_url=profile.co2_source_url,
    )


def non_offer_cost_config_from_settings(settings: object) -> EnergyCostConfiguration:
    """Technische Rechenkonfiguration für Anlage-4-Texte; Kosten werden dort nie ausgegeben."""
    return EnergyCostConfiguration(
        electricity_price_eur_kwh=Decimal(str(settings.electricity_price_eur_kwh)),
        electricity_reference_year=int(settings.electricity_reference_year),
        annual_distance_km=int(settings.annual_distance_km),
        petrol_price_eur_l=Decimal(str(settings.petrol_price_eur_l)),
        diesel_price_eur_l=Decimal(str(settings.diesel_price_eur_l)),
        fuel_reference_year=int(settings.fuel_reference_year),
    )
