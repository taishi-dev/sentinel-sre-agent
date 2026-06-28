import logging

import pytest
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


def test_pii_leak_logs_sensitive_fields(caplog: pytest.LogCaptureFixture) -> None:
    client, _ = _client_with(FaultType.PII_LEAK)
    with caplog.at_level(logging.WARNING, logger="shop"):
        resp = client.get("/export", params={"user_id": "u-42"})
    assert resp.status_code == 200
    leaked = [r for r in caplog.records if getattr(r, "fields", {}).get("email")]
    assert leaked, "expected a WARNING log carrying PII email"
    assert "ssn" in leaked[-1].fields  # type: ignore[attr-defined]
