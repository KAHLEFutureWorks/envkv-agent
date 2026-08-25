from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app.config import Settings
from backend.app.domain.envkv import ComplianceProfileIncomplete, UsageContext
from backend.app.services.compliance import (
    ComplianceService, cost_config_from_settings, non_offer_cost_config_from_settings,
)
from backend.app.services.volkswagen.client import OkapiClient, OkapiError
from backend.app.services.volkswagen.provider import (
    ManualReviewRequired,
    VehicleNotEligible,
    VehicleNotFound,
    VolkswagenProvider,
)
from backend.app.storage import SQLiteStore
from backend.app.services.data_sheet import (
    render_data_sheet_html,
    render_data_sheet_pdf,
    render_data_sheet_snippet,
)


LOGGER = logging.getLogger("envkv")

# Der Cache und die Auditsätze werden einmal täglich bereinigt. Ohne diesen Lauf
# bliebe AUDIT_RETENTION_DAYS eine reine Angabe ohne Wirkung.
PRUNE_INTERVAL_SECONDS = 24 * 60 * 60


async def _prune_periodically(app: FastAPI) -> None:
    settings = app.state.settings
    store = app.state.store
    while True:
        try:
            removed = await asyncio.to_thread(
                store.prune, retention_days=settings.audit_retention_days
            )
            LOGGER.info(
                "Bereinigung abgeschlossen: %s Cache-Einträge, %s Auditsätze entfernt.",
                removed["cache_deleted"], removed["audit_deleted"],
            )
        except Exception:  # pragma: no cover - Bereinigung darf den Dienst nie stoppen
            LOGGER.exception("Die Bereinigung ist fehlgeschlagen.")
        await asyncio.sleep(PRUNE_INTERVAL_SECONDS)


class ComplianceRequest(BaseModel):
    vehicle_name: str = Field(min_length=2, max_length=300)
    usage_context: UsageContext = UsageContext.ADVERTISING
    selected_type_id: str | None = Field(default=None, max_length=100)


class ModelRangeRequest(BaseModel):
    vehicle_name: str = Field(min_length=2, max_length=300)
    usage_context: UsageContext = UsageContext.ADVERTISING


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()

    @contextlib.asynccontextmanager
    async def lifespan(running: FastAPI):
        task = None
        if running.state.store is not None:
            task = asyncio.create_task(_prune_periodically(running))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="KAHLE EnVKV API", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.compliance_service = None
    app.state.store = None
    if app_settings.vw_client_id and app_settings.vw_client_secret:
        store = SQLiteStore(app_settings.database_path)
        app.state.store = store
        provider = VolkswagenProvider(
            OkapiClient(
                app_settings.vw_client_id,
                app_settings.vw_client_secret,
                max_retries=app_settings.okapi_max_retries,
                min_interval_seconds=app_settings.okapi_min_interval_seconds,
            ),
            store,
            market=app_settings.vw_market,
            cache_ttl_seconds=app_settings.cache_ttl_seconds,
            require_vehicle_class_approval=True,
        )
        app.state.compliance_service = ComplianceService(
            provider,
            store,
            non_offer_cost_config_from_settings(app_settings),
            cost_config_factory=lambda: cost_config_from_settings(app_settings),
            timezone=app_settings.timezone,
        )

    def require_api_key(
        request: Request,
        x_api_key: Annotated[str | None, Header()] = None,
    ) -> None:
        expected = request.app.state.settings.extension_api_key
        if not expected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Der EnVKV-Dienst ist noch nicht vollständig konfiguriert.",
            )
        if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Der Zugriff auf den EnVKV-Dienst wurde nicht bestätigt.",
            )

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/vehicle/compliance", dependencies=[Depends(require_api_key)])
    def compliance(payload: ComplianceRequest, request: Request) -> dict[str, object]:
        service = request.app.state.compliance_service
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Die Volkswagen-Produktdaten sind noch nicht angebunden.",
            )
        try:
            return service.create(payload.vehicle_name, payload.usage_context, payload.selected_type_id)
        except VehicleNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except VehicleNotEligible as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ManualReviewRequired as error:
            raise HTTPException(
                status_code=409,
                detail={"message": str(error), "candidates": error.candidates},
            ) from error
        except ComplianceProfileIncomplete as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except OkapiError as error:
            raise HTTPException(status_code=503, detail="Die Volkswagen-Produktdaten sind aktuell nicht erreichbar.") from error

    @app.post("/api/v1/vehicle/model-range", dependencies=[Depends(require_api_key)])
    def model_range(payload: ModelRangeRequest, request: Request) -> dict[str, object]:
        service = request.app.state.compliance_service
        if service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Die Volkswagen-Produktdaten sind noch nicht angebunden.",
            )
        try:
            return service.create_model_range(payload.vehicle_name, payload.usage_context)
        except VehicleNotFound as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
            ) from error
        except VehicleNotEligible as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ManualReviewRequired as error:
            raise HTTPException(
                status_code=409,
                detail={"message": str(error), "candidates": error.candidates},
            ) from error
        except ComplianceProfileIncomplete as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except OkapiError as error:
            raise HTTPException(
                status_code=503, detail="Die Volkswagen-Produktdaten sind aktuell nicht erreichbar."
            ) from error

    def data_sheet_for(payload: ComplianceRequest, request: Request) -> dict[str, object]:
        service = request.app.state.compliance_service
        if service is None:
            raise HTTPException(status_code=503, detail="Die Volkswagen-Produktdaten sind noch nicht angebunden.")
        context = payload.usage_context
        if context not in {UsageContext.ONLINE_OFFER, UsageContext.LEASING_OFFER}:
            context = UsageContext.ONLINE_OFFER
        try:
            result = service.create(payload.vehicle_name, context, payload.selected_type_id)
            return result["data_sheet"]  # type: ignore[return-value]
        except (VehicleNotFound, VehicleNotEligible, ManualReviewRequired, ComplianceProfileIncomplete) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except OkapiError as error:
            raise HTTPException(status_code=503, detail="Die Volkswagen-Produktdaten sind aktuell nicht erreichbar.") from error

    @app.post("/api/v1/vehicle/data-sheet.html", dependencies=[Depends(require_api_key)], response_class=HTMLResponse)
    def data_sheet_html(payload: ComplianceRequest, request: Request) -> HTMLResponse:
        return HTMLResponse(render_data_sheet_html(data_sheet_for(payload, request)))

    @app.post(
        "/api/v1/vehicle/data-sheet-snippet.html",
        dependencies=[Depends(require_api_key)],
        response_class=Response,
    )
    def data_sheet_snippet(payload: ComplianceRequest, request: Request) -> Response:
        # Als text/plain ausgeliefert, weil der Ausschnitt zum Einfügen in eine
        # fremde Seite bestimmt ist und nicht selbst dargestellt werden soll.
        return Response(
            render_data_sheet_snippet(data_sheet_for(payload, request)),
            media_type="text/plain; charset=utf-8",
        )

    @app.post("/api/v1/vehicle/data-sheet.pdf", dependencies=[Depends(require_api_key)])
    def data_sheet_pdf(payload: ComplianceRequest, request: Request) -> Response:
        return Response(
            render_data_sheet_pdf(data_sheet_for(payload, request)),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="envkv-datenblatt.pdf"'},
        )

    return app


app = create_app()
