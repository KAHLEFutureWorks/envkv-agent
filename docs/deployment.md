# Inbetriebnahme auf dem KAHLE-Server

Stand: 25. August 2026

Dieses Dokument beschreibt den vollständigen Weg vom heutigen Entwicklungsstand
zum Pilotbetrieb unter `https://envkv.kahle.de` und was danach folgt. Es ist als
Ablaufplan gedacht: jeder Schritt nennt die Prüfung, mit der er als erledigt
gilt.

## 0. Was vor dem ersten Deployment geklärt sein muss

| Punkt | Warum er blockiert |
|---|---|
| Versionsverwaltung | Das Projekt liegt derzeit **nicht** in Git. Ohne Repository gibt es keinen nachvollziehbaren Stand, kein Rollback und keine Zuordnung „welcher Code erzeugte diesen Auditsatz". Für einen Dienst, dessen Ausgabe rechtlich verbindlich ist, ist das die wichtigste offene Voraussetzung. |
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

## 2. Voraussetzungen auf dem Server

- Docker mit Compose-Plugin
- Der DNS-Eintrag `envkv.kahle.de` zeigt auf den Server
- Ausgehender Zugriff auf `https://api.productdata.volkswagenag.com`
- Schreibrechte im Verzeichnis des neuen Stacks

## 3. Zugriffsschlüssel erzeugen

Der Schlüssel wird nie von Hand ausgedacht und nie in das Repository gelegt:

```bash
openssl rand -base64 48
```

Der Wert wird in `.env` als `EXTENSION_API_KEY` eingetragen und zusätzlich im
Passwortmanager der IT hinterlegt, weil ihn später auch die Intune-Richtlinie
benötigt.

## 4. Stack einrichten

```bash
mkdir -p /opt/envkv && cd /opt/envkv
```

Projektstand dorthin bringen, `.env.example` nach `.env` kopieren und ausfüllen.
Pflichtwerte sind `VW_CLIENT_ID`, `VW_CLIENT_SECRET` und `EXTENSION_API_KEY`;
ohne sie startet der Stack absichtlich nicht. `.env` gehört ausschließlich dem
Dienstkonto:

```bash
chmod 600 .env
```

Starten:

```bash
docker compose up --build -d
```

Prüfung — der Dienst antwortet nur lokal, das ist beabsichtigt:

```bash
curl -s http://127.0.0.1:8088/api/v1/health
```

Erwartet: `{"status":"ok"}`. Zusätzlich muss `docker compose ps` den Zustand
`healthy` zeigen; der Healthcheck ist im Abbild hinterlegt.

## 5. Caddy-Route ergänzen

In der bestehenden Caddyfile:

```
envkv.kahle.de {
	encode zstd gzip
	reverse_proxy 127.0.0.1:8088
}
```

Caddy neu laden, dann von außen prüfen:

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

```bash
cd /opt/envkv
docker compose up --build -d
docker compose ps
curl -s https://envkv.kahle.de/api/v1/health
```

Rückweg: den vorherigen Stand erneut ausrollen und den Stack neu bauen. Das
Datenvolumen bleibt dabei unberührt. Ohne Versionsverwaltung ist dieser Rückweg
derzeit nur manuell möglich — siehe Abschnitt 0.

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
