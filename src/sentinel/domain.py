from enum import StrEnum

from pydantic import BaseModel, Field


class RootCauseClass(StrEnum):
    CODE_REGRESSION = "code_regression"
    DEPENDENCY_OUTAGE = "dependency_outage"
    CONFIG_DRIFT = "config_drift"
    SECURITY_REGRESSION = "security_regression"
    PII_EXPOSURE = "pii_exposure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    BAD_MIGRATION = "bad_migration"
    TRANSIENT_BLIP = "transient_blip"
    COSMETIC = "cosmetic"
    RUNTIME_MISMATCH = "runtime_mismatch"
    UNKNOWN = "unknown"


class Action(StrEnum):
    ROLLBACK = "rollback"
    ESCALATE = "escalate"
    NOOP = "noop"


class Incident(BaseModel):
    service: str
    alert: str
    triggered_at: str


class Evidence(BaseModel):
    source: str
    detail: str


class Diagnosis(BaseModel):
    root_cause_class: RootCauseClass
    summary: str
    evidence: list[Evidence]
    recommended_action: Action
    confidence: float = Field(ge=0.0, le=1.0)


class Decision(BaseModel):
    action: Action
    requires_human: bool
    diagnosis: Diagnosis
    reason: str
