# Inbetriebnahme auf dem KAHLE-Server

Stand: 25. August 2026

Dieses Dokument beschreibt den vollständigen Weg vom heutigen Entwicklungsstand
zum Pilotbetrieb unter `https://envkv.kahle.de` und was danach folgt. Es ist als
Ablaufplan gedacht: jeder Schritt nennt die Prüfung, mit der er als erledigt
gilt.

## 0. Was vor dem ersten Deployment geklärt sein muss

| Punkt | Warum er blockiert |
|---|---|
| Visuelle Freigabe Anlage 1 | Die Rechtsmatrix stuft die Prüfung des Musters gegen das amtliche Original als kritisch ein. Sie ist noch nicht erfolgt. Bis dahin sollte das Datenblatt intern verwendet, aber nicht als „amtliches Datenblatt" bezeichnet werden. |
| Zugriffsmodell | Der Pilot verwendet einen gemeinsamen Zugriffsschlüssel. Das ist bewusst als Übergang gedacht und muss vor einer Ausweitung durch Entra ID ersetzt werden. |

## 1. Zielbild

```
Edge-Erweiterung (Side Panel)
        │  HTTPS + X-API-Key
        ▼
Caddy (bestehend, gemeinsam)         envkv.kahle.de
        │  reverse_proxy 127.0.0.1:8088
        ▼
Docker-Stack "envkv"                 eigener Stack, eigenes Volume
        │
        ▼
Volkswagen OKAPI                     ausgehend, OAuth
```

Der bestehende KAHLE-Vinci-Stack bleibt unverändert. Im gemeinsamen Caddy kommt
ausschließlich eine zusätzliche Route hinzu.

### Trennung von den übrigen Projekten

Der Stack ist so geschnitten, dass er sich mit keinem anderen Projekt auf dem
Server etwas teilt:

| Merkmal | Wert | Wirkung |
|---|---|---|
| Compose-Projekt | `envkv` | eigener Namensraum, keine Kollision mit anderen Stacks |
| Netz | `envkv` | eigenes Docker-Netz, keine Sicht auf andere Container |
| Volume | `envkv-data` | eigene Daten, von keinem anderen Dienst erreichbar |
| Port | `127.0.0.1:8088` | von außen nicht erreichbar, nur über Caddy |
| Benutzer | `envkv` | kein root im Container |
| Dateisystem | schreibgeschützt | nur `/app/data` und ein 32 MB großes `/tmp` sind beschreibbar |
| Rechte | `cap_drop: ALL`, `no-new-privileges` | keine zusätzlichen Kernel-Rechte |
| Grenzen | 1 CPU, 512 MB | kann anderen Projekten keine Ressourcen entziehen |

Nachgewiesen mit einem Probelauf: Der Dienst startet `healthy`, schreibt
Auditsätze und Cache in das Volume, erzeugt PDFs, und ein Schreibversuch in das
Abbild wird abgewiesen.

## 2. Voraussetzungen auf dem Server

- Docker mit Compose-Plugin (`docker compose version`)
- ein Konto mit `sudo`-Rechten; `/opt` gehört root, deshalb laufen die
  Installationsschritte über `sudo`
- der DNS-Eintrag `envkv.kahle.de` zeigt auf den Server
- ausgehender Zugriff auf `https://api.productdata.volkswagenag.com`
- die OKAPI-Zugangsdaten von Volkswagen liegen vor

## 3. Paket auf dem Arbeitsplatz bauen

Das Paket enthält exakt den Stand eines Commits. Der Arbeitsbaum muss sauber
sein, sonst bricht das Skript ab — sonst entstünde ein Paket, das keinem
nachvollziehbaren Stand entspricht.

```powershell
cd C:\Projekte\kahle-envkv-agent
.\deploy\build-package.ps1
```

Das Skript legt `deploy\dist\envkv-agent-<Datum>-<Commit>.tar.gz` an, prüft die
Zeilenenden von `install.sh` und gibt die SHA256-Prüfsumme aus. Es nimmt
ausschließlich versionierte Dateien auf; `.env`, Auditdaten und lokale
Umgebungen können dadurch nicht in das Paket geraten.

## 4. Paket übertragen

```powershell
scp -i "$env:USERPROFILE\.ssh\kahle-vinci-admin" -o IdentitiesOnly=yes `
  "deploy\dist\envkv-agent-<Datum>-<Commit>.tar.gz" `
  joltmanns@152.53.158.166:/tmp/envkv-agent-<Datum>-<Commit>.tar.gz
```

Auf dem Server die Prüfsumme vergleichen, entpacken und installieren:

```bash
cd /tmp
sha256sum envkv-agent-<Datum>-<Commit>.tar.gz
tar -xzf envkv-agent-<Datum>-<Commit>.tar.gz
cd envkv-agent-<Datum>-<Commit>
sudo bash install.sh
```

### Was install.sh tut

Das Skript ist wiederholbar und darf jederzeit erneut laufen:

1. prüft Docker und das Compose-Plugin
2. legt die Anwendungsdateien nach `/opt/envkv` (die Bäume `backend`, `spike`,
   `tools`, `docs` und `extension` werden dabei vollständig ersetzt, damit keine
   Dateien einer früheren Version zurückbleiben)
3. legt beim **ersten** Lauf `/opt/envkv/.env` an, erzeugt darin einen
   Zugriffsschlüssel, setzt die Rechte auf 600 — und **hält an**, bis die
   Volkswagen-Zugangsdaten eingetragen sind
4. entfernt Windows-Zeilenenden aus der `.env`, weil Docker sie sonst still in
   die Zugangsdaten übernähme
5. baut das Abbild und startet den Stack
6. wartet auf `healthy` und prüft Statusabfrage sowie Zugriffsschutz

Eine vorhandene `.env` und das Datenvolumen mit den Auditsätzen werden **nie**
überschrieben.

### Zugangsdaten eintragen

Nach dem ersten Lauf:

```bash
sudo nano /opt/envkv/.env
```

Auszufüllen sind `VW_CLIENT_ID` und `VW_CLIENT_SECRET`. Der
`EXTENSION_API_KEY` wurde bereits erzeugt. Speichern mit `Strg+O`, `Enter`,
schließen mit `Strg+X`. Danach:

```bash
cd /tmp/envkv-agent-<Datum>-<Commit>
sudo bash install.sh
```

Den erzeugten Zugriffsschlüssel später auslesen:

```bash
sudo grep '^EXTENSION_API_KEY=' /opt/envkv/.env
```

## 5. Caddy-Route ergänzen

Caddy läuft bei KAHLE selbst als Container im Netz `stack_appnet` und spricht
die übrigen Dienste über ihren Containernamen an. `127.0.0.1` zeigte aus dem
Caddy-Container heraus auf Caddy selbst und liefe ins Leere. Der EnVKV-Dienst
hängt deshalb zusätzlich in diesem Netz; die Portbindung bleibt davon unberührt
auf `127.0.0.1` beschränkt.

Voraussetzung: Der DNS-Eintrag muss stehen, sonst kann Caddy kein Zertifikat
ausstellen lassen.

```bash
getent hosts envkv.kahle.de
```

Dann folgenden Block an die Caddyfile anhängen:

```
envkv.kahle.de {
	encode zstd gzip
	reverse_proxy envkv-api:8088
}
```

Vor dem Neuladen prüfen, ob Caddy den Dienst überhaupt erreicht:

```bash
sudo docker run --rm --network stack_appnet curlimages/curl -s http://envkv-api:8088/api/v1/health
```

### Caddy neu starten

Zwei Besonderheiten der KAHLE-Umgebung:

- Die globale Konfiguration enthält `admin off`. Damit ist die
  Admin-Schnittstelle abgeschaltet und `caddy reload` funktioniert **nicht** —
  der Befehl spricht genau diese Schnittstelle an.
- `docker compose restart caddy` scheitert im Vinci-Stack, weil dessen
  Umgebungsdatei `.env.production` heißt und von Compose nicht automatisch
  gelesen wird. Compose bricht dann schon beim Auflösen der Platzhalter ab;
  angefasst wird dabei nichts.

Der verlässliche Weg ist deshalb der direkte Neustart des Containers. Er nimmt
die bestehende Containerkonfiguration unverändert mit und liest die eingebundene
Caddyfile neu ein:

```bash
sudo docker restart caddy
```

Das unterbricht für wenige Sekunden **alle** Seiten hinter diesem Caddy, nicht
nur den EnVKV-Dienst.

Danach von außen prüfen:

```bash
curl -s https://envkv.kahle.de/api/v1/health
```

Der Compliance-Endpunkt muss ohne Schlüssel abweisen:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://envkv.kahle.de/api/v1/vehicle/compliance
```

Erwartet: `401`.

## 6. Fachliche Abnahme vor der Freigabe an Mitarbeitende

Für jede Antriebsart mindestens ein Referenzfahrzeug prüfen und die Ausgabe
gegen das Label des Herstellers stellen:

| Antrieb | Referenz | Zu prüfen |
|---|---|---|
| BEV | ID.5 Pure | Verbrauch, CO₂-Klasse, Reichweite, Energiekosten, Steuerbefreiung |
| Benzin | T-Cross 1.0 TSI | Verbrauch, CO₂ ganzzahlig, Energie- und CO₂-Kosten, Kfz-Steuer |
| Diesel | Karoq TDI | wie Benzin |
| NOVC-HEV | T-Roc Mildhybrid | wird wie Verbrenner behandelt |
| PHEV | Golf eHybrid | beide CO₂-Klassen, EAER, beide Fahrphasengruppen |
| Modellspanne | Golf | Min/Max je Antriebsart, Alles-oder-nichts |

Ergänzend die Sperren nachweisen: ein Nutzfahrzeug ohne M1-Freigabe darf keinen
Angebotshinweis erzeugen, eine Cargo-Ausführung muss vollständig abgewiesen
werden.

## 7. Erweiterung verteilen

Für den Pilot genügt das entpackte Verzeichnis `extension/dist`. Für den
Regelbetrieb wird die Erweiterung über Intune verteilt und über Managed Storage
vorkonfiguriert, damit niemand Adresse und Schlüssel eintippen muss:

```json
{
  "apiUrl": { "Value": "https://envkv.kahle.de" },
  "apiKey": { "Value": "<Wert aus EXTENSION_API_KEY>" }
}
```

Die Erweiterung liest zuerst `chrome.storage.managed`; die Richtlinienwerte
überschreiben lokale Eingaben. Die Einstellungsseite akzeptiert im Betrieb
ausschließlich HTTPS-Adressen.

## 8. Sicherung

Die SQLite-Datei ist der Nachweis, welcher Text wann aus welchen Herstellerdaten
entstanden ist. Sie gehört in die Sicherung:

```bash
docker compose exec -T envkv-api \
  python -c "import sqlite3,sys; c=sqlite3.connect('/app/data/envkv.sqlite3'); [sys.stdout.buffer.write(l) for l in c.iterdump()]" \
  > /var/backups/envkv-$(date +%F).sql
```

Ein reines Kopieren der Datei im laufenden Betrieb ist nicht zulässig, weil dabei
ein inkonsistenter Stand entstehen kann. Die Aufbewahrung der Auditsätze richtet
sich nach `AUDIT_RETENTION_DAYS`; der Dienst bereinigt Cache und Audit einmal
täglich selbsttätig.

## 9. Aktualisierung und Rückweg

Eine Aktualisierung ist derselbe Weg wie die Erstinstallation: neues Paket
bauen, übertragen, entpacken, `sudo bash install.sh`. Die `.env` bleibt
erhalten, das Datenvolumen ebenfalls.

Rückweg auf einen früheren Stand: das Paket des gewünschten Commits erneut
übertragen und installieren. Welcher Stand gerade läuft, zeigt:

```bash
cat /opt/envkv/VERSION
```

Das Datenvolumen `envkv-data` bleibt bei allen Aktualisierungen unberührt;
Auditsätze gehen nicht verloren. Ein `docker compose down -v` würde das Volume
löschen und ist im Betrieb deshalb zu vermeiden.

## 10. Wiederkehrende Aufgaben

| Wann | Aufgabe |
|---|---|
| jährlich nach dem 30. Juni | Neues Preisprofil aus der BMWE-Veröffentlichung ergänzen, Gültigkeit ab 1. Juli. Ohne Nachtrag stoppt die Angebotserstellung nach Ablauf des letzten Profils. |
| laufend | Offene M1-Freigaben für Volkswagen Nutzfahrzeuge abarbeiten: `python -m backend.app.vehicle_class_admin --list-pending` |
| bei Störungen der Modellspanne | `python -m tools.diagnose_model_range '<Modell>'` im Container ausführen |
| bei Personalwechsel | Zugriffsschlüssel erneuern und Intune-Richtlinie nachziehen |

## 11. Was danach ansteht

1. **Entra ID statt gemeinsamem Schlüssel.** Der Pilotschlüssel ist auf einem
   verwalteten Endgerät auslesbar und kein Benutzerlogin. Das Zielbild ist in
   `authentication-and-compliance.md` beschrieben.
2. **Einbettung in die Angebotsseiten.** Der Hinweis nach Anlage 1 muss bei der
   Fahrzeugbeschreibung sichtbar sein. Der einbettbare Ausschnitt liefert das
   Werkzeug; die Umsetzung auf den Seiten braucht eine eigene verantwortliche
   Person.
3. **PDF-Ausgabe vereinheitlichen.** Sie wird derzeit getrennt im Hochformat
   gezeichnet und bildet den aktuellen Aufbau nicht ab.
4. **Visuelle Konformitätsprüfung** des Anlage-1-Musters abschließen.
