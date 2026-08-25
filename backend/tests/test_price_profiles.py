from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from backend.app.domain.envkv import (
    ComplianceProfileIncomplete, ConsumptionValues, EnergyCostConfiguration,
    PowertrainType, SourceReference, UsageContext, VehicleIdentity, VerifiedVehicleData,
)
from backend.app.services.compliance import ComplianceService, cost_config_from_settings
from backend.app.services.price_profiles import PriceProfileUnavailable, official_price_profile
from backend.app.storage import SQLiteStore


class PriceProfileAndScopeTests(unittest.TestCase):
    def test_official_2025_profile_is_date_bounded_and_auditable(self) -> None:
        profile = official_price_profile(date(2026, 5, 20))
        self.assertEqual("BMWE-2025", profile.profile_id)
        self.assertEqual(Decimal("127"), profile.config.co2_price_medium_eur_t)
        # Nach dem letzten hinterlegten Profil stoppt die Angebotserstellung,
        # statt mit fortgeschriebenen Werten weiterzurechnen.
        with self.assertRaises(PriceProfileUnavailable):
            official_price_profile(date(2027, 7, 1))

        class Settings:
            annual_distance_km = 15000

        config = cost_config_from_settings(Settings(), date(2026, 5, 20))
        self.assertEqual("BMWE-2025", config.price_profile_id)
        self.assertEqual("2026-06-30", config.price_profile_valid_until)
        self.assertTrue(config.energy_price_source_url.startswith("https://"))

    def test_commercial_vehicle_offer_is_blocked(self) -> None:
        vehicle = VehicleIdentity(
            brand="Volkswagen Nutzfahrzeuge", model="Multivan", trim="Life", power_kw=130,
            power_ps=None, battery_kwh=None, transmission="DSG", model_id="m", model_year=2027,
            type_id="t", type_code="TYPE:T", engine_displacement_cc=1498,
            vehicle_class="UNKNOWN",
        )
        data = VerifiedVehicleData(
            vehicle=vehicle,
            consumption=ConsumptionValues(
                combined_kwh_100km=None, combined_l_100km=Decimal("5"), co2_g_km=Decimal("120"),
                co2_class="D", electric_range_km=None, fuel_type="PETROL",
            ),
            source=SourceReference("Volkswagen OKAPI", "m", 2027, "t", "TYPE:T", "2026-08-20"),
            raw_wltp={}, powertrain=PowertrainType.PETROL,
            annual_vehicle_tax_eur=Decimal("100"), tax_data_verified=True,
        )

        class Provider:
            def retrieve(self, vehicle_name: str, selected_type_id: str | None = None) -> VerifiedVehicleData:
                return data

        with tempfile.TemporaryDirectory() as directory:
            service = ComplianceService(
                Provider(), SQLiteStore(Path(directory) / "db.sqlite3"),
                EnergyCostConfiguration(Decimal("0.321"), 2024, 15000),
            )
            social = service.create("Multivan Life", UsageContext.SOCIAL_MEDIA)
            self.assertEqual("UNKNOWN", social["scope"]["vehicle_class"])
            self.assertIn("Online- und Leasingangebote bleiben gesperrt", social["notice"])
            with self.assertRaisesRegex(ComplianceProfileIncomplete, "als M1 freigegeben"):
                service.create("Multivan Life", UsageContext.ONLINE_OFFER)

    def test_profiles_are_contiguous_and_switch_automatically_on_1_july(self) -> None:
        from backend.app.services.price_profiles import _PROFILES

        # Lückenlose, überschneidungsfreie Reihe: ohne das wäre der Wechsel nicht
        # allein über das Angebotsdatum steuerbar.
        for earlier, later in zip(_PROFILES, _PROFILES[1:]):
            self.assertEqual(later.valid_from - earlier.valid_until, timedelta(days=1))

        # Die Veröffentlichung gilt für Pkw, die nach dem 30. Juni angeboten
        # werden; der 1. Oktober ist nur die späteste Anwendungsfrist.
        self.assertEqual("BMWE-2025", official_price_profile(date(2026, 6, 30)).profile_id)
        self.assertEqual("BMWE-2026", official_price_profile(date(2026, 7, 1)).profile_id)

    def test_official_2026_profile_matches_the_publication_of_30_june_2026(self) -> None:
        profile = official_price_profile(date(2026, 7, 1))
        config = profile.config
        # Bezugsjahr 2025, anzuwenden spätestens ab dem 01.10.2026.
        self.assertEqual(2025, config.electricity_reference_year)
        self.assertEqual(2025, config.fuel_reference_year)
        self.assertEqual(Decimal("0.321"), config.electricity_price_eur_kwh)
        self.assertEqual(Decimal("1.744"), config.petrol_price_eur_l)
        self.assertEqual(Decimal("1.610"), config.diesel_price_eur_l)
        self.assertEqual(Decimal("60"), config.co2_price_low_eur_t)
        self.assertEqual(Decimal("142.5"), config.co2_price_medium_eur_t)
        self.assertEqual(Decimal("220"), config.co2_price_high_eur_t)
        self.assertEqual(2027, config.co2_cost_period_start_year)
        self.assertEqual(10, config.co2_cost_period_years)
        self.assertTrue(profile.energy_source_url.endswith(".pdf"))
        self.assertTrue(profile.co2_source_url.endswith(".pdf"))

    def test_official_2025_profile_uses_the_published_electricity_price(self) -> None:
        # Die Veröffentlichung vom 30.06.2025 nennt 0,312 EUR/kWh für das Jahr 2024.
        config = official_price_profile(date(2026, 1, 15)).config
        self.assertEqual(Decimal("0.312"), config.electricity_price_eur_kwh)
        self.assertEqual(Decimal("1.796"), config.petrol_price_eur_l)
        self.assertEqual(Decimal("1.649"), config.diesel_price_eur_l)
        self.assertEqual(Decimal("127"), config.co2_price_medium_eur_t)
        self.assertEqual(2026, config.co2_cost_period_start_year)

    def test_figures_match_the_published_volkswagen_labels(self) -> None:
        """Gegenprobe an drei Labels, die Volkswagen für dieselben Fahrzeuge ausweist."""
        from backend.app.domain.envkv import calculate_energy_costs

        config = cost_config_from_settings(_Distance(), date(2026, 8, 21))

        # ID.5 Pure, 15,5 kWh/100 km, 0 g/km
        bev = calculate_energy_costs(
            ConsumptionValues(
                combined_kwh_100km=Decimal("15.5"), co2_g_km=Decimal("0"),
                co2_class="A", electric_range_km=446,
            ), config)
        self.assertEqual(Decimal("746.33"), bev.annual_cost_eur)

        # T-Cross 1.0 TSI, 5,8 l/100 km, Rohwert 131,1 g/km
        petrol = calculate_energy_costs(
            ConsumptionValues(
                combined_kwh_100km=None, combined_l_100km=Decimal("5.8"),
                co2_g_km=Decimal("131.1"), co2_class="D", electric_range_km=None,
                fuel_type="PETROL",
            ), config)
        self.assertEqual(Decimal("1517.28"), petrol.annual_cost_eur)
        self.assertEqual(Decimal("1179.00"), petrol.co2_cost_low_eur)
        self.assertEqual(Decimal("2800.13"), petrol.co2_cost_medium_eur)
        self.assertEqual(Decimal("4323.00"), petrol.co2_cost_high_eur)

        # Golf eHybrid, 1,1 l + 12,1 kWh/100 km, Rohwert 25,4 g/km
        phev = calculate_energy_costs(
            ConsumptionValues(
                combined_kwh_100km=Decimal("12.1"), combined_l_100km=Decimal("1.1"),
                co2_g_km=Decimal("25.4"), co2_class="B", electric_range_km=143,
                discharged_l_100km=Decimal("5.0"), co2_class_discharged="C",
                fuel_type="PETROL",
            ), config)
        self.assertEqual(Decimal("870.38"), phev.annual_cost_eur)
        self.assertEqual(Decimal("534.38"), phev.co2_cost_medium_eur)


class _Distance:
    annual_distance_km = 15000


if __name__ == "__main__":
    unittest.main()
