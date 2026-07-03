import pytest

from sentinel.main import load_settings


def _full_env() -> dict[str, str]:
    return {
        "GOOGLE_CLOUD_PROJECT": "sentinel-sre-2026",
        "GOOGLE_CLOUD_REGION": "asia-northeast1",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/x",
    }


def test_load_settings_parses_required_env() -> None:
    s = load_settings(_full_env())
    assert s.project == "sentinel-sre-2026"
    assert s.region == "asia-northeast1"
    assert s.slack_webhook_url == "https://hooks.slack.com/services/x"
    assert s.target_service == "shop"  # default


def test_load_settings_honors_custom_target_service() -> None:
    env = _full_env() | {"SENTINEL_TARGET_SERVICE": "web"}
    assert load_settings(env).target_service == "web"


def test_load_settings_reports_all_missing_vars() -> None:
    with pytest.raises(ValueError) as exc:
        load_settings({"GOOGLE_CLOUD_PROJECT": "p"})
    message = str(exc.value)
    assert "GOOGLE_CLOUD_REGION" in message
    assert "SLACK_WEBHOOK_URL" in message
    assert "GOOGLE_CLOUD_PROJECT" not in message  # this one was provided
