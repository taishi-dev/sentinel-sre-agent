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
