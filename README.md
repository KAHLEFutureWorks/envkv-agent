# KAHLE EnVKV Agent

Der KAHLE EnVKV Agent liefert nachvollziehbare Verbrauchs- und EnVKV-Texte für
KAHLE-Mitarbeitende. Er ist ausdrücklich kein Generator oder Schätzer von
Verbrauchsdaten: Die KI hilft später nur bei der Identifikation eines Fahrzeugs.
Regulatorische Werte werden ausschließlich aus der verifizierten
Herstellerquelle Volkswagen OKAPI übernommen.

## Aktueller Stand: Phase 2, funktionsfähiger Backend-Dienst

Der technische OKAPI-Vorabtest bleibt als reproduzierbarer Spike erhalten. Die
Backend mit FastAPI, Fachlogik, SQLite-Cache und Audit ist angelegt. Der
Compliance-Endpunkt verwendet den verifizierten OKAPI-Ablauf für Volkswagen,
Audi, SEAT, CUPRA, Škoda und Volkswagen Nutzfahrzeuge und akzeptiert für die
automatische Einzelausgabe ausschließlich genau einen paketlosen, eindeutig
baubaren Fahrzeugtyp. Für die Werbung mit einem ganzen Modell tritt daneben die
gesetzliche Variantenspanne. Die Edge-Extension, die antriebsabhängige Fachlogik
und die Anlage-1-Ausgabe als einbettbarer HTML-Ausschnitt, als Browseransicht und
als PDF sind umgesetzt. Noch ausstehend sind die produktive Serverbereitstellung
und ein optionales IONOS-Parsing.

Der Live-Nachweis wurde am 20.08.2026 für den ID.5 Pure, Typ `TYPE:E392JM`,
Modelljahr 2027 erfolgreich erbracht. OKAPI bestätigte eine eindeutig baubare
Konfiguration und lieferte 15,5 kWh/100 km, 0 g CO₂/km, CO₂-Klasse A sowie
446 km kombinierte Reichweite.

## Voraussetzungen

- Python 3.11 oder neuer
- von Volkswagen bereitgestellte OKAPI-Zugangsdaten
- Zugriff auf `https://api.productdata.volkswagenag.com`

Die Zugangsdaten werden ausschließlich als Prozessvariablen gesetzt. Sie werden
nicht aus einer Datei eingelesen, nicht geloggt und nicht in Ausgaben abgelegt.

```powershell
$env:VW_CLIENT_ID = '<von Volkswagen erhalten>'
$env:VW_CLIENT_SECRET = '<von Volkswagen erhalten>'
$env:VW_MARKET = 'DE'
python -m unittest discover -s tests -v
python -m spike.okapi_probe --model 'ID.5' --type-query 'Pure 140 kW'
```

Wenn genau ein paketloser Typkandidat vorhanden ist, kann der vollständige
Phase-1-Nachweis ausgeführt werden. Der Spike lädt zuerst die Basiskonfiguration
für Typ und Modelljahr, prüft `buildable` sowie `distinct` und ruft nur danach
WLTP ab:

```powershell
python -m spike.okapi_probe --model 'ID.5' --type-query 'Pure 140 kW' --fetch-wltp
```

Falls der zunächst angenommene Markt `DE` nicht freigeschaltet ist, zeigt
dieser Befehl die tatsächlich verfügbaren Marktkennungen. Zugangsdaten werden
nie ausgegeben:

```powershell
python -m spike.okapi_probe --list-countries
```

Bei einer abweichenden Markenstruktur kann der öffentliche Katalogausschnitt
ohne Zugangsdaten in der Ausgabe geprüft werden:

```powershell
python -m spike.okapi_probe --list-brands --market 'DE'
```

Das Live-Schema und konkrete Treffer der Volkswagen-Modellliste lassen sich
ebenfalls ohne Secrets prüfen:

```powershell
python -m spike.okapi_probe --list-models --model 'ID.5' --market 'DE'
```

Für die Typen eines gefundenen Modells steht dieselbe Diagnose zur Verfügung:

```powershell
python -m spike.okapi_probe --list-types --model 'ID.5' --type-query 'Pure' --market 'DE'
```

## Optional: WLTP mit einer vollständigen Konfiguration prüfen

OKAPI liefert WLTP-Daten erst für eine eindeutige und baubare Konfiguration.
Die Konfigurationsdatei enthält nur die von OKAPI erwarteten technischen IDs,
keine Zugangsdaten und keine Personenbezüge.

```json
{
  "brand_id": "<OKAPI-Brand-ID>",
  "model_id": "<OKAPI-Modell-ID>",
  "options": [{"id": "<OKAPI-Options-ID>"}]
}
```

```powershell
python -m spike.okapi_probe --model 'ID.5' --configuration .\id5-configuration.json
```

Der Befehl ruft zuerst `check` auf. Nur wenn `buildable` und `distinct` beide
`true` sind, folgt der WLTP-Abruf. Damit ist ausgeschlossen, dass der Spike eine
nicht eindeutige Konfiguration als Herstellerwert ausgibt.

## Phase 2: Backend

Das Backend liegt unter `backend/`. Es enthält bereits:

- `GET /api/v1/health`
- API-Key-Schutz für `POST /api/v1/vehicle/compliance`
- deterministische Energiekostenberechnung mit `Decimal`
- deutsche EnVKV-Textausgabe
- technischen 24-Stunden-Cache auf Basis kanonischer Konfigurationsdaten
- vollständige Audit-Persistenz in SQLite
- konfigurierbare Aufbewahrung und Bereinigung
- Live-Abruf über Volkswagen OKAPI mit sicherem Abbruch bei Mehrdeutigkeit
- automatische M1-Einstufung für die reinen Pkw-Kataloge der Konzernmarken
- auditierbare M1-/N1-Freigabe nur für Volkswagen Nutzfahrzeuge
- Steuerberechnung nur aus bestätigten technischen Order-/CoC-Feldern
- datierte amtliche Energie- und CO₂-Preisprofile (`BMWE-2025`, `BMWE-2026`)
  mit automatischem Wechsel zum 01.07. und sicherem Stopp bei Ablauf
- CO₂-Ausweisung in ganzen Gramm; Energie- und CO₂-Kosten stimmen damit auf den
  Cent mit den Labels von Volkswagen überein
- vollständige Anlage-1-Ausgabe als A4-Browseransicht im Querformat
- einbettbarer Anlage-1-Ausschnitt zum Einfügen bei der Fahrzeugbeschreibung
- gesetzliche Modellspanne über alle Varianten für Werbung und Social Media
- Steuerbefreiung für Elektrofahrzeuge hergeleitet aus § 3d KraftStG

### Modellspanne für die Werbung mit einem ganzen Modell

Ist die Eingabe nicht eindeutig, bietet die Erweiterung neben der Auswahl einer
konkreten Variante auch `POST /api/v1/vehicle/model-range` an. Der Dienst löst
dann jede Variante der Modellfamilie einzeln über OKAPI auf und gibt niedrigsten
und höchsten Wert sowie günstigste und ungünstigste CO₂-Klasse aus. Antriebsarten
werden dabei nie vermischt; je Antriebsart entsteht ein eigener Pflichtblock.
Lässt sich auch nur eine Variante nicht bestätigen, wird keine Spanne ausgegeben,
sondern die manuelle Prüfung mit Nennung der betroffenen Typen verlangt. Für
konkrete Online- und Leasingangebote ist die Spanne gesperrt.

### Einbettbarer Anlage-1-Hinweis

`POST /api/v1/vehicle/data-sheet-snippet.html` liefert den vollständigen Hinweis
als HTML-Ausschnitt ohne Seitenrahmen. Er bringt seine Gestaltung selbst mit,
lädt nichts nach, enthält keine Skripte und verändert die einbettende Seite
nicht. Anlage 4 Teil II Nummer 3 verlangt, dass der Hinweis bei der
Fahrzeugbeschreibung dargestellt wird; Druckansicht und PDF sind nur eine
Ergänzung.

Für Volkswagen Nutzfahrzeuge sind Verbrauchstexte in Werbung und Social Media
auch ohne M1-Freigabe möglich, wenn OKAPI das Fahrzeug eindeutig bestätigt.
Online- und Leasingangebote benötigen eine M1-Freigabe des Basistyps. Eindeutige
oder bestätigte N1-Ausführungen werden vollständig gesperrt.

Lokale Einrichtung:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s .\backend\tests -v
```

Lokaler Start:

```powershell
$env:EXTENSION_API_KEY = '<lokaler Testschlüssel>'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8088
```

Beispielaufruf in einem zweiten PowerShell-Fenster:

```powershell
$headers = @{ 'X-API-Key' = '<lokaler Testschlüssel>' }
$body = @{ vehicle_name = 'ID.5 Pure 140 kW (190 PS) 58 kWh 1-Gang-Automatik' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/v1/vehicle/compliance' -Headers $headers -ContentType 'application/json' -Body $body
```

## Diagnose der Modellspanne

Bildet der Dienst für eine Modellfamilie keine Spanne, nennt dieses Werkzeug für
jeden Typ das Ergebnis oder den Grund. Es wird im selben Fenster aufgerufen, in
dem die OKAPI-Zugangsdaten gesetzt sind, und gibt keine Zugangsdaten aus.

```powershell
python -m tools.diagnose_model_range 'Golf Energy'
```

## Docker

Der Dienst läuft als eigenständiger Stack mit eigenem Compose-Projekt, eigenem
Netz und eigenem Volume; er teilt sich mit anderen Projekten auf dem Server
nichts. Der Container läuft ohne root, mit schreibgeschütztem Dateisystem und
begrenzt auf 1 CPU und 512 MB.

Die Variablen aus `.env.example` in eine nicht versionierte `.env` übernehmen
und anschließend starten:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod 'http://127.0.0.1:8088/api/v1/health'
```

## Edge-Erweiterung

Die Side-Panel-Erweiterung liegt unter `extension/`. Sie enthält keine
Volkswagen- oder IONOS-Zugangsdaten. Für die lokale Entwicklung wird nur der
eigene Zugriffsschlüssel des EnVKV-Dienstes über die Einstellungsseite der
Erweiterung gespeichert.

```powershell
cd .\extension
npm install
npm run typecheck
npm run build
```

Danach in Edge `edge://extensions` öffnen, den Entwicklermodus aktivieren und
`extension/dist` über „Entpackte Erweiterung laden“ auswählen. Über
„Verbindung einrichten“ werden lokal `http://127.0.0.1:8088` und der Wert aus
`EXTENSION_API_KEY` hinterlegt. Für den Serverbetrieb akzeptiert die
Einstellungsseite ausschließlich HTTPS.

Bei einer späteren Intune-Verteilung können API-Adresse und Pilot-Schlüssel
über Managed Storage vorgegeben werden; Mitarbeitende müssen sie dann nicht
eingeben. Das Zielbild ohne gemeinsamen Browser-Schlüssel ist in
`docs/authentication-and-compliance.md` beschrieben und verwendet Microsoft
Entra ID mit kurzlebigen Tokens.

## Inbetriebnahme

Der Server erhält den Stand als Paket, nicht per `git clone`. Paket bauen:

```powershell
.\deployuild-package.ps1
```

Danach übertragen, auf dem Server entpacken und `sudo bash install.sh`
ausführen. Der vollständige Ablauf steht in `docs/deployment.md`:
Voraussetzungen, Zugangsdaten, Caddy-Route, fachliche Abnahme, Sicherung,
Rückweg und die wiederkehrenden Aufgaben.

Lokale Einrichtung inklusive Testabhängigkeiten:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .ackend
equirements-dev.txt
```

## Fachliche Begründung für Mitarbeitende

Warum in der Werbung nur der kombinierte Wert steht und keine Fahrphasen, und
warum dort auch beim Benziner „Energieverbrauch" steht: `docs/werbung-pflichtangaben.md`.

## Betriebsperspektive

Für die Produktivversion erhält der Service einen eigenen Docker-Stack
und eine eigene HTTPS-Subdomain. Der bestehende KAHLE-Vinci-Stack bleibt
unverändert; im gemeinsamen Caddy ist nur eine separate Route auf den neuen
Service erforderlich. `compose.yaml` bindet den Dienst ausschließlich an
`127.0.0.1:8088`; der öffentliche Zugriff soll später nur über HTTPS und Caddy
erfolgen.
