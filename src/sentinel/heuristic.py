from sentinel.domain import Action, Diagnosis, Evidence, Incident, RootCauseClass
from sentinel.telemetry import TelemetryProvider

CODE_REGRESSION_MARKERS: tuple[str, ...] = (
    "TypeError",
    "NullPointer",
    "NullPointerException",
    "Traceback",
    "Unhandled exception",
    "panic:",
)


class HeuristicDiagnoser:
    """Deterministic, GCP-free baseline. Conservative: fails toward escalation."""

    def diagnose(self, incident: Incident, telemetry: TelemetryProvider) -> Diagnosis:
        snap = telemetry.snapshot(incident.service)
        error_rate = snap.metrics.get("error_rate", 0.0)
        recent_deploy = len(snap.revisions) >= 2
        has_stacktrace = any(
            marker in entry.message
            for entry in snap.logs
            for marker in CODE_REGRESSION_MARKERS
        )

        if has_stacktrace and error_rate >= 0.2 and recent_deploy:
            return Diagnosis(
                root_cause_class=RootCauseClass.CODE_REGRESSION,
                summary="In-app exception coincident with a recent deploy and error spike.",
                evidence=[
                    Evidence(source="logs", detail="stack trace in current revision"),
                    Evidence(source="metrics", detail=f"error_rate={error_rate:.2f}"),
                ],
                recommended_action=Action.ROLLBACK,
                confidence=0.9,
            )

        warning_only = all(entry.severity in {"WARNING", "INFO"} for entry in snap.logs)
        if error_rate < 0.1 and warning_only and len(snap.revisions) <= 1:
            return Diagnosis(
                root_cause_class=RootCauseClass.TRANSIENT_BLIP,
                summary="Low error rate, warnings only, no recent deploy; likely self-healing.",
                evidence=[Evidence(source="metrics", detail=f"error_rate={error_rate:.2f}")],
                recommended_action=Action.NOOP,
                confidence=0.85,
            )

        return Diagnosis(
            root_cause_class=RootCauseClass.UNKNOWN,
            summary="Signals do not match a known routine-regression pattern; escalating.",
            evidence=[Evidence(source="metrics", detail=f"error_rate={error_rate:.2f}")],
            recommended_action=Action.ESCALATE,
            confidence=0.4,
        )
