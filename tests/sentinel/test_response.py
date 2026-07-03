from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)
from sentinel.response import FakeActionExecutor, FakeNotifier, RollbackOutcome, respond


class _RaisingExecutor:
    def rollback(self, service: str) -> RollbackOutcome:
        raise RuntimeError("cloud run api error")


class _RaisingNotifier:
    def notify(self, message: str) -> None:
        raise RuntimeError("slack webhook down")


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


def test_failed_rollback_reports_failure_not_action() -> None:
    failed = RollbackOutcome(
        success=False, from_revision="shop-1", to_revision="", recovered=False,
        detail="no previous revision to roll back to",
    )
    ex, no = FakeActionExecutor(outcome=failed), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ROLLBACK, False), ex, no)
    assert rec.executed is False
    assert rec.notified is True
    assert "ESCALATION" in no.messages[0]
    assert "AUTONOMOUS ROLLBACK" not in no.messages[0]


def test_rollback_executor_exception_is_absorbed() -> None:
    ex, no = _RaisingExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ROLLBACK, False), ex, no)
    assert rec.executed is False
    assert rec.rollback is not None
    assert rec.rollback.success is False
    assert "ESCALATION" in no.messages[0]
    assert "cloud run api error" in no.messages[0]


def test_notifier_failure_is_absorbed_on_rollback() -> None:
    ex, no = FakeActionExecutor(), _RaisingNotifier()
    rec = respond(_incident(), _decision(Action.ROLLBACK, False), ex, no)
    assert rec.executed is True
    assert rec.notified is False


def test_notifier_failure_is_absorbed_on_escalate() -> None:
    ex, no = FakeActionExecutor(), _RaisingNotifier()
    rec = respond(_incident(), _decision(Action.ESCALATE, True), ex, no)
    assert rec.executed is False
    assert rec.notified is False
