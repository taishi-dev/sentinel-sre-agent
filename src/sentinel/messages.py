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
    status = (
        "recovery confirmed" if recovered else "verification pending (manual check recommended)"
    )
    return (
        "[AUTONOMOUS ROLLBACK] Sentinel acted.\n"
        f"{_header(incident, decision)}\n"
        f"rolled back traffic: {from_revision} -> {to_revision}\n"
        f"post-rollback: {status}\n"
        f"reason: {decision.reason}"
    )


def format_rollback_failure(
    incident: Incident,
    decision: Decision,
    detail: str,
    from_revision: str,
    to_revision: str,
) -> str:
    attempted = f"{from_revision} -> {to_revision}" if from_revision or to_revision else "n/a"
    return (
        "[ESCALATION] Sentinel needs a human.\n"
        f"{_header(incident, decision)}\n"
        f"rollback FAILED: {detail}\n"
        f"attempted traffic shift: {attempted}\n"
        f"reason: {decision.reason}"
    )


def format_diagnosis_failure(incident: Incident, error: str) -> str:
    return (
        "[ESCALATION] Sentinel needs a human.\n"
        f"service: {incident.service} | alert: {incident.alert}\n"
        f"diagnosis failed: {error}\n"
        "no action taken; investigate manually"
    )


def format_observation(incident: Incident, decision: Decision) -> str:
    return (
        "[OBSERVE] Sentinel took no action.\n"
        f"{_header(incident, decision)}\n"
        f"reason: {decision.reason}"
    )
