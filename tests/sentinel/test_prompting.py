from sentinel.domain import Incident, RootCauseClass
from sentinel.prompting import build_diagnosis_prompt
from sentinel.telemetry import LogEntry, TelemetrySnapshot


def _snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="TypeError in finalize")],
        metrics={"error_rate": 0.4},
        revisions=["shop-2", "shop-1"],
    )


def test_prompt_includes_evidence_and_taxonomy_and_json_instruction() -> None:
    incident = Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")
    prompt = build_diagnosis_prompt(incident, _snapshot())
    assert "TypeError in finalize" in prompt
    assert "error_rate" in prompt
    assert "shop-2" in prompt
    for rc in RootCauseClass:
        assert rc.value in prompt
    assert "JSON" in prompt
    assert "escalate" in prompt.lower()


def test_prompt_states_the_fail_toward_escalation_rule() -> None:
    incident = Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")
    prompt = build_diagnosis_prompt(incident, _snapshot())
    lowered = prompt.lower()
    assert "uncertain" in lowered or "thin" in lowered
    assert "security" in lowered and "pii" in lowered
