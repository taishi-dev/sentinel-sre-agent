from pathlib import Path

from sentinel.telemetry import FixtureTelemetryProvider, TelemetrySnapshot

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_code_regression_fixture() -> None:
    provider = FixtureTelemetryProvider(FIXTURES / "code_regression.json")
    snap = provider.snapshot("shop")
    assert isinstance(snap, TelemetrySnapshot)
    assert snap.metrics["error_rate"] == 0.42
    assert snap.revisions == ["shop-0008", "shop-0007"]
    assert any("NullPointer" in entry.message for entry in snap.logs)


def test_loads_transient_fixture() -> None:
    provider = FixtureTelemetryProvider(FIXTURES / "transient_blip.json")
    snap = provider.snapshot("shop")
    assert snap.metrics["error_rate"] == 0.03
    assert len(snap.logs) == 1
