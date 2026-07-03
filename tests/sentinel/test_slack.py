from sentinel.adapters.slack import SlackNotifier


def test_notifier_forwards_message_to_poster() -> None:
    sent: list[str] = []
    notifier = SlackNotifier(poster=sent.append)
    notifier.notify("[ESCALATION] something happened")
    assert sent == ["[ESCALATION] something happened"]
