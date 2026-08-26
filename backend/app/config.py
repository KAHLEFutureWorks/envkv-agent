from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    extension_api_key: str
    database_path: Path
    vw_client_id: str = ""
    vw_client_secret: str = ""
    vw_market: str = "DE"
    cache_ttl_seconds: int = 86_400
    timezone: str = "Europe/Berlin"
    okapi_max_retries: int = 4
    okapi_min_interval_seconds: float = 0.2
    audit_retention_days: int = 90
    electricity_price_eur_kwh: str = "0.321"
    electricity_reference_year: int = 2024
    petrol_price_eur_l: str = "1.796"
    diesel_price_eur_l: str = "1.649"
    fuel_reference_year: int = 2024
    annual_distance_km: int = 15_000
    co2_price_low_eur_t: str = "60"
    co2_price_medium_eur_t: str = "142.5"
    co2_price_high_eur_t: str = "220"
    co2_cost_period_years: int = 10
    # Selbstauslieferung des Edge-Add-ins. Ohne Verzeichnis und Kennung bleiben
    # die Auslieferungsadressen abgeschaltet.
    extension_release_dir: Path | None = None
    extension_id: str = ""
    extension_base_url: str = "https://envkv.kahle.de"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            extension_api_key=os.getenv("EXTENSION_API_KEY", ""),
            database_path=Path(os.getenv("ENVKV_DATABASE_PATH", "./data/envkv.sqlite3")),
            vw_client_id=os.getenv("VW_CLIENT_ID", ""),
            vw_client_secret=os.getenv("VW_CLIENT_SECRET", ""),
            vw_market=os.getenv("VW_MARKET", "DE").upper(),
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "86400")),
            timezone=os.getenv("ENVKV_TIMEZONE", "Europe/Berlin"),
            okapi_max_retries=int(os.getenv("OKAPI_MAX_RETRIES", "4")),
            okapi_min_interval_seconds=float(os.getenv("OKAPI_MIN_INTERVAL_SECONDS", "0.2")),
            audit_retention_days=int(os.getenv("AUDIT_RETENTION_DAYS", "90")),
            electricity_price_eur_kwh=os.getenv("ELECTRICITY_PRICE_EUR_KWH", "0.321"),
            electricity_reference_year=int(os.getenv("ELECTRICITY_REFERENCE_YEAR", "2024")),
            petrol_price_eur_l=os.getenv("PETROL_PRICE_EUR_L", "1.796"),
            diesel_price_eur_l=os.getenv("DIESEL_PRICE_EUR_L", "1.649"),
            fuel_reference_year=int(os.getenv("FUEL_REFERENCE_YEAR", "2024")),
            annual_distance_km=int(os.getenv("ANNUAL_DISTANCE_KM", "15000")),
            co2_price_low_eur_t=os.getenv("CO2_PRICE_LOW_EUR_T", "60"),
            co2_price_medium_eur_t=os.getenv("CO2_PRICE_MEDIUM_EUR_T", "142.5"),
            co2_price_high_eur_t=os.getenv("CO2_PRICE_HIGH_EUR_T", "220"),
            co2_cost_period_years=int(os.getenv("CO2_COST_PERIOD_YEARS", "10")),
            extension_release_dir=(
                Path(os.environ["ENVKV_EXTENSION_DIR"])
                if os.getenv("ENVKV_EXTENSION_DIR")
                else None
            ),
            extension_id=os.getenv("ENVKV_EXTENSION_ID", ""),
            extension_base_url=os.getenv("ENVKV_BASE_URL", "https://envkv.kahle.de"),
        )
