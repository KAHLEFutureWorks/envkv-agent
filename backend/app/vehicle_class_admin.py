from __future__ import annotations

import argparse
import json

from backend.app.config import Settings
from backend.app.storage import SQLiteStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verwaltet die nachvollziehbare M1-/N1-Freigabe technischer OKAPI-Typen."
    )
    parser.add_argument("--list-pending", action="store_true", help="zeigt noch nicht klassifizierte Typen")
    parser.add_argument(
        "--type-id", "--approval-key", dest="type_id",
        help="OKAPI-Basistyp (bei Altdaten technische Typ-ID)",
    )
    parser.add_argument("--class", dest="vehicle_class", choices=("M1", "N1"), help="bestätigte Fahrzeugklasse")
    parser.add_argument("--source", help="nachvollziehbare Quelle, z. B. CoC oder Herstellerunterlage")
    parser.add_argument("--approved-by", help="Name oder Benutzerkennung der freigebenden Person")
    args = parser.parse_args()

    store = SQLiteStore(Settings.from_env().database_path)
    if args.list_pending:
        pending = [
            item for item in store.list_pending_vehicle_classes()
            if item.get("brand") == "Volkswagen Nutzfahrzeuge"
        ]
        print(json.dumps(pending, ensure_ascii=False, indent=2))
        return 0
    if not all((args.type_id, args.vehicle_class, args.source, args.approved_by)):
        parser.error("Für eine Freigabe sind --type-id, --class, --source und --approved-by erforderlich.")
    store.approve_vehicle_class(args.type_id, args.vehicle_class, args.source, args.approved_by)
    print(f"Fahrzeugklasse {args.vehicle_class} wurde für den technischen Typ gespeichert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
