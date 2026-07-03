from typing import assert_never

from sentinel.diagnoser import Diagnoser
from sentinel.domain import Action, Decision, Diagnosis, Incident
from sentinel.policy import PolicyGate
from sentinel.telemetry import TelemetryProvider


def decide(incident: Incident, diagnosis: Diagnosis, gate: PolicyGate) -> Decision:
    gate_result = gate.evaluate(incident, diagnosis)
    if not gate_result.allowed:
        return Decision(
            action=Action.ESCALATE,
            requires_human=True,
            diagnosis=diagnosis,
            reason=f"escalated by policy gate: {gate_result.reason}",
        )
    if diagnosis.confidence < gate.config.min_confidence:
        return Decision(
            action=Action.ESCALATE,
            requires_human=True,
            diagnosis=diagnosis,
            reason=(
                f"escalated: confidence {diagnosis.confidence:.2f} "
                f"below threshold {gate.config.min_confidence:.2f}"
            ),
        )
    match diagnosis.recommended_action:
        case Action.ESCALATE:
            return Decision(
                action=Action.ESCALATE,
                requires_human=True,
                diagnosis=diagnosis,
                reason="diagnosis recommends escalation",
            )
        case Action.NOOP:
            return Decision(
                action=Action.NOOP,
                requires_human=False,
                diagnosis=diagnosis,
                reason="no action needed",
            )
        case Action.ROLLBACK:
            return Decision(
                action=Action.ROLLBACK,
                requires_human=False,
                diagnosis=diagnosis,
                reason="autonomous rollback: routine regression on eligible service",
            )
        case _ as unreachable:
            assert_never(unreachable)


class DecisionPipeline:
    def __init__(
        self,
        telemetry: TelemetryProvider,
        diagnoser: Diagnoser,
        gate: PolicyGate,
    ) -> None:
        self._telemetry = telemetry
        self._diagnoser = diagnoser
        self._gate = gate

    def run(self, incident: Incident) -> Decision:
        diagnosis = self._diagnoser.diagnose(incident, self._telemetry)
        return decide(incident, diagnosis, self._gate)
