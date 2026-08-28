"""Prueft, dass der tatsaechliche Grund eines OKAPI-Fehlers im Protokoll landet.

Nach aussen bleibt es bei einer Sammelmeldung. Ohne Protokolleintrag waere
hinterher nicht zu unterscheiden, ob Volkswagen abgewiesen hat oder die Antwort
unbrauchbar war - genau diese Unterscheidung fehlte beim Grand California.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from spike.okapi import OkapiError


class Dienst:
    """Steht fuer den Fachdienst und scheitert wie OKAPI im Ernstfall."""

    def create(self, *args, **kwargs):
        raise OkapiError("Volkswagen OKAPI antwortet mit HTTP 429.")

    create_model_range = create


def client_mit_fehler(tmp_path: Path) -> TestClient:
    app = create_app(Settings(extension_api_key="geheim", database_path=tmp_path / "db.sqlite3"))
    app.state.compliance_service = Dienst()
    return TestClient(app, raise_server_exceptions=False)


def test_grund_steht_im_protokoll(tmp_path: Path, caplog) -> None:
    client = client_mit_fehler(tmp_path)
    with caplog.at_level(logging.WARNING, logger="envkv"):
        antwort = client.post(
            "/api/v1/vehicle/compliance",
            headers={"X-API-Key": "geheim"},
            json={"vehicle_name": "Grand California Dune 600"},
        )
    assert antwort.status_code == 503
    protokoll = caplog.text
    assert "HTTP 429" in protokoll
    assert "Grand California Dune 600" in protokoll


def test_nach_aussen_bleibt_es_bei_der_sammelmeldung(tmp_path: Path) -> None:
    # Der Grund gehoert ins Protokoll, nicht in die Antwort an die Erweiterung.
    client = client_mit_fehler(tmp_path)
    antwort = client.post(
        "/api/v1/vehicle/compliance",
        headers={"X-API-Key": "geheim"},
        json={"vehicle_name": "Grand California Dune 600"},
    )
    assert "429" not in antwort.text
    assert antwort.json()["detail"] == "Die Volkswagen-Produktdaten sind aktuell nicht erreichbar."


def test_auch_die_modellspanne_protokolliert(tmp_path: Path, caplog) -> None:
    client = client_mit_fehler(tmp_path)
    with caplog.at_level(logging.WARNING, logger="envkv"):
        antwort = client.post(
            "/api/v1/vehicle/model-range",
            headers={"X-API-Key": "geheim"},
            json={"vehicle_name": "Grand California"},
        )
    assert antwort.status_code == 503
    assert "HTTP 429" in caplog.text
