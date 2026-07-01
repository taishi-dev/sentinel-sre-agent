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
        "CLASSIFICATION GUIDANCE\n"
        "  - A code regression shows a server-side error spike (elevated error_rate, "
        "5xx responses, or exceptions/stack traces in application code) that begins at "
        "a deploy. A low error rate with only a missing static asset, a visual defect, "
        "or a brand/UI issue is NOT a code regression; classify it as cosmetic and "
        "escalate to product.\n"
        "  - A recent deploy is not by itself evidence of a regression: the new "
        "revision may be a security fix (rolling back would reopen the vulnerability) "
        "or otherwise unrelated to the symptom.\n"
        "  - Errors from a downstream/external dependency, missing configuration, "
        "resource exhaustion, or a database migration are not fixed by a code "
        "rollback; classify them accordingly and escalate.\n\n"
        "SAFETY RULES\n"
        "  - If the evidence is thin or you are uncertain, recommend 'escalate' "
        "and set a low confidence.\n"
        "  - If the incident touches security, privacy, PII, payments, or legal "
        "concerns, recommend 'escalate' regardless of confidence; never recommend "
        "an autonomous rollback for those.\n"
        "  - Only recommend 'rollback' for a routine code regression in a recent "
        "revision where rolling back is clearly the safe, low-blast-radius remedy.\n"
        "  - Conversely, when you ARE confident (>= 0.8) the root cause is a routine "
        "code regression in a recent revision and the incident is not security, "
        "privacy, PII, config, or data related, recommend 'rollback' - that is the "
        "designed remedy. Do not escalate a clear, confident code regression; "
        "escalation is for uncertainty or sensitive incidents.\n"
    )
