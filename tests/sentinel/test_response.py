from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)
from sentinel.response import FakeActionExecutor, FakeNotifier, respond


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")


def _decision(action: Action, requires_human: bool) -> Decision:
    diag = Diagnosis(
        root_cause_class=RootCauseClass.CODE_REGRESSION,
        summary="s",
        evidence=[Evidence(source="logs", detail="d")],
        recommended_action=action,
        confidence=0.9,
    )
    return Decision(action=action, requires_human=requires_human, diagnosis=diag, reason="r")


def test_rollback_executes_and_reports() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ROLLBACK, False), ex, no)
    assert rec.executed is True
    assert ex.rollback_calls == ["shop"]
    assert rec.rollback is not None
    assert len(no.messages) == 1
    assert "ROLLBACK" in no.messages[0]


def test_escalate_never_touches_executor() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ESCALATE, True), ex, no)
    assert rec.executed is False
    assert ex.rollback_calls == []
    assert "ESCALATION" in no.messages[0]


def test_noop_never_touches_executor() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.NOOP, False), ex, no)
    assert rec.executed is False
    assert ex.rollback_calls == []
    assert "OBSERVE" in no.messages[0]
