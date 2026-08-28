"""Prueft, in welchem Katalog eine Fahrzeugbezeichnung gesucht wird.

Volkswagen fuehrt Pkw und Nutzfahrzeuge in zwei getrennten OKAPI-Katalogen.
Im Alltag heissen aber beide "VW". Landet eine Anfrage im falschen Katalog,
meldet der Dienst "nicht eindeutig gefunden", obwohl das Fahrzeug existiert.
"""
from __future__ import annotations

import pytest

from backend.app.services.volkswagen.provider import (
    VehicleNotFound, _brand_for_input,
)

VN = "Volkswagen Nutzfahrzeuge"
VW = "Volkswagen"


@pytest.mark.parametrize(
    ("eingabe", "erwartete_marke"),
    [
        # Die Schreibweise aus dem Fahrzeugbestand: Kuerzel, Artikel, Modell.
        ("VW Der Grand California 680 Motor: 2,0 l TDI EURO VI-e SCR", VN),
        ("VW Der Grand California 600 Motor: 2,0 l TDI EURO VI-e SCR", VN),
        ("Der Grand California 680 Motor: 2,0 l TDI EURO VI-e SCR", VN),
        ("Grand California 600", VN),
        # Dasselbe Muster bei den uebrigen Nutzfahrzeug-Familien.
        ("VW Multivan 2,0 l TDI 110 kW", VN),
        ("VW Der Caddy 1,5 l TSI", VN),
        ("VW California Ocean", VN),
        ("VW ID. Buzz Pro", VN),
        ("Volkswagen Transporter Kombi", VN),
        ("VW Caravelle 2,0 l TDI", VN),
        # Ausdrueckliche Marke bleibt unveraendert gueltig.
        ("Volkswagen Nutzfahrzeuge Der Grand California 680", VN),
        # Pkw duerfen dadurch nicht in den Nutzfahrzeug-Katalog rutschen.
        ("VW Golf 1,5 l TSI 110 kW", VW),
        ("Volkswagen T-Cross R-Line", VW),
        ("VW ID.5 Pro", VW),
        ("Der Tiguan 2,0 l TDI", VW),
    ],
)
def test_katalog_wird_richtig_gewaehlt(eingabe: str, erwartete_marke: str) -> None:
    marke, _ = _brand_for_input(eingabe)
    assert marke["display"] == erwartete_marke


def test_grand_california_geht_nicht_an_california(  ) -> None:
    # "California" ist ein Praefix von "Grand California". Stuende der kuerzere
    # Name zuerst, bliebe der Grand California dauerhaft unauffindbar.
    _, suchtext = _brand_for_input("Der Grand California 680")
    assert suchtext.startswith("grand california")


@pytest.mark.parametrize(
    ("eingabe", "erwartete_marke"),
    [("SEAT Leon", "SEAT"), ("CUPRA Leon", "CUPRA"), ("Skoda Octavia", "Škoda"), ("Audi Q4 e-tron", "Audi")],
)
def test_uebrige_konzernmarken_unveraendert(eingabe: str, erwartete_marke: str) -> None:
    marke, _ = _brand_for_input(eingabe)
    assert marke["display"] == erwartete_marke


def test_geteilte_modellnamen_verlangen_weiterhin_die_marke() -> None:
    with pytest.raises(VehicleNotFound, match="SEAT oder CUPRA"):
        _brand_for_input("Leon 1,5 TSI")


def test_unbekannte_marke_wird_weiterhin_abgewiesen() -> None:
    with pytest.raises(VehicleNotFound, match="Fahrzeugmarke"):
        _brand_for_input("Renault Clio 1,0 TCe")
