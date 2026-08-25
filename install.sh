#!/usr/bin/env bash
#
# Richtet den KAHLE EnVKV Agent auf dem Server ein.
#
# Aufruf im entpackten Paketverzeichnis:
#     sudo bash install.sh
#
# Das Skript ist wiederholbar. Es überschreibt niemals eine vorhandene .env und
# löscht niemals das Datenvolumen mit den Auditsätzen.

set -euo pipefail

TARGET="${ENVKV_TARGET:-/opt/envkv}"
SERVICE_USER="${ENVKV_SERVICE_USER:-root}"
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Das Wagenrücklaufzeichen wird zur Laufzeit erzeugt und steht nirgends als
# Rohbyte im Quelltext. Eine spätere Zeilenendennormalisierung kann es dadurch
# nicht zerstören.
CR="$(printf '\r')"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32mOK\033[0m  %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m   %s\n' "$*"; }
die()  { printf '\n\033[31mFEHLER: %s\033[0m\n\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- Vorprüfungen
say "Voraussetzungen prüfen"

[ "$(id -u)" -eq 0 ] || die "Bitte mit sudo ausführen: sudo bash install.sh"

command -v docker >/dev/null 2>&1 || die "Docker ist nicht installiert."
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo '?')"

docker compose version >/dev/null 2>&1 \
  || die "Das Docker-Compose-Plugin fehlt. Erwartet wird 'docker compose', nicht 'docker-compose'."
ok "Compose $(docker compose version --short 2>/dev/null || echo '?')"

[ -f "$PACKAGE_DIR/compose.yaml" ] || die "compose.yaml fehlt. Wird das Skript im entpackten Paket ausgeführt?"
[ -f "$PACKAGE_DIR/Dockerfile" ]   || die "Dockerfile fehlt. Wird das Skript im entpackten Paket ausgeführt?"

if [ -f "$PACKAGE_DIR/VERSION" ]; then
  version_line="$(grep -E '^Commit:' "$PACKAGE_DIR/VERSION" | head -1 || true)"
  case "$version_line" in
    *'Format:'*) warn "Paketstand unbekannt (nicht über deploy/build-package.ps1 erzeugt)" ;;
    "")          warn "Paketstand unbekannt" ;;
    *)           ok "Paketstand: $version_line" ;;
  esac
fi

# ------------------------------------------------------------ Dateien ablegen
say "Anwendungsdateien nach $TARGET übertragen"

FIRST_INSTALL=no
[ -d "$TARGET" ] || FIRST_INSTALL=yes
mkdir -p "$TARGET"

# Diese Bäume werden vollständig ersetzt, damit entfallene Dateien einer
# früheren Version nicht zurückbleiben. Alles andere in $TARGET bleibt
# unangetastet, insbesondere .env.
for tree in backend spike tools docs extension; do
  rm -rf "${TARGET:?}/$tree"
  if [ -d "$PACKAGE_DIR/$tree" ]; then
    cp -a "$PACKAGE_DIR/$tree" "$TARGET/"
  fi
done

for file in Dockerfile compose.yaml .dockerignore .env.example README.md install.sh VERSION; do
  if [ -f "$PACKAGE_DIR/$file" ]; then
    cp -a "$PACKAGE_DIR/$file" "$TARGET/"
  fi
done

ok "Dateien abgelegt"

# ------------------------------------------------------------------ .env
say "Konfiguration prüfen"

ENV_FILE="$TARGET/.env"

if [ ! -f "$ENV_FILE" ]; then
  cp "$TARGET/.env.example" "$ENV_FILE"

  # Der Zugriffsschlüssel wird erzeugt, nicht ausgedacht.
  GENERATED_KEY="$(openssl rand -base64 48 | tr -d '\n=' | tr '+/' '-_')"
  sed -i "s|^EXTENSION_API_KEY=.*|EXTENSION_API_KEY=${GENERATED_KEY}|" "$ENV_FILE"

  chmod 600 "$ENV_FILE"
  chown "$SERVICE_USER":"$SERVICE_USER" "$ENV_FILE" 2>/dev/null || true

  cat <<MELDUNG

  Eine neue $ENV_FILE wurde angelegt und ein Zugriffsschlüssel erzeugt.

  Jetzt fehlen noch die Zugangsdaten von Volkswagen. Bitte eintragen:

      sudo nano $ENV_FILE

  Auszufüllen sind:
      VW_CLIENT_ID=...
      VW_CLIENT_SECRET=...

  Danach dieses Skript erneut ausführen:

      sudo bash install.sh

  Den erzeugten Zugriffsschlüssel für die Edge-Erweiterung zeigt später:

      sudo grep '^EXTENSION_API_KEY=' $ENV_FILE

MELDUNG
  exit 0
fi

chmod 600 "$ENV_FILE"
ok ".env vorhanden, Rechte auf 600 gesetzt"

# Eine unter Windows bearbeitete .env enthält CRLF. Docker übernähme das
# Wagenrücklaufzeichen als Teil des Wertes; die Zugangsdaten wären damit still
# falsch und der Fehler später schwer zu finden.
if LC_ALL=C grep -q "$CR" "$ENV_FILE"; then
  env_tmp="$(mktemp)"
  tr -d "$CR" < "$ENV_FILE" > "$env_tmp"
  cat "$env_tmp" > "$ENV_FILE"
  rm -f "$env_tmp"
  chmod 600 "$ENV_FILE"
  warn "Windows-Zeilenenden in .env gefunden und entfernt"
fi

# Pflichtwerte prüfen, ohne sie auszugeben.
missing=""
for key in VW_CLIENT_ID VW_CLIENT_SECRET EXTENSION_API_KEY; do
  value="$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d "$CR" || true)"
  if [ -z "$value" ]; then
    missing="$missing $key"
  fi
done
if [ -n "$missing" ]; then
  die "In $ENV_FILE fehlen Werte für:$missing
Bitte mit 'sudo nano $ENV_FILE' ergänzen und das Skript erneut ausführen."
fi
ok "Alle Pflichtwerte gesetzt"

# ------------------------------------------------------------------ Start
say "Container bauen und starten"

cd "$TARGET"
docker compose up --build -d

say "Auf Betriebsbereitschaft warten"

for _ in $(seq 1 60); do
  state="$(docker inspect -f '{{.State.Health.Status}}' envkv-api 2>/dev/null || echo unbekannt)"
  if [ "$state" = "healthy" ]; then
    break
  fi
  sleep 3
done

state="$(docker inspect -f '{{.State.Health.Status}}' envkv-api 2>/dev/null || echo unbekannt)"
if [ "$state" != "healthy" ]; then
  warn "Zustand: $state"
  echo
  docker compose logs --tail 40 envkv-api || true
  die "Der Dienst ist nicht betriebsbereit geworden. Die Ausgabe oben nennt den Grund."
fi
ok "Zustand: healthy"

# ------------------------------------------------------------------ Prüfungen
say "Funktionsprüfung"

health="$(curl -fsS http://127.0.0.1:8088/api/v1/health || true)"
if [ "$health" != '{"status":"ok"}' ]; then
  die "Unerwartete Antwort der Statusabfrage: $health"
fi
ok "Statusabfrage: $health"

code="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  http://127.0.0.1:8088/api/v1/vehicle/compliance \
  -H 'Content-Type: application/json' --data '{"vehicle_name":"ID.5"}')"
if [ "$code" != "401" ]; then
  die "Der Zugriffsschutz greift nicht. Erwartet 401, erhalten $code."
fi
ok "Ohne Zugriffsschlüssel abgewiesen (401)"

# ------------------------------------------------------------------ Abschluss
say "Fertig"

cat <<ABSCHLUSS
    Der Dienst läuft und ist ausschließlich lokal erreichbar
    (127.0.0.1:8088). Das ist beabsichtigt.

    Noch offen: die Route im gemeinsamen Caddy. Folgenden Block in die
    Caddyfile aufnehmen und Caddy neu laden:

        envkv.kahle.de {
            encode zstd gzip
            reverse_proxy 127.0.0.1:8088
        }

    Danach von außen prüfen:

        curl -s https://envkv.kahle.de/api/v1/health

    Zugriffsschlüssel für die Edge-Erweiterung auslesen:

        sudo grep '^EXTENSION_API_KEY=' $ENV_FILE

    Nützliche Befehle:

        cd $TARGET
        docker compose ps
        docker compose logs -f envkv-api
        docker compose restart envkv-api

ABSCHLUSS

if [ "$FIRST_INSTALL" = "yes" ]; then
  warn "Erstinstallation: Bitte die fachliche Abnahme nach docs/deployment.md durchführen,"
  warn "bevor die Erweiterung an Mitarbeitende verteilt wird."
fi
