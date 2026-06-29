from pathlib import Path

from pydantic import BaseModel

from sentinel.domain import Action, Incident, RootCauseClass
from sentinel.telemetry import TelemetrySnapshot


class ScenarioLabels(BaseModel):
    root_cause_class: RootCauseClass
    correct_action: Action
    requires_human: bool


class Scenario(BaseModel):
    id: str
    number: int
    title: str
    tier: int
    service: str = "shop"
    alert: str = "slo_breach"
    labels: ScenarioLabels
    telemetry: TelemetrySnapshot

    def incident(self) -> Incident:
        return Incident(
            service=self.service,
            alert=self.alert,
            triggered_at="2026-06-28T00:00:00Z",
        )


class StaticTelemetryProvider:
    def __init__(self, snapshot: TelemetrySnapshot) -> None:
        self._snapshot = snapshot

    def snapshot(self, service: str) -> TelemetrySnapshot:
        return self._snapshot


def load_catalog(directory: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.json")):
        scenarios.append(Scenario.model_validate_json(path.read_bytes()))
    return scenarios
