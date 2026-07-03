from dataclasses import dataclass
from datetime import UTC, datetime

from sentinel.adapters.gcp_telemetry import (
    GcpTelemetryProvider,
    derive_metrics,
    entry_message,
    names_newest_first,
)
from sentinel.telemetry import LogEntry


@dataclass
class _Rev:
    name: str
    create_time: datetime


@dataclass
class _RevNoTime:
    name: str


def _ts(hour: int) -> datetime:
    return datetime(2026, 7, 3, hour, 0, 0, tzinfo=UTC)


def test_entry_message_handles_text_struct_and_other() -> None:
    assert entry_message("plain text") == "plain text"
    # structured payloads are serialized whole so all fields reach the diagnoser
    assert entry_message({"message": "checkout failed", "error": "NPE"}) == (
        '{"message":"checkout failed","error":"NPE"}'
    )
    assert entry_message({"k": "v"}) == '{"k":"v"}'
    assert entry_message(None) == ""


def test_derive_metrics_counts_severities() -> None:
    logs = [
        LogEntry(severity="ERROR", message="a"),
        LogEntry(severity="CRITICAL", message="b"),
        LogEntry(severity="WARNING", message="c"),
        LogEntry(severity="INFO", message="d"),
    ]
    metrics = derive_metrics(logs)
    assert metrics["error_log_count"] == 2.0
    assert metrics["warning_log_count"] == 1.0


def test_snapshot_assembles_from_injected_readers() -> None:
    logs = [LogEntry(severity="ERROR", message="boom")]
    seen: dict[str, str] = {}

    def log_reader(service: str) -> list[LogEntry]:
        seen["log"] = service
        return logs

    def revision_lister(service: str) -> list[str]:
        seen["rev"] = service
        return ["shop-00002", "shop-00001"]

    provider = GcpTelemetryProvider(log_reader=log_reader, revision_lister=revision_lister)
    snap = provider.snapshot("shop")

    assert snap.logs == logs
    assert snap.revisions == ["shop-00002", "shop-00001"]
    assert snap.metrics["error_log_count"] == 1.0
    assert seen == {"log": "shop", "rev": "shop"}


def testnames_newest_first_sorts_by_create_time() -> None:
    revs = [
        _Rev(name="parent/shop-00001", create_time=_ts(1)),
        _Rev(name="parent/shop-00003", create_time=_ts(3)),
        _Rev(name="parent/shop-00002", create_time=_ts(2)),
    ]
    assert names_newest_first(revs) == ["shop-00003", "shop-00002", "shop-00001"]


def testnames_newest_first_keeps_order_when_no_create_time() -> None:
    revs = [_RevNoTime(name="parent/shop-00002"), _RevNoTime(name="parent/shop-00001")]
    assert names_newest_first(revs) == ["shop-00002", "shop-00001"]


def testnames_newest_first_keeps_order_on_mixed_input() -> None:
    revs: list[object] = [
        _Rev(name="parent/shop-00001", create_time=_ts(1)),
        _RevNoTime(name="parent/shop-00002"),
    ]
    assert names_newest_first(revs) == ["shop-00001", "shop-00002"]


def testnames_newest_first_empty_input() -> None:
    assert names_newest_first([]) == []
