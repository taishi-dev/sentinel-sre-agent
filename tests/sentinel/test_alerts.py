import base64
import json
from collections.abc import Mapping

import pytest

from sentinel.alerts import decode_push_envelope, parse_alert


def _envelope(payload: Mapping[str, object]) -> dict[str, object]:
    data = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"message": {"data": data}, "subscription": "sub"}


def test_decode_round_trips_payload() -> None:
    payload = {"incident": {"resource": {"labels": {"service_name": "shop"}}}}
    assert decode_push_envelope(_envelope(payload)) == payload


def test_decode_rejects_missing_message() -> None:
    with pytest.raises(ValueError):
        decode_push_envelope({"subscription": "sub"})


def test_parse_alert_extracts_service_and_alert() -> None:
    payload = {
        "incident": {
            "resource": {"labels": {"service_name": "shop"}},
            "condition_name": "error_rate_high",
            "started_at": 1751155200,
        }
    }
    incident = parse_alert(payload)
    assert incident.service == "shop"
    assert incident.alert == "error_rate_high"
    assert incident.triggered_at == "1751155200"


def test_parse_alert_falls_back_to_top_level_service() -> None:
    incident = parse_alert({"service": "shop"})
    assert incident.service == "shop"
    assert incident.alert == "slo_breach"


def test_parse_alert_without_service_raises() -> None:
    with pytest.raises(ValueError):
        parse_alert({"incident": {"resource": {"labels": {}}}})
