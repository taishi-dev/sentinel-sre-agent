import json
import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import cast

from sentinel.telemetry import LogEntry, TelemetrySnapshot

_logger = logging.getLogger("sentinel.telemetry")

# A log reader maps a service name to recent log entries (newest first).
LogReader = Callable[[str], list[LogEntry]]
# A revision lister maps a service name to its revision names (newest first).
RevisionLister = Callable[[str], list[str]]

_ERROR_SEVERITIES = frozenset({"ERROR", "CRITICAL", "ALERT", "EMERGENCY"})


def entry_message(payload: object) -> str:
    """Best-effort message text from a Cloud Logging payload (text or struct)."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        # Serialize the whole structured payload so every field (e.g. an `error`
        # stack trace alongside a `message`) reaches the diagnoser, not just one key.
        payload_dict = cast("dict[str, object]", payload)
        return json.dumps(payload_dict, separators=(",", ":"), default=str)
    return str(payload) if payload is not None else ""


def derive_metrics(logs: list[LogEntry]) -> dict[str, float]:
    """Coarse severity counts from the fetched logs.

    A pragmatic MVP stand-in for true Cloud Monitoring rates (error_rate / p95),
    which are deferred to a follow-up task. The live diagnoser reads log text as
    its primary signal, so these counts are a supporting hint, not the basis.
    """
    errors = sum(1 for e in logs if e.severity in _ERROR_SEVERITIES)
    warnings = sum(1 for e in logs if e.severity == "WARNING")
    return {"error_log_count": float(errors), "warning_log_count": float(warnings)}


class GcpTelemetryProvider:
    """TelemetryProvider adapter over live GCP. Pure assembly; the SDK calls live
    in the injected readers (see the factory functions below)."""

    def __init__(self, log_reader: LogReader, revision_lister: RevisionLister) -> None:
        self._log_reader = log_reader
        self._revision_lister = revision_lister

    def snapshot(self, service: str) -> TelemetrySnapshot:
        logs = self._log_reader(service)
        revisions = self._revision_lister(service)
        _logger.info(
            "telemetry service=%s logs_read=%d revisions=%s",
            service,
            len(logs),
            revisions,
        )
        return TelemetrySnapshot(logs=logs, metrics=derive_metrics(logs), revisions=revisions)


def names_newest_first(revisions: Iterable[object]) -> list[str]:
    """Revision names sorted newest-first by create_time.

    The rollback executor picks revisions[1] as the target, so ordering is
    load-bearing: sort explicitly instead of trusting the SDK's default order.
    If ANY revision lacks a create_time, keep the whole input order (the API's
    documented default is newest first; a partial sort key would raise).
    """
    revs = list(revisions)
    times = [getattr(rev, "create_time", None) for rev in revs]
    if all(t is not None for t in times):
        order = sorted(range(len(revs)), key=lambda i: cast("datetime", times[i]), reverse=True)
        revs = [revs[i] for i in order]
    return [str(getattr(rev, "name", "")).split("/")[-1] for rev in revs]


def cloud_run_revision_lister(project: str, location: str) -> RevisionLister:
    """Build a revision lister backed by the Cloud Run Admin API (newest first)."""
    from google.cloud import run_v2

    client = run_v2.RevisionsClient()

    def list_revisions(service: str) -> list[str]:
        parent = f"projects/{project}/locations/{location}/services/{service}"
        request = run_v2.ListRevisionsRequest(parent=parent)
        revisions = cast(
            "Iterable[object]",
            client.list_revisions(request=request),  # pyright: ignore[reportUnknownMemberType]
        )
        return names_newest_first(revisions)

    return list_revisions


def cloud_logging_reader(
    project: str,
    lookback_minutes: int = 30,
    limit: int = 50,
) -> LogReader:
    """Build a log reader over Cloud Logging for a Cloud Run service (newest first)."""
    from datetime import datetime, timedelta

    from google.cloud import logging as cloud_logging

    client = cloud_logging.Client(project=project)

    def read_logs(service: str) -> list[LogEntry]:
        since = (datetime.now(UTC) - timedelta(minutes=lookback_minutes)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        log_filter = (
            'resource.type="cloud_run_revision" '
            f'AND resource.labels.service_name="{service}" '
            "AND severity>=WARNING "
            f'AND timestamp>="{since}"'
        )
        entries = cast(
            "Iterable[object]",
            client.list_entries(  # pyright: ignore[reportUnknownMemberType]
                filter_=log_filter,
                order_by=cloud_logging.DESCENDING,
                max_results=limit,
            ),
        )
        result: list[LogEntry] = []
        for entry in entries:
            severity = str(getattr(entry, "severity", None) or "DEFAULT")
            message = entry_message(getattr(entry, "payload", None))
            if not message.strip():
                continue  # skip request-log noise (payload empty; data is in httpRequest)
            result.append(LogEntry(severity=severity, message=message))
        return result

    return read_logs
