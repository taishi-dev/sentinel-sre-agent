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
        text = text.strip()
    return text


def parse_diagnosis(raw: str) -> Diagnosis:
    text = _strip_fence(raw)
    try:
        return Diagnosis.model_validate_json(text)
    except (ValidationError, ValueError) as exc:
        return _escalation_fallback(str(exc).splitlines()[0][:200])
