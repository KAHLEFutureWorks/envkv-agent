"""Kleiner, expliziter Client für den Volkswagen-OKAPI-Vorabtest.

Der Client kennt keine Fachlogik und speichert keine Daten. Er dient nur dazu,
den tatsächlichen OAuth- und Katalogzugang vor dem Produktbau zu belegen.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


TOKEN_URL = "https://api.productdata.volkswagenag.com/oauth2/token"
API_BASE_URL = "https://api.productdata.volkswagenag.com/v3"


class OkapiError(RuntimeError):
    """Eine bereinigte, für die technische Diagnose geeignete OKAPI-Fehlermeldung."""


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: float


Transport = Callable[[Request], Any]


class OkapiClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        transport: Transport | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 4,
        min_interval_seconds: float = 0.0,
    ) -> None:
        if not client_id or not client_secret:
            raise ValueError("VW_CLIENT_ID und VW_CLIENT_SECRET müssen gesetzt sein.")
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport or self._default_transport
        self._clock = clock
        self._sleep = sleep
        self._max_retries = max_retries
        self._min_interval_seconds = min_interval_seconds
        self._next_earliest_call = 0.0
        self._token: AccessToken | None = None

    @staticmethod
    def _default_transport(request: Request) -> Any:
        return urlopen(request, timeout=20)

    def _access_token(self) -> str:
        if self._token and self._token.expires_at > self._clock() + 60:
            return self._token.value

        body = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        ).encode("utf-8")
        payload = self._send(
            Request(
                TOKEN_URL,
                data=body,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )
        token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(token, str) or not token or not isinstance(expires_in, (int, float)):
            raise OkapiError("Die OAuth-Antwort enthält keinen verwendbaren Access Token.")
        self._token = AccessToken(value=token, expires_at=self._clock() + float(expires_in))
        return token

    def _retry_delay(self, error: HTTPError, attempt: int) -> float:
        """Wartezeit vor dem nächsten Versuch, bevorzugt aus dem Retry-After-Kopf."""
        header = None
        try:
            header = error.headers.get("Retry-After") if error.headers else None
        except AttributeError:
            header = None
        if header:
            try:
                return max(0.0, float(str(header).strip()))
            except ValueError:
                pass
        return float(2**attempt)

    def _throttle(self) -> None:
        if self._min_interval_seconds <= 0:
            return
        pending = self._next_earliest_call - self._clock()
        if pending > 0:
            self._sleep(pending)
        self._next_earliest_call = self._clock() + self._min_interval_seconds

    def _send(self, request: Request) -> dict[str, Any] | list[Any]:
        # OKAPI begrenzt die Aufrufrate. Beim Abruf einer ganzen Modellfamilie
        # entstehen viele Anfragen kurz hintereinander; ohne Wiederholung würden
        # einzelne Varianten allein an HTTP 429 scheitern und die gesamte
        # gesetzliche Spanne unbrauchbar machen.
        last_error: HTTPError | None = None
        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
                with self._transport(request) as response:
                    raw = response.read().decode("utf-8")
                break
            except HTTPError as error:
                if error.code not in (429, 500, 502, 503, 504) or attempt == self._max_retries:
                    raise OkapiError(f"Volkswagen OKAPI antwortet mit HTTP {error.code}.") from error
                last_error = error
                self._sleep(self._retry_delay(error, attempt))
            except URLError as error:
                raise OkapiError("Volkswagen OKAPI ist nicht erreichbar.") from error
            except TimeoutError as error:
                raise OkapiError("Die Verbindung zu Volkswagen OKAPI hat zu lange gedauert.") from error
        else:  # pragma: no cover - durch die Abbruchbedingung oben unerreichbar
            raise OkapiError(
                f"Volkswagen OKAPI antwortet mit HTTP {last_error.code if last_error else 429}."
            )

        try:
            return json.loads(raw)
        except json.JSONDecodeError as error:
            raise OkapiError("Volkswagen OKAPI hat keine lesbare JSON-Antwort geliefert.") from error

    def _get(self, path: str) -> dict[str, Any] | list[Any]:
        return self._send(
            Request(
                f"{API_BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self._access_token()}", "Accept": "application/json"},
            )
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | list[Any]:
        return self._send(
            Request(
                f"{API_BASE_URL}{path}",
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._access_token()}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        )

    def countries(self) -> dict[str, Any] | list[Any]:
        return self._get("/countries")

    def brands(self, market: str) -> dict[str, Any] | list[Any]:
        return self._get(f"/catalog/{market}/brands")

    def models(self, market: str, brand_id: str) -> dict[str, Any] | list[Any]:
        return self._get(f"/catalog/{market}/brands/{brand_id}/models")

    def model_types(self, market: str, model_id: str) -> dict[str, Any] | list[Any]:
        return self._get(f"/catalog/{market}/models/{model_id}/types")

    def base_configuration(
        self,
        market: str,
        brand_id: str,
        type_id: str,
        modelyear_code: str,
    ) -> dict[str, Any] | list[Any]:
        return self._get(
            "/catalog/"
            f"{quote(market, safe='')}/brands/{quote(brand_id, safe='')}/types/"
            f"{quote(type_id, safe=':')}/model_year/{quote(modelyear_code, safe=':')}/base_configuration"
        )

    def check(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]:
        return self._post(f"/operation/{market}/check", configuration)

    def wltp(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]:
        return self._post(f"/operation/{market}/wltp", configuration)

    def order(self, market: str, configuration: dict[str, Any]) -> dict[str, Any] | list[Any]:
        # Das Pluszeichen ist laut OKAPI-V3-Dokumentation der Trenner innerhalb
        # des einzelnen extended_with-Parameters und muss hier unverändert in
        # der URL stehen. technical_attributes kann CoC-nahe Rohfelder liefern,
        # die in den marktüblichen technischen Daten nicht sichtbar sind.
        return self._post(
            f"/operation/{market}/order?extended_with=technical_data+technical_attributes&language_code=de&no_default_padding=true",
            configuration,
        )
