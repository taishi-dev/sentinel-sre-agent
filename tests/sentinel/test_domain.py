import pytest
from pydantic import ValidationError

from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)


def test_enum_values() -> None:
    assert RootCauseClass.CODE_REGRESSION.value == "code_regression"
    assert RootCauseClass.PII_EXPOSURE.value == "pii_exposure"
    assert Action.ROLLBACK.value == "rollback"
    assert Action.ESCALATE.value == "escalate"
    assert Action.NOOP.value == "noop"


def test_diagnosis_roundtrip() -> None:
    d = Diagnosis(
        root_cause_class=RootCauseClass.CODE_REGRESSION,
        summary="NPE in checkout after deploy",
        evidence=[Evidence(source="logs", detail="NullPointer in finalize()")],
        recommended_action=Action.ROLLBACK,
        confidence=0.92,
    )
    assert d.recommended_action is Action.ROLLBACK
    assert d.evidence[0].source == "logs"
    # JSON round-trip preserves enum values
    reparsed = Diagnosis.model_validate_json(d.model_dump_json())
    assert reparsed == d


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        Diagnosis(
            root_cause_class=RootCauseClass.UNKNOWN,
            summary="x",
            evidence=[],
            recommended_action=Action.ESCALATE,
            confidence=1.5,
        )


def test_incident_and_decision_construct() -> None:
    incident = Incident(
        service="shop", alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z"
    )
    diag = Diagnosis(
        root_cause_class=RootCauseClass.TRANSIENT_BLIP,
        summary="brief spike, recovered",
        evidence=[],
        recommended_action=Action.NOOP,
        confidence=0.7,
    )
    decision = Decision(
        action=Action.NOOP,
        requires_human=False,
        diagnosis=diag,
        reason="self-healed",
    )
    assert decision.action is Action.NOOP
    assert decision.requires_human is False
    assert incident.service == "shop"
