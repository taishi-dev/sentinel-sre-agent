from pathlib import Path

from sentinel.diagnoser import FakeDiagnoser
from sentinel.domain import Action, Diagnosis, Evidence, Incident, RootCauseClass
from sentinel.telemetry import FixtureTelemetryProvider

FIXTURES = Path(__file__).parent / "fixtures"


def test_fake_diagnoser_returns_canned_and_records_service() -> None:
    canned = Diagnosis(
        root_cause_class=RootCauseClass.CODE_REGRESSION,
        summary="NPE after deploy",
        evidence=[Evidence(source="logs", detail="NullPointer")],
        recommended_action=Action.ROLLBACK,
        confidence=0.9,
    )
    diagnoser = FakeDiagnoser(canned)
    provider = FixtureTelemetryProvider(FIXTURES / "code_regression.json")
    incident = Incident(
        service="shop",
        alert="error_rate_spike",
        triggered_at="2026-06-28T00:00:00Z",
    )

    result = diagnoser.diagnose(incident, provider)

    assert result is canned
    assert diagnoser.last_service == "shop"
