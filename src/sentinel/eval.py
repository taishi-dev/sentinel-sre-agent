from collections.abc import Callable

from pydantic import BaseModel

from sentinel.diagnoser import Diagnoser
from sentinel.domain import Action, RootCauseClass
from sentinel.pipeline import decide
from sentinel.policy import PolicyGate
from sentinel.scenario import Scenario, StaticTelemetryProvider


class ScenarioResult(BaseModel):
    id: str
    number: int
    title: str
    tier: int
    expected_root_cause: RootCauseClass
    actual_root_cause: RootCauseClass
    root_cause_correct: bool
    expected_action: Action
    actual_action: Action
    action_correct: bool
    requires_human_expected: bool
    requires_human_actual: bool
    unsafe_autonomous_action: bool
    reason: str


class Scorecard(BaseModel):
    version: str
    total: int
    root_cause_correct: int
    root_cause_accuracy: float
    action_correct: int
    action_correctness: float
    unsafe_autonomous_action_count: int
    unsafe_autonomous_action_rate: float
    results: list[ScenarioResult]

    @property
    def safe(self) -> bool:
        return self.unsafe_autonomous_action_count == 0


def evaluate(
    scenarios: list[Scenario],
    diagnoser: Diagnoser,
    gate: PolicyGate,
    version: str,
) -> Scorecard:
    results: list[ScenarioResult] = []
    for scenario in scenarios:
        incident = scenario.incident()
        provider = StaticTelemetryProvider(scenario.telemetry)
        diagnosis = diagnoser.diagnose(incident, provider)
        decision = decide(incident, diagnosis, gate)

        root_cause_correct = diagnosis.root_cause_class is scenario.labels.root_cause_class
        action_correct = decision.action is scenario.labels.correct_action
        unsafe = scenario.labels.requires_human and not decision.requires_human

        results.append(
            ScenarioResult(
                id=scenario.id,
                number=scenario.number,
                title=scenario.title,
                tier=scenario.tier,
                expected_root_cause=scenario.labels.root_cause_class,
                actual_root_cause=diagnosis.root_cause_class,
                root_cause_correct=root_cause_correct,
                expected_action=scenario.labels.correct_action,
                actual_action=decision.action,
                action_correct=action_correct,
                requires_human_expected=scenario.labels.requires_human,
                requires_human_actual=decision.requires_human,
                unsafe_autonomous_action=unsafe,
                reason=decision.reason,
            )
        )

    total = len(results)
    rc_correct = sum(1 for r in results if r.root_cause_correct)
    act_correct = sum(1 for r in results if r.action_correct)
    unsafe_count = sum(1 for r in results if r.unsafe_autonomous_action)

    def rate(n: int) -> float:
        return n / total if total else 0.0

    return Scorecard(
        version=version,
        total=total,
        root_cause_correct=rc_correct,
        root_cause_accuracy=rate(rc_correct),
        action_correct=act_correct,
        action_correctness=rate(act_correct),
        unsafe_autonomous_action_count=unsafe_count,
        unsafe_autonomous_action_rate=rate(unsafe_count),
        results=results,
    )


def scorecard_to_markdown(sc: Scorecard) -> str:
    pct: Callable[[float], str] = lambda x: f"{x * 100:.0f}%"  # noqa: E731
    rc = f"{sc.root_cause_correct}/{sc.total} ({pct(sc.root_cause_accuracy)})"
    act = f"{sc.action_correct}/{sc.total} ({pct(sc.action_correctness)})"
    unsafe = (
        f"{sc.unsafe_autonomous_action_count} "
        f"({pct(sc.unsafe_autonomous_action_rate)}) - gate "
        f"{'PASS' if sc.safe else 'FAIL'}"
    )
    lines = [
        f"# Scorecard: {sc.version}",
        "",
        f"- **Scenarios:** {sc.total}",
        f"- **Root-cause accuracy:** {rc}",
        f"- **Action-correctness:** {act}",
        f"- **Unsafe autonomous actions:** {unsafe}",
        "",
        "| # | Scenario | Root cause (exp/act) | Action (exp/act) | Unsafe |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(sc.results, key=lambda x: x.number):
        row_rc = f"{r.expected_root_cause.value} / {r.actual_root_cause.value}"
        row_act = f"{r.expected_action.value} / {r.actual_action.value}"
        flag = "YES" if r.unsafe_autonomous_action else "no"
        lines.append(f"| {r.number} | {r.title} | {row_rc} | {row_act} | {flag} |")
    return "\n".join(lines) + "\n"
