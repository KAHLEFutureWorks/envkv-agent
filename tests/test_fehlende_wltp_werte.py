"""Prueft die Unterscheidung zwischen Stoerung und fehlenden Verbrauchswerten.

Beim Grand California meldete der Dienst "aktuell nicht erreichbar", obwohl
Volkswagen geantwortet hatte - es gibt fuer dieses Fahrzeug schlicht keine
WLTP-Werte. Diese beiden Faelle verlangen verschiedene Antworten: Der eine
laedt zum spaeteren Versuch ein, der andere ist dauerhaft.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from spike.okapi import OkapiError
from spike.okapi_probe import MissingWltpData, extract_verified_wltp

KOPF = {"X-API-Key": "geheim"}


def antwort(**datensatz):
    return {"data": [{"wltp_metadata": {"status": 200}, "wltp_value": [datensatz]}]}


def test_fehlende_werte_sind_kein_uebertragungsfehler() -> None:
    with pytest.raises(MissingWltpData):
        extract_verified_wltp(antwort(energy_efficiency={"class_wltp": "D"}))


def test_fehlende_co2_klasse_ist_kein_uebertragungsfehler() -> None:
    with pytest.raises(MissingWltpData):
        extract_verified_wltp(antwort(interpolations=[], energy_efficiency={}))


def test_abgewiesener_datensatz_ist_kein_uebertragungsfehler() -> None:
    with pytest.raises(MissingWltpData):
        extract_verified_wltp({"data": [{"wltp_metadata": {"status": 404}, "wltp_value": []}]})


def test_unlesbare_antwort_bleibt_ein_uebertragungsfehler() -> None:
    # Hier hat Volkswagen nicht sinnvoll geantwortet - ein spaeterer Versuch
    # kann durchaus gelingen.
    with pytest.raises(OkapiError) as fehler:
        extract_verified_wltp({"kein": "datenfeld"})
    assert not isinstance(fehler.value, MissingWltpData)


class OhneWerte:
    def create(self, *args, **kwargs):
        raise MissingWltpData("Im WLTP-Datensatz von Volkswagen fehlt die CO₂-Klasse.")

    create_model_range = create


class Gestoert:
    def create(self, *args, **kwargs):
        raise OkapiError("Volkswagen OKAPI ist nicht erreichbar.")

    create_model_range = create


def client(tmp_path: Path, dienst) -> TestClient:
    app = create_app(Settings(extension_api_key="geheim", database_path=tmp_path / "db.sqlite3"))
    app.state.compliance_service = dienst
    return TestClient(app, raise_server_exceptions=False)


def test_ohne_werte_wird_nicht_als_stoerung_gemeldet(tmp_path: Path) -> None:
    a = client(tmp_path, OhneWerte()).post(
        "/api/v1/vehicle/compliance", headers=KOPF,
        json={"vehicle_name": "Der Grand California Dune 600"},
    )
    assert a.status_code == 422
    meldung = a.json()["detail"]
    assert "keine WLTP-Verbrauchswerte" in meldung
    assert "erreichbar" not in meldung


def test_echte_stoerung_bleibt_eine_stoerung(tmp_path: Path) -> None:
    a = client(tmp_path, Gestoert()).post(
        "/api/v1/vehicle/compliance", headers=KOPF, json={"vehicle_name": "ID.5 Pro"},
    )
    assert a.status_code == 503
    assert "erreichbar" in a.json()["detail"]


def test_auch_die_modellspanne_unterscheidet(tmp_path: Path) -> None:
    a = client(tmp_path, OhneWerte()).post(
        "/api/v1/vehicle/model-range", headers=KOPF, json={"vehicle_name": "Grand California"},
    )
    assert a.status_code == 422
