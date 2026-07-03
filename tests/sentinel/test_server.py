import base64
import json

from fastapi.testclient import TestClient

from sentinel.diagnoser import FakeDiagnoser
from sentinel.domain import Action, Diagnosis, Evidence, RootCauseClass
from sentinel.policy import PolicyConfig, PolicyGate
from sentinel.response import FakeActionExecutor, FakeNotifier
from sentinel.scenario import StaticTelemetryProvider
from sentinel.server import SentinelDeps, create_app
from sentinel.telemetry import LogEntry, TelemetrySnapshot


def _snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        logs=[LogEntry(severity="ERROR", message="TypeError")],
        metrics={"error_rate": 0.4},
        revisions=["shop-2", "shop-1"],
    )


def _diag(rc: RootCauseClass, action: Action, confidence: float) -> Diagnosis:
    return Diagnosis(
        root_cause_class=rc,
        summary="s",
        evidence=[Evidence(source="logs", detail="d")],
        recommended_action=action,
        confidence=confidence,
    )


def _gate() -> PolicyGate:
    return PolicyGate(
        PolicyConfig(
            autonomous_eligible_services=["shop"],
            autonomous_eligible_root_causes=[
                RootCauseClass.CODE_REGRESSION,
                RootCauseClass.TRANSIENT_BLIP,
                RootCauseClass.RUNTIME_MISMATCH,
            ],
            sensitive_root_causes=[RootCauseClass.SECURITY_REGRESSION, RootCauseClass.PII_EXPOSURE],
            min_confidence=0.8,
        )
    )


def _deps(diag: Diagnosis) -> tuple[SentinelDeps, FakeActionExecutor, FakeNotifier]:
    ex, no = FakeActionExecutor(), FakeNotifier()
    deps = SentinelDeps(
        telemetry=StaticTelemetryProvider(_snapshot()),
        diagnoser=FakeDiagnoser(diag),
        gate=_gate(),
        executor=ex,
        notifier=no,
    )
    return deps, ex, no


def _push_body(service: str = "shop") -> dict[str, object]:
    payload = {
        "incident": {"resource": {"labels": {"service_name": service}}, "condition_name": "x"}
    }
    data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"message": {"data": data}}


def test_health() -> None:
    deps, _, _ = _deps(_diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95))
    client = TestClient(create_app(deps))
    assert client.get("/health").json() == {"status": "ok"}


def test_push_routine_regression_triggers_autonomous_rollback() -> None:
    deps, ex, no = _deps(_diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95))
    client = TestClient(create_app(deps))
    resp = client.post("/pubsub/push", json=_push_body())
    assert resp.status_code == 200
    assert resp.json()["action"] == Action.ROLLBACK.value
    assert resp.json()["executed"] is True
    assert ex.rollback_calls == ["shop"]
    assert len(no.messages) == 1


def test_push_sensitive_incident_escalates_without_acting() -> None:
    deps, ex, no = _deps(_diag(RootCauseClass.PII_EXPOSURE, Action.ROLLBACK, 0.99))
    client = TestClient(create_app(deps))
    resp = client.post("/pubsub/push", json=_push_body())
    assert resp.status_code == 200
    assert resp.json()["action"] == Action.ESCALATE.value
    assert resp.json()["executed"] is False
    assert ex.rollback_calls == []
    assert "ESCALATION" in no.messages[0]


def test_push_malformed_envelope_returns_400() -> None:
    deps, _, _ = _deps(_diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95))
    client = TestClient(create_app(deps))
    assert client.post("/pubsub/push", json={"nope": 1}).status_code == 400
