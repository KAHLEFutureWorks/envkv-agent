# Rechtsmatrix zur Pkw-EnVKV

Stand: 20. August 2026

## Zweck und verbindliche Quellen

Diese Matrix übersetzt die aktuell geltende Pkw-Energieverbrauchskennzeichnungsverordnung in technische Ausgaberegeln für den KAHLE EnVKV Agent. Sie ist keine Rechtsberatung und ersetzt nicht die formale Freigabe durch die Rechtsabteilung. Für die Implementierung dürfen nur Werte aus der Übereinstimmungsbescheinigung beziehungsweise verlässlich darauf zurückgeführte Herstellerdaten verwendet werden.

Maßgebliche amtliche Quellen:

- [Pkw-EnVKV, aktuelle Gesamtausgabe](https://www.gesetze-im-internet.de/pkw-envkv/BJNR103700004.html)
- [§ 1 Pkw-EnVKV, Kennzeichnungspflicht](https://www.gesetze-im-internet.de/pkw-envkv/BJNR103700004.html#BJNR103700004BJNE000505360)
- [§ 2 Pkw-EnVKV, Begriffsbestimmungen](https://www.gesetze-im-internet.de/pkw-envkv/__2.html)
- [§ 3a Pkw-EnVKV, CO₂-Klassen](https://www.gesetze-im-internet.de/pkw-envkv/__3a.html)
- [§ 5 Pkw-EnVKV, Werbung](https://www.gesetze-im-internet.de/pkw-envkv/__5.html)
- [§ 6 Pkw-EnVKV, Verbot missbräuchlicher Angaben](https://www.gesetze-im-internet.de/pkw-envkv/BJNR103700004.html#BJNR103700004BJNE001401116)
- [Anlage 1 Pkw-EnVKV, vollständiger Hinweis und Muster](https://www.gesetze-im-internet.de/pkw-envkv/anlage_1.html)
- [Anlage 4 Pkw-EnVKV, Pflichtangaben in Werbung](https://www.gesetze-im-internet.de/pkw-envkv/anlage_4.html)
- [BMWE-Seite mit jährlich aktualisierten Preisveröffentlichungen](https://www.bundeswirtschaftsministerium.de/Redaktion/DE/Artikel/Energie/energieverbrauchskennzeichnung-von-pkw.html)
- [BMWE-Veröffentlichung der CO₂-Preise vom 30. Juni 2026](https://www.bundeswirtschaftsministerium.de/Redaktion/DE/Downloads/V/veroffentlichung-zur-pkw-energieverbrauchskennzeichnungsverordnung-co2-preise.pdf?__blob=publicationFile&v=1)
- [§ 3d KraftStG, Steuerbefreiung für Elektrofahrzeuge](https://www.gesetze-im-internet.de/kraftstg/__3d.html)
- [§ 9 KraftStG, Steuersatz](https://www.gesetze-im-internet.de/kraftstg/__9.html)

## 1. Geltungsbereich vor jeder Ausgabe

Der Agent darf einen rechtlich als Pkw-EnVKV-Ausgabe bezeichneten Text nur erzeugen, wenn alle folgenden Bedingungen bestätigt sind:

1. Das Fahrzeug ist ein Personenkraftwagen der Klasse M1 und kein Fahrzeug mit besonderer Zweckbestimmung.
2. Das Fahrzeug ist im Sinne von § 2 Absatz 1 Nummer 2 Pkw-EnVKV neu. Ein Fahrzeug gilt grundsätzlich als neu, wenn die Erstzulassung höchstens acht Monate zurückliegt oder der Kilometerstand höchstens 1.000 Kilometer beträgt.
3. Es liegen verbindliche WLTP-Werte für die konkrete Variante oder Version vor. Vorläufige Werte dürfen nur entsprechend ausdrücklich als „vorläufig“ gekennzeichnet werden.
4. Antriebsart, Kraftstoff beziehungsweise Energieträger und die genaue Variante oder Version sind eindeutig bestimmt.
5. Die Werte stammen aus den einschlägigen Feldern der Übereinstimmungsbescheinigung. Eine freie Ableitung aus Modellnamen, Leistung, Ausstattung oder Marketingtext reicht nicht.

Wichtig für Volkswagen Nutzfahrzeuge: Ein Modellname wie Caddy, Transporter oder ID. Buzz Cargo beweist nicht die Fahrzeugklasse M1. Fahrzeuge der Klasse N1 fallen nicht unter die Pkw-EnVKV. Die Fahrzeugklasse muss deshalb als eigenes, verifiziertes Datenfeld vorliegen.

## 2. Matrix nach Verwendungszweck

| Verwendungszweck | Pflichtumfang | Zeitpunkt und Sichtbarkeit | Fahrphasen | Kosten, Steuer und Fußnoten |
|---|---|---|---|---|
| Gedruckte Fahrzeugwerbung, Werbeschrift | Pflichtangaben nach Anlage 4 Teil I | Gut lesbar, nicht weniger hervorgehoben als der Hauptteil der Werbebotschaft und bereits bei flüchtigem Lesen leicht verständlich | Nein | Energiekosten, CO₂-Kosten und Kraftfahrzeugsteuer sind nach Anlage 4 nicht Bestandteil des Pflichtblocks |
| Elektronische Werbung | Pflichtangaben nach Anlage 4 Teil I entsprechend | Sobald erstmals Motorisierungsangaben wie Leistung, Hubraum oder Beschleunigung erscheinen. Auch ohne Motorisierungsangaben müssen die Pflichtwerte mitgeteilt werden | Nein | Wie bei gedruckter Werbung |
| Social Media und Online-Videoportal | Pflichtangaben nach Anlage 4 Teil I entsprechend | Wie elektronische Werbung. Die CO₂-Klasse sollte mindestens den gleichen Schriftgrad wie die Motorisierungsangaben haben | Nein | Wie bei gedruckter Werbung |
| Allgemeine Online-Fahrzeugwerbung ohne konkreten Fernabsatz | Pflichtangaben nach Anlage 4 Teil I entsprechend | Wie elektronische Werbung | Nein | Wie bei gedruckter Werbung |
| Konkretes Online-Kaufangebot im Fernabsatz | Pflichtblock nach Anlage 4 plus vollständige Angaben nach Anlage 1 | Gut lesbar bei der Beschreibung des Modells, der Variante oder Version. Spätestens sichtbar, wenn die Konfiguration eines konkreten Fahrzeugs abgeschlossen ist | Ja, im Anlage-1-Hinweis | Ja, vollständig nach Anlage 1 |
| Konkretes Online-Leasingangebot im Fernabsatz | Wie konkretes Online-Kaufangebot | Wie konkretes Online-Kaufangebot | Ja, im Anlage-1-Hinweis | Ja, vollständig nach Anlage 1 |
| Konkrete Online-Langzeitmiete im Fernabsatz | Wie konkretes Online-Kaufangebot. Langzeitmiete bedeutet eine modellspezifische Auswahl oder Konfiguration für mindestens einen Monat | Wie konkretes Online-Kaufangebot | Ja, im Anlage-1-Hinweis | Ja, vollständig nach Anlage 1 |

Ein Download-Button allein ist für ein konkretes Onlineangebot rechtlich riskant. Anlage 4 verlangt, dass die Angaben nach Anlage 1 bei der Fahrzeugbeschreibung dargestellt werden und spätestens nach Abschluss der Konfiguration zur Kenntnis gelangen. Der sichere Produktweg ist deshalb, den vollständigen Hinweis direkt sichtbar einzubetten und Druck beziehungsweise PDF nur zusätzlich anzubieten.

Die Ausnahme für technisch eingeschränkte Plattformdarstellungen bei Internetwerbung greift nur, wenn die fehlende oder teilweise fehlende Sichtbarkeit ausschließlich durch die Plattformtechnik und ohne weiteres Zutun des Herstellers oder Händlers entsteht. Sie ist kein allgemeiner Freibrief für gekürzte Social-Media-Texte.

## 3. Pflichtblock für Werbung und Social Media nach Anlage 4

Die Fahrphasen Innenstadt, Stadtrand, Landstraße und Autobahn gehören nicht in den gesetzlichen Pflichtblock nach Anlage 4. Sie dürfen im KAHLE-Werbetext weggelassen werden. Zusätzliche Angaben sind nur sinnvoll, wenn sie zweifelsfrei richtig sind und weder täuschen noch die Vergleichbarkeit einschränken. § 6 Pkw-EnVKV verbietet irreführende oder missverständliche abweichende Angaben.

| Antrieb | Pflichtangaben für eine eindeutig bestimmte Variante oder Version |
|---|---|
| Benzin | Kraftstoffverbrauch kombiniert in l/100 km; CO₂-Emissionen kombiniert in g/km; CO₂-Klasse |
| Diesel | Kraftstoffverbrauch kombiniert in l/100 km; CO₂-Emissionen kombiniert in g/km; CO₂-Klasse |
| NOVC-HEV, Mild- oder Vollhybrid ohne externe Aufladung | Rechtlich wie ein Fahrzeug mit Verbrennungsmotor: Kraftstoffverbrauch kombiniert in l/100 km; CO₂-Emissionen kombiniert in g/km; CO₂-Klasse |
| OVC-HEV beziehungsweise PHEV | Kraftstoffverbrauch gewichtet kombiniert in l/100 km; Stromverbrauch gewichtet kombiniert in kWh/100 km; CO₂-Emissionen gewichtet kombiniert in g/km; CO₂-Klasse gewichtet kombiniert; zusätzlich Kraftstoffverbrauch bei entladener Batterie kombiniert in l/100 km und zweite CO₂-Klasse „bei entladener Batterie“ |
| BEV | Stromverbrauch kombiniert in kWh/100 km; CO₂-Emissionen kombiniert 0 g/km; CO₂-Klasse A |
| Brennstoffzelle | Wasserstoffverbrauch kombiniert in kg/100 km; CO₂-Emissionen kombiniert 0 g/km; CO₂-Klasse A |

Die elektrische Reichweite ist für BEV und PHEV Bestandteil der allgemeinen Kennzeichnungspflicht nach § 1 und des vollständigen Hinweises nach Anlage 1. Anlage 4 nennt sie nicht als eigenen Bestandteil des kurzen Werbepflichtblocks. Wenn sie in Werbung freiwillig ausgegeben wird, muss sie exakt aus der Übereinstimmungsbescheinigung stammen. Für PHEV ist im vollständigen Hinweis die elektrische Reichweite EAER maßgeblich.

### Empfohlene rechtssichere Textstruktur

Die Bezeichnungen sollten sich eng an die Verordnung halten und nicht durch freie Kurzformen ersetzt werden:

- ICE und NOVC-HEV: „Energieverbrauch kombiniert: … l/100 km; CO₂-Emissionen kombiniert: … g/km; CO₂-Klasse: …“
- PHEV: „Energieverbrauch gewichtet kombiniert: … l/100 km plus … kWh/100 km; CO₂-Emissionen gewichtet kombiniert: … g/km; CO₂-Klasse: …; bei entladener Batterie: Kraftstoffverbrauch kombiniert … l/100 km, CO₂-Klasse …“
- BEV: „Energieverbrauch kombiniert: … kWh/100 km; CO₂-Emissionen kombiniert: 0 g/km; CO₂-Klasse: A“
- Brennstoffzelle: „Wasserstoffverbrauch kombiniert: … kg/100 km; CO₂-Emissionen kombiniert: 0 g/km; CO₂-Klasse: A“

Für das Produkt sollte der genaue gesetzliche Wortlaut abschließend anhand der Herstellerfreigabe vereinheitlicht werden. Insbesondere beim PHEV dürfen gewichtet kombinierte Werte und Werte bei entladener Batterie niemals vermischt werden.

## 4. Einzelvariante gegenüber Modell mit mehreren Varianten

### Eindeutig bestimmte Variante oder Version

- Auszugeben sind die Werte der konkreten Variante oder Version aus der Übereinstimmungsbescheinigung.
- Gibt es innerhalb derselben Variante oder Version unterschiedliche Werte, ist für die Werbung jeweils der höchste Wert maßgeblich.
- Gehört dieselbe Variante oder Version wegen unterschiedlicher Werte mehreren CO₂-Klassen an, ist die ungünstigste Klasse anzugeben.

### Werbung für ein Modell mit mehreren Varianten oder Versionen

- Beim Energieverbrauch und bei den CO₂-Emissionen müssen jeweils niedrigster und höchster Wert der zusammengefassten Varianten oder Versionen angegeben werden.
- Bei den CO₂-Klassen müssen die günstigste und die ungünstigste Klasse angegeben werden.
- Die Spannen müssen aus dem vollständigen, aktuell angebotenen Variantenbestand dieses Modells berechnet werden. Eine auf fünf Treffer begrenzte Kandidatenliste ist dafür ungeeignet.
- Wird nur für die Fabrikmarke und nicht für ein bestimmtes Modell geworben, entfallen die Angaben nach Anlage 4 Teil I Nummer 1.

Produktregel: Der Agent muss zwischen „konkrete Variante“ und „Modellwerbung mit Varianten“ unterscheiden. Bei unsicherer Zuordnung darf er nicht stillschweigend einen Einzelwert wählen. Entweder wählt der Nutzer eine konkrete Variante oder der Agent erzeugt ausdrücklich einen Modellbereich mit vollständigen Min-/Max-Werten.

## 5. Vollständiger Anlage-1-Hinweis für Online-Kauf, Leasing und Langzeitmiete

Für konkrete Fernabsatzangebote reicht der kopierbare Fließtext nicht. Zusätzlich sind die Angaben nach Anlage 1 darzustellen. Die Anforderungen gelten sicher als erfüllt, wenn das zutreffende Muster aus Anlage 1 Teil II verwendet wird. Im Internet darf die Fahrzeug-Identifizierungsnummer entfallen.

### Verbindliche Darstellungsmerkmale

- Format 297 mm x 210 mm, also DIN A4 quer.

  > **Offener Widerspruch, Stand 25.08.2026:** Die Labels, die Volkswagen für
  > dieselben Fahrzeuge ausgibt, sind im Hochformat gehalten, ebenso das
  > klassische Pkw-Label am Verkaufsort. Die Ausgabe des Agenten erfolgt daher
  > vorerst in DIN A4 hoch. Welche Angabe zutrifft, muss die rechtliche Prüfung
  > anhand des amtlichen Musters klären.
- Einheitlicher Aufbau nach dem passenden Muster 1 bis 5.
- Überschrift „Information über den Energieverbrauch und die CO₂-Emissionen des neuen Pkw“ in 26 pt fett.
- Grundsätzlich schwarze Angaben auf weißem Hintergrund.
- Gesetzliche Kästen, Mindestschriftgrößen, Farbwerte, Pfeilformen und Größenverhältnisse der CO₂-Skala müssen eingehalten werden.
- Bei PHEV sind zwei schwarze Klassenpfeile mit vertikaler Trennlinie darzustellen: gewichtet kombiniert und „bei entladener Batterie“.
- Die Erläuterungen des fünften Kastens müssen vollständig und mit der Internetseite der von den Herstellern bestimmten Stelle sowie dem maßgeblichen Zehnjahreszeitraum ergänzt werden.
- Erstellungsdatum ist anzugeben. Die VIN darf ausschließlich beim Fernabsatz-Hinweis nach Anlage 4 Teil II Nummer 3 entfallen.

Eine optisch nur „ähnliche“ Eigenkreation ist unnötig riskant. Für die finale Version sollte das amtliche Muster strukturell und gestalterisch exakt nachgebaut und anschließend für jede Antriebsart visuell gegen das Original geprüft werden.

### Werte je Antriebsart im Anlage-1-Hinweis

| Antrieb | Zweiter Kasten | CO₂-Skala | Weitere Angaben rechts im dritten Kasten |
|---|---|---|---|
| Benzin oder Diesel | Energieverbrauch kombiniert; CO₂-Emissionen kombiniert mit Betriebs-CO₂-Fußnote | Eine Klasse | Kraftstoffverbrauch kombiniert plus Innenstadt, Stadtrand, Landstraße und Autobahn |
| NOVC-HEV | Wie Verbrennungsmotor | Eine Klasse | Wie Verbrennungsmotor |
| PHEV | Energieverbrauch und CO₂-Emissionen gewichtet kombiniert; elektrische Reichweite EAER; Betriebs-CO₂-Fußnote | Zwei Klassen: gewichtet kombiniert und bei entladener Batterie | Stromverbrauch bei rein elektrischem Betrieb kombiniert plus vier Fahrphasen; Kraftstoffverbrauch bei entladener Batterie kombiniert plus vier Fahrphasen |
| BEV | Stromverbrauch kombiniert; CO₂-Emissionen 0 g/km mit Betriebs-CO₂-Fußnote; elektrische Reichweite | Klasse A | Stromverbrauch kombiniert plus vier Fahrphasen |
| Brennstoffzelle | Wasserstoffverbrauch kombiniert; CO₂-Emissionen 0 g/km mit Betriebs-CO₂-Fußnote | Klasse A | Wasserstoffverbrauch kombiniert plus vier Fahrphasen |

Die Begriffe für die Fahrphasen sind gesetzlich festgelegt: Innenstadt entspricht WLTP „Niedrig“, Stadtrand „Mittel“, Landstraße „Hoch“ und Autobahn „Höchstwert“.

### Energiekosten, CO₂-Kosten und Kraftfahrzeugsteuer

Der vierte Kasten des Anlage-1-Hinweises muss enthalten:

1. Energiekosten bei 15.000 km Jahresfahrleistung. Berechnung mit dem jeweils amtlich veröffentlichten Durchschnittspreis und dem Verbrauch mal Faktor 150.
2. Bei PHEV sind Kraftstoff- und Strompreis zu berücksichtigen.
3. Preisjahr und Preis je Liter, Kilogramm oder kWh müssen unter den jährlichen Energiekosten genannt werden.
4. Drei mögliche CO₂-Kosten über zehn Jahre bei 15.000 km pro Jahr, jeweils mit verwendetem CO₂-Preis. Berechnung: CO₂-Emissionen in g/km mal angenommener Europreis je Tonne mal 0,15; kaufmännisch auf zwei Nachkommastellen runden.
5. Die vollständige vorgeschriebene Fußnote zur unsicheren CO₂-Preisentwicklung, zu möglichen Abweichungen, zur Entrichtung beim Tanken und zur Informationsplattform.
6. Kraftfahrzeugsteuer als Jahressteuer. Die Berechnung muss auf den steuerlich maßgeblichen Fahrzeugdaten beruhen.

Die Energie- und CO₂-Preisparameter werden jährlich zum 30. Juni veröffentlicht. Neue Werte sind für nach dem 30. Juni angebotene Fahrzeuge spätestens ab dem 1. Oktober anzuwenden. Die Anwendung muss deshalb über versionierte Parameter mit Gültigkeitsdatum erfolgen und darf nicht dauerhaft im Quellcode festgeschrieben sein.

Die Veröffentlichung vom 30. Juni 2026 nennt für den Zeitraum 2027 bis 2036 die durchschnittlichen CO₂-Preise 60,00 Euro pro Tonne für die niedrige, 142,50 Euro pro Tonne für die mittlere und 220,00 Euro pro Tonne für die hohe Annahme. Die zugehörige Kraftstoffpreisliste vom selben Tag nennt für das Bezugsjahr 2025 die Durchschnittspreise 1,744 Euro je Liter Super, 1,687 Euro je Liter Super E 10, 1,610 Euro je Liter Diesel, 0,321 Euro je Kilowattstunde Ladestrom und 17,10 Euro je Kilogramm Wasserstoff. Vor dem 1. Oktober 2026 ist noch die Veröffentlichung vom 30. Juni 2025 maßgeblich; sie nennt für das Bezugsjahr 2024 1,796 Euro je Liter Super, 1,649 Euro je Liter Diesel und 0,312 Euro je Kilowattstunde Ladestrom sowie die CO₂-Preise 60,00, 127,00 und 200,00 Euro pro Tonne für den Zeitraum 2026 bis 2035. Der Agent muss das Angebotsdatum berücksichtigen.

Bei Elektrofahrzeugen ist nicht pauschal „0,00 EUR/Jahr“ als Kraftfahrzeugsteuer einzutragen, wenn eine Steuerbefreiung greift. Anlage 1 verlangt den Text „befristet steuerbefreit“ mit einer Fußnote zum Ende der Befristung. Nach § 3d KraftStG gilt die Befreiung bei Erstzulassung bis 31. Dezember 2030 für zehn Jahre, längstens bis 31. Dezember 2035. Ohne tatsächliches oder rechtlich angenommenes Erstzulassungsdatum kann das individuelle Befristungsende nicht korrekt bestimmt werden.

## 6. Kritische Risiken im aktuellen Projektstand

Die folgenden Punkte müssen vor einer Produktivfreigabe anhand des Codes und realer Ausgaben geprüft werden:

### Kritisch

1. **Anlage-1-Hinweis nur als Button:** Wenn bei Online- oder Leasingangeboten lediglich ein PDF- oder Druckbutton erscheint, ohne dass die vollständigen Angaben bei der Fahrzeugbeschreibung sichtbar sind, ist die Anforderung aus Anlage 4 Teil II Nummer 3 voraussichtlich nicht erfüllt.
2. **Eigene Datenblattgestaltung:** Das aktuelle Datenblatt orientiert sich optisch am VW-Muster, muss aber exakt gegen Anlage 1 geprüft werden. A4-Querformat, fünf Kästen, Schriftgrößen, Farben, Pfeile, PHEV-Doppelpfeil und vollständige Erläuterungen sind verbindlich.
3. **Fahrzeugklasse M1:** Nutzfahrzeugmodelle dürfen nicht allein anhand des Namens als Pkw behandelt werden. N1 muss technisch ausgeschlossen werden.
4. **Kraftfahrzeugsteuer aus Marketingtext:** Hubraum, Motorart, CO₂-Wert, Erstzulassungsdatum und gegebenenfalls Masse müssen aus verlässlichen Fahrzeugdaten stammen. Eine Ableitung aus der eingegebenen Fahrzeugbezeichnung ist für einen gesetzlichen Hinweis nicht ausreichend.
5. **PHEV-Datenvollständigkeit:** Gewichtet kombinierter Kraftstoff- und Stromverbrauch, gewichtet kombinierte CO₂-Emissionen, Verbrauch und CO₂-Klasse bei entladener Batterie, EAER sowie beide Gruppen von Fahrphasen müssen separat vorhanden sein. Fehlt ein Feld, darf kein „verifiziertes“ Datenblatt ausgegeben werden.

### Hoch

6. **Verwendungszweck steuert mehr als Textlänge:** „Onlineangebot“ und „Leasingangebot“ müssen technisch die Anzeige des vollständigen Anlage-1-Hinweises erzwingen. Ein kurzer, rechtmäßiger Werbetext allein reicht dort nicht.
7. **Modell statt Variante:** Bei nicht eindeutiger Variante sind keine erfundenen Einzelwerte zulässig. Entweder muss eine Variante gewählt oder eine vollständige gesetzliche Modellspanne ausgegeben werden.
8. **Jährliche Parameter:** Energieträgerpreise, CO₂-Preise und Zehnjahreszeitraum brauchen Gültigkeitszeiträume, Quellenbeleg und rechtzeitige Aktualisierung. Eine Jahreszahl in einer allgemeinen Datenversion reicht nicht.
9. **BEV-Steuerbefreiung:** „0,00 EUR“ und „befristet steuerbefreit“ sind rechtlich nicht austauschbar. Das Ende der Befreiung muss korrekt in der Fußnote stehen.
10. **Brennstoffzelle:** Falls dieser Antrieb unterstützt werden soll, braucht er ein eigenes Datenmodell mit Wasserstoffverbrauch, eigenen Einheiten und Anlage-1-Muster 5. Eine Behandlung als BEV wäre falsch.

### Mittel

11. **Zusätzliche Angaben in Werbung:** Energiekosten, Steuer, CO₂-Kosten oder Fahrphasen sind im kurzen Anlage-4-Pflichtblock nicht erforderlich. Wenn sie freiwillig ausgegeben werden, erhöhen sie das Fehlerrisiko und unterliegen dem Irreführungsverbot des § 6. Für Werbung und Social Media sollte der Agent deshalb nur den verifizierten Pflichtblock ausgeben.
12. **Plattformspezifische Sichtbarkeit:** Hashtags, „Mehr anzeigen“, abgeschnittene Captions oder Text im Video können Pflichtangaben verdecken. Der Plattform-Ausnahmetatbestand darf nicht als Produktregel eingeplant werden.
13. **Begriff „offizielles Datenblatt“:** Diese Bezeichnung sollte erst verwendet werden, wenn Inhalt und Gestaltung des zutreffenden amtlichen Musters vollständig erfüllt und fachlich freigegeben sind.

## 7. Technische Freigaberegeln

Eine Ausgabe darf nur den Status „rechtlich vollständig“ erhalten, wenn eine automatisierte Regelprüfung mindestens bestätigt:

- Geltungsbereich M1 und Neuwagenstatus,
- eindeutige Variante oder korrekt berechnete Modellspanne,
- vollständige Pflichtfelder der jeweiligen Antriebsart,
- richtige Wertart, Einheit und gesetzliche Bezeichnung,
- richtige CO₂-Klasse beziehungsweise zwei Klassen bei PHEV,
- zum Verwendungszweck passender Umfang,
- bei konkretem Online-Kauf, Leasing oder Langzeitmiete vollständiger Anlage-1-Hinweis,
- aktuelle, am Angebotsdatum gültige Kostenparameter,
- vollständige Pflichtfußnoten und aktuelle Steuerlogik,
- visuelle Konformität des Anlage-1-Musters.

Fehlt ein Pflichtwert oder ist die Zuordnung nicht eindeutig, muss der Agent die Ausgabe blockieren und eine manuelle Prüfung verlangen. Ein LLM darf fehlende WLTP-, Steuer- oder Klassendaten weder schätzen noch ergänzen.

## 8. Empfohlener Abnahmetest

Vor dem Server-Rollout sollte für jede Kombination mindestens ein goldenes Referenzfahrzeug gegen Herstellerdaten und das amtliche Muster geprüft werden:

- Benziner,
- Diesel,
- NOVC-HEV,
- PHEV,
- BEV,
- Brennstoffzelle, sofern im Produktscope,
- konkrete Variante,
- Modellwerbung mit mehreren Varianten,
- Werbung,
- Social Media,
- allgemeine Onlinewerbung,
- Online-Kaufangebot,
- Leasingangebot,
- Langzeitmiete.

Der Test muss nicht nur Zahlen vergleichen. Er muss außerdem Bezeichnungen, Einheiten, Reihenfolge, Sichtbarkeit, Pflichtfußnoten, CO₂-Pfeile, Seitenformat und die am Angebotsdatum gültigen Preisparameter prüfen.
