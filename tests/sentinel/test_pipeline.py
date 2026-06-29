from pathlib import Path

from sentinel.diagnoser import FakeDiagnoser
from sentinel.domain import Action, Diagnosis, Evidence, Incident, RootCauseClass
from sentinel.pipeline import DecisionPipeline, decide
from sentinel.policy import PolicyConfig, PolicyGate
from sentinel.telemetry import FixtureTelemetryProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _incident(service: str = "shop") -> Incident:
    return Incident(service=service, alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z")


def _diag(rc: RootCauseClass, action: Action, confidence: float) -> Diagnosis:
    return Diagnosis(
        root_cause_class=rc,
        summary="x",
        evidence=[Evidence(source="logs", detail="y")],
        recommended_action=action,
        confidence=confidence,
    )


def _gate() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            autonomous_eligible_services=["shop"],
            sensitive_root_causes=[RootCauseClass.SECURITY_REGRESSION, RootCauseClass.PII_EXPOSURE],
            min_confidence=0.8,
        )
    )


def test_autonomous_rollback_on_routine_high_confidence() -> None:
    d = decide(_incident(), _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95), _gate())
    assert d.action is Action.ROLLBACK
    assert d.requires_human is False


def test_low_confidence_escalates_even_if_rollback_recommended() -> None:
    d = decide(_incident(), _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.5), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True
    assert "confidence" in d.reason.lower()


def test_sensitive_cause_escalates_even_if_rollback_recommended_high_confidence() -> None:
    d = decide(_incident(), _diag(RootCauseClass.PII_EXPOSURE, Action.ROLLBACK, 0.99), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True


def test_service_not_allowlisted_escalates() -> None:
    d = decide(
        _incident("payments"),
        _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.99),
        _gate(),
    )
    assert d.action is Action.ESCALATE


def test_noop_recommendation_is_autonomous_noop() -> None:
    d = decide(_incident(), _diag(RootCauseClass.TRANSIENT_BLIP, Action.NOOP, 0.9), _gate())
    assert d.action is Action.NOOP
    assert d.requires_human is False


def test_escalate_recommendation_passes_through() -> None:
    d = decide(_incident(), _diag(RootCauseClass.DEPENDENCY_OUTAGE, Action.ESCALATE, 0.9), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True


def test_pipeline_end_to_end_with_fake() -> None:
    diag = _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95)
    pipeline = DecisionPipeline(
        telemetry=FixtureTelemetryProvider(FIXTURES / "code_regression.json"),
        diagnoser=FakeDiagnoser(diag),
        gate=_gate(),
    )
    decision = pipeline.run(_incident())
    assert decision.action is Action.ROLLBACK
    assert decision.diagnosis is diag
