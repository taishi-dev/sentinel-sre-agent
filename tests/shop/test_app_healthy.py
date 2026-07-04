from fastapi.testclient import TestClient

from shop.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root() -> None:
    client = TestClient(create_app())
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "shop"
    assert "Sentinel" in resp.json()["about"]
    assert resp.json()["sentinel_repo"].startswith("https://github.com/")


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


def test_middleware_logs_request_fields() -> None:
    import logging

    from shop.logging_config import get_logger

    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger = get_logger("shop")
    logger.addHandler(handler)
    try:
        TestClient(create_app()).get("/health")
    finally:
        logger.removeHandler(handler)
    req_logs = [r for r in records if getattr(r, "fields", {}).get("path") == "/health"]
    assert req_logs, "expected a request log for /health"
    fields = req_logs[-1].fields  # type: ignore[attr-defined]
    assert fields["method"] == "GET"
    assert fields["status"] == 200
    assert "latency_ms" in fields
