import logging
import time

from fastapi import FastAPI, Request, Response

from shop.faults import FaultState
from shop.logging_config import configure_logging, get_logger, log_event

_logger = get_logger("shop")


def create_app(state: FaultState | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI()
    app.state.fault_state = state if state is not None else FaultState()

    @app.middleware("http")
    async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.monotonic()
        response: Response = await call_next(request)
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
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "shop", "status": "ok"}

    @app.post("/checkout")
    def checkout() -> dict[str, str]:
        return {"order_id": "ord-1001", "status": "confirmed"}

    @app.get("/export")
    def export(user_id: str) -> dict[str, object]:
        return {"user_id": user_id, "records": 2}

    return app
