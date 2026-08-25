"""Diagnose: Warum lässt sich für eine Modellfamilie keine Spanne bilden?

Der Aufruf erfolgt im selben Fenster, in dem VW_CLIENT_ID und VW_CLIENT_SECRET
gesetzt sind. Es werden keine Zugangsdaten ausgegeben.

    python -m tools.diagnose_model_range "Golf Energy"
"""

from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path

from backend.app.config import Settings
from backend.app.services.volkswagen.client import OkapiClient, OkapiError
from backend.app.services.volkswagen.provider import (
    ManualReviewRequired,
    VolkswagenProvider,
    _catalog_model_display,
    _consumption_for,
    _is_excluded_n1_candidate,
    _powertrain_for,
    _text,
)
from backend.app.storage import SQLiteStore


def main() -> int:
    query = " ".join(sys.argv[1:]) or "Golf"
    settings = Settings.from_env()
    if not settings.vw_client_id or not settings.vw_client_secret:
        print("VW_CLIENT_ID und VW_CLIENT_SECRET sind in diesem Fenster nicht gesetzt.")
        return 2

    with tempfile.TemporaryDirectory() as folder:
        provider = VolkswagenProvider(
            OkapiClient(settings.vw_client_id, settings.vw_client_secret),
            SQLiteStore(Path(folder) / "diagnose.sqlite3"),
            market=settings.vw_market,
        )
        brand_definition, brand_id, selected_models, vehicle_query = provider._resolve_family(query)
        print(f"Eingabe:        {query!r}")
        print(f"Suchtext:       {vehicle_query!r}")
        print(f"Marke:          {brand_definition['display']}")
        print("Modellfamilie:  " + ", ".join(
            _catalog_model_display(_text(m, "description", "name") or "") for m in selected_models
        ))

        model_types = provider._family_types(selected_models)
        print(f"Typen gesamt:   {len(model_types)}\n")

        reasons: Counter[str] = Counter()
        ok = 0
        excluded = 0
        lines: list[str] = []
        for _model_item, entry in model_types:
            description = _text(entry, "description", "name") or "(ohne Bezeichnung)"
            type_id = _text(entry, "id")
            modelyear_code = _text(entry, "modelyear_code")
            packages = entry.get("extensions") or []
            marker = f"[{len(packages)} Paket(e)]" if packages else "[paketlos]"
            if _is_excluded_n1_candidate(brand_definition["code"], description):
                excluded += 1
                lines.append(f"  UEBERGANGEN {marker} {description}")
                continue
            if type_id is None or modelyear_code is None:
                reasons["Technische Zuordnungsdaten fehlen"] += 1
                lines.append(f"  FEHLER      {marker} {description} -> Zuordnungsdaten fehlen")
                continue
            try:
                values, _w, _c, _k = provider._verified_wltp(brand_id, type_id, modelyear_code)
                powertrain = _powertrain_for(values)
                _consumption_for(values)
            except (ManualReviewRequired, OkapiError) as error:
                reasons[str(error)] += 1
                lines.append(f"  FEHLER      {marker} {description} -> {error}")
                continue
            ok += 1
            lines.append(f"  OK          {marker} {description} -> {powertrain.value}")

        print("\n".join(lines))
        print(f"\nErgebnis: {ok} bestätigt, {len(reasons.total() * [0])} nicht bestätigt, {excluded} übergangen")
        if reasons:
            print("\nGründe nach Häufigkeit:")
            for reason, count in reasons.most_common():
                print(f"  {count:3d}x  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
