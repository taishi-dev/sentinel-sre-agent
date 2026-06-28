from enum import StrEnum


class FaultType(StrEnum):
    NONE = "none"
    CHECKOUT_ERROR = "checkout_error"
    DEPENDENCY_OUTAGE = "dependency_outage"
    PII_LEAK = "pii_leak"
    TRANSIENT = "transient"


class FaultState:
    def __init__(self) -> None:
        self.active: FaultType = FaultType.NONE
        self.transient_remaining: int = 0

    def inject(self, fault: FaultType, fail_count: int = 3) -> None:
        self.active = fault
        self.transient_remaining = fail_count if fault is FaultType.TRANSIENT else 0

    def clear(self) -> None:
        self.active = FaultType.NONE
        self.transient_remaining = 0

    def consume_transient(self) -> bool:
        if self.transient_remaining > 0:
            self.transient_remaining -= 1
            return True
        return False
