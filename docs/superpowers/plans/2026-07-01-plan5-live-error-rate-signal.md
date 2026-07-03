# Plan 5: Live server-error-rate signal for reliable autonomous rollback — Implementation Plan (CLOSED, NOT EXECUTED)

> **Outcome (recorded 2026-07-02): falsified at the Phase 1 decision gate; no Plan 5 code was built.**
>
> - **Phase 1 confirmation experiment result.** With a staged code regression on the shop service (the injected checkout fault producing six Hypertext Transfer Protocol status-500 responses, yielding live telemetry with `error_log_count` equal to 3.0), the Gemini diagnoser recommended rollback in ten out of ten calls on the current telemetry input, and also in ten out of ten calls on the input augmented with `server_error_rate_per_second` equal to 3.0. The augmented input did not raise the rollback count, because the baseline rollback count was already at the maximum. The falsification condition in Phase 1 Step 4 therefore applied.
> - **Cause of the earlier unreliability.** The earlier escalate-instead-of-rollback behavior that motivated Plan 5 was resolved by the decisive-prompt change in commit db2e80b (version 0.3.1), which was already present on the branch before Plan 5 execution began.
> - **Completion bar met without Plan 5 code.** A live trial of the current code (no Plan 5 changes) produced five rollbacks out of five staged live incidents, recorded in `scorecards/v0.3.1-live-trial.md`. The completion bar in the "Plan 5 Done-When" section (Decision 4.A) is therefore satisfied by the current code.
> - **Disposition.** The plan document below is retained unchanged as a record of the not-executed design. The Cloud Monitoring per-second server-error rate remains available as a possible future telemetry enhancement, not as a reliability fix.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement the plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Draft status:** Written under the Explicit, Self-Contained Language rules. This draft precedes the Quality Assurance subagent review, the Architecture subagent review, and code validation. Numbers such as file line ranges were read on 2026-07-01 and must be re-read during code validation before execution.

## Terms used in this plan

- **Sentinel agent** — the autonomous site reliability engineering program that reads telemetry about a monitored service and decides whether to roll the service back or escalate to a human.
- **shop service** — the demonstration web service on Google Cloud Run that the Sentinel agent monitors and can roll back.
- **rollback** — shifting one hundred percent of shop-service web traffic from the current revision to the previous revision.
- **escalate** — the Sentinel agent taking no action and posting a message for a human in Slack.
- **code regression** — a fault introduced by a recent deployment, for which rollback is the correct repair.
- **diagnoser** — the component that reads telemetry and produces a diagnosis (root-cause class, recommended action, confidence between 0.0 and 1.0). The diagnoser used in production is `GeminiDiagnoser` in `src/sentinel/adapters/gemini_diagnoser.py`, which calls the Gemini large language model through Google Vertex Artificial Intelligence.
- **live telemetry provider** — the class `GcpTelemetryProvider` in `src/sentinel/adapters/gcp_telemetry.py` that reads real Google Cloud logs and the revision list for the deployed Sentinel agent.
- **metrics dictionary** — the `metrics` field of a `TelemetrySnapshot` (defined in `src/sentinel/telemetry.py`), a mapping from a metric name string to a floating-point number.
- **error_log_count** — the metric name the live telemetry provider currently produces in the metrics dictionary: a count of error-severity log entries. Produced by `derive_metrics` at [gcp_telemetry.py:31](src/sentinel/adapters/gcp_telemetry.py#L31).
- **server_error_rate_per_second** — the new metric name the plan adds: the per-second count of Hypertext Transfer Protocol server-error responses (status codes 500 through 599) for the shop service, read from Cloud Monitoring.
- **Cloud Monitoring** — the Google Cloud Platform product storing time-series metrics.
- **request_count metric** — the Cloud Monitoring metric named `run.googleapis.com/request_count`.
- **response_code_class** — a label on the request_count metric with values such as "2xx", "4xx", "5xx".
- **eval harness** — the offline program in `src/sentinel/eval.py` and `src/sentinel/eval_cli.py` that runs the Scenario Catalog through a diagnoser and records accuracy and unsafe-action counts.
- **Scenario Catalog** — the ten labeled offline test cases stored as JavaScript Object Notation files under the `scenarios` directory; each case carries a fixed `error_rate` value and does not call the live telemetry provider.
- **staged live incident** — a manually created shop-service failure (inject the checkout fault, generate server-error traffic, then trigger the Sentinel agent) used to observe whether the Sentinel agent rolls back.
- **downgrade-only rule** — the safety rule that the final action may be equal to or more cautious than the action the diagnosis recommended, and never more autonomous.
- **Cloud Monitoring ingestion delay** — the time between a web request occurring and the corresponding request_count point becoming queryable in Cloud Monitoring, reported by Google as on the order of one to several minutes.

## Revisions incorporated from the Quality Assurance review and the Architecture review (version 2)

The list below records every change made to the draft after the Quality Assurance subagent review, the Architecture subagent review, and Phase 5 code validation. Both reviews reported no must-fix issue with the safety invariant; the ports-and-adapters fit and the downgrade-only rule are preserved.

1. **(Correctness, must-fix) Completion-bar signal corrected.** The observable signal for the live trial changed from "the shop-service health endpoint changes from status 200 to status 404" to "the Sentinel agent decision log records action=rollback, the executor records a traffic shift from the current revision to the previous revision, and the shop-service /checkout endpoint returns status 500 before the rollback and status 200 after." Reason: the /health endpoint returns status 200 unconditionally ([app.py:45-47](src/shop/app.py#L45)), so the status-200-to-status-404 change is not guaranteed by shop-service code; the status-404 result occurred in earlier live testing only because the rollback-target revision predates the /health route and therefore lacks a /health route, which is an environment assumption rather than a code guarantee.
2. **(Correctness, must-fix) Snapshot refactor made explicit.** Phase 3 now states that the snapshot method computes derive_metrics(logs) inline inside the TelemetrySnapshot(...) constructor call at [gcp_telemetry.py:60](src/sentinel/adapters/gcp_telemetry.py#L60), and must first be refactored to a local metrics variable before the metric-reader merge.
3. **(Risk, from Question 17) Cloud Monitoring ingestion delay handled.** The request_count metric is not queryable immediately after a server-error burst, so the fast synthetic-alert demo path can read an empty rate and fail to roll back. Phase 1 now measures the Cloud Monitoring ingestion delay, and Phase 6 now confirms the per-second server-error rate is greater than zero, by polling the metric reader, before publishing the synthetic alert in each staged live incident.
4. **(Correctness, from Question 18) Aggregation semantics changed to peak.** The aggregation helper now sums, across series, each series' maximum aligned per-second value over the lookback window (the peak rate), rather than the latest single aligned bucket, because a server-error burst that has decayed by query time yields a latest-bucket rate near zero.
5. **(Test coverage, should-fix) Helper unit test added.** Phase 3 now adds an offline unit test for the aggregation helper, because the helper is pure logic with no Software Development Kit dependency.
6. **(Observability, should-fix) Exception is logged and narrowed.** The Cloud Monitoring reader now logs the swallowed exception through the module logger and narrows the caught exception type, because the sibling readers do not swallow exceptions and a silently-empty rate is otherwise indistinguishable from a genuine zero rate.
7. **(Naming, should-fix, flagged against Decision 2.A) Naming divergence recorded as debt.** The three metric names for the failure concept now coexist: error_rate (a 0-to-1 fraction, used offline in the Scenario Catalog and read by the HeuristicDiagnoser at [heuristic.py:19](src/sentinel/heuristic.py#L19)), error_log_count (a count, produced live), and server_error_rate_per_second (a per-second rate, added by the plan). The divergence is recorded as known debt. An OPTIONAL prompt clause, contingent on the Phase 1 confirmation experiment showing the Gemini model misreads the magnitude, states that server_error_rate_per_second is an absolute per-second count. The optional prompt clause edits prompting.py and therefore brushes Decision 2.A (strengthen the signal, not the prompt), so execution requires explicit approval before the optional prompt clause is added.

**Goal:** Make the shop-service rollback fire reliably when the deployed Sentinel agent runs against live telemetry for a clear code regression, by adding a per-second server-error rate to the live telemetry provider so the diagnoser receives a stronger failure signal. Prove the result with a live trial of five rollbacks out of five staged live incidents.

**Architecture:** The change is confined to the live telemetry provider and the production wiring. A new metric reader function reads the per-second server-error rate from Cloud Monitoring and adds the rate to the metrics dictionary under the name `server_error_rate_per_second`. The `GcpTelemetryProvider` class gains an optional injected metric reader, following the same injected-callable pattern already used for the log reader and the revision lister, so the assembly logic stays unit-testable offline and the Cloud Monitoring Software Development Kit call is isolated in one factory function. The decision pipeline, the policy gate, and the downgrade-only rule are not changed, so the safety model is preserved.

**Tech Stack:** Python 3.12 or later (continuous integration on Python 3.14), the `google-cloud-monitoring` Python client library (new dependency), Pydantic version 2, pytest, ruff, pyright in strict mode.

## Global Constraints

- All source code under `src` must pass pyright in strict mode with no project-wide rule disables; per-line `# pyright: ignore[...]` is allowed where a Google client library type is only partially known, matching the existing suppressions at [gcp_telemetry.py:74](src/sentinel/adapters/gcp_telemetry.py#L74) and [gcp_telemetry.py:105](src/sentinel/adapters/gcp_telemetry.py#L105).
- ruff must pass on `src` and `tests`.
- Test-driven development: write the failing test first, then the minimal code.
- The downgrade-only rule must remain intact: no code in the plan may cause the pipeline to select a more autonomous action than the diagnosis recommended. The plan changes only the telemetry input to the diagnoser, never the pipeline decision.
- Fail toward escalation: if the Cloud Monitoring read fails or returns no data, the metric reader returns a metrics dictionary without the `server_error_rate_per_second` key (or with the value 0.0), so a missing rate never forces an autonomous action.
- The plan does not change the offline Scenario Catalog files, so the offline eval harness result is a no-regression check only, not the completion proof.
- Cloud Monitoring ingestion delay is a first-class risk: the request_count metric is not queryable immediately after a server-error burst. The live trial must confirm the per-second server-error rate is greater than zero (by polling the metric reader) before triggering the Sentinel agent, otherwise the metric reader returns an empty result and the rollback does not fire. The real Monitoring alert policy inherently waits for ingestion because the policy itself evaluates the same metric, so the real alert path is unaffected; only the fast synthetic-alert demo path needs the pre-trigger confirmation.

---

### Phase 1: Confirmation experiment (decision gate, throwaway code)

**Purpose:** Confirm two claims before building committed code, because the signal-strengthening decision (recorded as Decision 2.A) and the absolute-rate decision (recorded as Decision 3.A) both rest on an unproven root cause. Claim one: the deployed diagnoser recommends escalate on a clear code regression because the live signal is weak. Claim two: adding a per-second server-error rate to the telemetry makes the diagnoser recommend rollback.

**Files:** a throwaway script under the scratchpad directory only; no committed source changes in Phase 1.

- [ ] **Step 1.** Write a script that reads the current live shop-service telemetry through the existing `GcpTelemetryProvider`, then builds two prompt inputs: one input as produced today, and one input with an added `server_error_rate_per_second` value set from a hand-supplied number that represents a clear server-error rate.
- [ ] **Step 2.** Call the Gemini diagnoser ten times for each of the two inputs and count how many of the ten diagnoses recommend rollback.
- [ ] **Step 3. Measure the Cloud Monitoring ingestion delay.** After a server-error burst on the shop service, poll the metric reader `cloud_monitoring_5xx_rate` (once the metric reader exists; if Phase 1 runs before Phase 4, use a short inline query instead) until the returned `server_error_rate_per_second` value is greater than zero, and record the elapsed time. The recorded elapsed time is the minimum wait the live trial in Phase 6 must observe between generating server errors and publishing the synthetic alert. If the elapsed time is longer than a few minutes, prefer the real Monitoring alert policy path for the live trial, because the real alert policy already waits for ingestion.
- [ ] **Step 4. Decision gate.** If the input with the added `server_error_rate_per_second` value produces rollback in a clear majority of the ten diagnoses while the input without the added value does not, claim two holds and the plan proceeds to Phase 2. If the added value does not raise the rollback count, the falsification condition recorded in Question 3 applies: stop and reconsider the fraction form (option 3.B) instead of the absolute-rate form (option 3.A). If the Gemini model misreads the magnitude of the absolute per-second value (for example, treating a per-second rate as a fraction), record the finding for the OPTIONAL prompt clause noted in revision item 7, which requires explicit approval because the optional prompt clause brushes Decision 2.A.

**Verification for Phase 1:** the printed rollback counts for the two inputs, recorded in the plan-execution notes.

---

### Phase 2: Add the google-cloud-monitoring dependency

**Files:** `pyproject.toml`.

- [ ] **Step 1.** Add `"google-cloud-monitoring>=2.0"` to the `dependencies` list in `pyproject.toml`, next to the existing `"google-cloud-logging>=3.0"` and `"google-cloud-run>=0.10"` entries. (Exact current dependency lines to be confirmed in code validation.)
- [ ] **Step 2.** Install the dependency into the development environment so pyright can resolve the import: `python -m pip install "google-cloud-monitoring>=2.0"`.
- [ ] **Step 3. Verify:** `python -c "from google.cloud import monitoring_v3; print(monitoring_v3.MetricServiceClient)"` prints the class without error.

---

### Phase 3: Metric reader port and the provider extension (test-driven, offline)

**Files:**
- Modify: `src/sentinel/adapters/gcp_telemetry.py`
- Modify: `tests/sentinel/test_gcp_telemetry.py`

**Interfaces produced:**
- `MetricReader = Callable[[str], dict[str, float]]` — a metric reader maps a service name to extra metric values.
- `GcpTelemetryProvider.__init__(self, log_reader, revision_lister, metric_reader: MetricReader | None = None)` — the constructor gains a third, optional parameter. When `metric_reader` is `None`, behavior is unchanged.
- `GcpTelemetryProvider.snapshot` merges the result of `derive_metrics(logs)` with the result of `metric_reader(service)` when a metric reader is present, so the metrics dictionary contains both the log-severity counts and the added server-error rate.

- [ ] **Step 1: Write the failing test.**
```python
# addition to tests/sentinel/test_gcp_telemetry.py
def test_snapshot_merges_metric_reader_values() -> None:
    logs = [LogEntry(severity="ERROR", message="boom")]
    provider = GcpTelemetryProvider(
        log_reader=lambda _s: logs,
        revision_lister=lambda _s: ["shop-00002", "shop-00001"],
        metric_reader=lambda _s: {"server_error_rate_per_second": 2.5},
    )
    snap = provider.snapshot("shop")
    assert snap.metrics["server_error_rate_per_second"] == 2.5
    assert snap.metrics["error_log_count"] == 1.0  # existing values still present


def test_snapshot_without_metric_reader_is_unchanged() -> None:
    provider = GcpTelemetryProvider(
        log_reader=lambda _s: [],
        revision_lister=lambda _s: [],
    )
    snap = provider.snapshot("shop")
    assert "server_error_rate_per_second" not in snap.metrics
```
- [ ] **Step 2.** Run the two new tests and confirm they fail (the `metric_reader` parameter does not yet exist).
- [ ] **Step 3: Write the minimal code.** Add the `MetricReader` type alias next to the existing `LogReader` and `RevisionLister` aliases (the `LogReader` alias is at [gcp_telemetry.py:12](src/sentinel/adapters/gcp_telemetry.py#L12) and the `RevisionLister` alias is at [gcp_telemetry.py:14](src/sentinel/adapters/gcp_telemetry.py#L14)); insert the `MetricReader` alias before the `_ERROR_SEVERITIES` line at [gcp_telemetry.py:16](src/sentinel/adapters/gcp_telemetry.py#L16). Change `GcpTelemetryProvider.__init__` at [gcp_telemetry.py:47](src/sentinel/adapters/gcp_telemetry.py#L47) to accept `metric_reader: MetricReader | None = None` and store the metric reader. Change the `snapshot` method: the current `snapshot` at [gcp_telemetry.py:60](src/sentinel/adapters/gcp_telemetry.py#L60) computes `derive_metrics(logs)` inline inside the `TelemetrySnapshot(...)` constructor call, so first refactor the constructor call to assign a local variable `metrics = derive_metrics(logs)`, then, when a metric reader is present, call `metrics.update(self._metric_reader(service))`, then pass the local `metrics` variable into `TelemetrySnapshot(...)`.
- [ ] **Step 4.** Run the full test file, pyright, and ruff; confirm all pass.
- [ ] **Step 5. Commit.**

---

### Phase 4: Cloud Monitoring server-error-rate factory (Software Development Kit isolated)

**Files:**
- Modify: `src/sentinel/adapters/gcp_telemetry.py`

**Interface produced:**
- `cloud_monitoring_5xx_rate(project: str, location: str, lookback_minutes: int = 5) -> MetricReader` — returns a metric reader that reads the per-second server-error rate for the named service from Cloud Monitoring and returns `{"server_error_rate_per_second": <rate>}`.

**Verified Application Programming Interface facts (Phase 1 research):**
- Read call: `monitoring_v3.MetricServiceClient().list_time_series(request={"name": f"projects/{project}", "filter": <string>, "interval": <TimeInterval>, "aggregation": <Aggregation>, "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL})`. Source: https://cloud.google.com/monitoring/docs/samples/monitoring-read-timeseries-align
- Aligner `monitoring_v3.Aggregation.Aligner.ALIGN_RATE` converts the counter to a per-second rate. Source: https://docs.cloud.google.com/monitoring/api/ref_v3/rpc/google.monitoring.v3
- Filter fields `metric.type="run.googleapis.com/request_count"`, `resource.labels.service_name`, `metric.labels.response_code_class="5xx"`, resource type `cloud_run_revision`. Sources: https://docs.cloud.google.com/stackdriver/docs/solutions/slo-monitoring/sli-metrics/req-resp-metrics and the project file `deploy/alert-policy.json`.

- [ ] **Step 1: Write the code (marked as new code to write; the Software Development Kit call is exercised by a live smoke test, not by an offline unit test, matching the existing pattern for `cloud_logging_reader` and `cloud_run_revision_lister`).**
```python
def cloud_monitoring_5xx_rate(
    project: str,
    location: str,
    lookback_minutes: int = 5,
) -> MetricReader:
    """Build a metric reader for the per-second 5xx rate of a Cloud Run service."""
    from datetime import datetime, timedelta

    from google.api_core.exceptions import GoogleAPICallError
    from google.cloud import monitoring_v3

    client = monitoring_v3.MetricServiceClient()

    def read_rate(service: str) -> dict[str, float]:
        now = datetime.now(UTC)
        start = now - timedelta(minutes=lookback_minutes)
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(now.timestamp())},
                "start_time": {"seconds": int(start.timestamp())},
            }
        )
        aggregation = monitoring_v3.Aggregation(
            {
                "alignment_period": {"seconds": 60},
                "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_RATE,
            }
        )
        metric_filter = (
            'metric.type="run.googleapis.com/request_count" '
            'AND resource.type="cloud_run_revision" '
            f'AND resource.labels.service_name="{service}" '
            'AND metric.labels.response_code_class="5xx"'
        )
        try:
            series = cast(
                "Iterable[object]",
                client.list_time_series(  # pyright: ignore[reportUnknownMemberType]
                    request={
                        "name": f"projects/{project}",
                        "filter": metric_filter,
                        "interval": interval,
                        "aggregation": aggregation,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    }
                ),
            )
            rate = _sum_peak_rates(series)
        except (GoogleAPICallError, ValueError) as exc:  # fail toward escalation
            _logger.warning("cloud monitoring 5xx-rate read failed: %s", exc)
            return {}
        return {"server_error_rate_per_second": rate}

    return read_rate
```
- [ ] **Step 2.** Write the pure helper `_sum_peak_rates(series: Iterable[object]) -> float`. For each returned series, read the maximum aligned per-second value across the points of the series (the peak over the lookback window), then return the sum of the per-series peaks, so multiple revisions serving server errors combine into one rate without relying on the unverified cross-series reducer, and so a server-error burst that has decayed by query time is still captured by the peak rather than by the latest single bucket. Read the points and their numeric values defensively with `getattr`, matching the existing defensive pattern at [gcp_telemetry.py:112-114](src/sentinel/adapters/gcp_telemetry.py#L112). The exact attribute names of a Cloud Monitoring point (expected to be a `points` list on each series, each point carrying a `value` object with a `double_value` number) are not yet verified against the google-cloud-monitoring types; verify the attribute names during Phase 4 by reading the installed google-cloud-monitoring type stubs or by introspecting the client result, before finalizing `_sum_peak_rates`. Because `_sum_peak_rates` is pure logic with no Software Development Kit dependency, add an offline unit test in `tests/sentinel/test_gcp_telemetry.py` covering: an empty iterable returns 0.0; a series whose points list is empty returns 0.0; a single series returns the maximum of its point values; and two series return the sum of their per-series maxima. Build the test inputs as small fake objects that carry the same attribute names the verification step confirms.
- [ ] **Step 3.** Run pyright and ruff; confirm both pass (expect one `# pyright: ignore[reportUnknownMemberType]` on the `list_time_series` call, matching the existing suppressions).
- [ ] **Step 4. Live smoke test (throwaway script).** Against the deployed shop service with a staged server-error burst, call `cloud_monitoring_5xx_rate("sentinel-sre-2026", "asia-northeast1")("shop")` and confirm the returned `server_error_rate_per_second` value is greater than zero. Record the value.
- [ ] **Step 5. Commit.**

---

### Phase 5: Wire the metric reader into production and redeploy

**Files:**
- Modify: `src/sentinel/main.py`

- [ ] **Step 1.** In `build_deps` at [main.py:50-65](src/sentinel/main.py#L50), add `metric_reader=cloud_monitoring_5xx_rate(settings.project, settings.region)` to the `GcpTelemetryProvider(...)` construction at [main.py:54-57](src/sentinel/main.py#L54), and add `cloud_monitoring_5xx_rate` to the existing import from `sentinel.adapters.gcp_telemetry` at [main.py:9-13](src/sentinel/main.py#L9).
- [ ] **Step 2.** Run the full test suite, pyright, and ruff.
- [ ] **Step 3.** Redeploy the sentinel service with the same deploy command recorded in `deploy/trigger-setup.md`. The Sentinel agent service account already holds the `roles/monitoring.viewer` role, so no new permission is required (confirmed in code validation against `deploy/trigger-setup.md`).
- [ ] **Step 4. Commit.**

---

### Phase 6: Verification against the completion bar

- [ ] **Step 1. No-regression offline check.** Run the Gemini eval harness (`python -m sentinel.eval_cli --diagnoser gemini ...`) and confirm the scorecard still shows ten-out-of-ten action-correctness with zero unsafe autonomous actions. The offline check does not exercise the new metric reader, so the offline check is a guard only.
- [ ] **Step 2. Live trial (the completion bar, Decision 4.A).** Run five staged live incidents. For each staged live incident: inject the checkout fault and generate server-error traffic with `deploy/demo.sh beat1`; then poll the metric reader `cloud_monitoring_5xx_rate` (through a short script) until the returned `server_error_rate_per_second` value is greater than zero, so the Cloud Monitoring point is ingested before the Sentinel agent reads it; then publish the synthetic alert; then restore the shop service with `deploy/demo.sh restore` and clear queued alerts with `deploy/demo.sh reset` before the next staged live incident. Confirm the Sentinel agent rolled back by reading, in the Sentinel agent decision log, the line `sentinel decision ... action=rollback ... requires_human=False` together with the line `sentinel responded ... executed=True rollback={...}` that records the traffic shift from the current revision to the previous revision. As a secondary confirmation, the shop-service `/checkout` endpoint returns status 500 while the checkout fault is active on the current revision and returns status 200 after the rollback moves traffic to the previous revision (which carries no injected fault). Do not use the `/health` endpoint as the signal, because `/health` returns status 200 unconditionally ([app.py:45-47](src/shop/app.py#L45)).
- [ ] **Step 3.** Record the five-out-of-five live-trial result in a committed note or scorecard entry.

## Plan 5 Done-When

- The five-out-of-five live trial passes: the deployed Sentinel agent rolls back in five out of five staged live incidents.
- The offline eval scorecard still shows ten-out-of-ten action-correctness with zero unsafe autonomous actions.
- pyright in strict mode reports zero errors, ruff passes, and the full test suite passes.
- The downgrade-only rule is unchanged: no plan code alters the pipeline decision, only the telemetry input to the diagnoser.
