import logging

from fastapi.testclient import TestClient

from shop.app import create_app
from shop.faults import FaultState, FaultType
from shop.logging_config import get_logger


def _client_with(
    fault: FaultType, fail_count: int = 3, *, raise_server_exceptions: bool = True
) -> tuple[TestClient, FaultState]:
    state = FaultState()
    state.inject(fault, fail_count)
    return TestClient(create_app(state), raise_server_exceptions=raise_server_exceptions), state


def _capture_shop_logs() -> tuple[list[logging.LogRecord], logging.Handler]:
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    get_logger("shop").addHandler(handler)
    return records, handler


def test_checkout_error_returns_500() -> None:
    client, _ = _client_with(FaultType.CHECKOUT_ERROR, raise_server_exceptions=False)
    records, handler = _capture_shop_logs()
    try:
        resp = client.post("/checkout")
    finally:
        get_logger("shop").removeHandler(handler)
    assert resp.status_code == 500
    fault_logs = [r for r in records if getattr(r, "fields", {}).get("fault") == "checkout_error"]
    assert fault_logs, "expected a log record with fault=checkout_error"
    assert "error" in fault_logs[-1].fields  # type: ignore[attr-defined]


def test_dependency_outage_returns_503() -> None:
    client, _ = _client_with(FaultType.DEPENDENCY_OUTAGE, raise_server_exceptions=False)
    records, handler = _capture_shop_logs()
    try:
        resp = client.post("/checkout")
    finally:
        get_logger("shop").removeHandler(handler)
    assert resp.status_code == 503
    fault_logs = [
        r for r in records if getattr(r, "fields", {}).get("fault") == "dependency_outage"
    ]
    assert fault_logs, "expected a log record with fault=dependency_outage"
    assert fault_logs[-1].fields["dependency"] == "payments-api"  # type: ignore[attr-defined]


def test_transient_self_heals() -> None:
    client, _ = _client_with(FaultType.TRANSIENT, fail_count=2, raise_server_exceptions=False)
    assert client.post("/checkout").status_code == 500
    assert client.post("/checkout").status_code == 500
    assert client.post("/checkout").status_code == 200


def test_pii_leak_logs_sensitive_fields() -> None:
    client, _ = _client_with(FaultType.PII_LEAK, raise_server_exceptions=False)
    records, handler = _capture_shop_logs()
    try:
        resp = client.get("/export", params={"user_id": "u-42"})
    finally:
        get_logger("shop").removeHandler(handler)
    assert resp.status_code == 200
    leaked = [r for r in records if getattr(r, "fields", {}).get("email")]
    assert leaked, "expected a WARNING log carrying PII email"
    assert leaked[-1].levelno == logging.WARNING
    assert "ssn" in leaked[-1].fields  # type: ignore[attr-defined]
