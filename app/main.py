"""FastAPI application factory and Phase 3 persistence lifecycle."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.requests import router as requests_router
from app.api.workflows import router as workflows_router
from app.persistence.database import Database
from app.persistence.repositories import synchronize_workflow_snapshots
from app.services.configuration_snapshots import build_config_snapshots


logger = logging.getLogger(__name__)


def _error_payload(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def create_app(
    *,
    database_url: str | None = None,
    workflow_config_dir: str | Path | None = None,
    input_schema_dir: str | Path | None = None,
) -> FastAPI:
    """Create an app instance; pass a temporary SQLite URL for isolated tests."""
    database = Database(database_url)
    snapshots = build_config_snapshots(workflow_config_dir, input_schema_dir)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            database.create_schema()
            with database.session() as session:
                with session.begin():
                    synchronize_workflow_snapshots(session, snapshots)
            yield
        finally:
            database.dispose()

    app = FastAPI(
        title="FlowGuard",
        description="Configurable workflow decision platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.config_snapshots = snapshots
    app.include_router(requests_router)
    app.include_router(workflows_router)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(_request: Request, exc: RequestValidationError):
        details = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload("validation_error", "Request validation failed", details),
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        codes = {404: "not_found", 409: "conflict", 422: "validation_error"}
        message = exc.detail if isinstance(exc.detail, str) else "Request could not be completed"
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=_error_payload(codes.get(exc.status_code, "http_error"), message),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        logger.exception("Unhandled FlowGuard request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_error_payload("internal_error", "An internal error occurred"),
        )

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        """Return the process health status."""
        return {"status": "ok"}

    return app


app = create_app()
