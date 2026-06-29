from sentinel.domain import Action, Diagnosis, Evidence, Incident, RootCauseClass
from sentinel.policy import PolicyConfig, PolicyGate


def _incident(service: str = "shop") -> Incident:
    return Incident(service=service, alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z")


def _diag(rc: RootCauseClass) -> Diagnosis:
    return Diagnosis(
        root_cause_class=rc,
        summary="x",
        evidence=[Evidence(source="logs", detail="y")],
        recommended_action=Action.ROLLBACK,
        confidence=0.95,
    )


def _gate() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            autonomous_eligible_services=["shop"],
            sensitive_root_causes=[RootCauseClass.SECURITY_REGRESSION, RootCauseClass.PII_EXPOSURE],
        )
    )


def test_allows_eligible_service_and_nonsensitive_cause() -> None:
    result = _gate().evaluate(_incident(), _diag(RootCauseClass.CODE_REGRESSION))
    assert result.allowed is True


def test_blocks_service_not_in_allowlist() -> None:
    result = _gate().evaluate(_incident("payments"), _diag(RootCauseClass.CODE_REGRESSION))
    assert result.allowed is False
    assert "allowlist" in result.reason.lower()


def test_blocks_sensitive_root_cause() -> None:
    result = _gate().evaluate(_incident(), _diag(RootCauseClass.PII_EXPOSURE))
    assert result.allowed is False
    assert "sensitive" in result.reason.lower()
