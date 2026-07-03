from typing import Protocol, assert_never

from pydantic import BaseModel

from sentinel.domain import Action, Decision, Incident
from sentinel.messages import format_action_report, format_escalation, format_observation


class RollbackOutcome(BaseModel):
    success: bool
    from_revision: str
    to_revision: str
    recovered: bool
    detail: str


class ActionExecutor(Protocol):
    def rollback(self, service: str) -> RollbackOutcome: ...


class Notifier(Protocol):
    def notify(self, message: str) -> None: ...


class FakeActionExecutor:
    def __init__(self, outcome: RollbackOutcome | None = None) -> None:
        self.rollback_calls: list[str] = []
        self._outcome = outcome or RollbackOutcome(
            success=True,
            from_revision="shop-2",
            to_revision="shop-1",
            recovered=True,
            detail="fake rollback",
        )

    def rollback(self, service: str) -> RollbackOutcome:
        self.rollback_calls.append(service)
        return self._outcome


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)


class ResponseRecord(BaseModel):
    action: Action
    executed: bool
    notified: bool
    message: str
    rollback: RollbackOutcome | None


def respond(
    incident: Incident,
    decision: Decision,
    executor: ActionExecutor,
    notifier: Notifier,
) -> ResponseRecord:
    match decision.action:
        case Action.ROLLBACK:
            outcome = executor.rollback(incident.service)
            message = format_action_report(
                incident,
                decision,
                recovered=outcome.recovered,
                from_revision=outcome.from_revision,
                to_revision=outcome.to_revision,
            )
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=True,
                notified=True,
                message=message,
                rollback=outcome,
            )
        case Action.ESCALATE:
            message = format_escalation(incident, decision)
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=True,
                message=message,
                rollback=None,
            )
        case Action.NOOP:
            message = format_observation(incident, decision)
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=True,
                message=message,
                rollback=None,
            )
        case _ as unreachable:
            assert_never(unreachable)
