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
