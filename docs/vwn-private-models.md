# Volkswagen Nutzfahrzeuge: potenziell privat nutzbare Modellfamilien

Stand: 21. August 2026

## Zweck und Abgrenzung

Diese Übersicht ordnet aktuelle Modellfamilien im deutschen Angebot von Volkswagen Nutzfahrzeuge danach ein, ob Volkswagen sie selbst für Familie, Alltag, Freizeit, Reisen oder Personenbeförderung beschreibt. Das ist **kein Nachweis der Fahrzeugklasse M1** für einen konkreten OKAPI-Typ.

Für die EnVKV-Verarbeitung muss die konkrete Fahrzeugklasse bei Zweifelsfällen weiterhin aus einer belastbaren typbezogenen Quelle stammen, beispielsweise CoC-Feld 0.4 oder einer eindeutigen Herstellerunterlage. Sitzplatzzahl, Modellname und private Vermarktung ersetzen diesen Nachweis nicht.

## Eindeutig familien-, alltags- oder freizeitorientierte Modellfamilien

| Modellfamilie | Privat relevante Varianten | Offizieller Befund | Abgrenzung |
|---|---|---|---|
| ID. Buzz | ID. Buzz, langer Radstand, GTX | Volkswagen führt den ID. Buzz zusammen mit Caddy und Multivan ausdrücklich als Familienauto. | **ID. Buzz Cargo ausschließen.** [ID. Buzz](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/id-buzz.html), [Familienautos](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/familienautos.html) |
| Caddy | Caddy mit 5 oder 7 Sitzen, einschließlich Caddy Maxi und Pkw-Ausstattungslinien | Volkswagen beschreibt den Caddy als Fahrzeug für Familien, Schulweg, Alltag und Kurzurlaub. | **Caddy Cargo ausschließen.** Caddy Flexible separat behandeln. [Caddy](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/caddy.html), [Familienautos](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/familienautos.html) |
| Caddy California | Caddy California, Caddy California Maxi | Volkswagen nennt fünf Sitzplätze, zwei Schlafplätze sowie Alltag und Wochenendausflüge. | Camperausführung; konkrete Fahrzeugklasse trotzdem typbezogen prüfen. [Caddy California](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/caddy-california.html) |
| Multivan | Multivan, langer Überhang, eHybrid und weitere Personenvarianten | Volkswagen nennt ausdrücklich Familie, Freizeit und Business sowie bis zu sieben Sitzplätze. | Keine pauschale Aussage über jeden einzelnen Typcode. [Multivan](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/multivan.html) |
| California | Beach, Beach Tour, Beach Camper, Coast, Ocean | Volkswagen beschreibt den California als Begleiter für Alltag und Freizeit sowie als Reisemobil. | Reisemobil-/Sonderzweckausführung: konkrete M1-Einstufung prüfen. [California](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/california.html), [California-Reisemobile](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/california-reisemobile.html) |
| Grand California | Grand California 600, 680 und DUNE | Volkswagen vermarktet ihn als voll ausgestatteten Camper für Reisen, Urlaub und Familie. | Crafter-basiertes Reisemobil; nicht aus der Crafter-Basis automatisch auf M1 schließen. [Grand California](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/grand-california.html) |

## Privat möglich, aber gemischter oder professioneller Modellkatalog

Diese Familien sollten nicht vollständig automatisch freigegeben werden:

| Modellfamilie | Privat relevante Variante | Warum typgenau prüfen? |
|---|---|---|
| Caravelle / e-Caravelle | Personenvarianten mit bis zu neun Sitzplätzen | Volkswagen nennt auch private Nutzung, positioniert die Caravelle aber stark als Shuttle, Großraumtaxi und professionellen Personentransporter. [Großraumlimousinen](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/grossraumlimousinen.html), [Caravelle](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/caravelle.html) |
| Transporter / e-Transporter | ausschließlich Kombi-/Personenvarianten | Der Transporter-Katalog enthält Personen-, Güter-, Kasten- und andere gewerbliche Ausführungen. Nur die konkrete Kombi-/Personenausführung kommt als Kandidat infrage. [Kombitransporter](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/kombitransporter.html), [Transporter-Modelle](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/transporter-modelle.html) |
| Caddy Flexible | Flexible Personen-/Laderaumkonfiguration | Volkswagen beschreibt eine gemischte private und berufliche Verwendung. Deshalb nicht mit dem normalen Caddy pauschal gleichsetzen. [Kombitransporter](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/kombitransporter.html) |

## Nicht pauschal als private Pkw-Kandidaten behandeln

- ID. Buzz Cargo
- Caddy Cargo
- Transporter Kastenwagen, Pritsche, Fahrgestell und andere reine Gütervarianten
- Crafter Kastenwagen, Pritsche, Fahrgestell und die allgemeine Crafter-Grundfamilie

Volkswagen beschreibt diese Ausführungen vorrangig über Laderaum, Nutzlast, Aufbau oder gewerbliche Einsätze. Der Crafter ist nur dann separat relevant, wenn daraus eine konkret dokumentierte Personen- oder Reisemobilausführung entstanden ist; der **Grand California** wird deshalb als eigene Modellfamilie behandelt. [Kastenwagen](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/nutzfahrzeugkategorien/kastenwagen.html), [Crafter](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/crafter.html), [ID. Buzz Cargo](https://www.volkswagen-nutzfahrzeuge.de/de/modelle/id-buzz-cargo.html)

## Empfehlung für die technische Freigabelogik

1. Als private Kandidaten automatisch erkennen: **ID. Buzz ohne Cargo, Caddy Pkw ohne Cargo/Flexible, Caddy California und Multivan**.
2. Weiterhin typbezogen auf M1 prüfen: **California, Grand California, Caravelle, Transporter Kombi/e-Transporter Kombi und Caddy Flexible**.
3. Automatisch sperren: Bezeichnungen mit **Cargo, Kasten, Kastenwagen, Pritsche, Fahrgestell** sowie die allgemeine **Crafter**-Familie ohne eindeutig dokumentierte Reisemobil-/Personenausführung.
4. Eine Freigabe sollte möglichst für einen belastbar abgegrenzten OKAPI-Basistyp oder eine Modell-/Aufbaukombination gelten und nicht unnötig für jede Ausstattungslinie einzeln erfolgen.

Damit bleibt der manuelle Aufwand überschaubar, ohne aus einer werblichen Bezeichnung eine rechtlich nicht belegte M1-Zuordnung abzuleiten.
