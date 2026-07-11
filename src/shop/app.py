import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.responses import Response as StarletteResponse

from shop.faults import FaultState, FaultType
from shop.logging_config import configure_logging, get_logger, log_event


class InjectRequest(BaseModel):
    fault: str
    fail_count: int = 3

_logger = get_logger("shop")

_ROOT_INFO = {
    "service": "shop",
    "status": "ok",
    "about": (
        "Demo victim service monitored by Sentinel, an autonomous SRE agent "
        "that diagnoses incidents with Gemini and rolls back or escalates"
    ),
    "sentinel_repo": "https://github.com/taishi-dev/sentinel-sre-agent",
}

_LANDING_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel — autonomous SRE agent</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                 "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
    background: #0b1020;
    color: #e8ecf5;
    padding: 2rem;
  }
  .card {
    max-width: 640px;
    width: 100%;
    background: #131a2e;
    border: 1px solid #263149;
    border-radius: 16px;
    padding: 2.5rem;
    box-shadow: 0 20px 60px rgba(0, 0, 0, .4);
  }
  .badge {
    display: inline-block;
    font-size: .72rem;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #8aa0c8;
    border: 1px solid #2c3a58;
    border-radius: 999px;
    padding: .25rem .7rem;
    margin-bottom: 1.2rem;
  }
  h1 { margin: .2rem 0 .3rem; font-size: 2.4rem; letter-spacing: -.02em; }
  .tagline { font-size: 1.1rem; color: #aeb9d4; margin: 0 0 1.4rem; }
  p { line-height: 1.75; color: #c7d0e6; margin: .6rem 0; }
  .links { display: flex; flex-wrap: wrap; gap: .8rem; margin-top: 1.8rem; }
  a.btn {
    text-decoration: none;
    padding: .7rem 1.1rem;
    border-radius: 10px;
    font-weight: 600;
    font-size: .95rem;
  }
  a.primary { background: #3b82f6; color: #fff; }
  a.ghost { background: transparent; color: #cdd7ef; border: 1px solid #34435f; }
  .foot {
    margin-top: 2rem;
    font-size: .85rem;
    color: #7c8bab;
    border-top: 1px solid #222c44;
    padding-top: 1rem;
  }
  .dot { color: #37d67a; }
</style>
</head>
<body>
  <div class="card">
    <span class="badge">DevOps &times; AI Agent Hackathon 2026</span>
    <h1>Sentinel</h1>
    <p class="tagline">「動かない」を判断できる自律SREエージェント</p>
    <p>
      You are looking at the <strong>&ldquo;shop&rdquo; demo service</strong> &mdash;
      the monitored &ldquo;victim.&rdquo; <strong>Sentinel</strong> watches this
      service, and when an incident fires it investigates the logs, diagnoses the
      root cause with Gemini, then <strong>rolls back automatically</strong> when it
      is safe or <strong>escalates to a human</strong> when it is not.
    </p>
    <p>
      This page is the demo target; Sentinel&rsquo;s behavior is shown in the video
      and repository below.
    </p>
    <div class="links">
      <a class="btn primary" href="https://youtu.be/7I-2-rrsw3o">&#9654; Demo video</a>
      <a class="btn ghost" href="https://github.com/taishi-dev/sentinel-sre-agent">GitHub</a>
      <a class="btn ghost" href="https://protopedia.net/prototype/8850">ProtoPedia</a>
    </div>
    <div class="foot">
      <span class="dot">&#9679;</span>
      service: shop &middot; status: ok &middot; monitored by Sentinel
    </div>
  </div>
</body>
</html>
"""


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
    def root(request: Request) -> StarletteResponse:  # type: ignore[misc]  # registered via decorator side-effect
        # Browsers (Accept: text/html) get a human-friendly landing page; API and
        # CLI clients (curl, health probes) keep the self-describing JSON.
        if "text/html" in request.headers.get("accept", ""):
            return HTMLResponse(_LANDING_HTML)
        return JSONResponse(_ROOT_INFO)

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
