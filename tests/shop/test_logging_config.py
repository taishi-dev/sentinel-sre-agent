import json
import logging

from shop.logging_config import JsonFormatter, get_logger, log_event


def test_formatter_emits_required_keys() -> None:
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    out = JsonFormatter().format(record)
    parsed = json.loads(out)
    assert parsed["severity"] == "INFO"
    assert parsed["message"] == "hello"
    assert "timestamp" in parsed


def test_formatter_includes_fields() -> None:
    record = logging.LogRecord(
        name="t", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="boom", args=(), exc_info=None,
    )
    record.fields = {"path": "/checkout", "status": 500}
    out = JsonFormatter().format(record)
    parsed = json.loads(out)
    assert parsed["severity"] == "ERROR"
    assert parsed["path"] == "/checkout"
    assert parsed["status"] == 500


def test_log_event_attaches_fields() -> None:
    logger = get_logger("test.logger.fields")
    logger.setLevel(logging.INFO)
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    logger.addHandler(handler)
    try:
        log_event(logger, logging.INFO, "did thing", widget="cog", count=3)
    finally:
        logger.removeHandler(handler)
    assert records[-1].fields == {"widget": "cog", "count": 3}  # type: ignore[attr-defined]
