from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException, Path, Query

from pylontech_console.outputs.api.models import (
    CurrentValueModel,
    HealthModel,
    ModuleModel,
    ModulesModel,
    PositionDetailModel,
    PositionModel,
    RackValueModel,
    TopologyEventsModel,
)
from pylontech_console.outputs.api.query import Clock, StateQuery, utc_now
from pylontech_console.polling import CurrentStateStore


class ApplicationRuntime(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...


def create_application(
    store: CurrentStateStore,
    *,
    clock: Clock = utc_now,
    query: StateQuery | None = None,
    runtime: ApplicationRuntime | None = None,
) -> FastAPI:
    """Build the read-only API with deterministic injected dependencies."""
    state_query = query or StateQuery(store, clock)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if runtime is not None:
            await runtime.start()
        try:
            yield
        finally:
            if runtime is not None:
                await runtime.stop()

    app = FastAPI(
        title="Pylontech Console",
        version="0.1",
        lifespan=lifespan,
    )

    @app.get("/api/v1/health", response_model=HealthModel)
    def health() -> HealthModel:
        return state_query.health()

    @app.get(
        "/api/v1/rack",
        response_model=CurrentValueModel[RackValueModel],
    )
    def rack() -> CurrentValueModel[RackValueModel]:
        return state_query.rack()

    @app.get(
        "/api/v1/positions",
        response_model=CurrentValueModel[list[PositionModel]],
    )
    def positions() -> CurrentValueModel[list[PositionModel]]:
        return state_query.positions()

    @app.get(
        "/api/v1/positions/{position}",
        response_model=PositionDetailModel,
    )
    def position(
        position: int = Path(ge=1, le=16),
    ) -> PositionDetailModel:
        result = state_query.position(position)
        if result is None:
            raise HTTPException(status_code=404, detail="position not occupied")
        return result

    @app.get("/api/v1/modules", response_model=ModulesModel)
    def modules() -> ModulesModel:
        return state_query.modules()

    @app.get("/api/v1/modules/{barcode}", response_model=ModuleModel)
    def module(barcode: str) -> ModuleModel:
        result = state_query.module(barcode)
        if result is None:
            raise HTTPException(status_code=404, detail="module not found")
        return result

    @app.get(
        "/api/v1/topology-events",
        response_model=TopologyEventsModel,
    )
    def topology_events(
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> TopologyEventsModel:
        return state_query.topology_events(limit)

    return app
