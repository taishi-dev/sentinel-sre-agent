from pydantic import BaseModel

from sentinel.domain import Diagnosis, Incident, RootCauseClass


class PolicyConfig(BaseModel):
    autonomous_eligible_services: list[str]
    autonomous_eligible_root_causes: list[RootCauseClass]
    sensitive_root_causes: list[RootCauseClass]
    min_confidence: float = 0.8


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
