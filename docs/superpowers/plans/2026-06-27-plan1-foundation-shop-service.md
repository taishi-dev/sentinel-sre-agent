# Plan 1: Foundation + `shop` Victim Service — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Python project scaffold and the `shop` victim service: a local HTTP service with structured JSON logging and on-demand fault injection, fully testable without any GCP access.

**Architecture:** A `src/` layout Python package with FastAPI serving the `shop` service. An in-memory fault-state manager lets an operator inject one of four fault behaviors via admin endpoints; the business endpoints consult that state to misbehave on demand. All requests emit Cloud-Logging-compatible JSON to stdout. This service is the deliberate demo prop and the eval target for later plans.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pytest, httpx (test client), ruff, pyright (strict).

## Global Constraints

- Python 3.12+ is the target runtime; the project is developed and CI-tested on Python 3.14. All code must type-check under **pyright strict**.
- **ruff** must pass with no errors on `src/` and `tests/`.
- Every feature is built **test-first (TDD)**: failing test, then minimal implementation.
- The `shop` service emits **structured JSON logs to stdout**, one JSON object per line, each containing at minimum `severity`, `message`, and `timestamp` keys (Cloud Logging convention).
- No GCP SDK calls anywhere in this plan; everything runs and tests locally.
- Fault behavior must be **deterministic in tests** (no wall-clock-dependent logic in fault decisions).
- Package imports use absolute paths rooted at `src/` (e.g. `from shop.faults import ...`).
- The four fault types are named exactly: `NONE`, `CHECKOUT_ERROR`, `DEPENDENCY_OUTAGE`, `PII_LEAK`, `TRANSIENT`.

---

### Task 1: Project scaffold and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `src/shop/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_sanity.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a working `pytest` / `ruff` / `pyright` setup with `pythonpath = ["src"]`, so all later tasks import packages under `src/`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "sentinel"
version = "0.1.0"
description = "Autonomous SRE agent — DevOps x AI Agent Hackathon 2026"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "httpx>=0.27",
    "ruff>=0.6",
    "pyright>=1.1.380",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests"]
typeCheckingMode = "strict"
pythonVersion = "3.14"
```

- [ ] **Step 2: Create empty package files**

Create `src/shop/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 3: Write the sanity test**

```python
# tests/test_sanity.py
def test_python_runs() -> None:
    assert 1 + 1 == 2
```

- [ ] **Step 4: Install and run the toolchain**

Run:
```
pip install -e ".[dev]"
pytest -q
ruff check .
pyright
```
Expected: pytest passes 1 test; ruff reports no issues; pyright reports 0 errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/shop/__init__.py tests/__init__.py tests/test_sanity.py
git commit -m "chore: project scaffold with pytest, ruff, pyright-strict"
```

---

### Task 2: Structured JSON logging

**Files:**
- Create: `src/shop/logging_config.py`
- Create: `tests/shop/__init__.py` (empty)
- Test: `tests/shop/test_logging_config.py`

**Interfaces:**
- Consumes: tooling from Task 1.
- Produces:
  - `JsonFormatter` — a `logging.Formatter` subclass emitting one JSON object per record with keys `severity`, `message`, `timestamp`, and any `fields` dict attached to the record.
  - `configure_logging() -> None` — installs a stdout `StreamHandler` with `JsonFormatter` on the root logger at INFO.
  - `get_logger(name: str) -> logging.Logger` — returns a named logger.
  - `log_event(logger: logging.Logger, level: int, message: str, **fields: object) -> None` — logs `message` at `level` with structured `fields`.

- [ ] **Step 1: Write the failing test**

```python
# tests/shop/test_logging_config.py
import json
import logging

from shop.logging_config import JsonFormatter, get_logger, log_event


def test_formatter_emits_required_keys() -> None:
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    out = JsonFormatter().format(record)
    parsed = json.loads(out)
    assert parsed["severity"] == "INFO"
    assert parsed["message"] == "hello"
    assert "timestamp" in parsed


def test_formatter_includes_fields() -> None:
    record = logging.LogRecord(
        name="t", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="boom", args=(), exc_info=None,
    )
    record.fields = {"path": "/checkout", "status": 500}
    out = JsonFormatter().format(record)
    parsed = json.loads(out)
    assert parsed["severity"] == "ERROR"
    assert parsed["path"] == "/checkout"
    assert parsed["status"] == 500


def test_log_event_attaches_fields(caplog: object) -> None:
    logger = get_logger("test.logger")
    logger.setLevel(logging.INFO)
    with __import__("pytest").LogCaptureFixture.__class__ and _capture(logger) as records:
        log_event(logger, logging.INFO, "did thing", widget="cog", count=3)
    assert records[-1].fields == {"widget": "cog", "count": 3}


class _capture:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self.records: list[logging.LogRecord] = []
        self.handler = logging.Handler()
        self.handler.emit = self.records.append  # type: ignore[method-assign]

    def __enter__(self) -> list[logging.LogRecord]:
        self.logger.addHandler(self.handler)
        return self.records

    def __exit__(self, *exc: object) -> None:
        self.logger.removeHandler(self.handler)
```

Note to implementer: the `test_log_event_attaches_fields` body above is awkward; replace it with the clean version below and delete the unused `caplog` param and the `_capture` indirection if you prefer a simpler capture. The REQUIRED assertions are: after `log_event(logger, logging.INFO, "did thing", widget="cog", count=3)`, the emitted record carries `record.fields == {"widget": "cog", "count": 3}`. Use this clean form:

```python
# tests/shop/test_logging_config.py  (clean version of the third test)
import json
import logging

from shop.logging_config import JsonFormatter, get_logger, log_event


def test_log_event_attaches_fields() -> None:
    logger = get_logger("test.logger.fields")
    logger.setLevel(logging.INFO)
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger.addHandler(handler)
    try:
        log_event(logger, logging.INFO, "did thing", widget="cog", count=3)
    finally:
        logger.removeHandler(handler)
    assert records[-1].fields == {"widget": "cog", "count": 3}  # type: ignore[attr-defined]
```

The implementer should write `tests/shop/test_logging_config.py` containing the two formatter tests plus this clean `test_log_event_attaches_fields`, and create the empty `tests/shop/__init__.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/shop/test_logging_config.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'shop.logging_config').

- [ ] **Step 3: Write the implementation**

```python
# src/shop/logging_config.py
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)  # type: ignore[arg-type]
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger, level: int, message: str, **fields: object
) -> None:
    logger.log(level, message, extra={"fields": fields})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/shop/test_logging_config.py -v && pyright && ruff check .`
Expected: all tests PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/shop/logging_config.py tests/shop/__init__.py tests/shop/test_logging_config.py
git commit -m "feat(shop): structured JSON logging"
```

---

### Task 3: Fault state manager

**Files:**
- Create: `src/shop/faults.py`
- Test: `tests/shop/test_faults.py`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces:
  - `FaultType(str, Enum)` with members `NONE`, `CHECKOUT_ERROR`, `DEPENDENCY_OUTAGE`, `PII_LEAK`, `TRANSIENT` (values equal to lowercase names, e.g. `FaultType.CHECKOUT_ERROR.value == "checkout_error"`).
  - `FaultState` class with:
    - `active: FaultType` (defaults to `FaultType.NONE`)
    - `transient_remaining: int` (defaults to 0)
    - `inject(self, fault: FaultType, fail_count: int = 3) -> None` — sets `active`; if `fault is TRANSIENT`, sets `transient_remaining = fail_count`.
    - `clear(self) -> None` — resets to `NONE`, `transient_remaining = 0`.
    - `consume_transient(self) -> bool` — returns True and decrements while `transient_remaining > 0`; once exhausted returns False (used to model self-healing).

- [ ] **Step 1: Write the failing test**

```python
# tests/shop/test_faults.py
from shop.faults import FaultState, FaultType


def test_fault_type_values() -> None:
    assert FaultType.NONE.value == "none"
    assert FaultType.CHECKOUT_ERROR.value == "checkout_error"
    assert FaultType.DEPENDENCY_OUTAGE.value == "dependency_outage"
    assert FaultType.PII_LEAK.value == "pii_leak"
    assert FaultType.TRANSIENT.value == "transient"


def test_default_state_is_none() -> None:
    state = FaultState()
    assert state.active is FaultType.NONE
    assert state.transient_remaining == 0


def test_inject_and_clear() -> None:
    state = FaultState()
    state.inject(FaultType.CHECKOUT_ERROR)
    assert state.active is FaultType.CHECKOUT_ERROR
    state.clear()
    assert state.active is FaultType.NONE


def test_transient_self_heals_after_fail_count() -> None:
    state = FaultState()
    state.inject(FaultType.TRANSIENT, fail_count=2)
    assert state.consume_transient() is True
    assert state.consume_transient() is True
    assert state.consume_transient() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/shop/test_faults.py -v`
Expected: FAIL (No module named 'shop.faults').

- [ ] **Step 3: Write the implementation**

```python
# src/shop/faults.py
from enum import Enum


class FaultType(str, Enum):
    NONE = "none"
    CHECKOUT_ERROR = "checkout_error"
    DEPENDENCY_OUTAGE = "dependency_outage"
    PII_LEAK = "pii_leak"
    TRANSIENT = "transient"


class FaultState:
    def __init__(self) -> None:
        self.active: FaultType = FaultType.NONE
        self.transient_remaining: int = 0

    def inject(self, fault: FaultType, fail_count: int = 3) -> None:
        self.active = fault
        self.transient_remaining = fail_count if fault is FaultType.TRANSIENT else 0

    def clear(self) -> None:
        self.active = FaultType.NONE
        self.transient_remaining = 0

    def consume_transient(self) -> bool:
        if self.transient_remaining > 0:
            self.transient_remaining -= 1
            return True
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/shop/test_faults.py -v && pyright && ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/shop/faults.py tests/shop/test_faults.py
git commit -m "feat(shop): fault-state manager and fault types"
```

---

### Task 4: Shop app — healthy endpoints and request-logging middleware

**Files:**
- Create: `src/shop/app.py`
- Test: `tests/shop/test_app_healthy.py`

**Interfaces:**
- Consumes: `configure_logging`, `get_logger`, `log_event` from `shop.logging_config`; `FaultState`, `FaultType` from `shop.faults`.
- Produces:
  - `create_app(state: FaultState | None = None) -> FastAPI` — builds the app; if `state` is None, creates a fresh `FaultState`. Stores the state on `app.state.fault_state`.
  - Endpoints (healthy behavior): `GET /healthz` -> `{"status": "ok"}`; `GET /` -> `{"service": "shop", "status": "ok"}`; `POST /checkout` -> `{"order_id": "ord-1001", "status": "confirmed"}`; `GET /export?user_id=<id>` -> `{"user_id": <id>, "records": 2}`.
  - A middleware that logs one JSON line per request with fields `method`, `path`, `status`, `latency_ms` (latency may be 0 in tests; do not assert its value).

- [ ] **Step 1: Write the failing test**

```python
# tests/shop/test_app_healthy.py
from fastapi.testclient import TestClient

from shop.app import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root() -> None:
    client = TestClient(create_app())
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "shop"


def test_checkout_healthy() -> None:
    client = TestClient(create_app())
    resp = client.post("/checkout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_export_healthy() -> None:
    client = TestClient(create_app())
    resp = client.get("/export", params={"user_id": "u-42"})
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "u-42"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/shop/test_app_healthy.py -v`
Expected: FAIL (No module named 'shop.app').

- [ ] **Step 3: Write the implementation**

```python
# src/shop/app.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/shop/test_app_healthy.py -v && pyright && ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/shop/app.py tests/shop/test_app_healthy.py
git commit -m "feat(shop): app with healthy endpoints and request logging"
```

---

### Task 5: Admin endpoints for fault injection

**Files:**
- Modify: `src/shop/app.py` (add admin routes)
- Test: `tests/shop/test_admin.py`

**Interfaces:**
- Consumes: `create_app`, `FaultState`, `FaultType`.
- Produces:
  - `POST /admin/inject` with JSON body `{"fault": "<fault_value>", "fail_count": <int optional, default 3>}` -> `{"active": "<fault_value>"}`, mutating `app.state.fault_state`. Unknown fault value -> 400.
  - `POST /admin/clear` -> `{"active": "none"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/shop/test_admin.py
from fastapi.testclient import TestClient

from shop.app import create_app
from shop.faults import FaultState, FaultType


def test_inject_sets_state() -> None:
    state = FaultState()
    client = TestClient(create_app(state))
    resp = client.post("/admin/inject", json={"fault": "checkout_error"})
    assert resp.status_code == 200
    assert resp.json() == {"active": "checkout_error"}
    assert state.active is FaultType.CHECKOUT_ERROR


def test_inject_transient_sets_fail_count() -> None:
    state = FaultState()
    client = TestClient(create_app(state))
    resp = client.post("/admin/inject", json={"fault": "transient", "fail_count": 5})
    assert resp.status_code == 200
    assert state.transient_remaining == 5


def test_inject_unknown_fault_is_400() -> None:
    client = TestClient(create_app())
    resp = client.post("/admin/inject", json={"fault": "nonsense"})
    assert resp.status_code == 400


def test_clear_resets_state() -> None:
    state = FaultState()
    state.inject(FaultType.CHECKOUT_ERROR)
    client = TestClient(create_app(state))
    resp = client.post("/admin/clear")
    assert resp.status_code == 200
    assert resp.json() == {"active": "none"}
    assert state.active is FaultType.NONE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/shop/test_admin.py -v`
Expected: FAIL (404 on /admin/inject, routes not defined).

- [ ] **Step 3: Add the implementation**

Add these imports and routes inside `create_app` in `src/shop/app.py`. Add `from pydantic import BaseModel` and `from fastapi import HTTPException` to the imports at the top, and define the request model above `create_app`:

```python
# add near the top of src/shop/app.py
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel


class InjectRequest(BaseModel):
    fault: str
    fail_count: int = 3
```

```python
# add these routes inside create_app, before `return app`
    @app.post("/admin/inject")
    def admin_inject(body: InjectRequest) -> dict[str, str]:
        try:
            fault = FaultType(body.fault)
        except ValueError:
            raise HTTPException(status_code=400, detail="unknown fault") from None
        app.state.fault_state.inject(fault, body.fail_count)
        return {"active": fault.value}

    @app.post("/admin/clear")
    def admin_clear() -> dict[str, str]:
        app.state.fault_state.clear()
        return {"active": FaultType.NONE.value}
```

Also add `FaultType` to the existing `from shop.faults import FaultState` line so it reads `from shop.faults import FaultState, FaultType`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/shop/test_admin.py tests/shop/test_app_healthy.py -v && pyright && ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/shop/app.py tests/shop/test_admin.py
git commit -m "feat(shop): admin endpoints for fault injection"
```

---

### Task 6: Fault behaviors in business endpoints

**Files:**
- Modify: `src/shop/app.py` (apply fault behavior in `/checkout` and `/export`)
- Test: `tests/shop/test_fault_behaviors.py`

**Interfaces:**
- Consumes: everything above.
- Produces: business endpoints that consult `app.state.fault_state`:
  - `CHECKOUT_ERROR`: `POST /checkout` returns HTTP 500 and logs an ERROR with `fields` containing `fault="checkout_error"` and an `error` message resembling a stack-trace summary.
  - `DEPENDENCY_OUTAGE`: `POST /checkout` returns HTTP 503 and logs an ERROR with `fields` containing `fault="dependency_outage"` and `dependency="payments-api"`.
  - `TRANSIENT`: `POST /checkout` returns 500 while `consume_transient()` is True, then 200 once exhausted (self-heals).
  - `PII_LEAK`: `GET /export` returns 200 but logs a WARNING whose `fields` include the raw PII (`email`, `ssn`) — modeling the exposure.
  - Healthy behavior (Task 4) is unchanged when `active is NONE`.

- [ ] **Step 1: Write the failing test**

```python
# tests/shop/test_fault_behaviors.py
import logging

from fastapi.testclient import TestClient

from shop.app import create_app
from shop.faults import FaultState, FaultType


def _client_with(fault: FaultType, fail_count: int = 3) -> tuple[TestClient, FaultState]:
    state = FaultState()
    state.inject(fault, fail_count)
    return TestClient(create_app(state), raise_server_exceptions=False), state


def test_checkout_error_returns_500() -> None:
    client, _ = _client_with(FaultType.CHECKOUT_ERROR)
    resp = client.post("/checkout")
    assert resp.status_code == 500


def test_dependency_outage_returns_503() -> None:
    client, _ = _client_with(FaultType.DEPENDENCY_OUTAGE)
    resp = client.post("/checkout")
    assert resp.status_code == 503


def test_transient_self_heals() -> None:
    client, _ = _client_with(FaultType.TRANSIENT, fail_count=2)
    assert client.post("/checkout").status_code == 500
    assert client.post("/checkout").status_code == 500
    assert client.post("/checkout").status_code == 200


def test_pii_leak_logs_sensitive_fields(caplog: object) -> None:
    import pytest

    client, _ = _client_with(FaultType.PII_LEAK)
    with pytest.LogCaptureFixture(client).__class__:  # placeholder; see note
        pass
    # Real assertion uses caplog fixture; see clean version below.
```

Note to implementer: write the PII test using pytest's built-in `caplog` fixture rather than the placeholder above. The required behavior: with `PII_LEAK` active, `GET /export` returns 200 and a log record at WARNING level carries `fields` containing keys `email` and `ssn`. Clean form:

```python
# clean version of the PII test
import pytest


def test_pii_leak_logs_sensitive_fields(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = _client_with(FaultType.PII_LEAK)
    with caplog.at_level(logging.WARNING, logger="shop"):
        resp = client.get("/export", params={"user_id": "u-42"})
    assert resp.status_code == 200
    leaked = [r for r in caplog.records if getattr(r, "fields", {}).get("email")]
    assert leaked, "expected a WARNING log carrying PII email"
    assert "ssn" in leaked[-1].fields  # type: ignore[attr-defined]
```

The implementer should write `tests/shop/test_fault_behaviors.py` with the four 500/503/transient tests plus this clean `caplog`-based PII test. Delete the placeholder block.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/shop/test_fault_behaviors.py -v`
Expected: FAIL (checkout returns 200, not 500/503; no PII log).

- [ ] **Step 3: Update the implementation**

Replace the `checkout` and `export` route bodies in `src/shop/app.py` with fault-aware versions. Add `from fastapi.responses import JSONResponse` to the imports.

```python
    @app.post("/checkout")
    def checkout() -> Response:
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
        return JSONResponse(status_code=200, content={"order_id": "ord-1001", "status": "confirmed"})

    @app.get("/export")
    def export(user_id: str) -> dict[str, object]:
        state: FaultState = app.state.fault_state
        if state.active is FaultType.PII_LEAK:
            log_event(
                _logger, logging.WARNING, "exported user record",
                fault="pii_leak", user_id=user_id,
                email="jane.doe@example.com", ssn="123-45-6789",
            )
        return {"user_id": user_id, "records": 2}
```

Note: the healthy `/checkout` test from Task 4 asserts `resp.json()["status"] == "confirmed"`, which the 200 branch above still satisfies.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -v && pyright && ruff check .`
Expected: ALL tests across the suite PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/shop/app.py tests/shop/test_fault_behaviors.py
git commit -m "feat(shop): fault behaviors for checkout and export endpoints"
```

---

## Plan 1 Done-When

- `pytest -v` is fully green; `pyright` reports 0 errors; `ruff check .` is clean.
- The `shop` service runs locally (`uvicorn shop.app:create_app --factory --reload --app-dir src`) and you can inject each fault via `POST /admin/inject` and observe the corresponding misbehavior and JSON logs.
