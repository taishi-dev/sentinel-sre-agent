import logging
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request

from sentinel.alerts import decode_push_envelope, parse_alert
from sentinel.diagnoser import Diagnoser
from sentinel.pipeline import DecisionPipeline
from sentinel.policy import PolicyGate
from sentinel.response import ActionExecutor, Notifier, respond
from sentinel.telemetry import TelemetryProvider

_logger = logging.getLogger("sentinel")


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

    @app.get("/health")
    def health() -> dict[str, str]:  # type: ignore[misc]  # registered via decorator side-effect
        return {"status": "ok"}

    @app.post("/pubsub/push")
    async def push(request: Request) -> dict[str, object]:  # type: ignore[misc]  # decorator side-effect
        body = await request.json()
        try:
            payload = decode_push_envelope(body)
            incident = parse_alert(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        decision = pipeline.run(incident)
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
