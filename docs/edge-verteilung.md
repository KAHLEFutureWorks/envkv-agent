# Verteilung der Erweiterung über den eigenen Server

Die Erweiterung wird nicht über den Microsoft-Store bezogen, sondern von
`envkv.kahle.de` selbst ausgeliefert. Mitarbeitende installieren nichts und
tragen nichts ein: Edge holt sich das Paket über eine Geräterichtlinie, und
Adresse und Zugriffsschlüssel kommen ebenfalls aus einer Richtlinie.

## Voraussetzung: Art der Geräteanbindung

Microsoft erlaubt selbst gehostete Erweiterungen nur auf Geräten, die einer
Active-Directory-Domäne angehören — reine Entra-Geräte sind ausgeschlossen,
solange sie nicht zusätzlich hybrid eingebunden sind.

Prüfung auf einem Beispielgerät:

```
dsregcmd /status
```

Erforderlich ist `DomainJoined : YES`. Für KAHLE ist das am 26.08.2026 auf dem
geprüften Gerät der Fall (`AzureAdJoined: YES`, `DomainJoined: YES`, also
Hybrid Join). Wird künftig auf reines Entra-Join umgestellt, funktioniert
dieser Weg nicht mehr und die Erweiterung muss unsichtbar über den
Edge-Add-ons-Store veröffentlicht werden.

## Der Signaturschlüssel

Beim ersten Packen entsteht eine Datei `kahle-envkv-agent.pem`. Aus ihrem
öffentlichen Teil leitet Edge die Kennung der Erweiterung ab.

**Diese Datei ist nicht ersetzbar.** Geht sie verloren, bekommt die Erweiterung
eine neue Kennung; jede Richtlinie muss dann neu geschrieben und die alte
Erweiterung auf allen Geräten entfernt werden. Sie gehört in den Passwortmanager
der IT und niemals in dieses Projektverzeichnis — `.gitignore` schließt `*.pem`
und `*.crx` aus, damit ein Versehen nicht in die Versionsverwaltung gelangt.

## Ablauf einer Auslieferung

1. Versionsnummer in `extension/manifest.json` erhöhen. Edge aktualisiert nur
   bei einer höheren Nummer.
2. Paket bauen und signieren:

   ```
   .\deploy\build-extension.ps1 -PemPath C:\sicher\kahle-envkv-agent.pem
   ```

   Ergebnis: `deploy\dist\releases\kahle-envkv-agent-<version>.crx`
3. Paket auf den Server legen (die genauen Befehle nennt das Skript am Ende).
   Ziel ist `/opt/envkv/releases/`, Rechte `644`.
4. Prüfen:

   ```
   curl -s https://envkv.kahle.de/ext/updates.xml
   ```

   Die Antwort muss die neue Versionsnummer enthalten.

Ältere Pakete dürfen liegen bleiben; ausgeliefert wird immer die höchste
Fassung. Der Aktualisierungshinweis wird bei jeder Anfrage neu erzeugt.

## Die beiden offenen Adressen

`/ext/updates.xml` und `/ext/*.crx` sind bewusst ohne Zugriffsschlüssel
erreichbar — Edge kennt beim Abholen keinen. Ausgeliefert wird ausschließlich
das signierte Paket; es enthält keine Zugangsdaten. Die Verbindungsdaten
entstehen erst auf dem Gerät aus der Richtlinie.

Solange `ENVKV_EXTENSION_ID` in der `.env` leer ist, antworten beide Adressen
mit 404. Die Selbstauslieferung ist also standardmäßig abgeschaltet.

Das Paket wird mit `Content-Type: application/x-chrome-extension` ausgeliefert.
Ohne genau diesen Typ bricht Edge die Installation ab.

## Richtlinien in Intune

### 1. Erweiterung erzwingen

Einstellungskatalog → *Microsoft Edge* → **Configure extension management
settings** (`ExtensionSettings`). Wert:

```json
{
  "KENNUNG_DER_ERWEITERUNG": {
    "installation_mode": "force_installed",
    "update_url": "https://envkv.kahle.de/ext/updates.xml",
    "override_update_url": true,
    "toolbar_pin": "force_pinned"
  }
}
```

`override_update_url` ist erforderlich. Ohne diesen Eintrag versucht Edge,
Aktualisierungen beim Store zu suchen, und findet dort nichts.

### 2. Verbindung vorgeben

Die Erweiterung liest Adresse und Schlüssel aus
`HKLM\SOFTWARE\Policies\Microsoft\Edge\3rdparty\extensions\<Kennung>\policy`.
Dafür `deploy\intune-verbindung.ps1` ausfüllen und in Intune als Plattformskript
im **Systemkontext** (nicht als angemeldeter Benutzer) hinterlegen.

Danach zeigt die Einstellungsseite der Erweiterung die Werte schreibgeschützt
mit dem Hinweis, dass die IT sie vorgibt.

## Was Mitarbeitende merken

Nichts. Die Erweiterung erscheint nach der nächsten Richtlinienaktualisierung
in der Symbolleiste und ist sofort einsatzbereit.

## Grenze des Verfahrens

Der Zugriffsschlüssel ist auf jedem Gerät in der Registry lesbar. Er
unterscheidet nicht zwischen Personen und lässt sich nur zentral wechseln.
Für den Pilotbetrieb ist das vertretbar; für den Dauerbetrieb bleibt die
Anmeldung über Entra ID der vorgesehene nächste Schritt.
