import json
import urllib.request
from collections.abc import Callable

# Sends one already-formatted message to the configured Slack channel.
SlackPoster = Callable[[str], None]


class SlackNotifier:
    """Notifier adapter. The HTTP POST lives in the injected poster, so the
    routing logic is testable without a network call."""

    def __init__(self, poster: SlackPoster) -> None:
        self._poster = poster

    def notify(self, message: str) -> None:
        self._poster(message)


def slack_webhook_poster(webhook_url: str) -> SlackPoster:
    """Build a poster that POSTs messages to a Slack Incoming Webhook."""

    def post(message: str) -> None:
        data = json.dumps({"text": message}).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()

    return post
