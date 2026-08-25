# Authentifizierung und EnVKV-Freigabemodell

## Extension-Konfiguration

Für lokale Entwicklung können API-Adresse und Zugriffsschlüssel über die
Einstellungsseite gespeichert werden. In einer per Intune verwalteten
Installation liest die Extension zuerst `chrome.storage.managed`. Die
Richtlinienwerte `apiUrl` und `apiKey` überschreiben lokale Einstellungen.
Mitarbeitende müssen dadurch nichts eintragen.

Ein gemeinsam verteilter API-Key ist nur für den internen Pilot vorgesehen.
Er ist kein Benutzerlogin und kann auf einem verwalteten Endgerät grundsätzlich
ausgelesen werden.

## Zielbild Microsoft Entra ID

Die finale Version soll den gemeinsamen API-Key durch Entra ID ersetzen:

1. Die Edge-Extension fordert über `chrome.identity` ein kurzlebiges Token für
   die EnVKV-API an.
2. Microsoft Entra stellt das Token nur angemeldeten KAHLE-Konten aus.
3. Das Backend validiert Signatur, Aussteller, Zielgruppe und Ablaufzeit.
4. Nur benötigte technische Auditdaten werden gespeichert; keine dauerhaften
   Zugangstoken und keine Volkswagen-Secrets gelangen in den Browser.
5. Intune installiert die Extension und verteilt nur öffentliche Konfiguration
   wie API-Adresse, Tenant-ID und Client-ID.

## Fachliche Freigabe

Die automatische Ausgabe wird aus der Kombination von Antriebsart und
Verwendungszweck bestimmt. Werbung und Social Media erhalten ausschließlich
den Pflichtblock nach Anlage 4; Fahrphasen, Energiekosten und Steuer werden dort
nicht ergänzt. Online- und Leasingangebote erhalten zusätzlich den vollständigen
Hinweis nach Anlage 1 als einbettbaren HTML-Ausschnitt, als Browseransicht und
als PDF. Der Ausschnitt ist der maßgebliche Weg, weil der Hinweis bei der
Fahrzeugbeschreibung sichtbar sein muss und ein Download allein nicht genügt. Diese Ausgabe wird gesperrt,
wenn technische Steuerwerte, Fahrphasen oder das zum Angebotsdatum gültige
amtliche Preisprofil fehlen.

Die Pkw-Kataloge von Volkswagen Pkw, Audi, SEAT, CUPRA und Škoda werden als
M1-Kataloge behandelt. Für diese Marken ist keine Freigabe jedes einzelnen
technischen Typs erforderlich. Bei Volkswagen Nutzfahrzeuge wird ein korrekt
gefundener Verbrauchstext für Werbung und Social Media auch ohne bestätigte
Fahrzeugklasse ausgegeben. Online- und Leasingangebote benötigen dagegen eine
M1-Freigabe. Eindeutige oder bestätigte N1-Ausführungen werden vollständig
gesperrt, weil die Pkw-EnVKV-Kennzeichnung für sie nicht erforderlich ist.
Unbekannte Nutzfahrzeug-Basistypen erscheinen in der Freigabeliste:

```powershell
python -m backend.app.vehicle_class_admin --list-pending
python -m backend.app.vehicle_class_admin --type-id '<OKAPI-Typ-ID>' --class M1 --source '<CoC/Herstellerunterlage>' --approved-by '<Name/Kennung>'
```

Basistyp, Klasse, Quelle, freigebende Person und Zeitpunkt werden in SQLite
protokolliert. N1-Typen werden abgewiesen. Bereits gespeicherte Prüfanfragen aus
den Pkw-Katalogen bleiben aus Gründen der Nachvollziehbarkeit erhalten, werden
aber nicht mehr als offene Freigaben angezeigt. Eine M1-Freigabe gilt möglichst
für den OKAPI-Basistyp und damit für dessen Ausstattungslinien, nicht nur für
eine einzelne Verkaufsvariante.

Bei Elektrofahrzeugen wird das Ende der Steuerbefreiung aus § 3d KraftStG
berechnet: zehn Jahre ab der Erstzulassung, längstens bis zum 31.12.2035. Solange
kein Zulassungsdatum erfasst wird, gilt das Erstellungsdatum als geplante
Erstzulassung; die Fußnote nennt sowohl den gesetzlichen Rahmen als auch das
daraus abgeleitete Ende. Für eine Erstzulassung nach dem 31.12.2030 greift keine
Befreiung mehr, die Ausgabe stoppt dann mit einem Prüfhinweis.

Für die Werbung mit einem ganzen Modell erzeugt der Dienst die gesetzliche
Variantenspanne. Sie wird nur ausgegeben, wenn jede Variante der Modellfamilie
bestätigt werden konnte, und nie über mehrere Antriebsarten hinweg vermischt.

Amtliche Energie- und CO₂-Preise sind als datierte Profile hinterlegt. Der
Wechsel erfolgt allein über das Angebotsdatum und damit ohne Eingriff:

| Profil | gültig | Bezugsjahr | Strom | Super | Diesel | CO₂ niedrig/mittel/hoch | Zeitraum |
|---|---|---|---|---|---|---|---|
| `BMWE-2025` | 01.07.2025–30.06.2026 | 2024 | 0,312 €/kWh | 1,796 €/l | 1,649 €/l | 60 / 127 / 200 €/t | 2026–2035 |
| `BMWE-2026` | 01.07.2026–30.06.2027 | 2025 | 0,321 €/kWh | 1,744 €/l | 1,610 €/l | 60 / 142,50 / 220 €/t | 2027–2036 |

Als Benzinpreis wird durchgängig „Super" geführt; die Veröffentlichung ordnet an,
für Super Plus mangels marktgängigem Preis ebenfalls den Preis für Super zu
verwenden. Die Werte stammen ausschließlich aus der amtlichen Veröffentlichung
und werden nie geschätzt oder fortgeschrieben. Gibt es für das Angebotsdatum kein
Profil, stoppt nur die Angebotserstellung mit einem klaren Prüfhinweis. Das BMWE
veröffentlicht jährlich zum 30. Juni; das jeweils neue Profil ist danach mit
Gültigkeitsbeginn 1. Juli zu ergänzen. Die Veröffentlichung gilt für Pkw, die
„nach dem 30. Juni“ angeboten werden, und ist „spätestens ab dem 1. Oktober“
anzuwenden; der 1. Oktober ist damit die Übergangsfrist, nicht der Beginn der
Gültigkeit. Volkswagen verfährt in seinen eigenen Labels ebenso. Werbung und Social Media benötigen
diese Preiswerte nicht.

Unterstützte OKAPI-Konzernmarken in der Fahrzeugerkennung:

- Volkswagen Pkw
- Audi
- SEAT
- CUPRA
- Škoda
- Volkswagen Nutzfahrzeuge

Bei Modellnamen, die sowohl bei SEAT als auch bei CUPRA vorkommen, wird keine
Marke geraten. Für `Leon` und `Ateca` muss die Eingabe deshalb ausdrücklich
`SEAT` oder `CUPRA` enthalten. Eindeutige Modellnamen können weiterhin ohne
Markenangabe gesucht werden.

Fehlende oder mehrdeutige Herstellerwerte dürfen nie durch ein LLM ergänzt
werden. IONOS kann später ausschließlich freie Eingaben strukturieren; jede
Ausgabe muss anschließend vollständig gegen OKAPI validiert werden.

## Ausweisung der CO₂-Emissionen

OKAPI liefert den interpolierten CO₂-Rohwert mit einer Nachkommastelle, etwa
131,1 g/km. Ausgewiesen und für die möglichen CO₂-Kosten verwendet wird der
ganzzahlige Wert. Die Labels, die Volkswagen für dieselben Fahrzeuge
veröffentlicht, weisen ihn ebenso aus; mit dieser Rundung stimmen Energie- und
CO₂-Kosten auf den Cent mit dem Herstellerlabel überein. Die Regel liegt in
`declared_co2_g_km` und gilt einheitlich für den Werbetext nach Anlage 4, den
Hinweis nach Anlage 1 und die Modellspanne.

## Aufbau des Anlage-1-Hinweises

Der Hinweis wird in DIN A4 hoch erzeugt, wie die Labels des Herstellers. Die
Rechtsmatrix nennt an dieser Stelle Querformat; der Widerspruch ist dort
vermerkt und Teil der offenen rechtlichen Prüfung.

Die Klassenpfeile und die Klassenmarke tragen `print-color-adjust: exact`. Ohne
diese Angabe lassen Browser beim Drucken alle Hintergrundfarben weg, und die
Pfeile erschienen leer. Der zweite
Kasten enthält ausschließlich Verbrauch, CO₂-Emissionen und, sofern vorhanden,
die elektrische Reichweite. Energiekosten und Kraftfahrzeugsteuer stehen im
vierten Kasten und werden nicht wiederholt. Die Fußnotenverweise sind fest
vergeben: 1) am CO₂-Wert, 2) an den möglichen CO₂-Kosten, 3) an der
Kraftfahrzeugsteuer eines Elektrofahrzeugs.

Bei Plug-in-Hybriden zeigt die CO₂-Skala zwei Spalten nebeneinander, getrennt
durch eine senkrechte Linie: „gewichtet kombiniert“ und „bei entladener
Batterie“. Jede Klassenmarke steht in derselben Rasterzeile wie ihr Pfeil.

Die Klassenpfeile tragen eine schwarze Kontur, die Buchstaben sind weiß mit
schwarzer Kontur, und die beiden Kästen des dritten Blocks sind gleich breit.
Beträge werden mit Tausenderpunkt ausgegeben.

Es gibt nur noch **eine** Darstellung des Hinweises. Die zuvor getrennt
gezeichnete PDF-Ausgabe ist entfallen; zwei Darstellungen desselben
gesetzlichen Dokuments wären auf Dauer nicht deckungsgleich zu halten. Ein PDF
entsteht bei Bedarf über die Druckansicht des Browsers.

Offen bleibt die visuelle Konformitätsprüfung gegen das amtliche Muster. Die
Längen der Klassenpfeile beruhen auf dem Abgleich mit dem Herstellerlabel, nicht
auf den verbindlichen Maßen aus Anlage 1.

Am Bildschirm ist der Hinweis rund 369 mm hoch. Für den Ausdruck greift eine
Verdichtung über `@media print`: Fließtext 9,5 pt statt 12 pt, Fußnoten 7,5 pt
statt 10 pt, engere Innenabstände und flachere Klassenpfeile. Damit bleibt die
Ausgabe auf einer Seite:

| Fahrzeug | Bildschirm | Ausdruck | verfügbar |
|---|---|---|---|
| Golf eHybrid (Plug-in-Hybrid, umfangreichster Fall) | 366 mm | 253 mm | 283 mm |
| T-Cross (Benzin) | 332 mm | 228 mm | 283 mm |

Die Überschrift behält in beiden Fassungen ihre 26 pt, weil Anlage 1 sie
ausdrücklich vorschreibt. Für die übrigen Schriftgrade liegen die verbindlichen
Mindestwerte nicht vor; sie sind Teil der offenen rechtlichen Prüfung. Sollte
sich dort ein höherer Mindestwert ergeben, ist die Verdichtung in
`_CSS_PRINT` an einer Stelle anzupassen.
