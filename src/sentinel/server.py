import logging
import time
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI, HTTPException, Request

from sentinel.alerts import decode_push_envelope, parse_alert
from sentinel.diagnoser import Diagnoser
from sentinel.messages import format_diagnosis_failure
from sentinel.pipeline import DecisionPipeline
from sentinel.policy import PolicyGate
from sentinel.response import ActionExecutor, Notifier, notify_safely, respond
from sentinel.telemetry import TelemetryProvider

_logger = logging.getLogger("sentinel")

_DEDUP_TTL_SECONDS = 600.0
# Module-level indirection so tests can substitute a fake clock.
_now = time.monotonic


def _message_id(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    message = cast("dict[str, object]", body).get("message")
    if not isinstance(message, dict):
        return None
    message_id = cast("dict[str, object]", message).get("messageId")
    return message_id if isinstance(message_id, str) and message_id else None


@dataclass
class SentinelDeps:
    telemetry: TelemetryProvider
    diagnoser: Diagnoser
    gate: PolicyGate
    executor: ActionExecutor
    notifier: Notifier


def create_app(deps: SentinelDeps) -> FastAPI:
    app = FastAPI()
    app.state.deps = deps
    pipeline = DecisionPipeline(deps.telemetry, deps.diagnoser, deps.gate)
    # Pub/Sub delivers at-least-once; dedup redeliveries by message id. The cache
    # is per app instance (in-memory): it does not survive restarts nor span
    # Cloud Run instances — acceptable because the traffic shift is idempotent.
    seen_message_ids: dict[str, float] = {}

    def _is_duplicate(message_id: str) -> bool:
        now = _now()
        for key, stamp in list(seen_message_ids.items()):
            if now - stamp > _DEDUP_TTL_SECONDS:
                del seen_message_ids[key]
        if message_id in seen_message_ids:
            return True
        seen_message_ids[message_id] = now
        return False

    @app.get("/health")
    def health() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"status": "ok"}

    @app.post("/pubsub/push")
    async def push(request: Request) -> dict[str, object]:  # type: ignore[misc]  # decorator side-effect
        body = await request.json()
        # Dedup before decoding so redelivered malformed payloads are also
        # short-circuited instead of feeding the retry loop with 400s.
        message_id = _message_id(body)
        if message_id is not None and _is_duplicate(message_id):
            _logger.info("sentinel duplicate push message_id=%s ignored", message_id)
            return {"action": "duplicate", "requires_human": False, "executed": False}
        try:
            payload = decode_push_envelope(body)
            incident = parse_alert(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            decision = pipeline.run(incident)
        except Exception as exc:
            # Fail toward escalation: a failed diagnosis (Gemini call, telemetry
            # read) notifies a human and returns 200 so Pub/Sub does not
            # redeliver into a repeated attempt.
            _logger.exception("sentinel diagnosis failed service=%s", incident.service)
            notify_safely(deps.notifier, format_diagnosis_failure(incident, str(exc)))
            return {"action": "escalate", "requires_human": True, "executed": False}
        _logger.info(
            "sentinel decision service=%s action=%s root_cause=%s confidence=%.2f "
            "requires_human=%s reason=%s",
            incident.service,
            decision.action.value,
            decision.diagnosis.root_cause_class.value,
            decision.diagnosis.confidence,
            decision.requires_human,
            decision.reason,
        )
        record = respond(incident, decision, deps.executor, deps.notifier)
        _logger.info(
            "sentinel responded action=%s executed=%s rollback=%s",
            record.action.value,
            record.executed,
            record.rollback.model_dump() if record.rollback is not None else None,
        )
        return {
            "action": decision.action.value,
            "requires_human": decision.requires_human,
            "executed": record.executed,
        }

    return app
