from sentinel.adapters.cloud_run import CloudRunRollbackExecutor


def test_rollback_shifts_traffic_to_previous_revision() -> None:
    shifts: list[tuple[str, str]] = []
    executor = CloudRunRollbackExecutor(
        revision_lister=lambda _s: ["shop-00002", "shop-00001"],
        traffic_shifter=lambda service, target: shifts.append((service, target)),
    )
    outcome = executor.rollback("shop")
    assert outcome.success is True
    assert outcome.from_revision == "shop-00002"
    assert outcome.to_revision == "shop-00001"
    assert shifts == [("shop", "shop-00001")]


def test_rollback_without_previous_revision_fails_safely() -> None:
    shifts: list[tuple[str, str]] = []
    executor = CloudRunRollbackExecutor(
        revision_lister=lambda _s: ["shop-00001"],
        traffic_shifter=lambda service, target: shifts.append((service, target)),
    )
    outcome = executor.rollback("shop")
    assert outcome.success is False
    assert outcome.to_revision == ""
    assert "no previous revision" in outcome.detail
    assert shifts == []  # never touches traffic when there is nothing to roll back to


def test_rollback_with_no_revisions_fails_safely() -> None:
    executor = CloudRunRollbackExecutor(
        revision_lister=lambda _s: [],
        traffic_shifter=lambda _s, _t: None,
    )
    outcome = executor.rollback("shop")
    assert outcome.success is False
    assert outcome.from_revision == ""
