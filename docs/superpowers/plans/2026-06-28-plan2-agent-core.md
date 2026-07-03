# Plan 2: Agent Core (local, fixture-backed) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python, fully-testable decision core of the Sentinel agent — domain types, telemetry port, deterministic policy gate, diagnoser port, and the safety-critical decision pipeline — with no GCP, no Gemini, and no ADK, all behind interfaces that Plan 4 will implement with the real ADK + Gemini adapter.

**Architecture:** Ports-and-adapters. `src/sentinel/` holds: `domain.py` (Pydantic models + enums), `telemetry.py` (a `TelemetryProvider` Protocol + a `FixtureTelemetryProvider` reading JSON fixtures), `policy.py` (a deterministic `PolicyGate`), `diagnoser.py` (a `Diagnoser` Protocol + a `FakeDiagnoser` for tests), and `pipeline.py` (the `decide()` function and `DecisionPipeline` orchestration). The decision logic encodes the two-gate, fail-toward-escalation, downgrade-only safety model from the spec. The real ADK+Gemini `Diagnoser` and live GCP `TelemetryProvider` are deferred to Plan 4.

**Tech Stack:** Python 3.14, Pydantic v2, pytest, ruff, pyright (strict).

## Global Constraints

- Python 3.12+ runtime; developed/CI-tested on Python 3.14. All code must type-check under **pyright strict** with NO global rule disables for `src/` (per-line `# type: ignore[...]`/`# pyright: ignore[...]` allowed where justified; a `tests/`-scoped `executionEnvironments` relaxation already exists in `pyproject.toml`).
- **ruff** must pass on `src/` and `tests/`.
- **TDD**: failing test first, then minimal implementation.
- Structured output uses **Pydantic v2** models. The gate decision uses an `enum` and is guarded for exhaustiveness with `typing.assert_never`.
- **Fail toward escalation**: any uncertainty (low confidence, policy block, unknown class) must resolve to `ESCALATE`, never to an autonomous production-mutating action.
- **Downgrade-only**: the final action may only be equal to or more cautious than the diagnosis's recommended action; gates can never grant more autonomy than recommended.
- Absolute imports rooted at `src/` (e.g. `from sentinel.domain import ...`). New package lives at `src/sentinel/`.
- No GCP SDK, no Gemini SDK, no ADK imports anywhere in this plan.

---

### Task 1: Domain types

**Files:**
- Create: `src/sentinel/__init__.py` (empty)
- Create: `src/sentinel/domain.py`
- Create: `tests/sentinel/__init__.py` (empty)
- Test: `tests/sentinel/test_domain.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `RootCauseClass(str, Enum)`: `CODE_REGRESSION`, `DEPENDENCY_OUTAGE`, `CONFIG_DRIFT`, `SECURITY_REGRESSION`, `PII_EXPOSURE`, `RESOURCE_EXHAUSTION`, `BAD_MIGRATION`, `TRANSIENT_BLIP`, `COSMETIC`, `RUNTIME_MISMATCH`, `UNKNOWN` (values are the lowercase member names).
  - `Action(str, Enum)`: `ROLLBACK="rollback"`, `ESCALATE="escalate"`, `NOOP="noop"`.
  - `Incident(BaseModel)`: `service: str`, `alert: str`, `triggered_at: str`.
  - `Evidence(BaseModel)`: `source: str`, `detail: str`.
  - `Diagnosis(BaseModel)`: `root_cause_class: RootCauseClass`, `summary: str`, `evidence: list[Evidence]`, `recommended_action: Action`, `confidence: float` (validated 0.0–1.0).
  - `Decision(BaseModel)`: `action: Action`, `requires_human: bool`, `diagnosis: Diagnosis`, `reason: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_domain.py
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
    incident = Incident(service="shop", alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z")
    diag = Diagnosis(
        root_cause_class=RootCauseClass.TRANSIENT_BLIP,
        summary="brief spike, recovered",
        evidence=[],
        recommended_action=Action.NOOP,
        confidence=0.7,
    )
    decision = Decision(action=Action.NOOP, requires_human=False, diagnosis=diag, reason="self-healed")
    assert decision.action is Action.NOOP
    assert decision.requires_human is False
    assert incident.service == "shop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_domain.py -v`
Expected: FAIL (No module named 'sentinel.domain').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/domain.py
from enum import Enum

from pydantic import BaseModel, Field


class RootCauseClass(str, Enum):
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


class Action(str, Enum):
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
```

Note: ruff's `UP` rules may suggest `StrEnum`. Either `(str, Enum)` or `StrEnum` is acceptable as long as `.value` equals the lowercase string and pyright/ruff pass. If ruff flags it, use `from enum import StrEnum` and `class RootCauseClass(StrEnum)` / `class Action(StrEnum)` (matches the project's existing `FaultType` choice).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_domain.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/__init__.py src/sentinel/domain.py tests/sentinel/__init__.py tests/sentinel/test_domain.py
git commit -m "feat(sentinel): domain types (incident, diagnosis, decision, enums)"
```

---

### Task 2: Telemetry port and fixture provider

**Files:**
- Create: `src/sentinel/telemetry.py`
- Create: `tests/sentinel/fixtures/code_regression.json`
- Create: `tests/sentinel/fixtures/transient_blip.json`
- Test: `tests/sentinel/test_telemetry.py`

**Interfaces:**
- Consumes: nothing from prior tasks (uses its own `LogEntry`).
- Produces:
  - `LogEntry(BaseModel)`: `severity: str`, `message: str`.
  - `TelemetrySnapshot(BaseModel)`: `logs: list[LogEntry]`, `metrics: dict[str, float]`, `revisions: list[str]`.
  - `TelemetryProvider(Protocol)`: `snapshot(self, service: str) -> TelemetrySnapshot`.
  - `FixtureTelemetryProvider`: `__init__(self, fixture_path: Path)`; `snapshot(self, service: str) -> TelemetrySnapshot` returns the parsed fixture (ignores `service`, since a fixture represents one scenario for one service).

- [ ] **Step 1: Write the fixtures**

```json
// tests/sentinel/fixtures/code_regression.json
{
  "logs": [
    {"severity": "ERROR", "message": "NullPointer: order.total in CheckoutService.finalize()"},
    {"severity": "ERROR", "message": "NullPointer: order.total in CheckoutService.finalize()"}
  ],
  "metrics": {"error_rate": 0.42, "p95_latency_ms": 180.0},
  "revisions": ["shop-0008", "shop-0007"]
}
```

```json
// tests/sentinel/fixtures/transient_blip.json
{
  "logs": [
    {"severity": "WARNING", "message": "upstream timeout, retrying"}
  ],
  "metrics": {"error_rate": 0.03, "p95_latency_ms": 210.0},
  "revisions": ["shop-0007"]
}
```

Note: JSON does not allow `//` comments — the `// path` lines above are for the implementer's orientation only. Write valid JSON (the object starting at `{`), and name the files exactly as shown.

- [ ] **Step 2: Write the failing test**

```python
# tests/sentinel/test_telemetry.py
from pathlib import Path

from sentinel.telemetry import FixtureTelemetryProvider, TelemetrySnapshot

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_code_regression_fixture() -> None:
    provider = FixtureTelemetryProvider(FIXTURES / "code_regression.json")
    snap = provider.snapshot("shop")
    assert isinstance(snap, TelemetrySnapshot)
    assert snap.metrics["error_rate"] == 0.42
    assert snap.revisions == ["shop-0008", "shop-0007"]
    assert any("NullPointer" in entry.message for entry in snap.logs)


def test_loads_transient_fixture() -> None:
    provider = FixtureTelemetryProvider(FIXTURES / "transient_blip.json")
    snap = provider.snapshot("shop")
    assert snap.metrics["error_rate"] == 0.03
    assert len(snap.logs) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_telemetry.py -v`
Expected: FAIL (No module named 'sentinel.telemetry').

- [ ] **Step 4: Write the implementation**

```python
# src/sentinel/telemetry.py
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class LogEntry(BaseModel):
    severity: str
    message: str


class TelemetrySnapshot(BaseModel):
    logs: list[LogEntry]
    metrics: dict[str, float]
    revisions: list[str]


class TelemetryProvider(Protocol):
    def snapshot(self, service: str) -> TelemetrySnapshot: ...


class FixtureTelemetryProvider:
    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path

    def snapshot(self, service: str) -> TelemetrySnapshot:
        return TelemetrySnapshot.model_validate_json(self._fixture_path.read_text())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_telemetry.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/sentinel/telemetry.py tests/sentinel/fixtures/ tests/sentinel/test_telemetry.py
git commit -m "feat(sentinel): telemetry port and fixture-backed provider"
```

---

### Task 3: Deterministic policy gate

**Files:**
- Create: `src/sentinel/policy.py`
- Test: `tests/sentinel/test_policy.py`

**Interfaces:**
- Consumes: `RootCauseClass`, `Incident`, `Diagnosis` from `sentinel.domain`.
- Produces:
  - `PolicyConfig(BaseModel)`: `autonomous_eligible_services: list[str]`, `sensitive_root_causes: list[RootCauseClass]`, `min_confidence: float = 0.8`.
  - `GateResult(BaseModel)`: `allowed: bool`, `reason: str`.
  - `PolicyGate`: `__init__(self, config: PolicyConfig)`; `evaluate(self, incident: Incident, diagnosis: Diagnosis) -> GateResult`. Returns `allowed=False` (with a reason) if the service is not in the allowlist OR the diagnosis's `root_cause_class` is in `sensitive_root_causes`; otherwise `allowed=True`. The gate is purely deterministic (no confidence check — that lives in the pipeline).

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_policy.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_policy.py -v`
Expected: FAIL (No module named 'sentinel.policy').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/policy.py
from pydantic import BaseModel

from sentinel.domain import Diagnosis, Incident, RootCauseClass


class PolicyConfig(BaseModel):
    autonomous_eligible_services: list[str]
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
        return GateResult(allowed=True, reason="policy gate passed")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_policy.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/policy.py tests/sentinel/test_policy.py
git commit -m "feat(sentinel): deterministic policy gate"
```

---

### Task 4: Diagnoser port and fake

**Files:**
- Create: `src/sentinel/diagnoser.py`
- Test: `tests/sentinel/test_diagnoser.py`

**Interfaces:**
- Consumes: `Diagnosis`, `Incident` from `sentinel.domain`; `TelemetryProvider` from `sentinel.telemetry`.
- Produces:
  - `Diagnoser(Protocol)`: `diagnose(self, incident: Incident, telemetry: TelemetryProvider) -> Diagnosis`.
  - `FakeDiagnoser`: `__init__(self, diagnosis: Diagnosis)`; `diagnose(...)` records the `service` it was asked about (on `self.last_service`) and returns the canned `Diagnosis`. Used by tests and as the seam the real ADK+Gemini adapter (Plan 4) will replace.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_diagnoser.py
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
    incident = Incident(service="shop", alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z")

    result = diagnoser.diagnose(incident, provider)

    assert result is canned
    assert diagnoser.last_service == "shop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_diagnoser.py -v`
Expected: FAIL (No module named 'sentinel.diagnoser').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/diagnoser.py
from typing import Protocol

from sentinel.domain import Diagnosis, Incident
from sentinel.telemetry import TelemetryProvider


class Diagnoser(Protocol):
    def diagnose(self, incident: Incident, telemetry: TelemetryProvider) -> Diagnosis: ...


class FakeDiagnoser:
    def __init__(self, diagnosis: Diagnosis) -> None:
        self._diagnosis = diagnosis
        self.last_service: str | None = None

    def diagnose(self, incident: Incident, telemetry: TelemetryProvider) -> Diagnosis:
        self.last_service = incident.service
        return self._diagnosis
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/sentinel/test_diagnoser.py -v && python -m pyright && python -m ruff check .`
Expected: PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/diagnoser.py tests/sentinel/test_diagnoser.py
git commit -m "feat(sentinel): diagnoser port and fake implementation"
```

---

### Task 5: Decision pipeline (safety-critical)

**Files:**
- Create: `src/sentinel/pipeline.py`
- Test: `tests/sentinel/test_pipeline.py`

**Interfaces:**
- Consumes: `Action`, `Decision`, `Diagnosis`, `Incident` from `sentinel.domain`; `PolicyGate` from `sentinel.policy`; `Diagnoser` from `sentinel.diagnoser`; `TelemetryProvider` from `sentinel.telemetry`.
- Produces:
  - `decide(incident: Incident, diagnosis: Diagnosis, gate: PolicyGate) -> Decision` — the pure decision function implementing fail-toward-escalation + downgrade-only. Logic, in order:
    1. Evaluate the deterministic gate. If `not allowed` → `Decision(action=ESCALATE, requires_human=True, reason=<gate reason>)`.
    2. If `diagnosis.confidence < gate.config.min_confidence` → `ESCALATE` (reason mentions low confidence).
    3. Branch on `diagnosis.recommended_action` (exhaustive, guarded by `assert_never`):
       - `ESCALATE` → `Decision(ESCALATE, requires_human=True, reason="diagnosis recommends escalation")`.
       - `NOOP` → `Decision(NOOP, requires_human=False, reason="no action needed")`.
       - `ROLLBACK` → `Decision(ROLLBACK, requires_human=False, reason="autonomous rollback: routine regression on eligible service")`.
  - `DecisionPipeline`: `__init__(self, telemetry: TelemetryProvider, diagnoser: Diagnoser, gate: PolicyGate)`; `run(self, incident: Incident) -> Decision` — calls `diagnoser.diagnose(incident, telemetry)` then `decide(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/sentinel/test_pipeline.py
from pathlib import Path

from sentinel.diagnoser import FakeDiagnoser
from sentinel.domain import Action, Diagnosis, Evidence, Incident, RootCauseClass
from sentinel.pipeline import DecisionPipeline, decide
from sentinel.policy import PolicyConfig, PolicyGate
from sentinel.telemetry import FixtureTelemetryProvider

FIXTURES = Path(__file__).parent / "fixtures"


def _incident(service: str = "shop") -> Incident:
    return Incident(service=service, alert="error_rate_spike", triggered_at="2026-06-28T00:00:00Z")


def _diag(rc: RootCauseClass, action: Action, confidence: float) -> Diagnosis:
    return Diagnosis(
        root_cause_class=rc,
        summary="x",
        evidence=[Evidence(source="logs", detail="y")],
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


def test_autonomous_rollback_on_routine_high_confidence() -> None:
    d = decide(_incident(), _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95), _gate())
    assert d.action is Action.ROLLBACK
    assert d.requires_human is False


def test_low_confidence_escalates_even_if_rollback_recommended() -> None:
    d = decide(_incident(), _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.5), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True
    assert "confidence" in d.reason.lower()


def test_sensitive_cause_escalates_even_if_rollback_recommended_high_confidence() -> None:
    d = decide(_incident(), _diag(RootCauseClass.PII_EXPOSURE, Action.ROLLBACK, 0.99), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True


def test_service_not_allowlisted_escalates() -> None:
    d = decide(_incident("payments"), _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.99), _gate())
    assert d.action is Action.ESCALATE


def test_noop_recommendation_is_autonomous_noop() -> None:
    d = decide(_incident(), _diag(RootCauseClass.TRANSIENT_BLIP, Action.NOOP, 0.9), _gate())
    assert d.action is Action.NOOP
    assert d.requires_human is False


def test_escalate_recommendation_passes_through() -> None:
    d = decide(_incident(), _diag(RootCauseClass.DEPENDENCY_OUTAGE, Action.ESCALATE, 0.9), _gate())
    assert d.action is Action.ESCALATE
    assert d.requires_human is True


def test_pipeline_end_to_end_with_fake() -> None:
    diag = _diag(RootCauseClass.CODE_REGRESSION, Action.ROLLBACK, 0.95)
    pipeline = DecisionPipeline(
        telemetry=FixtureTelemetryProvider(FIXTURES / "code_regression.json"),
        diagnoser=FakeDiagnoser(diag),
        gate=_gate(),
    )
    decision = pipeline.run(_incident())
    assert decision.action is Action.ROLLBACK
    assert decision.diagnosis is diag
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/sentinel/test_pipeline.py -v`
Expected: FAIL (No module named 'sentinel.pipeline').

- [ ] **Step 3: Write the implementation**

```python
# src/sentinel/pipeline.py
from typing import assert_never

from sentinel.diagnoser import Diagnoser
from sentinel.domain import Action, Decision, Diagnosis, Incident
from sentinel.policy import PolicyGate
from sentinel.telemetry import TelemetryProvider


def decide(incident: Incident, diagnosis: Diagnosis, gate: PolicyGate) -> Decision:
    gate_result = gate.evaluate(incident, diagnosis)
    if not gate_result.allowed:
        return Decision(
            action=Action.ESCALATE,
            requires_human=True,
            diagnosis=diagnosis,
            reason=f"escalated by policy gate: {gate_result.reason}",
        )
    if diagnosis.confidence < gate.config.min_confidence:
        return Decision(
            action=Action.ESCALATE,
            requires_human=True,
            diagnosis=diagnosis,
            reason=(
                f"escalated: confidence {diagnosis.confidence:.2f} "
                f"below threshold {gate.config.min_confidence:.2f}"
            ),
        )
    match diagnosis.recommended_action:
        case Action.ESCALATE:
            return Decision(
                action=Action.ESCALATE,
                requires_human=True,
                diagnosis=diagnosis,
                reason="diagnosis recommends escalation",
            )
        case Action.NOOP:
            return Decision(
                action=Action.NOOP,
                requires_human=False,
                diagnosis=diagnosis,
                reason="no action needed",
            )
        case Action.ROLLBACK:
            return Decision(
                action=Action.ROLLBACK,
                requires_human=False,
                diagnosis=diagnosis,
                reason="autonomous rollback: routine regression on eligible service",
            )
        case _ as unreachable:
            assert_never(unreachable)


class DecisionPipeline:
    def __init__(
        self,
        telemetry: TelemetryProvider,
        diagnoser: Diagnoser,
        gate: PolicyGate,
    ) -> None:
        self._telemetry = telemetry
        self._diagnoser = diagnoser
        self._gate = gate

    def run(self, incident: Incident) -> Decision:
        diagnosis = self._diagnoser.diagnose(incident, self._telemetry)
        return decide(incident, diagnosis, self._gate)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v && python -m pyright && python -m ruff check .`
Expected: ALL tests across the suite PASS; pyright 0 errors; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/sentinel/pipeline.py tests/sentinel/test_pipeline.py
git commit -m "feat(sentinel): decision pipeline with fail-toward-escalation safety logic"
```

---

## Plan 2 Done-When

- `python -m pytest -v` fully green; `python -m pyright` 0 errors; `python -m ruff check .` clean.
- The decision core runs end-to-end against fixtures with a `FakeDiagnoser`, correctly producing autonomous ROLLBACK on a routine high-confidence case and ESCALATE on sensitive/low-confidence/not-allowlisted cases.
- All ports (`TelemetryProvider`, `Diagnoser`) are defined so Plan 4 can drop in the real ADK+Gemini and live-GCP adapters without touching the decision logic.
