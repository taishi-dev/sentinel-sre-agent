from pydantic import BaseModel

from sentinel.domain import Diagnosis, Incident, RootCauseClass


class PolicyConfig(BaseModel):
    autonomous_eligible_services: list[str]
    autonomous_eligible_root_causes: list[RootCauseClass]
    sensitive_root_causes: list[RootCauseClass]
    min_confidence: float = 0.8


# Classes where autonomous action (rollback or noop) is acceptable. Anything else
# escalates, no matter how confident the model is.
AUTONOMOUS_ELIGIBLE_ROOT_CAUSES = (
    RootCauseClass.CODE_REGRESSION,
    RootCauseClass.TRANSIENT_BLIP,
    RootCauseClass.RUNTIME_MISMATCH,
)
# Classes the agent must never act on autonomously.
SENSITIVE_ROOT_CAUSES = (
    RootCauseClass.SECURITY_REGRESSION,
    RootCauseClass.PII_EXPOSURE,
)


def default_policy_config(service: str = "shop") -> PolicyConfig:
    """The canonical policy shared by the eval gate and the live agent, so the
    scorecard tests exactly the policy production runs."""
    return PolicyConfig(
        autonomous_eligible_services=[service],
        autonomous_eligible_root_causes=list(AUTONOMOUS_ELIGIBLE_ROOT_CAUSES),
        sensitive_root_causes=list(SENSITIVE_ROOT_CAUSES),
        min_confidence=0.8,
    )


class GateResult(BaseModel):
    allowed: bool
    reason: str


class PolicyGate:
    def __init__(self, config: PolicyConfig) -> None:
        self.config = config

    def evaluate(self, incident: Incident, diagnosis: Diagnosis) -> GateResult:
        if incident.service not in self.config.autonomous_eligible_services:
            return GateResult(
                allowed=False,
                reason=f"service '{incident.service}' not in autonomy allowlist",
            )
        if diagnosis.root_cause_class in self.config.sensitive_root_causes:
            return GateResult(
                allowed=False,
                reason=f"root cause '{diagnosis.root_cause_class.value}' is sensitive",
            )
        if diagnosis.root_cause_class not in self.config.autonomous_eligible_root_causes:
            return GateResult(
                allowed=False,
                reason=(
                    f"root cause '{diagnosis.root_cause_class.value}' "
                    "is not autonomous-eligible"
                ),
            )
        return GateResult(allowed=True, reason="policy gate passed")
