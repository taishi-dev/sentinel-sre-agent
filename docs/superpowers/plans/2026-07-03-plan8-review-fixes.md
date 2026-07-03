# Plan 8: Whole-project review fixes — handler hardening, honest reporting, spec reconciliation (version 2, post-review)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement the plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Status:** Version 2. Quality Assurance and Architecture subagent reviews complete. Requirements source: the whole-project code-and-spec review of 2026-07-03 (branch V1-sentinel/develop, HEAD fca9d36).

## Revisions incorporated from the Quality Assurance review and the Architecture review (version 2)

1. **(Must-fix, both reviews) `format_rollback_failure` takes primitives, not the outcome object.** `RollbackOutcome` lives in `response.py`, which imports from `messages.py`; passing the object would create a circular import that crashes at startup. The formatter signature is `format_rollback_failure(incident, decision, detail: str, from_revision: str, to_revision: str)` — matching the existing `format_action_report` convention of destructured primitives.
2. **(Must-fix, Architecture 2) `notified` must reflect reality.** `ResponseRecord.notified` is currently hardcoded `True` in all three branches. `_notify_safely` returns a `bool` (delivery succeeded or not), and every branch sets `notified` from that return value — otherwise a swallowed Slack failure would still record `notified=True`, the exact dishonest-reporting class the plan exists to fix.
3. **(Must-fix, QA 2) Phase D must also update the video script.** `docs/submission/video-script.md` quotes the current `beat1` echo line verbatim and builds a presenter warning around it. Phase D now edits both files together: the new echo text in `deploy/demo.sh`, and the video script's presenter-warning paragraph updated to match (the "never curl /health on camera" instruction stays — the rollback-target revision still returns 404 on `/health`; only the "this echo line will appear" wording changes). The Global Constraint is corrected: README stays untouched, but the video script IS updated by Phase D.
4. **(Should-fix, QA 3 + Architecture 7) Dedup cache lives in the `create_app` closure**, mirroring how `pipeline` is already scoped, so each test's fresh `create_app(deps)` gets a fresh cache and there is no cross-test pollution.
5. **(Should-fix, Architecture 3) Dedup check runs BEFORE envelope decoding**, on the raw body's `message.messageId`, so redelivered malformed payloads are short-circuited too (today each redelivery re-runs validation, 400s, and feeds the retry loop).
6. **(Should-fix, QA 4) The diagnosis-failure escalation is a new plain-text formatter, not a forced reuse.** `format_escalation` requires a `Decision` that does not exist when the pipeline raises. New formatter `format_diagnosis_failure(incident, error: str)` in `messages.py`, header `[ESCALATION] Sentinel needs a human.`, body naming the service, alert, and the failure.
7. **(Should-fix, QA 5) Step A6 adds a new test case** for `recovered=False` — no such case exists today, so "update the existing test" was wrong.
8. **(Should-fix, QA 6) Mixed-list sort rule pinned.** If ANY revision object lacks a `create_time` attribute, `_names_newest_first` keeps the entire input order (a naive sort key of `None` raises `TypeError` mid-sort). Test cases: all-sortable out-of-order input, none-sortable, MIXED, and empty.
9. **(Should-fix, Architecture 4) The executor backstop is documented as a backstop.** A comment on `respond()`'s new except-block states the adapter's primary contract is to return a failed `RollbackOutcome` rather than raise; the catch exists for SDK exceptions the adapter cannot anticipate.
10. **(Should-fix, Architecture 8) Spec amendment style split in two.** §17 open questions: extend the section's own existing "Resolved (date): …" list — no new convention. Substantive staleness (status line, ADK references, §6 investigation loop, §11 continuous integration): clean in-place rewrite with ONE top-of-document note ("Updated 2026-07-03 to describe the v0.3.1 implementation as built; the pre-implementation draft is preserved in git history") — no per-section strikethrough.
11. **(Notes adopted) Spec edit line numbers** from the Quality Assurance review: status at line 7; ADK occurrences at lines 61, 66, 85, 161 (×2), 162, 185, 193; §6 loop claim at line 85 and the recovery-verification claim at line 90; §11 jobs at lines 154-155; §17 resolved-list at lines 206-211 and still-open items at lines 213-216. Telemetry-provider failures need no separate guard — `snapshot` is called inside `pipeline.run`, which Step A4 already wraps (Architecture 5). The downgrade-only invariant was re-traced across all new paths and holds (Architecture 6).

## Terms used in this plan

- **push handler** — the `POST /pubsub/push` route in `src/sentinel/server.py` that receives a Pub/Sub push, runs the decision pipeline, and executes the response.
- **respond()** — the dispatch function in `src/sentinel/response.py` that executes a rollback via the `ActionExecutor` port and posts Slack messages via the `Notifier` port.
- **fail toward escalation** — the design promise that any uncertainty or failure results in a human being notified, never a silent error and never an autonomous action.
- **at-least-once redelivery** — Pub/Sub's delivery guarantee: a message answered with a non-2xx status (or not answered in time) is delivered again.

## Decisions (flagged for veto where judgment was applied)

1. **Scope: review findings Critical-1, Important-2, Important-3, Important-4, Important-5, and the spec staleness report, plus the trivial `demo.sh` echo-line fix.** Excluded, with reasons: the credentialed Gemini evaluation job in continuous integration (disclosed debt, not reachable before the deadline), the in-app OIDC audience check (platform Identity and Access Management already enforces the boundary), the pyright 3.14 target (harmless), and the heuristic metric-name divergence (offline-only, documented debt).
2. **Recovery verification (Important-3): reword, do not implement.** A real post-rollback re-read would block the push handler on a multi-minute metric-ingestion wait; too risky days before the deadline. Instead the Slack action report stops claiming an unbuilt feature: when `recovered` is false the line reads `post-rollback: verification pending (manual check recommended)` instead of `recovery NOT confirmed`. The spec records automated recovery verification as a roadmap item. **Flagged for veto** because the alternative (implementing verification) was plausible.
3. **Redelivery deduplication (Important-5): in-memory per-instance cache keyed by the Pub/Sub message identifier, with a time-to-live.** A shared store (Firestore) is out of scope; the Sentinel service is low-traffic and the in-memory limit (deduplication does not survive instance restarts or span instances) is documented in code. Time-to-live: 600 seconds, matching Pub/Sub's default acknowledgement-retry horizon order of magnitude.
4. **Error-handling placement:** notification failures are absorbed inside `respond()` (a notification failure must never fail the request nor re-trigger an action); executor failures are absorbed inside `respond()` (producing a failed-rollback record and an escalation message); diagnosis failures are absorbed in the push handler (escalate to Slack, return 200). Rationale: after any handled decision the handler returns 200 so Pub/Sub does not redeliver into a repeated action.

## Global Constraints

- Test-driven development: each behavior change lands with a failing test first, in the existing offline style (fakes, no cloud).
- pyright strict zero errors, ruff clean, full suite passing.
- The downgrade-only invariant is untouched: no change to `pipeline.decide` or `policy.py`.
- The eval scorecard must be unchanged: `python -m sentinel.eval_cli --diagnoser heuristic` still prints 2/10 root-cause, 9/10 action, 0 unsafe.
- README and submission documents are not changed by this plan (their quoted strings — the two Slack headers and the gate reason — must therefore keep their exact current wording).

---

### Phase A: Harden respond() and the push handler (test-driven)

**Files:** modify `src/sentinel/response.py`, `src/sentinel/messages.py`, `src/sentinel/server.py`; tests in `tests/sentinel/test_response.py`, `tests/sentinel/test_messages.py`, `tests/sentinel/test_server.py`.

- [ ] **Step A1 (Important-2): failing tests, then fix `executed` and the failed-rollback message.** In `respond()`'s ROLLBACK branch ([response.py:64-80](src/sentinel/response.py#L64)): set `executed=outcome.success`; when `outcome.success` is false, send an escalation-style failure message (new formatter `format_rollback_failure(incident, decision, outcome)` in `messages.py`, header `[ESCALATION] Sentinel needs a human.` reusing `_header`, body naming the rollback failure detail) instead of `[AUTONOMOUS ROLLBACK] Sentinel acted.`. Tests: fake executor returning `success=False` → record `executed` is false and the notifier received the failure message, not the action report.
- [ ] **Step A2 (Critical-1c): failing test, then absorb executor exceptions in `respond()`.** Wrap the `executor.rollback(service)` call; on exception, log through the module logger, build a `RollbackOutcome(success=False, ..., detail="rollback raised: <exc>")`, and proceed down the Step-A1 failure path. Test: fake executor that raises → `respond` does not raise, record `executed` false, notifier received the failure message.
- [ ] **Step A3 (Critical-1b): failing tests, then absorb notifier exceptions in `respond()`.** Wrap every `notifier.notify(...)` call (one helper `_notify_safely`): on exception, log a warning and continue. Tests: raising fake notifier on the rollback path and on the escalate path → `respond` does not raise and still returns the correct record.
- [ ] **Step A4 (Critical-1a): failing test, then absorb diagnosis failures in the push handler.** In `server.py`, wrap `pipeline.run(incident)`: on exception, log an error, post `[ESCALATION] Sentinel needs a human.` with a diagnosis-failure reason directly through `deps.notifier` (via the same safe-notify pattern), and return 200 with `{"action": "escalate", "requires_human": True, "executed": False}`. Test: deps whose diagnoser raises → response status 200, body says escalate, fake notifier received a message.
- [ ] **Step A5 (Important-5): failing tests, then message deduplication.** In `server.py`: read the Pub/Sub message identifier from the push body (`body["message"]["messageId"]`, present in real pushes; absent → skip deduplication), keep a per-application in-memory `dict[str, float]` of identifier → monotonic timestamp with a 600-second time-to-live, and when a duplicate arrives return 200 with `{"action": "duplicate", "requires_human": False, "executed": False}` without running the pipeline. Document the per-instance limitation in a comment. Tests: same identifier twice → pipeline ran once; second response marked duplicate; an identifier older than the time-to-live is processed again (inject a fake clock or expose the cache for the test).
- [ ] **Step A6 (Important-3, Decision 2): reword the pending-verification line.** In `format_action_report` ([messages.py:29](src/sentinel/messages.py#L29)): `recovered=False` renders `post-rollback: verification pending (manual check recommended)`; `recovered=True` keeps `recovery confirmed`. Update the existing message test.
- [ ] **Step A7. Verify:** full suite, pyright strict, ruff, and the unchanged heuristic eval scorecard.

### Phase B: Revision-ordering robustness (Important-4)

**Files:** modify `src/sentinel/adapters/gcp_telemetry.py`; tests in `tests/sentinel/test_gcp_telemetry.py`.

- [ ] **Step B1.** Extract a pure helper `_names_newest_first(revisions: Iterable[object]) -> list[str]` that sorts revision objects by `create_time` descending (defensive `getattr`, falling back to input order for objects lacking the attribute) and returns their names — then use the helper inside `cloud_run_revision_lister` instead of relying on the Software Development Kit's default ordering. Offline tests with small fake objects: out-of-order input sorts newest-first; objects without `create_time` keep input order; empty input returns empty list.
- [ ] **Step B2. Verify:** suite, pyright, ruff.

### Phase C: Spec reconciliation (documentation only)

**Files:** modify `docs/superpowers/specs/2026-06-27-sentinel-design.md`.

- [ ] **Step C1.** Apply the staleness corrections from the review: status line → implemented and live-verified (v0.3.1); every "ADK" reference → the `google-genai` Software Development Kit on Vertex AI (delete the "official TypeScript support" sentence); §6 investigate step → single telemetry snapshot plus a single structured Gemini call, moving the multi-step tool-calling loop (query tools, iteration bound) and automated post-rollback recovery verification to an explicit "Roadmap (not built)" subsection; §11 continuous integration → the actual two jobs (cross-platform full unit suite; hermetic heuristic eval gate, no cloud credentials, manual deploy via `deploy/trigger-setup.md`); §17 open questions → mark the alert threshold (5xx rate greater than zero, 60-second alignment, 1800-second auto-close), the Slack webhook storage (Secret Manager `sentinel-slack-webhook`), and the region quota (confirmed by the live trial) as resolved, with an "amended 2026-07-03" note preserving the original text as history where practical.
- [ ] **Step C2. Verify:** no remaining "ADK" occurrences in the spec; the amended sections cite the files that resolve them.

### Phase D: Demo-driver echo line (Minor)

**Files:** modify `deploy/demo.sh`.

- [ ] **Step D1.** Replace the `beat1` WATCH echo ([deploy/demo.sh:38](deploy/demo.sh#L38)) claim about `/health` flipping 200→404 with the reliable signal: Slack gets `[AUTONOMOUS ROLLBACK]`; `/checkout` flips 500→200 after traffic moves to the previous revision. `bash -n` passes.

### Phase E: Verification, pull request, merge

- [ ] **Step E1.** Branch `V1-sentinel/feature/review-fixes` off `V1-sentinel/develop` (created before any Phase A work).
- [ ] **Step E2.** Full verification (pytest, pyright strict, ruff, heuristic eval unchanged), independent review of the branch diff, fixes if found, push, pull request to `V1-sentinel/develop`, merge on green continuous integration.

## Plan 8 Done-When

- All five code findings are fixed with tests proving each failure mode (executor failure, notifier failure, diagnosis failure, duplicate delivery, failed-rollback reporting), and the push handler returns 200 after every handled decision.
- The spec describes the system as built, with the unbuilt investigation loop and recovery verification recorded as roadmap items.
- pyright strict zero errors, ruff clean, full suite green, heuristic eval scorecard unchanged, pull request merged with green continuous integration.
