from sentinel.domain import Action, Diagnosis, Incident, RootCauseClass
from sentinel.heuristic import HeuristicDiagnoser
from sentinel.scenario import StaticTelemetryProvider
from sentinel.telemetry import LogEntry, TelemetrySnapshot


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-28T00:00:00Z")


def _diagnose(snap: TelemetrySnapshot) -> Diagnosis:
    return HeuristicDiagnoser().diagnose(_incident(), StaticTelemetryProvider(snap))


def test_stacktrace_spike_after_deploy_is_code_regression_rollback() -> None:
    snap = TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="TypeError: x at Service.finalize")],
        metrics={"error_rate": 0.4},
        revisions=["shop-2", "shop-1"],
    )
    d = _diagnose(snap)
    assert d.root_cause_class is RootCauseClass.CODE_REGRESSION
    assert d.recommended_action is Action.ROLLBACK
    assert d.confidence >= 0.8
    assert d.evidence


def test_low_error_single_revision_warning_only_is_transient_noop() -> None:
    snap = TelemetrySnapshot(
        logs=[LogEntry(severity="WARNING", message="upstream timeout, retrying")],
        metrics={"error_rate": 0.03},
        revisions=["shop-1"],
    )
    d = _diagnose(snap)
    assert d.root_cause_class is RootCauseClass.TRANSIENT_BLIP
    assert d.recommended_action is Action.NOOP


def test_dependency_outage_without_stacktrace_escalates_as_unknown() -> None:
    snap = TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="HTTP 503 from upstream")],
        metrics={"error_rate": 0.38},
        revisions=["shop-1"],
    )
    d = _diagnose(snap)
    assert d.root_cause_class is RootCauseClass.UNKNOWN
    assert d.recommended_action is Action.ESCALATE
    assert d.confidence < 0.8


def test_db_error_with_deploy_does_not_trigger_rollback() -> None:
    snap = TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message='psql: column "x" does not exist')],
        metrics={"error_rate": 0.55},
        revisions=["shop-2", "shop-1"],
    )
    d = _diagnose(snap)
    assert d.recommended_action is Action.ESCALATE
