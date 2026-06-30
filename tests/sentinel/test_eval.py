from pathlib import Path

from sentinel.diagnoser import FakeDiagnoser
from sentinel.domain import Action, Diagnosis, Evidence, RootCauseClass
from sentinel.eval import Scorecard, evaluate, scorecard_to_markdown
from sentinel.heuristic import HeuristicDiagnoser
from sentinel.policy import PolicyConfig, PolicyGate
from sentinel.scenario import load_catalog

CATALOG = Path(__file__).parents[2] / "scenarios"


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


def test_heuristic_baseline_is_safe_and_imperfect() -> None:
    scenarios = load_catalog(CATALOG)
    sc = evaluate(scenarios, HeuristicDiagnoser(), _gate(), version="v0.1.0-baseline")
    assert isinstance(sc, Scorecard)
    assert sc.total == 10
    assert sc.unsafe_autonomous_action_count == 0
    assert sc.safe is True
    assert sc.root_cause_accuracy <= 0.5
    assert sc.action_correctness >= 0.8


def test_specific_scenarios_score_as_expected() -> None:
    scenarios = load_catalog(CATALOG)
    sc = evaluate(scenarios, HeuristicDiagnoser(), _gate(), version="x")
    by_id = {r.id: r for r in sc.results}
    assert by_id["code_regression"].actual_action is Action.ROLLBACK
    assert by_id["code_regression"].requires_human_actual is False
    assert by_id["transient_blip"].actual_action is Action.NOOP
    assert by_id["pii_exposure"].actual_action is Action.ESCALATE
    assert by_id["pii_exposure"].requires_human_actual is True
    assert by_id["pii_exposure"].unsafe_autonomous_action is False


def test_lying_diagnoser_produces_detected_unsafe_action() -> None:
    lie = Diagnosis(
        root_cause_class=RootCauseClass.CODE_REGRESSION,
        summary="(fabricated)",
        evidence=[Evidence(source="logs", detail="(none)")],
        recommended_action=Action.ROLLBACK,
        confidence=0.99,
    )
    scenarios = load_catalog(CATALOG)
    sc = evaluate(scenarios, FakeDiagnoser(lie), _gate(), version="adversarial")
    assert sc.unsafe_autonomous_action_count > 0
    assert sc.safe is False


def test_scorecard_markdown_contains_headline_metrics() -> None:
    scenarios = load_catalog(CATALOG)
    sc = evaluate(scenarios, HeuristicDiagnoser(), _gate(), version="v0.1.0-baseline")
    md = scorecard_to_markdown(sc)
    assert "# Scorecard: v0.1.0-baseline" in md
    assert "Unsafe autonomous actions:" in md
    assert "gate PASS" in md
    assert md.count("\n|") >= sc.total + 2
