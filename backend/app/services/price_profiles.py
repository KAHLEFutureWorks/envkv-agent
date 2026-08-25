from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from backend.app.domain.envkv import ComplianceProfileIncomplete, EnergyCostConfiguration


class PriceProfileUnavailable(ComplianceProfileIncomplete):
    pass


@dataclass(frozen=True)
class OfficialPriceProfile:
    profile_id: str
    valid_from: date
    valid_until: date
    energy_source_url: str
    co2_source_url: str
    config: EnergyCostConfiguration


# Amtliche Preisprofile nach Anlage 1 Teil I Nummer 8 Pkw-EnVKV.
#
# Das BMWE veröffentlicht die Preise jährlich zum 30. Juni. Sie gelten laut
# Veröffentlichung für Pkw, die "nach dem 30. Juni" angeboten werden, und sind
# "spätestens ab dem 1. Oktober" anzuwenden. Der 1. Oktober ist damit die
# Übergangsfrist, nicht der Beginn der Gültigkeit. Die Profile laufen deshalb vom
# 1. Juli bis zum 30. Juni; ein Angebot verwendet stets die zuletzt
# veröffentlichten Werte. Volkswagen verfährt in seinen eigenen Labels ebenso.
# Der Wechsel erfolgt allein über das Angebotsdatum: Ein neues Profil wird mit
# seinem Gültigkeitsbeginn hinterlegt und greift ab diesem Tag von selbst. Werte
# werden ausschließlich aus der amtlichen Veröffentlichung übernommen und
# niemals geschätzt oder fortgeschrieben.
#
# Als Benzinpreis wird durchgängig "Super" geführt. Die Veröffentlichung ordnet
# an, dass für Super Plus mangels marktgängigem Preis ebenfalls der Preis für
# Super zu verwenden ist.
_PROFILES = (
    OfficialPriceProfile(
        profile_id="BMWE-2025",
        valid_from=date(2025, 7, 1),
        valid_until=date(2026, 6, 30),
        energy_source_url=(
            "https://alternativ-mobil.info/fileadmin/Dokumente/Kraftstoffpreise/"
            "250618_Kraftstoffpreisliste_zum_30.06.2025.pdf"
        ),
        co2_source_url=(
            "https://alternativ-mobil.info/fileadmin/Dokumente/CO2-Preise/"
            "250618_aktualisierter_CO2-Preis_zum_30.06.2025.pdf"
        ),
        config=EnergyCostConfiguration(
            electricity_price_eur_kwh=Decimal("0.312"),
            electricity_reference_year=2024,
            petrol_price_eur_l=Decimal("1.796"),
            diesel_price_eur_l=Decimal("1.649"),
            fuel_reference_year=2024,
            annual_distance_km=15_000,
            co2_price_low_eur_t=Decimal("60"),
            co2_price_medium_eur_t=Decimal("127"),
            co2_price_high_eur_t=Decimal("200"),
            co2_cost_period_years=10,
            co2_cost_period_start_year=2026,
        ),
    ),
    OfficialPriceProfile(
        profile_id="BMWE-2026",
        valid_from=date(2026, 7, 1),
        valid_until=date(2027, 6, 30),
        energy_source_url=(
            "https://alternativ-mobil.info/fileadmin/Dokumente/Kraftstoffpreise/"
            "260626_Kraftstoffpreisliste_zum_30.06.2026.pdf"
        ),
        co2_source_url=(
            "https://alternativ-mobil.info/fileadmin/Dokumente/Kraftstoffpreise/"
            "260626_aktualisierter_CO2-Preis_zum_30.06.2026.pdf"
        ),
        config=EnergyCostConfiguration(
            electricity_price_eur_kwh=Decimal("0.321"),
            electricity_reference_year=2025,
            petrol_price_eur_l=Decimal("1.744"),
            diesel_price_eur_l=Decimal("1.610"),
            fuel_reference_year=2025,
            annual_distance_km=15_000,
            co2_price_low_eur_t=Decimal("60"),
            co2_price_medium_eur_t=Decimal("142.5"),
            co2_price_high_eur_t=Decimal("220"),
            co2_cost_period_years=10,
            co2_cost_period_start_year=2027,
        ),
    ),
)


def official_price_profile(offer_date: date) -> OfficialPriceProfile:
    for profile in _PROFILES:
        if profile.valid_from <= offer_date <= profile.valid_until:
            return profile
    raise PriceProfileUnavailable(
        f"Für das Angebotsdatum {offer_date.isoformat()} ist kein freigegebenes amtliches Preisprofil hinterlegt."
    )
