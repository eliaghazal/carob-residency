"""The Carob HTTP API: the customer app (/v1), Paystub webhooks, the staff console (/staff) and ops."""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from carob.api.routes import customers, fx, health, staff, support, topups, transfers, webhooks
from carob.config import get_settings
from carob.errors import CarobError
from carob.logging import configure_logging
from carob.metrics import HTTP_LATENCY, HTTP_REQUESTS

log = logging.getLogger("carob.http")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title="Carob API", version="1.0.0", docs_url="/docs" if settings.env != "production" else None
    )

    @app.middleware("http")
    async def observe(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.scope.get("route")
            template = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, template, str(status)).inc()
            HTTP_LATENCY.labels(request.method, template).observe(elapsed)
            if template not in ("/healthz", "/metrics"):
                log.info(
                    "request",
                    extra={
                        "fields": {
                            "method": request.method,
                            "path": request.url.path,
                            "route": template,
                            "status": status,
                            "duration_ms": round(elapsed * 1000, 1),
                        }
                    },
                )

    @app.exception_handler(CarobError)
    async def carob_error(_request: Request, exc: CarobError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "validation_error", "message": "invalid request", "details": exc.errors()}
            },
        )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    for module in (health, customers, topups, transfers, fx, support, webhooks, staff):
        app.include_router(module.router)
    return app


app = create_app()
