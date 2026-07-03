# Plan 4: Agent Runtime — Orchestration Core + Live Adapters — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the agent runtime that turns an incoming alert into a diagnosis, a gated decision, and an executed response (rollback + report, or escalation), wiring the Plan 2 decision core to the outside world. Tasks 1–6 are the **hermetic orchestration core** (no GCP, no Gemini, fully testable now). Tasks 7–10 are the **live adapters** (Gemini diagnoser, GCP telemetry, Cloud Run rollback, live Slack) that require billing + credentials and are implemented when those land.

**Architecture:** Continue ports-and-adapters. New pure modules — `prompting`, `parsing`, `messages`, `response`, `alerts`, `server` — depend only on the Plan 2 domain/ports and on each other. The Gemini diagnoser, GCP telemetry provider, Cloud Run executor, and httpx Slack notifier are adapters behind the `Diagnoser`, `TelemetryProvider`, `ActionExecutor`, and `Notifier` ports; the orchestration core never imports an SDK. The FastAPI `create_app(deps)` factory mirrors `src/shop/app.py`: dependencies hang off `app.state` so tests inject fakes.

**Tech Stack:** Python 3.12+ (CI on 3.14), Pydantic v2, FastAPI, pytest + FastAPI TestClient (httpx), ruff, pyright (strict). Live adapters (Tasks 7–10): `google-genai`/Vertex AI SDK, Google Cloud client libraries, httpx — added to dependencies only when those tasks begin.

## Global Constraints

- Python 3.12+ runtime; developed/CI-tested on Python 3.14. All `src/` code must type-check under **pyright strict** with NO global rule disables for `src/` (per-line `# type: ignore[...]`/`# pyright: ignore[...]` allowed where justified; the existing `tests/`-scoped `executionEnvironments` relaxation stands). FastAPI route handlers registered by decorator carry `# type: ignore[misc]` exactly as `src/shop/app.py` does.
- **ruff** must pass on `src/` and `tests/` (`select = ["E", "F", "I", "UP", "B"]`, line-length 100).
- **TDD**: failing test first, then minimal implementation.
- **Fail toward escalation everywhere**: unparseable model output, missing telemetry, or any uncertainty resolves to `ESCALATE`/`UNKNOWN` with low confidence — never to an autonomous mutation.
- **Execution safety invariant**: `respond()` may invoke the `ActionExecutor` **only** when `Decision.action is Action.ROLLBACK`. `ESCALATE` and `NOOP` must never touch the executor. A test pins this.
- No GCP/Gemini/ADK SDK imports in Tasks 1–6. Those appear only in Tasks 7–10.
- Absolute imports rooted at `src/`. New modules live at `src/sentinel/`.

## File Structure

- `src/sentinel/parsing.py` — `parse_diagnosis(raw: str) -> Diagnosis` (validates model JSON; safe escalation fallback).
- `src/sentinel/prompting.py` — `build_diagnosis_prompt(incident, snapshot) -> str`.
- `src/sentinel/messages.py` — `format_escalation`, `format_action_report`, `format_observation` (pure Slack text).
- `src/sentinel/response.py` — `RollbackOutcome`, `ActionExecutor`/`Notifier` protocols, `FakeActionExecutor`/`FakeNotifier`, `ResponseRecord`, `respond(...)`.
- `src/sentinel/alerts.py` — `decode_push_envelope(body) -> dict`, `parse_alert(payload) -> Incident`.
- `src/sentinel/server.py` — `SentinelDeps`, `create_app(deps) -> FastAPI` with `/healthz` and `POST /pubsub/push`.
- Tests: `tests/sentinel/test_parsing.py`, `test_prompting.py`, `test_messages.py`, `test_response.py`, `test_alerts.py`, `test_server.py`.
- **Deferred (Tasks 7–10):** `src/sentinel/adapters/gemini_diagnoser.py`, `adapters/gcp_telemetry.py`, `adapters/cloud_run.py`, `adapters/slack.py`.

---

### Task 1: Diagnosis output parser (fail toward escalation)

**Files:**
- Create: `src/sentinel/parsing.py`
- Test: `tests/sentinel/test_parsing.py`

**Interfaces:**
- Consumes: `Action`, `Diagnosis`, `Evidence`, `RootCauseClass` from `sentinel.domain`.
- Produces: `parse_diagnosis(raw: str) -> Diagnosis`. Strips a leading/trailing Markdown code fence if present, then `Diagnosis.model_validate_json`. On any `ValidationError`/`ValueError` (bad JSON, out-of-range confidence, missing field) returns the fallback `Diagnosis(root_cause_class=UNKNOWN, summary="unparseable model output; escalating", evidence=[Evidence(source="parser", detail=<reason>)], recommended_action=ESCALATE, confidence=0.0)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_parsing.py
from sentinel.domain import Action, RootCauseClass
from sentinel.parsing import parse_diagnosis

VALID = (
    '{"root_cause_class": "code_regression", "summary": "NPE after deploy",'
    ' "evidence": [{"source": "logs", "detail": "TypeError"}],'
    ' "recommended_action": "rollback", "confidence": 0.91}'
)


def test_parses_valid_json() -> None:
    d = parse_diagnosis(VALID)
    assert d.root_cause_class is RootCauseClass.CODE_REGRESSION
    assert d.recommended_action is Action.ROLLBACK
    assert d.confidence == 0.91


def test_strips_markdown_code_fence() -> None:
    fenced = "```json\n" + VALID + "\n```"
    d = parse_diagnosis(fenced)
    assert d.recommended_action is Action.ROLLBACK


def test_garbage_falls_back_to_escalation() -> None:
    d = parse_diagnosis("not json at all")
    assert d.root_cause_class is RootCauseClass.UNKNOWN
    assert d.recommended_action is Action.ESCALATE
    assert d.confidence == 0.0


def test_out_of_range_confidence_falls_back_to_escalation() -> None:
    bad = VALID.replace("0.91", "1.7")
    d = parse_diagnosis(bad)
    assert d.recommended_action is Action.ESCALATE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_parsing.py -v`
Expected: FAIL (No module named 'sentinel.parsing').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/parsing.py
from pydantic import ValidationError

from sentinel.domain import Action, Diagnosis, Evidence, RootCauseClass


def _escalation_fallback(reason: str) -> Diagnosis:
    return Diagnosis(
        root_cause_class=RootCauseClass.UNKNOWN,
        summary="unparseable model output; escalating",
        evidence=[Evidence(source="parser", detail=reason)],
        recommended_action=Action.ESCALATE,
        confidence=0.0,
    )


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -len("```")]
        # drop a leading "json" hint left after removing the opening fence line
        text = text.strip()
    return text


def parse_diagnosis(raw: str) -> Diagnosis:
    text = _strip_fence(raw)
    try:
        return Diagnosis.model_validate_json(text)
    except (ValidationError, ValueError) as exc:
        return _escalation_fallback(str(exc).splitlines()[0][:200])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_parsing.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/parsing.py tests/sentinel/test_parsing.py
git commit -m "feat(sentinel): diagnosis output parser with escalation fallback"
```

---

### Task 2: Diagnosis prompt builder

**Files:**
- Create: `src/sentinel/prompting.py`
- Test: `tests/sentinel/test_prompting.py`

**Interfaces:**
- Consumes: `Incident` from `sentinel.domain`; `RootCauseClass`, `Action` from `sentinel.domain`; `TelemetrySnapshot` from `sentinel.telemetry`.
- Produces: `build_diagnosis_prompt(incident: Incident, snapshot: TelemetrySnapshot) -> str`. The prompt embeds the incident, every log line (`severity: message`), the metrics, the revisions, the full `RootCauseClass` taxonomy and `Action` options, an instruction to emit strict JSON matching the `Diagnosis` schema, and the safety directive: if evidence is thin or the incident touches security/privacy/PII/payments, recommend `escalate` with low confidence.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_prompting.py
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
    # every root-cause class value is offered to the model
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_prompting.py -v`
Expected: FAIL (No module named 'sentinel.prompting').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/prompting.py
from sentinel.domain import Action, Incident, RootCauseClass
from sentinel.telemetry import TelemetrySnapshot


def build_diagnosis_prompt(incident: Incident, snapshot: TelemetrySnapshot) -> str:
    logs = "\n".join(f"  {e.severity}: {e.message}" for e in snapshot.logs) or "  (none)"
    metrics = "\n".join(f"  {k}={v}" for k, v in snapshot.metrics.items()) or "  (none)"
    revisions = ", ".join(snapshot.revisions) or "(none)"
    classes = ", ".join(rc.value for rc in RootCauseClass)
    actions = ", ".join(a.value for a in Action)
    return (
        "You are Sentinel, an SRE diagnosis engine. Read the incident evidence and "
        "classify the root cause.\n\n"
        f"INCIDENT\n  service: {incident.service}\n  alert: {incident.alert}\n"
        f"  triggered_at: {incident.triggered_at}\n\n"
        f"LOGS\n{logs}\n\n"
        f"METRICS\n{metrics}\n\n"
        f"REVISIONS (newest first)\n  {revisions}\n\n"
        f"ROOT CAUSE CLASSES\n  {classes}\n\n"
        f"ACTIONS\n  {actions}\n\n"
        "Respond with STRICT JSON only, matching this schema: "
        '{"root_cause_class": <class>, "summary": <str>, '
        '"evidence": [{"source": <str>, "detail": <str>}], '
        '"recommended_action": <action>, "confidence": <0.0-1.0>}.\n\n'
        "SAFETY RULES\n"
        "  - If the evidence is thin or you are uncertain, recommend 'escalate' "
        "and set a low confidence.\n"
        "  - If the incident touches security, privacy, PII, payments, or legal "
        "concerns, recommend 'escalate' regardless of confidence; never recommend "
        "an autonomous rollback for those.\n"
        "  - Only recommend 'rollback' for a routine code regression in a recent "
        "revision where rolling back is clearly the safe, low-blast-radius remedy.\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_prompting.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/prompting.py tests/sentinel/test_prompting.py
git commit -m "feat(sentinel): diagnosis prompt builder with safety directives"
```

---

### Task 3: Slack message formatting

**Files:**
- Create: `src/sentinel/messages.py`
- Test: `tests/sentinel/test_messages.py`

**Interfaces:**
- Consumes: `Decision`, `Incident` from `sentinel.domain`; `RollbackOutcome` from `sentinel.response` — **defined in Task 4**. To keep Task 3 self-contained and before Task 4, `format_action_report` takes the three primitive fields it needs (`recovered: bool`, `from_revision: str`, `to_revision: str`) rather than the `RollbackOutcome` object.
- Produces:
  - `format_escalation(incident: Incident, decision: Decision) -> str` — a human escalation with root cause, recommended action, confidence, and the decision reason.
  - `format_action_report(incident: Incident, decision: Decision, recovered: bool, from_revision: str, to_revision: str) -> str` — an autonomous-rollback report.
  - `format_observation(incident: Incident, decision: Decision) -> str` — a low-key no-op note.
  - All are ASCII-only (cross-OS console safety, per Plan 3).

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_messages.py
from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)
from sentinel.messages import format_action_report, format_escalation, format_observation


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")


def _decision(action: Action, rc: RootCauseClass, requires_human: bool, reason: str) -> Decision:
    diag = Diagnosis(
        root_cause_class=rc,
        summary="s",
        evidence=[Evidence(source="logs", detail="d")],
        recommended_action=action,
        confidence=0.9,
    )
    return Decision(action=action, requires_human=requires_human, diagnosis=diag, reason=reason)


def test_escalation_mentions_service_cause_and_reason() -> None:
    d = _decision(Action.ESCALATE, RootCauseClass.PII_EXPOSURE, True, "root cause is sensitive")
    msg = format_escalation(_incident(), d)
    assert "shop" in msg
    assert "pii_exposure" in msg
    assert "sensitive" in msg
    assert msg.isascii()


def test_action_report_states_rollback_and_recovery() -> None:
    d = _decision(Action.ROLLBACK, RootCauseClass.CODE_REGRESSION, False, "autonomous rollback")
    msg = format_action_report(_incident(), d, recovered=True, from_revision="shop-2", to_revision="shop-1")
    assert "rollback" in msg.lower()
    assert "shop-2" in msg and "shop-1" in msg
    assert "recover" in msg.lower()
    assert msg.isascii()


def test_observation_is_noop_note() -> None:
    d = _decision(Action.NOOP, RootCauseClass.TRANSIENT_BLIP, False, "no action needed")
    msg = format_observation(_incident(), d)
    assert "shop" in msg
    assert msg.isascii()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_messages.py -v`
Expected: FAIL (No module named 'sentinel.messages').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/messages.py
from sentinel.domain import Decision, Incident


def _header(incident: Incident, decision: Decision) -> str:
    d = decision.diagnosis
    return (
        f"service: {incident.service} | alert: {incident.alert}\n"
        f"root cause: {d.root_cause_class.value} (confidence {d.confidence:.2f})\n"
        f"summary: {d.summary}"
    )


def format_escalation(incident: Incident, decision: Decision) -> str:
    return (
        "[ESCALATION] Sentinel needs a human.\n"
        f"{_header(incident, decision)}\n"
        f"recommended action: {decision.diagnosis.recommended_action.value}\n"
        f"reason: {decision.reason}"
    )


def format_action_report(
    incident: Incident,
    decision: Decision,
    recovered: bool,
    from_revision: str,
    to_revision: str,
) -> str:
    status = "recovery confirmed" if recovered else "recovery NOT confirmed"
    return (
        "[AUTONOMOUS ROLLBACK] Sentinel acted.\n"
        f"{_header(incident, decision)}\n"
        f"rolled back traffic: {from_revision} -> {to_revision}\n"
        f"post-rollback: {status}\n"
        f"reason: {decision.reason}"
    )


def format_observation(incident: Incident, decision: Decision) -> str:
    return (
        "[OBSERVE] Sentinel took no action.\n"
        f"{_header(incident, decision)}\n"
        f"reason: {decision.reason}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_messages.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/messages.py tests/sentinel/test_messages.py
git commit -m "feat(sentinel): slack message formatting for escalation/action/observe"
```

---

### Task 4: Response orchestration (ports + respond)

**Files:**
- Create: `src/sentinel/response.py`
- Test: `tests/sentinel/test_response.py`

**Interfaces:**
- Consumes: `Action`, `Decision`, `Incident` from `sentinel.domain`; `format_action_report`, `format_escalation`, `format_observation` from `sentinel.messages`.
- Produces:
  - `RollbackOutcome(BaseModel)`: `success: bool`, `from_revision: str`, `to_revision: str`, `recovered: bool`, `detail: str`.
  - `ActionExecutor(Protocol)`: `rollback(self, service: str) -> RollbackOutcome`.
  - `Notifier(Protocol)`: `notify(self, message: str) -> None`.
  - `FakeActionExecutor`: records `rollback_calls: list[str]`; returns a canned `RollbackOutcome` (default success, `shop-2 -> shop-1`, recovered True).
  - `FakeNotifier`: records `messages: list[str]`.
  - `ResponseRecord(BaseModel)`: `action: Action`, `executed: bool`, `notified: bool`, `message: str`, `rollback: RollbackOutcome | None`.
  - `respond(incident: Incident, decision: Decision, executor: ActionExecutor, notifier: Notifier) -> ResponseRecord` — `ROLLBACK` calls `executor.rollback` then posts the action report (`executed=True`); `ESCALATE` posts the escalation (`executed=False`, executor untouched); `NOOP` posts the observation (`executed=False`, executor untouched); exhaustive with `assert_never`.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_response.py
from sentinel.domain import (
    Action,
    Decision,
    Diagnosis,
    Evidence,
    Incident,
    RootCauseClass,
)
from sentinel.response import FakeActionExecutor, FakeNotifier, respond


def _incident() -> Incident:
    return Incident(service="shop", alert="slo_breach", triggered_at="2026-06-29T00:00:00Z")


def _decision(action: Action, requires_human: bool) -> Decision:
    diag = Diagnosis(
        root_cause_class=RootCauseClass.CODE_REGRESSION,
        summary="s",
        evidence=[Evidence(source="logs", detail="d")],
        recommended_action=action,
        confidence=0.9,
    )
    return Decision(action=action, requires_human=requires_human, diagnosis=diag, reason="r")


def test_rollback_executes_and_reports() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ROLLBACK, False), ex, no)
    assert rec.executed is True
    assert ex.rollback_calls == ["shop"]
    assert rec.rollback is not None
    assert len(no.messages) == 1
    assert "ROLLBACK" in no.messages[0]


def test_escalate_never_touches_executor() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.ESCALATE, True), ex, no)
    assert rec.executed is False
    assert ex.rollback_calls == []
    assert "ESCALATION" in no.messages[0]


def test_noop_never_touches_executor() -> None:
    ex, no = FakeActionExecutor(), FakeNotifier()
    rec = respond(_incident(), _decision(Action.NOOP, False), ex, no)
    assert rec.executed is False
    assert ex.rollback_calls == []
    assert "OBSERVE" in no.messages[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_response.py -v`
Expected: FAIL (No module named 'sentinel.response').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/response.py
from typing import Protocol, assert_never

from pydantic import BaseModel

from sentinel.domain import Action, Decision, Incident
from sentinel.messages import format_action_report, format_escalation, format_observation


class RollbackOutcome(BaseModel):
    success: bool
    from_revision: str
    to_revision: str
    recovered: bool
    detail: str


class ActionExecutor(Protocol):
    def rollback(self, service: str) -> RollbackOutcome: ...


class Notifier(Protocol):
    def notify(self, message: str) -> None: ...


class FakeActionExecutor:
    def __init__(self, outcome: RollbackOutcome | None = None) -> None:
        self.rollback_calls: list[str] = []
        self._outcome = outcome or RollbackOutcome(
            success=True,
            from_revision="shop-2",
            to_revision="shop-1",
            recovered=True,
            detail="fake rollback",
        )

    def rollback(self, service: str) -> RollbackOutcome:
        self.rollback_calls.append(service)
        return self._outcome


class FakeNotifier:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)


class ResponseRecord(BaseModel):
    action: Action
    executed: bool
    notified: bool
    message: str
    rollback: RollbackOutcome | None


def respond(
    incident: Incident,
    decision: Decision,
    executor: ActionExecutor,
    notifier: Notifier,
) -> ResponseRecord:
    match decision.action:
        case Action.ROLLBACK:
            outcome = executor.rollback(incident.service)
            message = format_action_report(
                incident,
                decision,
                recovered=outcome.recovered,
                from_revision=outcome.from_revision,
                to_revision=outcome.to_revision,
            )
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=True,
                notified=True,
                message=message,
                rollback=outcome,
            )
        case Action.ESCALATE:
            message = format_escalation(incident, decision)
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=True,
                message=message,
                rollback=None,
            )
        case Action.NOOP:
            message = format_observation(incident, decision)
            notifier.notify(message)
            return ResponseRecord(
                action=decision.action,
                executed=False,
                notified=True,
                message=message,
                rollback=None,
            )
        case _ as unreachable:
            assert_never(unreachable)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_response.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/response.py tests/sentinel/test_response.py
git commit -m "feat(sentinel): response orchestration with executor/notifier ports"
```

---

### Task 5: Alert envelope decoding and parsing

**Files:**
- Create: `src/sentinel/alerts.py`
- Test: `tests/sentinel/test_alerts.py`

**Interfaces:**
- Consumes: `Incident` from `sentinel.domain`.
- Produces:
  - `decode_push_envelope(body: dict[str, object]) -> dict[str, object]` — reads `body["message"]["data"]` (a base64 string), base64-decodes, `json.loads`, returns the payload dict. Raises `ValueError` if the envelope or data is missing/malformed.
  - `parse_alert(payload: dict[str, object]) -> Incident` — extracts the service from `payload["incident"]["resource"]["labels"]["service_name"]` (falling back to a top-level `"service"` key), the alert from `incident["condition_name"]` (falling back to `"policy_name"`, then `"slo_breach"`), and `triggered_at` from `incident["started_at"]` (stringified) falling back to `"unknown"`. Raises `ValueError` if no service can be determined.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_alerts.py
import base64
import json

import pytest

from sentinel.alerts import decode_push_envelope, parse_alert


def _envelope(payload: dict[str, object]) -> dict[str, object]:
    data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"message": {"data": data}, "subscription": "sub"}


def test_decode_round_trips_payload() -> None:
    payload = {"incident": {"resource": {"labels": {"service_name": "shop"}}}}
    assert decode_push_envelope(_envelope(payload)) == payload


def test_decode_rejects_missing_message() -> None:
    with pytest.raises(ValueError):
        decode_push_envelope({"subscription": "sub"})


def test_parse_alert_extracts_service_and_alert() -> None:
    payload = {
        "incident": {
            "resource": {"labels": {"service_name": "shop"}},
            "condition_name": "error_rate_high",
            "started_at": 1751155200,
        }
    }
    incident = parse_alert(payload)
    assert incident.service == "shop"
    assert incident.alert == "error_rate_high"
    assert incident.triggered_at == "1751155200"


def test_parse_alert_falls_back_to_top_level_service() -> None:
    incident = parse_alert({"service": "shop"})
    assert incident.service == "shop"
    assert incident.alert == "slo_breach"


def test_parse_alert_without_service_raises() -> None:
    with pytest.raises(ValueError):
        parse_alert({"incident": {"resource": {"labels": {}}}})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_alerts.py -v`
Expected: FAIL (No module named 'sentinel.alerts').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/alerts.py
import base64
import binascii
import json

from sentinel.domain import Incident


def decode_push_envelope(body: dict[str, object]) -> dict[str, object]:
    message = body.get("message")
    if not isinstance(message, dict):
        raise ValueError("push envelope missing 'message' object")
    data = message.get("data")
    if not isinstance(data, str):
        raise ValueError("push envelope missing 'message.data'")
    try:
        decoded = base64.b64decode(data, validate=True)
        payload = json.loads(decoded)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"malformed push data: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("push data is not a JSON object")
    return payload


def _incident_block(payload: dict[str, object]) -> dict[str, object]:
    incident = payload.get("incident")
    return incident if isinstance(incident, dict) else {}


def parse_alert(payload: dict[str, object]) -> Incident:
    incident = _incident_block(payload)
    resource = incident.get("resource")
    labels = resource.get("labels") if isinstance(resource, dict) else None
    service: object = None
    if isinstance(labels, dict):
        service = labels.get("service_name")
    if not isinstance(service, str) or not service:
        top = payload.get("service")
        service = top if isinstance(top, str) and top else None
    if not isinstance(service, str) or not service:
        raise ValueError("alert payload has no resolvable service")

    alert = incident.get("condition_name") or incident.get("policy_name") or "slo_breach"
    started = incident.get("started_at")
    triggered_at = str(started) if started is not None else "unknown"
    return Incident(service=service, alert=str(alert), triggered_at=triggered_at)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_alerts.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/alerts.py tests/sentinel/test_alerts.py
git commit -m "feat(sentinel): pub/sub push envelope decode and alert parsing"
```

---

### Task 6: FastAPI event endpoint wiring the pipeline to the response

**Files:**
- Create: `src/sentinel/server.py`
- Test: `tests/sentinel/test_server.py`

**Interfaces:**
- Consumes: `Incident` from `sentinel.domain`; `Diagnoser` from `sentinel.diagnoser`; `TelemetryProvider` from `sentinel.telemetry`; `PolicyGate` from `sentinel.policy`; `DecisionPipeline` from `sentinel.pipeline`; `ActionExecutor`, `Notifier`, `respond` from `sentinel.response`; `decode_push_envelope`, `parse_alert` from `sentinel.alerts`.
- Produces:
  - `SentinelDeps` (a plain dataclass): `telemetry: TelemetryProvider`, `diagnoser: Diagnoser`, `gate: PolicyGate`, `executor: ActionExecutor`, `notifier: Notifier`.
  - `create_app(deps: SentinelDeps) -> FastAPI`. Routes: `GET /healthz -> {"status": "ok"}`; `POST /pubsub/push` reads the raw JSON body, `decode_push_envelope` + `parse_alert` (→ `400` on `ValueError`), runs `DecisionPipeline(deps...).run(incident)`, then `respond(...)`, returning `200` with `{"action": <value>, "requires_human": <bool>, "executed": <bool>}`.
  - **Ack semantics note:** a malformed envelope returns `400`. In production Pub/Sub would redeliver; a follow-up task can switch permanent-parse-failures to `204` (ack-and-drop) once we observe behavior. For the MVP and tests, `400` makes the failure visible.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_server.py
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
    payload = {"incident": {"resource": {"labels": {"service_name": service}}, "condition_name": "x"}}
    data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"message": {"data": data}}


def test_healthz() -> None:
    deps, _, _ = _deps(_diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95))
    client = TestClient(create_app(deps))
    assert client.get("/healthz").json() == {"status": "ok"}


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_server.py -v`
Expected: FAIL (No module named 'sentinel.server').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/server.py
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request

from sentinel.alerts import decode_push_envelope, parse_alert
from sentinel.diagnoser import Diagnoser
from sentinel.pipeline import DecisionPipeline
from sentinel.policy import PolicyGate
from sentinel.response import ActionExecutor, Notifier, respond
from sentinel.telemetry import TelemetryProvider


@dataclass
class SentinelDeps:
    telemetry: TelemetryProvider
    diagnoser: Diagnoser
    gate: PolicyGate
    executor: ActionExecutor
    notifier: Notifier


def create_app(deps: SentinelDeps) -> FastAPI:
    app = FastAPI()
    app.state.deps = deps
    pipeline = DecisionPipeline(deps.telemetry, deps.diagnoser, deps.gate)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"status": "ok"}

    @app.post("/pubsub/push")
    async def push(request: Request) -> dict[str, object]:  # type: ignore[misc]  # decorator side-effect
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="body must be a JSON object")
        try:
            payload = decode_push_envelope(body)
            incident = parse_alert(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        decision = pipeline.run(incident)
        record = respond(incident, decision, deps.executor, deps.notifier)
        return {
            "action": decision.action.value,
            "requires_human": decision.requires_human,
            "executed": record.executed,
        }

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_server.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v && python -m pyright && python -m ruff check .`
Expected: ALL green; pyright 0 errors; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/sentinel/server.py tests/sentinel/test_server.py
git commit -m "feat(sentinel): fastapi pub/sub push endpoint wiring pipeline to response"
```

---

## Hermetic core Done-When (Tasks 1–6)

- `python -m pytest -v` fully green; `python -m pyright` 0 errors; `python -m ruff check .` clean.
- An alert envelope POSTed to `/pubsub/push` flows end-to-end through decode → parse → diagnose (fake) → gate → decide → respond, producing an autonomous rollback on a routine high-confidence regression and an escalation (executor untouched) on a sensitive incident, entirely without GCP or Gemini.
- The execution-safety invariant is pinned: `respond()` calls the executor only on `ROLLBACK`.

---

## Tasks 7–10: Live adapters (require billing + credentials; implement when ADC is hot)

> These tasks import real SDKs and make network calls. **Before writing each, verify the current API via Context7** (`google-genai` / Vertex AI, the Cloud Run Admin API, Cloud Logging/Monitoring client libraries). Each adapter implements an existing port, so the orchestration core (Tasks 1–6) and the eval harness (Plan 3) consume it unchanged. Add the corresponding dependency to `pyproject.toml` only when its task begins.

### Task 7: `GeminiDiagnoser` (adapter for the `Diagnoser` port)
- `src/sentinel/adapters/gemini_diagnoser.py`: build the prompt via `build_diagnosis_prompt`, call Gemini on Vertex AI with a JSON response schema (the `Diagnosis` model), parse with `parse_diagnosis`. Bound the agentic loop by a max-iteration count per spec §6. Inject the model client so a fake transport unit-tests prompt-in/Diagnosis-out without billing; the live call is exercised in the eval gate once credentials are hot. Then swap `HeuristicDiagnoser` for `GeminiDiagnoser` in `eval_cli.run()` and record the new scorecard (`v0.2.0`), proving measurable improvement with unsafe held at 0.

### Task 8: `GcpTelemetryProvider` (adapter for the `TelemetryProvider` port)
- `src/sentinel/adapters/gcp_telemetry.py`: implement `snapshot(service)` over Cloud Logging (recent error logs), Cloud Monitoring (error_rate, p95 latency), and the Cloud Run Admin API (revision list). Unit-test with mocked clients; integration-test against the live `shop` service once deployed.

### Task 9: `CloudRunRollbackExecutor` (adapter for the `ActionExecutor` port) + live `SlackNotifier`
- `src/sentinel/adapters/cloud_run.py`: `rollback(service)` shifts 100% traffic to the previous ready revision via the Cloud Run Admin API, waits, re-reads metrics to populate `recovered`. Scope the service account to the `shop` service only, per spec §5.
- `src/sentinel/adapters/slack.py`: `notify(message)` POSTs to the webhook (from Secret Manager / `.env`) via httpx. Unit-test by mocking the HTTP client.

### Task 10: Production wiring + deploy
- A `main` entrypoint constructs `SentinelDeps` from real adapters using env config (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_REGION`, `SLACK_WEBHOOK_URL`), serves `create_app(deps)` under uvicorn, containerizes, and deploys to Cloud Run as the `sentinel` service. Then connect the Monitoring alert policy → Pub/Sub topic → authenticated push subscription targeting `/pubsub/push`, per spec §6 and the §11 release pipeline.
