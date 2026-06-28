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
