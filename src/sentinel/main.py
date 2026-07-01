import logging
import os
from collections.abc import Mapping

from fastapi import FastAPI
from pydantic import BaseModel

from sentinel.adapters.cloud_run import CloudRunRollbackExecutor, cloud_run_traffic_shifter
from sentinel.adapters.gcp_telemetry import (
    GcpTelemetryProvider,
    cloud_logging_reader,
    cloud_run_revision_lister,
)
from sentinel.adapters.gemini_diagnoser import GeminiDiagnoser, vertex_generate
from sentinel.adapters.slack import SlackNotifier, slack_webhook_poster
from sentinel.policy import PolicyGate, default_policy_config
from sentinel.server import SentinelDeps, create_app


class SentinelSettings(BaseModel):
    project: str
    region: str
    slack_webhook_url: str
    target_service: str = "shop"


def load_settings(env: Mapping[str, str]) -> SentinelSettings:
    project = env.get("GOOGLE_CLOUD_PROJECT", "")
    region = env.get("GOOGLE_CLOUD_REGION", "")
    webhook = env.get("SLACK_WEBHOOK_URL", "")
    missing = [
        name
        for name, value in (
            ("GOOGLE_CLOUD_PROJECT", project),
            ("GOOGLE_CLOUD_REGION", region),
            ("SLACK_WEBHOOK_URL", webhook),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"missing required environment variables: {', '.join(missing)}")
    return SentinelSettings(
        project=project,
        region=region,
        slack_webhook_url=webhook,
        target_service=env.get("SENTINEL_TARGET_SERVICE", "shop"),
    )


def build_deps(settings: SentinelSettings) -> SentinelDeps:
    """Wire the live adapters from settings. Exercised at deploy, not in unit tests
    (each factory constructs a real GCP/Gemini client)."""
    return SentinelDeps(
        telemetry=GcpTelemetryProvider(
            log_reader=cloud_logging_reader(settings.project),
            revision_lister=cloud_run_revision_lister(settings.project, settings.region),
        ),
        diagnoser=GeminiDiagnoser(vertex_generate(settings.project, settings.region)),
        gate=PolicyGate(default_policy_config(settings.target_service)),
        executor=CloudRunRollbackExecutor(
            revision_lister=cloud_run_revision_lister(settings.project, settings.region),
            traffic_shifter=cloud_run_traffic_shifter(settings.project, settings.region),
        ),
        notifier=SlackNotifier(slack_webhook_poster(settings.slack_webhook_url)),
    )


def _configure_logging() -> None:
    logger = logging.getLogger("sentinel")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def create_app_from_env() -> FastAPI:
    """Zero-arg factory for `uvicorn sentinel.main:create_app_from_env --factory`."""
    _configure_logging()
    return create_app(build_deps(load_settings(os.environ)))
