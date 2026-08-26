"""Prueft die Auslieferung der Erweiterung als selbst gehostetes Edge-Add-in."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.extension_release import (
    latest_release, render_updates_xml, resolve_package,
)

KENNUNG = "abcdefghijklmnopabcdefghijklmnop"


def paket(verzeichnis: Path, version: str, inhalt: bytes = b"Cr24") -> Path:
    datei = verzeichnis / f"kahle-envkv-agent-{version}.crx"
    datei.write_bytes(inhalt)
    return datei


def einstellungen(tmp_path: Path, *, kennung: str = KENNUNG, verzeichnis: Path | None = None) -> Settings:
    return Settings(
        extension_api_key="geheim",
        database_path=tmp_path / "envkv.sqlite3",
        extension_release_dir=verzeichnis,
        extension_id=kennung,
        extension_base_url="https://envkv.kahle.de",
    )


def test_hoechste_fassung_gewinnt(tmp_path: Path) -> None:
    paket(tmp_path, "0.9.0")
    paket(tmp_path, "0.10.0")
    paket(tmp_path, "0.2.0")
    # Ein Zeichenvergleich haette hier "0.9.0" gewaehlt.
    assert latest_release(tmp_path).version == "0.10.0"


def test_leeres_verzeichnis_ohne_paket(tmp_path: Path) -> None:
    assert latest_release(tmp_path) is None


def test_fremde_dateien_werden_uebergangen(tmp_path: Path) -> None:
    (tmp_path / "notizen.txt").write_text("egal", encoding="utf-8")
    (tmp_path / "fremd.crx").write_bytes(b"Cr24")
    assert latest_release(tmp_path) is None


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd",
        r"..\..\windows\win.ini",
        "kahle-envkv-agent-0.1.0.crx/../../../etc/shadow",
        "/etc/passwd",
        "kahle-envkv-agent-.crx",
        "beliebig.crx",
    ],
)
def test_pfadausbruch_wird_abgewiesen(tmp_path: Path, name: str) -> None:
    paket(tmp_path, "0.1.0")
    assert resolve_package(tmp_path, name) is None


def test_aktualisierungshinweis_nennt_kennung_fassung_und_adresse(tmp_path: Path) -> None:
    paket(tmp_path, "1.2.3")
    xml = render_updates_xml(KENNUNG, "https://envkv.kahle.de/", latest_release(tmp_path))
    assert "protocol='2.0'" in xml
    assert f'appid="{KENNUNG}"' in xml
    assert 'version="1.2.3"' in xml
    assert 'codebase="https://envkv.kahle.de/ext/kahle-envkv-agent-1.2.3.crx"' in xml


def test_ungueltige_kennung_wird_abgelehnt(tmp_path: Path) -> None:
    paket(tmp_path, "1.0.0")
    with pytest.raises(ValueError):
        render_updates_xml("nicht-erlaubt", "https://envkv.kahle.de", latest_release(tmp_path))


def test_auslieferung_ohne_zugriffsschluessel_erreichbar(tmp_path: Path) -> None:
    # Edge kennt beim Abholen keinen Schluessel. Waere hier ein 401 noetig,
    # koennte die Erweiterung nie installiert werden.
    verzeichnis = tmp_path / "releases"
    verzeichnis.mkdir()
    paket(verzeichnis, "0.1.0", b"Cr24\x00\x00\x00")
    client = TestClient(create_app(einstellungen(tmp_path, verzeichnis=verzeichnis)))

    hinweis = client.get("/ext/updates.xml")
    assert hinweis.status_code == 200
    assert hinweis.headers["content-type"].startswith("application/xml")
    assert "kahle-envkv-agent-0.1.0.crx" in hinweis.text

    paket_antwort = client.get("/ext/kahle-envkv-agent-0.1.0.crx")
    assert paket_antwort.status_code == 200
    # Ohne genau diesen Inhaltstyp verweigert Edge die Installation.
    assert paket_antwort.headers["content-type"] == "application/x-chrome-extension"
    assert paket_antwort.content == b"Cr24\x00\x00\x00"


def test_ohne_kennung_bleibt_die_auslieferung_abgeschaltet(tmp_path: Path) -> None:
    verzeichnis = tmp_path / "releases"
    verzeichnis.mkdir()
    paket(verzeichnis, "0.1.0")
    client = TestClient(create_app(einstellungen(tmp_path, kennung="", verzeichnis=verzeichnis)))
    assert client.get("/ext/updates.xml").status_code == 404
    assert client.get("/ext/kahle-envkv-agent-0.1.0.crx").status_code == 404


def test_ohne_verzeichnis_bleibt_die_auslieferung_abgeschaltet(tmp_path: Path) -> None:
    client = TestClient(create_app(einstellungen(tmp_path, verzeichnis=None)))
    assert client.get("/ext/updates.xml").status_code == 404


def test_unbekanntes_paket_ist_kein_treffer(tmp_path: Path) -> None:
    verzeichnis = tmp_path / "releases"
    verzeichnis.mkdir()
    paket(verzeichnis, "0.1.0")
    client = TestClient(create_app(einstellungen(tmp_path, verzeichnis=verzeichnis)))
    assert client.get("/ext/kahle-envkv-agent-9.9.9.crx").status_code == 404


def test_fachrouten_bleiben_geschuetzt(tmp_path: Path) -> None:
    # Die offenen /ext-Adressen duerfen den Zugriffsschutz nicht aufweichen.
    verzeichnis = tmp_path / "releases"
    verzeichnis.mkdir()
    client = TestClient(create_app(einstellungen(tmp_path, verzeichnis=verzeichnis)))
    antwort = client.post("/api/v1/vehicle/compliance", json={"vehicle_name": "ID.5"})
    assert antwort.status_code == 401
