import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.responses import Response as StarletteResponse

from shop.faults import FaultState, FaultType
from shop.logging_config import configure_logging, get_logger, log_event


class InjectRequest(BaseModel):
    fault: str
    fail_count: int = 3

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

    @app.get("/health")
    def health() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"status": "ok"}

    @app.get("/")
    def root() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {
            "service": "shop",
            "status": "ok",
            "about": (
                "Demo victim service monitored by Sentinel, an autonomous SRE agent "
                "that diagnoses incidents with Gemini and rolls back or escalates"
            ),
            "sentinel_repo": "https://github.com/taishi-dev/sentinel-sre-agent",
        }

    @app.post("/checkout")
    def checkout() -> StarletteResponse:  # type: ignore[misc]  # registered via decorator side-effect
        state: FaultState = app.state.fault_state
        if state.active is FaultType.CHECKOUT_ERROR:
            log_event(
                _logger, logging.ERROR, "checkout failed",
                fault="checkout_error",
                error="NullPointer: order.total in CheckoutService.finalize()",
            )
            return JSONResponse(status_code=500, content={"error": "internal"})
        if state.active is FaultType.DEPENDENCY_OUTAGE:
            log_event(
                _logger, logging.ERROR, "checkout dependency failed",
                fault="dependency_outage", dependency="payments-api", status=503,
            )
            return JSONResponse(status_code=503, content={"error": "dependency unavailable"})
        if state.active is FaultType.TRANSIENT and state.consume_transient():
            log_event(
                _logger, logging.ERROR, "checkout transient failure",
                fault="transient",
            )
            return JSONResponse(status_code=500, content={"error": "transient"})
        return JSONResponse(
            status_code=200, content={"order_id": "ord-1001", "status": "confirmed"}
        )

    @app.get("/export")
    def export(user_id: str) -> dict[str, object]:  # type: ignore[misc]  # registered via decorator side-effect
        state: FaultState = app.state.fault_state
        if state.active is FaultType.PII_LEAK:
            log_event(
                _logger, logging.WARNING, "exported user record",
                fault="pii_leak", user_id=user_id,
                email="jane.doe@example.com", ssn="123-45-6789",
            )
        return {"user_id": user_id, "records": 2}

    @app.post("/admin/inject")
    def admin_inject(body: InjectRequest) -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        try:
            fault = FaultType(body.fault)
        except ValueError:
            raise HTTPException(status_code=400, detail="unknown fault") from None
        app.state.fault_state.inject(fault, body.fail_count)
        return {"active": fault.value}

    @app.post("/admin/clear")
    def admin_clear() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        app.state.fault_state.clear()
        return {"active": FaultType.NONE.value}

    return app
