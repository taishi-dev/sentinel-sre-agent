import base64
import binascii
import json
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sentinel.domain import Incident


class _PushMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    data: str


class _PushEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: _PushMessage


class _Resource(BaseModel):
    model_config = ConfigDict(extra="ignore")
    labels: dict[str, str] = Field(default_factory=dict)


class _IncidentBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    resource: _Resource = Field(default_factory=_Resource)
    condition_name: str | None = None
    policy_name: str | None = None
    started_at: object | None = None


class _AlertPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    incident: _IncidentBlock = Field(default_factory=_IncidentBlock)
    service: str | None = None


def decode_push_envelope(body: Mapping[str, object]) -> dict[str, object]:
    try:
        envelope = _PushEnvelope.model_validate(body)
    except ValidationError as exc:
        raise ValueError(f"invalid push envelope: {exc}") from exc
    try:
        decoded = base64.b64decode(envelope.message.data, validate=True)
        payload = json.loads(decoded)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"malformed push data: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("push data is not a JSON object")
    return cast("dict[str, object]", payload)


def parse_alert(payload: Mapping[str, object]) -> Incident:
    try:
        parsed = _AlertPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid alert payload: {exc}") from exc
    service = parsed.incident.resource.labels.get("service_name") or parsed.service
    if not service:
        raise ValueError("alert payload has no resolvable service")
    alert = parsed.incident.condition_name or parsed.incident.policy_name or "slo_breach"
    started = parsed.incident.started_at
    triggered_at = str(started) if started is not None else "unknown"
    return Incident(service=service, alert=alert, triggered_at=triggered_at)
