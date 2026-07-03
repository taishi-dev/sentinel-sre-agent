from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)
from sentinel.messages import format_action_report, format_escalation, format_observation


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")


def _decision(action: Action, rc: RootCauseClass, requires_human: bool, reason: str) -> Decision:
    diag = Diagnosis(
        root_cause_class=rc,
        summary="s",
        evidence=[Evidence(source="logs", detail="d")],
        recommended_action=action,
        confidence=0.9,
    )
    return Decision(action=action, requires_human=requires_human, diagnosis=diag, reason=reason)


def test_escalation_mentions_service_cause_and_reason() -> None:
    d = _decision(Action.ESCALATE, RootCauseClass.PII_EXPOSURE, True, "root cause is sensitive")
    msg = format_escalation(_incident(), d)
    assert "shop" in msg
    assert "pii_exposure" in msg
    assert "sensitive" in msg
    assert msg.isascii()


def test_action_report_states_rollback_and_recovery() -> None:
    d = _decision(Action.ROLLBACK, RootCauseClass.CODE_REGRESSION, False, "autonomous rollback")
    msg = format_action_report(
        _incident(), d, recovered=True, from_revision="shop-2", to_revision="shop-1"
    )
    assert "rollback" in msg.lower()
    assert "shop-2" in msg and "shop-1" in msg
    assert "recover" in msg.lower()
    assert msg.isascii()


def test_observation_is_noop_note() -> None:
    d = _decision(Action.NOOP, RootCauseClass.TRANSIENT_BLIP, False, "no action needed")
    msg = format_observation(_incident(), d)
    assert "shop" in msg
    assert msg.isascii()
