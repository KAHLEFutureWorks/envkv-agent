"""Auslieferung der Erweiterung als selbst gehostetes Edge-Add-in.

Edge laedt eine selbst gehostete Erweiterung nicht ueber die API, sondern ueber
zwei unauthentifizierte Adressen: einen Aktualisierungshinweis (``updates.xml``)
und das signierte Paket (``.crx``). Beide muessen ohne Zugangsschluessel
erreichbar sein, weil der Browser den Schluessel der Erweiterung nicht kennt.
Das ist unbedenklich: Das Paket ist signiert und enthaelt keine Zugangsdaten -
die Verbindungsdaten kommen erst auf dem Geraet aus der Unternehmensrichtlinie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

# Der Dateiname legt die Version fest. Ein freier Name waere ein Pfadrisiko und
# liesse zugleich offen, welche Fassung ausgeliefert wird.
_FILENAME = re.compile(r"^kahle-envkv-agent-(\d+(?:\.\d+){0,3})\.crx$")

# Chromium vergibt Erweiterungskennungen aus 32 Buchstaben von "a" bis "p".
EXTENSION_ID = re.compile(r"^[a-p]{32}$")

CRX_MEDIA_TYPE = "application/x-chrome-extension"


@dataclass(frozen=True)
class Release:
    version: str
    filename: str
    path: Path


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def latest_release(directory: Path) -> Release | None:
    """Die hoechste im Verzeichnis liegende Paketfassung."""
    if not directory.is_dir():
        return None
    releases = []
    for entry in directory.iterdir():
        treffer = _FILENAME.match(entry.name)
        if treffer is None or not entry.is_file():
            continue
        releases.append(Release(treffer.group(1), entry.name, entry))
    if not releases:
        return None
    return max(releases, key=lambda release: _version_key(release.version))


def resolve_package(directory: Path, filename: str) -> Release | None:
    """Ein Paket ueber seinen Namen finden, ohne den Namen als Pfad zu deuten."""
    if _FILENAME.match(filename) is None:
        return None
    # Der Name wird nie an den Pfad angehaengt, sondern gegen die tatsaechlich
    # vorhandenen Dateien geprueft. Damit ist ein Ausbruch aus dem Verzeichnis
    # auch dann ausgeschlossen, wenn der Ausdruck oben je gelockert wird.
    if not directory.is_dir():
        return None
    for entry in directory.iterdir():
        if entry.name == filename and entry.is_file():
            return Release(_FILENAME.match(filename).group(1), filename, entry)
    return None


def render_updates_xml(extension_id: str, base_url: str, release: Release) -> str:
    """Der Aktualisierungshinweis im von Chromium erwarteten Format."""
    if EXTENSION_ID.match(extension_id) is None:
        raise ValueError("Die Kennung der Erweiterung ist ungueltig.")
    codebase = f"{base_url.rstrip('/')}/ext/{release.filename}"
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>\n"
        f"  <app appid={quoteattr(extension_id)}>\n"
        f"    <updatecheck codebase={quoteattr(codebase)} version={quoteattr(release.version)} />\n"
        "  </app>\n"
        "</gupdate>\n"
    )
