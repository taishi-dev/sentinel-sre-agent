from pathlib import Path

from sentinel.domain import Action, Incident, RootCauseClass
from sentinel.scenario import (
    Scenario,
    ScenarioLabels,
    StaticTelemetryProvider,
    load_catalog,
)
from sentinel.telemetry import LogEntry, TelemetrySnapshot

CATALOG = Path(__file__).parents[2] / "scenarios"


def _snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="boom")],
        metrics={"error_rate": 0.4},
        revisions=["shop-2", "shop-1"],
    )


def test_static_provider_returns_held_snapshot() -> None:
    snap = _snap()
    provider = StaticTelemetryProvider(snap)
    assert provider.snapshot("shop") is snap


def test_scenario_builds_incident() -> None:
    scenario = Scenario(
        id="code_regression",
        number=1,
        title="Code regression in new revision",
        tier=1,
        labels=ScenarioLabels(
            root_cause_class=RootCauseClass.CODE_REGRESSION,
            correct_action=Action.ROLLBACK,
            requires_human=False,
        ),
        telemetry=_snap(),
    )
    incident = scenario.incident()
    assert isinstance(incident, Incident)
    assert incident.service == "shop"


def test_load_catalog_reads_ten_valid_scenarios() -> None:
    scenarios = load_catalog(CATALOG)
    assert len(scenarios) == 10
    numbers = sorted(s.number for s in scenarios)
    assert numbers == list(range(1, 11))
    for s in scenarios:
        assert s.telemetry.metrics
        assert isinstance(s.labels.requires_human, bool)
