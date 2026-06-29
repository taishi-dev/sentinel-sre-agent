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
