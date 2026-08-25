from __future__ import annotations

from html import escape
from typing import Any


COLORS = {"A": "#00a651", "B": "#50b848", "C": "#bfd730", "D": "#fff200", "E": "#f9a51a", "F": "#f36f21", "G": "#ed1c24"}

# Alle Angaben stehen unter einer eigenen Wurzelklasse. Dadurch verwenden die
# A4-Seite und das einbettbare Snippet denselben Stil und können nicht
# auseinanderlaufen, ohne dass das Snippet die Gestaltung der Zielseite verändert.
ROOT_CLASS = "kahle-envkv"

# Schutzregeln gegen Vorgaben der einbettenden Seite. Sie stehen bewusst vor den
# Layoutregeln und besitzen eine geringere Spezifität, damit sie die gesetzlich
# maßgeblichen Größen und Abstände niemals überschreiben.
_GUARDED_ELEMENTS = (
    "div", "span", "section", "p", "h1", "h2", "h3",
    "table", "thead", "tbody", "tr", "th", "td", "ol", "li", "b",
)

_CSS_GUARDS = (
    (
        " " + ",.{root} ".join(_GUARDED_ELEMENTS),
        "margin:0;padding:0;border:0;background:transparent;float:none;position:static;"
        "font-family:inherit;font-size:inherit;font-style:inherit;font-weight:inherit;"
        "line-height:inherit;color:inherit;text-align:inherit;text-transform:none;"
        "text-decoration:none;letter-spacing:normal;word-spacing:normal;"
        "vertical-align:baseline;width:auto;height:auto;min-width:0",
    ),
    # Der Reset entfernt auch die Vorgaben des Browsers. Alles, was Anlage 1
    # verbindlich vorschreibt, wird deshalb hier ausdrücklich wiederhergestellt.
    (" h1,.{root} h2,.{root} h3,.{root} th,.{root} b", "font-weight:bold"),
    (" p", "margin:1em 0"),
    (" ol", "margin:1em 0;padding-left:40px;list-style:decimal"),
    (" li", "display:list-item"),
    (" table", "border-spacing:0"),
    (" section,.{root} div,.{root} p,.{root} h1,.{root} h2,.{root} h3", "display:block"),
)

_CSS_RULES = (
    # print-color-adjust ist vererbbar und sorgt dafuer, dass die Klassenpfeile
    # auch im Ausdruck farbig erscheinen. Ohne diese Angabe lassen Browser
    # Hintergrundfarben weg, und die Pfeile blieben leer.
    ("", "font:12pt Arial,sans-serif;color:#000;background:#fff;max-width:196mm;margin:7mm auto;line-height:normal;text-align:left;print-color-adjust:exact;-webkit-print-color-adjust:exact"),
    (" *", "box-sizing:border-box"),
    (" h1", "font-size:26pt;line-height:1.05;margin:0 0 10px"),
    (" .box", "border:1.5px solid #172033;margin:0 0 9px;padding:10px;break-inside:avoid;page-break-inside:avoid"),
    (" .head", "display:grid;grid-template-columns:1fr 1fr;gap:7px 22px;font-size:14pt"),
    (" .head span:nth-child(even)", "text-align:right"),
    (" table", "width:100%;border-collapse:collapse;font-size:14pt"),
    (" th,.{root} td", "padding:5px;text-align:left"),
    (" td", "font-weight:bold;text-align:right"),
    (" .middle", "display:grid;grid-template-columns:1fr 1fr;padding:0;font-size:12pt"),
    (" .middle>section", "padding:10px"),
    (" .middle>section+section", "border-left:1.5px solid #172033"),
    (" h2", "font-size:16pt;margin:0 0 8px"),
    (" h3", "font-size:12pt;margin:8px 0 2px"),
    # Der Pfeil besteht aus einer schwarzen Grundfläche und einer leicht
    # eingerückten farbigen Füllung. Eine Umrandung liesse sich nicht darstellen,
    # weil clip-path jeden Rahmen mit abschneidet.
    (" .arrow", "position:relative;height:29px;margin:4px 0;padding:7px 10px;background:#000;clip-path:polygon(0 0,calc(100% - 16px) 0,100% 50%,calc(100% - 16px) 100%,0 100%);print-color-adjust:exact;-webkit-print-color-adjust:exact"),
    (" .arrow-fill", "position:absolute;left:1.5px;top:1.5px;right:1.5px;bottom:1.5px;clip-path:polygon(0 0,calc(100% - 16px) 0,100% 50%,calc(100% - 16px) 100%,0 100%);print-color-adjust:exact;-webkit-print-color-adjust:exact"),
    (" .arrow b", "position:relative;color:#fff;text-shadow:-1px -1px 0 #000,1px -1px 0 #000,-1px 1px 0 #000,1px 1px 0 #000,0 0 1px #000"),
    # Die Klassenmarke steht in derselben Rasterzeile wie ihr Pfeil und sitzt
    # dadurch immer auf der Höhe der zutreffenden Klasse.
    (" .scale", "display:grid;align-items:center;row-gap:0;column-gap:0;break-inside:avoid;page-break-inside:avoid"),
    (" .scale-head", "font-size:9pt;text-align:center;padding:0 6px 4px;align-self:end"),
    (" .scale-cell", "text-align:center;padding:0 6px;height:100%;display:flex;align-items:center;justify-content:center"),
    (" .scale-cell.divided,.{root} .scale-head.divided", "border-left:1.5px solid #172033"),
    (" .badge", "background:#07162e;color:#fff;font:bold 21px Arial;padding:9px 14px;clip-path:polygon(18px 0,100% 0,100% 100%,18px 100%,0 50%);text-align:center;min-width:66px;print-color-adjust:exact;-webkit-print-color-adjust:exact"),
    (" .details .row,.{root} .cost-row", "display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:3px 0"),
    # Ohne diese beiden Regeln zerreißt es lange Bezeichnungen und Messwerte.
    (" .details .row>span,.{root} .details .row>b:first-child", "flex:1 1 auto;min-width:0"),
    (" .details .row>b:last-child", "flex:0 0 auto;white-space:nowrap;text-align:right"),
    (" .cost-row b", "margin-left:auto"),
    (" .cost-row>span", "flex:1 1 auto;min-width:0"),
    (" .cost-row>b:last-child", "flex:0 0 auto;white-space:nowrap"),
    (" .foot", "font-size:10pt;margin:7px 0;padding-left:18px"),
)


def _stylesheet() -> str:
    return "".join(
        f".{ROOT_CLASS}{selector.format(root=ROOT_CLASS)}{{{declarations}}}"
        for selector, declarations in _CSS_GUARDS + _CSS_RULES
    )


LEGAL_INTRO = (
    "Die Informationen erfolgen gemäß der Pkw-Energieverbrauchskennzeichnungsverordnung. "
    "Die angegebenen Werte wurden nach dem vorgeschriebenen Messverfahren WLTP "
    "(Worldwide harmonised Light-duty vehicles Test Procedures) ermittelt. Der Kraftstoffverbrauch "
    "und die CO₂-Emissionen eines Pkw sind nicht nur von der effizienten Ausnutzung des Kraftstoffs "
    "durch den Pkw, sondern auch vom Fahrstil und anderen nichttechnischen Faktoren abhängig. "
    "CO₂ ist das für die Erderwärmung hauptsächlich verantwortliche Treibhausgas."
)

GUIDE_NOTE = (
    "Ein Leitfaden über den Kraftstoffverbrauch und die CO₂-Emissionen aller in Deutschland "
    "angebotenen neuen Pkw-Modelle ist unentgeltlich an jedem Verkaufsort in Deutschland einsehbar, "
    "an dem neue Pkw ausgestellt oder angeboten werden. Der Leitfaden ist auch unter "
    "www.dat.de/co2/ abrufbar."
)


def _german_number(text: str) -> str:
    """Wandelt eine englisch formatierte Zahl in die deutsche Schreibweise."""
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _value(value: Any, suffix: str = "", digits: int | None = None) -> str:
    if value is None:
        return "entfällt"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Tausendertrennzeichen wie im Herstellerlabel: 1.438,80 statt 1438,80.
        text = _german_number(f"{value:,.{1 if digits is None else digits}f}")
    else:
        text = str(value).replace(".", ",")
    return f"{text}{suffix}"


def _render_content(sheet: dict[str, Any]) -> str:
    """Erzeugt die fünf Kästen des Anlage-1-Hinweises ohne Seitenhülle."""
    vehicle = sheet["vehicle"]
    consumption = sheet["consumption"]
    costs = sheet["annual_energy_costs"]
    classes = sheet["co2_classes"]
    scale = list(classes["scale"])
    is_phev = sheet["powertrain"] == "plug_in_hybrid"
    discharged_selected = classes.get("discharged_battery")

    # Kasten 3 links: CO₂-Skala. Die Klassenmarke steht in derselben Rasterzeile
    # wie ihr Pfeil und sitzt dadurch auf der Höhe der zutreffenden Klasse. Bei
    # Plug-in-Hybriden verlangt Anlage 1 zwei Klassen nebeneinander, getrennt
    # durch eine senkrechte Trennlinie.
    columns = [(str(classes.get("combined")), "gewichtet kombiniert" if discharged_selected else "")]
    if discharged_selected:
        columns.append((str(discharged_selected), "bei entladener Batterie"))
    template = "1fr" + " 96px" * len(columns)
    cells: list[str] = []
    if discharged_selected:
        cells.append("<div></div>")
        for index, (_, heading) in enumerate(columns):
            divided = " divided" if index else ""
            cells.append(f'<div class="scale-head{divided}">{escape(heading)}</div>')
    for position, grade in enumerate(scale):
        cells.append(
            f'<div class="arrow" style="width:{30 + position * 5}%">'
            f'<span class="arrow-fill" style="background:{COLORS[grade]}"></span>'
            f"<b>{grade}</b></div>"
        )
        for index, (selected_grade, _) in enumerate(columns):
            divided = " divided" if index else ""
            badge = f'<div class="badge">{escape(grade)}</div>' if selected_grade == grade else ""
            cells.append(f'<div class="scale-cell{divided}">{badge}</div>')
    scale_grid = f'<div class="scale" style="grid-template-columns:{template}">{"".join(cells)}</div>'

    # Kasten 2: nur die Pflichtwerte nach Anlage 1. Energiekosten und
    # Kraftfahrzeugsteuer stehen im vierten Kasten und werden hier nicht wiederholt.
    co2_display = sheet.get("declared_co2_g_km", consumption.get("co2_g_km"))
    rows: list[tuple[str, str]] = []
    if consumption.get("combined_l_100km") is not None and consumption.get("combined_kwh_100km") is not None:
        rows.append((
            "Energieverbrauch (gewichtet, kombiniert)",
            f"{_value(consumption.get('combined_kwh_100km'), ' kWh/100 km')} plus "
            f"{_value(consumption.get('combined_l_100km'), ' l/100 km')}",
        ))
    elif consumption.get("combined_kwh_100km") is not None:
        rows.append(("Energieverbrauch (kombiniert)", _value(consumption.get("combined_kwh_100km"), " kWh/100 km")))
    else:
        rows.append(("Energieverbrauch (kombiniert)", _value(consumption.get("combined_l_100km"), " l/100 km")))
    rows.append((
        "CO₂-Emissionen (gewichtet, kombiniert)" if is_phev else "CO₂-Emissionen (kombiniert)",
        _value(co2_display, " g/km", 0),
    ))
    if consumption.get("electric_range_km") is not None:
        rows.append((
            "Elektrische Reichweite (EAER)" if is_phev else "Elektrische Reichweite",
            _value(consumption.get("electric_range_km"), " km", 0),
        ))
    table = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}"
        f'{"<sup>1)</sup>" if label.startswith("CO") else ""}</td></tr>'
        for label, value in rows
    )

    # Kasten 3 rechts: weitere Angaben mit den vier gesetzlich benannten Fahrphasen.
    phase_labels = (
        ("low", "Innenstadt"), ("medium", "Stadtrand"),
        ("high", "Landstraße"), ("extra_high", "Autobahn"),
    )
    fuel_phases = consumption.get("phase_l_100km") or {}
    electric_phases = consumption.get("phase_kwh_100km") or {}
    blocks: list[str] = []
    if consumption.get("combined_kwh_100km") is not None:
        heading = (
            "Stromverbrauch bei rein elektrischem Betrieb, kombiniert"
            if is_phev else "Stromverbrauch kombiniert"
        )
        value = consumption.get("pure_electric_kwh_100km") if is_phev else consumption.get("combined_kwh_100km")
        blocks.append(f'<div class="row"><b>{heading}</b><b>{_value(value, " kWh/100 km")}</b></div>')
        blocks += [
            f'<div class="row"><span>• {label}</span>'
            f'<b>{_value(electric_phases.get(key), " kWh/100 km")}</b></div>'
            for key, label in phase_labels if electric_phases.get(key) is not None
        ]
    if consumption.get("combined_l_100km") is not None:
        heading = (
            "Kraftstoffverbrauch bei entladener Batterie, kombiniert"
            if is_phev else "Kraftstoffverbrauch kombiniert"
        )
        value = consumption.get("discharged_l_100km") if is_phev else consumption.get("combined_l_100km")
        blocks.append(f'<div class="row"><b>{heading}</b><b>{_value(value, " l/100 km")}</b></div>')
        blocks += [
            f'<div class="row"><span>• {label}</span>'
            f'<b>{_value(fuel_phases.get(key), " l/100 km")}</b></div>'
            for key, label in phase_labels if fuel_phases.get(key) is not None
        ]
    details = "".join(blocks)

    # Kasten 4: Kosten. Der Strompreis wird wie im Herstellerlabel in ct/kWh genannt.
    price_notes: list[str] = []
    if consumption.get("combined_kwh_100km") is not None and costs.get("electricity_price_eur_kwh") is not None:
        cents = float(costs["electricity_price_eur_kwh"]) * 100
        price_notes.append(
            f"Strompreis: {_value(cents, ' ct/kWh', 2)} "
            f"Jahresdurchschnitt ({costs.get('electricity_reference_year')})"
        )
    if costs.get("fuel_price_eur_l") is not None:
        price_notes.append(
            f"Kraftstoffpreis: {_value(costs.get('fuel_price_eur_l'), ' EUR/l', 3)} "
            f"Jahresdurchschnitt ({costs.get('fuel_reference_year')})"
        )
    price_text = "; ".join(price_notes)
    distance = costs.get("annual_distance_km") or 15000
    distance_text = f"{distance:,}".replace(",", ".")
    period = sheet.get("co2_cost_period", "")
    tax = sheet["vehicle_tax"]
    tax_text = tax.get("text") or _value(tax.get("annual_eur"), " EUR/Jahr", 2)
    tax_marker = "<sup>3)</sup>" if tax.get("status") == "temporarily_exempt" else ""

    footnotes = "".join(f"<li>{escape(note)}</li>" for note in sheet["footnotes"])
    general = "".join(
        f'<p class="foot">{escape(note)}</p>' for note in sheet.get("general_notes", [])
    )
    powertrain_labels = {
        "battery_electric": "Elektromotor",
        "petrol": "Verbrennungsmotor",
        "diesel": "Verbrennungsmotor",
        "hybrid": "Verbrennungsmotor mit nicht extern aufladbarem Hybridantrieb",
        "plug_in_hybrid": "extern aufladbarer Hybridantrieb",
        "fuel_cell": "Brennstoffzelle",
    }
    fuel_labels = {"PETROL": "Benzin", "DIESEL": "Diesel", "HYDROGEN": "Wasserstoff"}
    scale_caption = (
        "Auf Grundlage der CO₂-Emissionen gewichtet kombiniert / bei entladener Batterie"
        if discharged_selected
        else "Auf Grundlage der CO₂-Emissionen kombiniert"
    )
    energy_carrier = "Strom" if consumption.get("combined_kwh_100km") is not None else "entfällt"
    return f"""<h1>Information über den Energieverbrauch und die CO₂-Emissionen des neuen Pkw</h1>
<div class="box head"><span><b>Marke:</b> {escape(str(vehicle.get('brand') or ''))}</span><span><b>Handelsbezeichnung:</b> {escape(str(vehicle.get('model') or ''))} {escape(str(vehicle.get('trim') or ''))}</span><span><b>Antriebsart:</b> {escape(powertrain_labels.get(sheet['powertrain'], sheet['powertrain']))}</span><span></span><span><b>Kraftstoff:</b> {escape(fuel_labels.get(str(consumption.get('fuel_type')), 'entfällt'))}</span><span><b>anderer Energieträger:</b> {energy_carrier}</span></div>
<div class="box"><table>{table}</table></div>
<div class="box middle"><section><h2>CO₂-Klasse</h2><p>{escape(scale_caption)}</p>{scale_grid}</section><section class="details"><h2>Weitere Angaben:</h2>{details}</section></div>
<div class="box"><div class="cost-row"><b>Energiekosten bei {distance_text} km Jahresfahrleistung:</b><b>{_value(costs.get('annual_cost_eur'), ' EUR/Jahr', 2)}</b></div><p>({escape(price_text)})</p><p><b>Mögliche CO₂-Kosten über die nächsten 10 Jahre ({distance_text} km/Jahr)<sup>2)</sup></b></p><div class="cost-row"><span>• bei einem angenommenen mittleren durchschnittlichen CO₂-Preis von {_value(costs.get('co2_price_medium_eur_t'), ' EUR/t', 2)}</span><b>{_value(costs.get('co2_cost_medium_eur'), ' EUR', 2)}</b></div><div class="cost-row"><span>• bei einem angenommenen niedrigen durchschnittlichen CO₂-Preis von {_value(costs.get('co2_price_low_eur_t'), ' EUR/t', 2)}</span><b>{_value(costs.get('co2_cost_low_eur'), ' EUR', 2)}</b></div><div class="cost-row"><span>• bei einem angenommenen hohen durchschnittlichen CO₂-Preis von {_value(costs.get('co2_price_high_eur_t'), ' EUR/t', 2)}</span><b>{_value(costs.get('co2_cost_high_eur'), ' EUR', 2)}</b></div><div class="cost-row"><b>Kraftfahrzeugsteuer:</b><b>{escape(tax_text)}{tax_marker}</b></div></div>
<div class="box"><p class="foot">{escape(LEGAL_INTRO)}</p><p class="foot">{escape(GUIDE_NOTE)}</p>{general}<ol class="foot">{footnotes}</ol><p class="foot">Maßgeblicher Zeitraum der CO₂-Kosten: {escape(str(period))} · Erstellt am: {escape(sheet['created_at'])} · Quelle: {escape(sheet['source']['provider'])}</p></div>"""


def _sheet_title(sheet: dict[str, Any]) -> str:
    vehicle = sheet["vehicle"]
    return " ".join(str(vehicle.get(key) or "") for key in ("brand", "model", "trim")).strip()


def render_data_sheet_html(sheet: dict[str, Any]) -> str:
    """Vollständige A4-Seite zum Ansehen, Drucken und Speichern."""
    page_css = (
        "@page{size:A4 portrait;margin:7mm}"
        "body{margin:0}"
        "button{padding:10px 18px;margin-bottom:12px}"
        "@media print{button{display:none}}"
    )
    return (
        f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
        f"<title>EnVKV-Datenblatt {escape(_sheet_title(sheet))}</title>\n"
        f"<style>{page_css}{_stylesheet()}</style></head><body>\n"
        f'<div class="{ROOT_CLASS}">\n'
        f'<button onclick="window.print()">Drucken oder als PDF speichern</button>\n'
        f"{_render_content(sheet)}</div></body></html>"
    )


def render_data_sheet_snippet(sheet: dict[str, Any]) -> str:
    """Einbettbarer Ausschnitt für die Fahrzeugbeschreibung eines Onlineangebots.

    Anlage 4 Teil II Nummer 3 verlangt, dass der vollständige Hinweis bei der
    Fahrzeugbeschreibung dargestellt wird. Ein reiner Download genügt dafür nicht.
    Der Ausschnitt bringt seine Gestaltung deshalb vollständig mit, verändert die
    einbettende Seite nicht und benötigt weder externe Dateien noch Skripte.
    """
    return (
        f'<!-- KAHLE EnVKV: Hinweis nach Anlage 1 Pkw-EnVKV, erstellt am '
        f"{escape(sheet['created_at'])}. Dieser Hinweis muss bei der Fahrzeugbeschreibung "
        f"sichtbar bleiben und darf nicht gekürzt werden. -->\n"
        f'<div class="{ROOT_CLASS}">\n'
        f"<style>{_stylesheet()}</style>\n"
        f"{_render_content(sheet)}</div>"
    )
