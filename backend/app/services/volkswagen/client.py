"""Produktiver Importpunkt für den bereits verifizierten OKAPI-Client.

Der Spike bleibt vorerst als ausführbares Diagnosewerkzeug erhalten. Alle
Backend-Komponenten importieren den Client ausschließlich über dieses Modul,
damit die Transportimplementierung später ohne Änderung der Fachlogik in das
Backend-Paket verschoben werden kann.
"""

from spike.okapi import OkapiClient, OkapiError
from spike.okapi_probe import MissingWltpData

__all__ = ["OkapiClient", "OkapiError", "MissingWltpData"]
