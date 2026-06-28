from shop.faults import FaultState, FaultType


def test_fault_type_values() -> None:
    assert FaultType.NONE.value == "none"
    assert FaultType.CHECKOUT_ERROR.value == "checkout_error"
    assert FaultType.DEPENDENCY_OUTAGE.value == "dependency_outage"
    assert FaultType.PII_LEAK.value == "pii_leak"
    assert FaultType.TRANSIENT.value == "transient"
    assert FaultType("checkout_error") is FaultType.CHECKOUT_ERROR


def test_default_state_is_none() -> None:
    state = FaultState()
    assert state.active is FaultType.NONE
    assert state.transient_remaining == 0


def test_inject_and_clear() -> None:
    state = FaultState()
    state.inject(FaultType.CHECKOUT_ERROR)
    assert state.active is FaultType.CHECKOUT_ERROR
    state.clear()
    assert state.active is FaultType.NONE


def test_transient_self_heals_after_fail_count() -> None:
    state = FaultState()
    state.inject(FaultType.TRANSIENT, fail_count=2)
    assert state.consume_transient() is True
    assert state.consume_transient() is True
    assert state.consume_transient() is False


def test_clear_resets_transient() -> None:
    state = FaultState()
    state.inject(FaultType.TRANSIENT, fail_count=3)
    state.clear()
    assert state.transient_remaining == 0
