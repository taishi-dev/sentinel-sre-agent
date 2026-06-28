import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from starlette.responses import Response as StarletteResponse

from shop.faults import FaultState
from shop.logging_config import configure_logging, get_logger, log_event

_logger = get_logger("shop")


def create_app(state: FaultState | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI()
    app.state.fault_state = state if state is not None else FaultState()

    @app.middleware("http")
    async def log_requests(  # type: ignore[misc]  # FastAPI middleware decorator untyped
        request: Request,
        call_next: Callable[[Request], Awaitable[StarletteResponse]],
    ) -> StarletteResponse:
        start = time.monotonic()
        response: StarletteResponse = await call_next(request)
        latency_ms = int((time.monotonic() - start) * 1000)
        log_event(
            _logger,
            logging.INFO,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response

    @app.get("/healthz")
    def healthz() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"status": "ok"}

    @app.get("/")
    def root() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"service": "shop", "status": "ok"}

    @app.post("/checkout")
    def checkout() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"order_id": "ord-1001", "status": "confirmed"}

    @app.get("/export")
    def export(user_id: str) -> dict[str, object]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"user_id": user_id, "records": 2}

    return app
