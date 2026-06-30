from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request

from sentinel.alerts import decode_push_envelope, parse_alert
from sentinel.diagnoser import Diagnoser
from sentinel.pipeline import DecisionPipeline
from sentinel.policy import PolicyGate
from sentinel.response import ActionExecutor, Notifier, respond
from sentinel.telemetry import TelemetryProvider


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
        record = respond(incident, decision, deps.executor, deps.notifier)
        return {
            "action": decision.action.value,
            "requires_human": decision.requires_human,
            "executed": record.executed,
        }

    return app
