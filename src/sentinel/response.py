import logging
from typing import Protocol, assert_never

from pydantic import BaseModel

from sentinel.domain import Action, Decision, Incident
from sentinel.messages import (
    format_action_report,
    format_escalation,
    format_observation,
    format_rollback_failure,
)

_logger = logging.getLogger("sentinel")


def notify_safely(notifier: "Notifier", message: str) -> bool:
    """Deliver a notification, absorbing failures.

    A notification failure must never fail the request (a non-2xx answer makes
    Pub/Sub redeliver and re-run an action that already happened). Returns
    whether delivery succeeded so callers can record the truth.
    """
    try:
        notifier.notify(message)
    except Exception:
        _logger.exception("sentinel notification failed")
        return False
    return True


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
            # Adapters' primary contract is to return a failed RollbackOutcome
            # rather than raise; this catch is a backstop for SDK exceptions
            # they cannot anticipate.
            try:
                outcome = executor.rollback(incident.service)
            except Exception as exc:
                _logger.exception("sentinel rollback executor raised")
                outcome = RollbackOutcome(
                    success=False,
                    from_revision="",
                    to_revision="",
                    recovered=False,
                    detail=f"rollback raised: {exc}",
                )
            if outcome.success:
                message = format_action_report(
                    incident,
                    decision,
                    recovered=outcome.recovered,
                    from_revision=outcome.from_revision,
                    to_revision=outcome.to_revision,
                )
            else:
                message = format_rollback_failure(
                    incident,
                    decision,
                    detail=outcome.detail,
                    from_revision=outcome.from_revision,
                    to_revision=outcome.to_revision,
                )
            notified = notify_safely(notifier, message)
            return ResponseRecord(
                action=decision.action,
                executed=outcome.success,
                notified=notified,
                message=message,
                rollback=outcome,
            )
        case Action.ESCALATE:
            message = format_escalation(incident, decision)
            notified = notify_safely(notifier, message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=notified,
                message=message,
                rollback=None,
            )
        case Action.NOOP:
            message = format_observation(incident, decision)
            notified = notify_safely(notifier, message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=notified,
                message=message,
                rollback=None,
            )
        case _ as unreachable:
            assert_never(unreachable)
