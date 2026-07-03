from collections.abc import Callable

from sentinel.adapters.gcp_telemetry import RevisionLister
from sentinel.response import RollbackOutcome

# Shifts 100% of a service's traffic to a target revision (service, target_revision).
TrafficShifter = Callable[[str, str], None]


class CloudRunRollbackExecutor:
    """ActionExecutor adapter. Pure logic; the traffic shift lives in the injected
    shifter (see the factory below). Rolls back to the previous revision."""

    def __init__(self, revision_lister: RevisionLister, traffic_shifter: TrafficShifter) -> None:
        self._revision_lister = revision_lister
        self._traffic_shifter = traffic_shifter

    def rollback(self, service: str) -> RollbackOutcome:
        revisions = self._revision_lister(service)
        if len(revisions) < 2:
            return RollbackOutcome(
                success=False,
                from_revision=revisions[0] if revisions else "",
                to_revision="",
                recovered=False,
                detail="no previous revision to roll back to",
            )
        current, previous = revisions[0], revisions[1]
        self._traffic_shifter(service, previous)
        return RollbackOutcome(
            success=True,
            from_revision=current,
            to_revision=previous,
            recovered=False,
            detail="traffic shifted to previous revision; recovery verification deferred",
        )


def cloud_run_traffic_shifter(project: str, location: str) -> TrafficShifter:
    """Build a traffic shifter backed by the Cloud Run Admin API."""
    from google.cloud import run_v2

    client = run_v2.ServicesClient()
    revision_type = run_v2.TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION

    def shift(service: str, target_revision: str) -> None:
        name = f"projects/{project}/locations/{location}/services/{service}"
        svc = client.get_service(name=name)  # pyright: ignore[reportUnknownMemberType]
        svc.traffic = [  # pyright: ignore[reportUnknownMemberType]
            run_v2.TrafficTarget(type_=revision_type, revision=target_revision, percent=100)
        ]
        operation = client.update_service(service=svc)  # pyright: ignore[reportUnknownMemberType]
        operation.result()  # pyright: ignore[reportUnknownMemberType]  # await rollout

    return shift
