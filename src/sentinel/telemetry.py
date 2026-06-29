from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class LogEntry(BaseModel):
    severity: str
    message: str


class TelemetrySnapshot(BaseModel):
    logs: list[LogEntry]
    metrics: dict[str, float]
    revisions: list[str]


class TelemetryProvider(Protocol):
    def snapshot(self, service: str) -> TelemetrySnapshot: ...


class FixtureTelemetryProvider:
    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path

    def snapshot(self, service: str) -> TelemetrySnapshot:
        return TelemetrySnapshot.model_validate_json(self._fixture_path.read_text())
