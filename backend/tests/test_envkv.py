from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from backend.app.domain.envkv import (
    ConsumptionValues,
    ComplianceProfileIncomplete,
    EnergyCostConfiguration,
    SourceReference,
    UsageContext,
    VehicleIdentity,
    VerifiedVehicleData,
    calculate_energy_costs,
    calculate_vehicle_tax,
    electric_vehicle_tax_exemption,
    build_data_sheet,
    PowertrainType,
    render_compliance_text,
)
from backend.app.services.data_sheet import (
    ROOT_CLASS,
    render_data_sheet_html,
    render_data_sheet_pdf,
    render_data_sheet_snippet,
)


class EnVKVCalculationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.consumption = ConsumptionValues(
            combined_kwh_100km=Decimal("15.5"),
            co2_g_km=Decimal("0"),
            co2_class="A",
            electric_range_km=446,
            phase_kwh_100km={
                "low": Decimal("11.1"), "medium": Decimal("12.2"),
                "high": Decimal("14.1"), "extra_high": Decimal("20.4"),
            },
        )
        self.cost_config = EnergyCostConfiguration(
            electricity_price_eur_kwh=Decimal("0.321"),
            electricity_reference_year=2025,
            annual_distance_km=15_000,
        )

    def test_energy_cost_is_calculated_with_decimal_half_up(self) -> None:
        costs = calculate_energy_costs(self.consumption, self.cost_config)
        self.assertEqual(Decimal("746.33"), costs.annual_cost_eur)

    def test_vehicle_tax_uses_current_progressive_formula(self) -> None:
        self.assertEqual(Decimal("95.20"), calculate_vehicle_tax(PowertrainType.PETROL, 999, Decimal("131")))
        self.assertEqual(Decimal("266.00"), calculate_vehicle_tax(PowertrainType.DIESEL, 1598, Decimal("147")))
        self.assertEqual(Decimal("0.00"), calculate_vehicle_tax(PowertrainType.BATTERY_ELECTRIC, None, Decimal("0")))

    def test_compliance_text_contains_verified_values_and_basis(self) -> None:
        vehicle = VehicleIdentity(
            brand="Volkswagen",
            model="ID.5",
            trim="Pure",
            power_kw=140,
            power_ps=190,
            battery_kwh=58,
            transmission="1-Gang-Automatik",
            model_id="model-id",
            model_year=2027,
            type_id="type-id",
            type_code="TYPE:E392JM",
        )
        verified = VerifiedVehicleData(
            vehicle=vehicle,
            consumption=self.consumption,
            source=SourceReference(
                provider="Volkswagen OKAPI",
                model_id="model-id",
                model_year=2027,
                type_id="type-id",
                type_code="TYPE:E392JM",
                retrieved_at="2026-08-20T12:15:36+02:00",
                data_version="3",
            ),
            raw_wltp={},
        )
        text = render_compliance_text(verified, calculate_energy_costs(self.consumption, self.cost_config))
        self.assertIn("15,5", text)
        self.assertIn("Energieverbrauch kombiniert: 15,5 kWh/100 km", text)
        self.assertIn("CO₂-Emissionen kombiniert: 0 g/km", text)
        self.assertIn("CO₂-Klasse: A", text)
        self.assertNotIn("Energiekosten", text)
        self.assertNotIn("Innenstadt", text)

    def test_detailed_online_offer_is_blocked_until_all_required_values_exist(self) -> None:
        vehicle = VehicleIdentity(
            brand="Volkswagen", model="ID.5", trim="Pure", power_kw=140, power_ps=190,
            battery_kwh=58, transmission="1-Gang-Automatik", model_id="model-id",
            model_year=2027, type_id="type-id", type_code="TYPE:E392JM",
        )
        verified = VerifiedVehicleData(
            vehicle=vehicle,
            consumption=self.consumption,
            source=SourceReference(
                provider="Volkswagen OKAPI", model_id="model-id", model_year=2027,
                type_id="type-id", type_code="TYPE:E392JM",
                retrieved_at="2026-08-20T12:15:36+02:00",
            ),
            raw_wltp={},
        )
        with self.assertRaises(ComplianceProfileIncomplete):
            render_compliance_text(
                verified,
                calculate_energy_costs(self.consumption, self.cost_config),
                UsageContext.ONLINE_OFFER,
            )

    def test_combustion_text_and_sheet_show_verified_wltp_phases_as_fuel_values(self) -> None:
        consumption = ConsumptionValues(
            combined_kwh_100km=None, combined_l_100km=Decimal("5.8"),
            co2_g_km=Decimal("131.1"), co2_class="D", electric_range_km=None,
            fuel_type="PETROL", phase_l_100km={
                "low": Decimal("7.2"), "medium": Decimal("5.7"),
                "high": Decimal("5.1"), "extra_high": Decimal("6.2"),
            },
        )
        vehicle = VehicleIdentity(
            brand="Volkswagen", model="T-Cross", trim="Style", power_kw=85,
            power_ps=116, battery_kwh=None, transmission="7-Gang-DSG",
            model_id="model", model_year=2027, type_id="type", type_code="TYPE:TCROSS",
            engine_displacement_cc=999,
        )
        verified = VerifiedVehicleData(
            vehicle=vehicle, consumption=consumption,
            source=SourceReference("Volkswagen OKAPI", "model", 2027, "type", "TYPE:TCROSS", "2026-08-20"),
            raw_wltp={}, powertrain=PowertrainType.PETROL,
            annual_vehicle_tax_eur=Decimal("95.20"),
        )
        costs = calculate_energy_costs(consumption, self.cost_config)
        text = render_compliance_text(verified, costs)
        self.assertNotIn("Innenstadt", text)
        self.assertNotIn("Autobahn", text)
        html = render_data_sheet_html(build_data_sheet(verified, costs, "2026-08-20"))
        self.assertIn("Kraftstoffverbrauch kombiniert", html)
        self.assertIn("Innenstadt", html)
        self.assertIn("7,2 l/100 km", html)
        self.assertNotIn("<b>Stromverbrauch kombiniert</b>", html)

    def test_verified_electric_online_offer_contains_tax_and_co2_costs(self) -> None:
        vehicle = VehicleIdentity(
            brand="Volkswagen", model="ID.5", trim="Pure", power_kw=140, power_ps=190,
            battery_kwh=58, transmission="1-Gang-Automatik", model_id="model-id",
            model_year=2027, type_id="type-id", type_code="TYPE:E392JM",
        )
        verified = VerifiedVehicleData(
            vehicle=vehicle,
            consumption=self.consumption,
            source=SourceReference(
                provider="Volkswagen OKAPI", model_id="model-id", model_year=2027,
                type_id="type-id", type_code="TYPE:E392JM",
                retrieved_at="2026-08-20T12:15:36+02:00",
            ),
            raw_wltp={},
            annual_vehicle_tax_eur=Decimal("0"),
        )
        text = render_compliance_text(
            verified,
            calculate_energy_costs(self.consumption, self.cost_config),
            UsageContext.ONLINE_OFFER,
        )
        self.assertNotIn("Kraftfahrzeugsteuer", text)
        self.assertNotIn("Mögliche CO₂-Kosten", text)
        sheet = build_data_sheet(
            verified, calculate_energy_costs(self.consumption, self.cost_config), "2026-08-20"
        )
        self.assertEqual("pkw_envkv_notice", sheet["document_type"])
        self.assertEqual("temporarily_exempt", sheet["vehicle_tax"]["status"])
        self.assertEqual("2027-2036", sheet["co2_cost_period"])
        self.assertEqual(["A", "B", "C", "D", "E", "F", "G"], sheet["co2_classes"]["scale"])
        self.assertIn("Drucken oder als PDF speichern", render_data_sheet_html(sheet))
        self.assertTrue(render_data_sheet_pdf(sheet).startswith(b"%PDF"))

    def test_embeddable_snippet_is_self_contained_and_matches_the_printed_sheet(self) -> None:
        consumption = ConsumptionValues(
            combined_kwh_100km=None, combined_l_100km=Decimal("5.8"),
            co2_g_km=Decimal("131.1"), co2_class="D", electric_range_km=None,
            fuel_type="PETROL", phase_l_100km={
                "low": Decimal("7.2"), "medium": Decimal("5.7"),
                "high": Decimal("5.1"), "extra_high": Decimal("6.2"),
            },
        )
        verified = VerifiedVehicleData(
            vehicle=VehicleIdentity(
                brand="Volkswagen", model="T-Cross", trim="Style", power_kw=85,
                power_ps=116, battery_kwh=None, transmission="7-Gang-DSG",
                model_id="model", model_year=2027, type_id="type", type_code="TYPE:TCROSS",
                engine_displacement_cc=999,
            ),
            consumption=consumption,
            source=SourceReference("Volkswagen OKAPI", "model", 2027, "type", "TYPE:TCROSS", "2026-08-20"),
            raw_wltp={}, powertrain=PowertrainType.PETROL,
            annual_vehicle_tax_eur=Decimal("95.20"),
        )
        costs = calculate_energy_costs(consumption, self.cost_config)
        sheet = build_data_sheet(verified, costs, "2026-08-20")
        snippet = render_data_sheet_snippet(sheet)

        # Der Ausschnitt darf die einbettende Seite weder ersetzen noch nachladen.
        for forbidden in ("<!doctype", "<html", "<head", "<body", "<script", "@page", "http://", "https://"):
            self.assertNotIn(forbidden, snippet.lower(), f"{forbidden} gehört nicht in den Ausschnitt")
        # Jede einzelne Stilregel bleibt auf die eigene Wurzelklasse begrenzt.
        css = snippet.split("<style>")[1].split("</style>")[0]
        rules = [rule for rule in css.split("}") if rule.strip()]
        self.assertGreater(len(rules), 10)
        for rule in rules:
            for selector in rule.split("{")[0].split(","):
                self.assertTrue(
                    selector.strip().startswith(f".{ROOT_CLASS}"),
                    f"Selektor {selector.strip()!r} ist nicht auf den Ausschnitt begrenzt",
                )
        self.assertTrue(snippet.lstrip().startswith("<!-- KAHLE EnVKV"))
        self.assertIn(f'<div class="{ROOT_CLASS}">', snippet)

        # Ausschnitt und A4-Seite tragen denselben Pflichtinhalt.
        page = render_data_sheet_html(sheet)
        for required in (
            "Information über den Energieverbrauch",
            "Kraftstoffverbrauch kombiniert",
            "Innenstadt", "7,2 l/100 km",
            "www.dat.de/co2/",
            "Kraftfahrzeugsteuer",
        ):
            self.assertIn(required, snippet)
            self.assertIn(required, page)
        # Nur die Seite darf die Druckschaltfläche enthalten.
        self.assertIn("Drucken oder als PDF speichern", page)
        self.assertNotIn("Drucken oder als PDF speichern", snippet)

    def test_electric_tax_exemption_end_is_derived_from_the_registration_date(self) -> None:
        # § 3d KraftStG: zehn Jahre ab Erstzulassung, längstens bis zum 31.12.2035.
        self.assertEqual(
            "2034-05-31", electric_vehicle_tax_exemption(date(2024, 6, 1))["exemption_end"]
        )
        # Ab einer Erstzulassung im Jahr 2026 greift durchgehend die gesetzliche Höchstgrenze.
        self.assertEqual(
            "2035-12-31", electric_vehicle_tax_exemption(date(2026, 8, 21))["exemption_end"]
        )
        self.assertEqual(
            "2035-12-31", electric_vehicle_tax_exemption(date(2030, 12, 31))["exemption_end"]
        )
        # Der 29. Februar besitzt im Zieljahr keine Entsprechung und darf nicht scheitern.
        self.assertEqual(
            "2035-12-31", electric_vehicle_tax_exemption(date(2028, 2, 29))["exemption_end"]
        )

    def test_electric_offer_is_blocked_when_no_exemption_can_apply(self) -> None:
        with self.assertRaises(ComplianceProfileIncomplete):
            electric_vehicle_tax_exemption(date(2031, 1, 1))

    def test_data_sheet_names_the_exemption_end_and_its_legal_basis(self) -> None:
        verified = VerifiedVehicleData(
            vehicle=VehicleIdentity(
                brand="Volkswagen", model="ID.5", trim="Pure", power_kw=140, power_ps=190,
                battery_kwh=58, transmission="1-Gang-Automatik", model_id="model-id",
                model_year=2027, type_id="type-id", type_code="TYPE:E392JM",
            ),
            consumption=self.consumption,
            source=SourceReference(
                provider="Volkswagen OKAPI", model_id="model-id", model_year=2027,
                type_id="type-id", type_code="TYPE:E392JM",
                retrieved_at="2026-08-20T12:15:36+02:00",
            ),
            raw_wltp={},
            annual_vehicle_tax_eur=Decimal("0"),
        )
        sheet = build_data_sheet(
            verified, calculate_energy_costs(self.consumption, self.cost_config), "2026-08-20"
        )
        tax = sheet["vehicle_tax"]
        self.assertEqual("§ 3d KraftStG", tax["legal_basis"])
        self.assertEqual("2035-12-31", tax["exemption_end"])
        self.assertTrue(tax["first_registration_is_assumed"])
        # Anlage 1 verlangt den Text zusammen mit einer Fußnote zum Ende der Befristung.
        self.assertEqual("Befristet steuerbefreit", tax["text"])
        # Die Steuerfußnote trägt den Verweis 3) und steht deshalb an dritter Stelle.
        self.assertIn("31.12.2035", sheet["footnotes"][2])
        self.assertIn("<sup>3)</sup>", render_data_sheet_html(sheet))
        self.assertIn("Befristet steuerbefreit", render_data_sheet_html(sheet))
        self.assertIn("31.12.2035", render_data_sheet_html(sheet))

    def test_label_marks_the_class_row_and_uses_two_columns_for_a_plug_in_hybrid(self) -> None:
        consumption = ConsumptionValues(
            combined_kwh_100km=Decimal("12.1"), combined_l_100km=Decimal("1.1"),
            co2_g_km=Decimal("25.4"), co2_class="B", electric_range_km=143,
            discharged_l_100km=Decimal("5.0"), co2_class_discharged="C", fuel_type="PETROL",
            pure_electric_kwh_100km=Decimal("14.9"),
            phase_kwh_100km={"low": Decimal("11.8"), "medium": Decimal("12.2"),
                             "high": Decimal("13.7"), "extra_high": Decimal("18.9")},
            phase_l_100km={"low": Decimal("5.6"), "medium": Decimal("4.6"),
                           "high": Decimal("4.3"), "extra_high": Decimal("5.5")},
        )
        verified = VerifiedVehicleData(
            vehicle=VehicleIdentity(
                brand="Volkswagen", model="Golf", trim="eHybrid", power_kw=110, power_ps=150,
                battery_kwh=Decimal("19.7"), transmission="6-Gang-DSG", model_id="m",
                model_year=2027, type_id="t", type_code="TYPE:G", engine_displacement_cc=1498,
            ),
            consumption=consumption,
            source=SourceReference("Volkswagen OKAPI", "m", 2027, "t", "TYPE:G", "2026-08-21"),
            raw_wltp={}, powertrain=PowertrainType.PLUG_IN_HYBRID,
            annual_vehicle_tax_eur=Decimal("30.00"), tax_data_verified=True,
        )
        sheet = build_data_sheet(verified, calculate_energy_costs(consumption, self.cost_config), "2026-08-21")
        html = render_data_sheet_html(sheet)

        # Zwei Klassenspalten mit Überschriften und Trennlinie.
        self.assertIn("gewichtet kombiniert", html)
        self.assertIn("bei entladener Batterie", html)
        self.assertIn("scale-head divided", html)
        self.assertIn("scale-cell divided", html)
        # Genau zwei Marken, je eine je Spalte.
        self.assertEqual(2, html.count('class="badge"'))
        # Sieben Pfeile und sieben Rasterzeilen je Spalte.
        self.assertEqual(7, html.count('class="arrow"'))
        self.assertEqual(14, html.count(chr(34) + "scale-cell"))

    def test_label_shows_integer_co2_and_omits_the_duplicated_cost_rows(self) -> None:
        consumption = ConsumptionValues(
            combined_kwh_100km=None, combined_l_100km=Decimal("5.8"),
            co2_g_km=Decimal("131.1"), co2_class="D", electric_range_km=None,
            fuel_type="PETROL",
            phase_l_100km={"low": Decimal("7.1"), "medium": Decimal("5.5"),
                           "high": Decimal("5.0"), "extra_high": Decimal("6.1")},
        )
        verified = VerifiedVehicleData(
            vehicle=VehicleIdentity(
                brand="Volkswagen", model="T-Cross", trim="Style", power_kw=85, power_ps=116,
                battery_kwh=None, transmission="7-Gang-DSG", model_id="m", model_year=2027,
                type_id="t", type_code="TYPE:T", engine_displacement_cc=999,
            ),
            consumption=consumption,
            source=SourceReference("Volkswagen OKAPI", "m", 2027, "t", "TYPE:T", "2026-08-21"),
            raw_wltp={}, powertrain=PowertrainType.PETROL,
            annual_vehicle_tax_eur=Decimal("95.20"), tax_data_verified=True,
        )
        sheet = build_data_sheet(verified, calculate_energy_costs(consumption, self.cost_config), "2026-08-21")
        html = render_data_sheet_html(sheet)

        # CO2 wird ganzzahlig ausgewiesen, wie im Label des Herstellers.
        self.assertEqual(131.0, sheet["declared_co2_g_km"])
        self.assertIn("131 g/km", html)
        self.assertNotIn("131,1 g/km", html)
        # Der zweite Kasten enthaelt keine leeren Zeilen und keine Kostenwiederholung.
        table = html.split('<div class="box"><table>')[1].split("</table>")[0]
        self.assertNotIn("entf", table)
        self.assertNotIn("Energiekosten", table)
        self.assertNotIn("Kraftfahrzeugsteuer", table)
        self.assertIn("<sup>1)</sup>", table)
        # Format und Fussnotenverweise wie im Herstellerlabel.
        self.assertIn("A4 landscape", html)
        self.assertIn("<sup>2)</sup>", html)
        self.assertIn("EUR/l Jahresdurchschnitt", html)

    def test_label_states_the_electricity_price_in_cents(self) -> None:
        sheet = build_data_sheet(
            VerifiedVehicleData(
                vehicle=VehicleIdentity(
                    brand="Volkswagen", model="ID.5", trim="Pure", power_kw=140, power_ps=190,
                    battery_kwh=Decimal("58"), transmission="1-Gang-Automatik", model_id="m",
                    model_year=2027, type_id="t", type_code="TYPE:E",
                ),
                consumption=self.consumption,
                source=SourceReference("Volkswagen OKAPI", "m", 2027, "t", "TYPE:E", "2026-08-21"),
                raw_wltp={}, annual_vehicle_tax_eur=Decimal("0"),
            ),
            calculate_energy_costs(self.consumption, self.cost_config), "2026-08-21",
        )
        html = render_data_sheet_html(sheet)
        # 0,321 EUR/kWh entspricht 32,10 ct/kWh.
        self.assertIn("32,10 ct/kWh", html)
        self.assertNotIn("0,321 EUR/kWh", html)


if __name__ == "__main__":
    unittest.main()
