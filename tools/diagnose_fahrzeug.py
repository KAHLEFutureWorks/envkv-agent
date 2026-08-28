"""Diagnose: Warum scheitert genau dieses Fahrzeug?

Zeigt, an welcher Stelle der Abruf abbricht und mit welchem Grund. Der Aufruf
erfolgt dort, wo VW_CLIENT_ID und VW_CLIENT_SECRET gesetzt sind; die
Zugangsdaten werden nicht ausgegeben.

    python -m tools.diagnose_fahrzeug "Der Grand California Dune 600 Motor: ..."
"""

from __future__ import annotations

import sys
import traceback

from backend.app.config import Settings
from backend.app.services.volkswagen.client import OkapiClient, OkapiError
from backend.app.services.volkswagen.provider import (
    ManualReviewRequired, VehicleNotEligible, VehicleNotFound, VolkswagenProvider, _text,
)
from backend.app.storage import SQLiteStore


def main() -> int:
    query = " ".join(sys.argv[1:])
    if not query:
        print("Bitte die vollständige Fahrzeugbezeichnung angeben.")
        return 2

    settings = Settings.from_env()
    if not settings.vw_client_id or not settings.vw_client_secret:
        print("VW_CLIENT_ID und VW_CLIENT_SECRET sind hier nicht gesetzt.")
        return 2

    provider = VolkswagenProvider(
        OkapiClient(
            settings.vw_client_id, settings.vw_client_secret,
            max_retries=settings.okapi_max_retries,
            min_interval_seconds=settings.okapi_min_interval_seconds,
        ),
        SQLiteStore(settings.database_path),
        market=settings.vw_market,
        require_vehicle_class_approval=True,
    )

    print(f"Eingabe: {query}\n")
    try:
        marke, brand_id, modelle, rest = provider._resolve_family(query)
    except (VehicleNotFound, ManualReviewRequired, OkapiError) as fehler:
        print(f"Abbruch bei der Modellfamilie: {type(fehler).__name__}: {fehler}")
        return 1
    print(f"Marke:   {marke['display']}")
    print(f"Familie: {[_text(m, 'description', 'name') for m in modelle]}\n")

    try:
        daten = provider.retrieve(query)
    except VehicleNotEligible as fehler:
        print(f"Ausserhalb des Anwendungsbereichs: {fehler}")
        return 1
    except ManualReviewRequired as fehler:
        print(f"Manuelle Prüfung nötig: {fehler}")
        for kandidat in fehler.candidates:
            print(f"  - {kandidat}")
        return 1
    except VehicleNotFound as fehler:
        print(f"Nicht gefunden: {fehler}")
        return 1
    except OkapiError as fehler:
        # Genau dieser Fall wird nach aussen zu "aktuell nicht erreichbar".
        print(f"OKAPI-Fehler: {fehler}\n")
        traceback.print_exc()
        return 1

    print("Erfolgreich abgerufen:")
    print(f"  Antrieb:  {daten.powertrain.value}")
    print(f"  CO2:      {daten.consumption.co2_g_km} g/km, Klasse {daten.consumption.co2_class}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
