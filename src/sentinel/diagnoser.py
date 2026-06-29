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
