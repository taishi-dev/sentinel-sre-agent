from sentinel.adapters.gemini_diagnoser import GeminiDiagnoser
from sentinel.domain import Action, Incident, RootCauseClass
from sentinel.scenario import StaticTelemetryProvider
from sentinel.telemetry import LogEntry, TelemetrySnapshot

VALID = (
    '{"root_cause_class": "code_regression", "summary": "NPE after deploy",'
    ' "evidence": [{"source": "logs", "detail": "TypeError"}],'
    ' "recommended_action": "rollback", "confidence": 0.9}'
)


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")


def test_builds_prompt_from_telemetry_and_parses_response() -> None:
    captured: dict[str, str] = {}

    def fake_generate(prompt: str) -> str:
        captured["prompt"] = prompt
        return VALID

    snap = TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="TypeError boom")],
        metrics={"error_rate": 0.4},
        revisions=["shop-2", "shop-1"],
    )
    result = GeminiDiagnoser(fake_generate).diagnose(_incident(), StaticTelemetryProvider(snap))

    assert result.root_cause_class is RootCauseClass.CODE_REGRESSION
    assert result.recommended_action is Action.ROLLBACK
    assert "TypeError boom" in captured["prompt"]


def test_garbage_response_escalates() -> None:
    snap = TelemetrySnapshot(logs=[], metrics={"error_rate": 0.4}, revisions=[])
    result = GeminiDiagnoser(lambda _p: "not json").diagnose(
        _incident(), StaticTelemetryProvider(snap)
    )
    assert result.recommended_action is Action.ESCALATE
