# Plan 7: Submission kit — video script, architecture diagram, Proto Pedia entry (version 2, post-review)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement the plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Status:** Version 2. The Quality Assurance subagent review and the Architecture subagent review are complete; key strings were code-validated on 2026-07-03 (citations below).

## Revisions incorporated from the Quality Assurance review and the Architecture review (version 2)

1. **(Must-fix, QA 1) Recovery proof command added.** The demo driver's `beat1` never re-checks `/checkout` after the rollback, so the video script now includes an explicit post-rollback command the presenter runs on camera: `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'` — expected 500 while the fault is live, 200 after the rollback.
2. **(Must-fix, QA 2) Multi-instance fault-state risk mitigated.** The shop service's fault state is in-memory per Cloud Run instance and the deployment sets no instance limits; a scaled-out shop can dilute the staged 5xx burst. The pre-flight checklist now includes a documented one-time recording setting — `gcloud run services update shop --min-instances=1 --max-instances=1 --region asia-northeast1 --project sentinel-sre-2026` — applied before the session and reverted after (`--min-instances=0 --max-instances=default` equivalent), plus a warm-up request so exactly one instance serves.
3. **(Should-fix, QA 3) Terminal-echo contradiction handled.** `beat1` prints "shop /health flips 200 -> 404" to the on-camera terminal; the 404 is an environment artifact (the rollback-target revision predates the `/health` route), not a code guarantee. The script now (a) warns the presenter that the echo line will appear and why, (b) instructs never to curl `/health` on camera, and (c) uses `/checkout` as the only narrated signal.
4. **(Should-fix, QA 4) Full rehearsal scheduled.** The script now mandates one complete non-recorded rehearsal (`reset → restore → beat1 → recovery proof → reset → restore → beat2 → reset`) in the recording shell before the kept take.
5. **(Should-fix, QA 6) Shell pinned.** The demo driver is bash-only; the recording machine is Windows. The pre-flight checklist pins Git Bash as the recording shell and includes verifying all four subcommands run there.
6. **(Should-fix, QA 5) Concrete image-export path.** Phase 1 commits to: wrap the SVG in a minimal HTML file with explicit pixel dimensions, then `msedge --headless=new --screenshot=<png> --window-size=<w>,<h> <html>`; the named fallback is a headed-browser screenshot by the human (documented as such), and the SVG source is committed regardless.
7. **(Should-fix, QA 7) External-source citation honesty.** The Proto Pedia field list comes from the official hackathon page supplied by the user on 2026-07-03 (no stable URL captured); the plan cites it as such, and Phase 3 adds a human step: confirm the live Proto Pedia form fields at entry-creation time. Accepted image formats remain unverified; PNG stays the chosen format.
8. **(Note, QA 8) Timing claim rephrased.** The ~12 seconds figure was measured as time-to-revision-change in the live trial; the script narrates "rollback completes and the Slack report lands in roughly the same ~12 seconds", not a measured Slack latency.
9. **(Should-fix, Architecture 1) Freshness headers.** Both markdown artifacts open with a one-line Japanese freshness marker: 「本書の内容は 2026-07-03 時点のコミット <hash> を基準に検証済み」.
10. **(Should-fix, Architecture 2) Ops gotcha moved into the operational path.** A one-line comment is added to `deploy/demo.sh` next to `reset()` documenting the between-takes gotcha (stray 5xx / retried Pub/Sub messages can trigger spurious rollbacks; fault state is in-memory per instance), so the knowledge survives outside the one-time video script.
11. **(Should-fix, Architecture 3) NOOP outcome added to the diagram.** The outcomes lane shows all three actions — rollback, escalate, and a lighter-weight noop/observe branch (`[OBSERVE]`, [src/sentinel/messages.py:39-44](src/sentinel/messages.py#L39)) — because the three-way judgment strengthens the "knows when not to act" thesis.
12. **(Note, Architecture 6) Beat weighting nudged.** Narration targets beat 1 ≈ 65 seconds and beat 2 ≈ 55 seconds, tilting a little more time toward the refusal beat that carries judging criterion 1.

## Terms used in this plan

- **Sentinel agent** — the autonomous site reliability engineering program in `src/sentinel/` that, on a Cloud Monitoring alert, diagnoses a root cause with Gemini and either autonomously rolls back a Cloud Run revision or escalates to a human via Slack.
- **shop service** — the public demonstration web service (`src/shop/`) at https://shop-71088340431.asia-northeast1.run.app with fault-injection endpoints.
- **demo driver** — the script `deploy/demo.sh` with subcommands `beat1` (code regression → autonomous rollback), `beat2` (personally identifiable information leak → refuse and escalate), `restore`, `reset` ([deploy/demo.sh:63-68](deploy/demo.sh#L63)).
- **Proto Pedia** — the Japanese work-sharing platform the hackathon uses for submissions; required fields include a video URL (YouTube or Vimeo), a system-architecture-diagram image, and a three-part story (①課題と背景 ②想定ユーザー ③プロダクトの特徴).
- **submission kit** — the set of files this plan produces under a new `docs/submission/` directory: the video shooting script, the architecture diagram (SVG source and PNG export), and the Proto Pedia entry text.
- **beat** — one staged incident segment in the demonstration video.

## Decisions already made

1. **Language: Japanese for submission-facing artifacts** (recommendation 1.A adopted after a 60-second no-response timeout, 2026-07-03). The video narration script and the Proto Pedia entry text are Japanese with technical terms kept in English; the repository stays English.
2. **Video format (resolved by judgment, flagged for veto):** a screen recording of about 3 minutes — terminal (demo driver), Slack channel, and the shop service in a browser — with Japanese narration. Structure: hook (the problem) → beat 1 (autonomous rollback, ~70 seconds) → beat 2 (refusal + escalation, ~50 seconds; the differentiator) → evidence and closing (~30 seconds). Rationale: first-round judges skim; the refusal beat is what distinguishes Sentinel under judging criterion 1 ("autonomous judgment", "necessity of being an agent").
3. **Deployed-URL strategy (resolved by judgment, flagged for veto):** submit the public shop service URL as the verifiable deployed component, and present the Sentinel service's authenticated-only ingress as a deliberate least-privilege security posture (judging criterion 5, implementation ability) documented in the Proto Pedia text. Changing the deployment days before the deadline is riskier than explaining it.
4. **Diagram format:** hand-authored SVG (versionable, editable) exported to PNG for upload. **Unverified and flagged:** Proto Pedia's accepted image formats were not verifiable from the pasted page; PNG is the safest universal choice.

**Goal:** produce, review, and commit the three submission artifacts so that the only remaining human steps before the 2026-07-10 deadline are: record the video following the script, upload the video to YouTube or Vimeo, create the Proto Pedia entry by pasting the prepared text and uploading the prepared image, and fill the final Google Form.

## Global Constraints

- **Every command, Uniform Resource Locator, log line, and Slack message quoted in the video script must be verified against the source.** Verified so far: Slack headers `[AUTONOMOUS ROLLBACK] Sentinel acted.` ([src/sentinel/messages.py:31](src/sentinel/messages.py#L31)) and `[ESCALATION] Sentinel needs a human.` ([src/sentinel/messages.py:15](src/sentinel/messages.py#L15)); gate reason `root cause 'pii_exposure' is sensitive` ([src/sentinel/policy.py:56](src/sentinel/policy.py#L56)); decision log lines `sentinel decision service=... action=... requires_human=...` and `sentinel responded action=... executed=... rollback=...` ([src/sentinel/server.py:44-60](src/sentinel/server.py#L44)); demo driver subcommands and hardcoded project/URL ([deploy/demo.sh:16-21](deploy/demo.sh#L16), [deploy/demo.sh:63-68](deploy/demo.sh#L63)).
- **The architecture diagram uses the same stage vocabulary as the README Mermaid diagram and `deploy/trigger-setup.md`** (shop 5xx → Monitoring alert policy → Pub/Sub topic sentinel-alerts → push subscription OIDC → POST /pubsub/push → investigate → diagnose → gate → rollback / Slack), so the three diagrams never describe different systems.
- **The Proto Pedia text must satisfy every required field from the official rules:** title, overview, video URL placeholder, system-architecture image, development-tools list (開発素材), tag `findy_hackathon`, three-part story.
- **No live cloud mutation during this plan.** The script documents live commands; executing them is the recording session, a human step.
- **Japanese prose quality:** natural engineering Japanese (だ・である or です・ます consistently — です・ます for narration,体言止め acceptable in Proto Pedia bullets), technical terms in English.

---

### Phase 1: Architecture diagram (SVG + PNG)

**Files:** create `docs/submission/architecture.svg`, `docs/submission/architecture.png`.

- [ ] **Step 1.** Author the SVG by hand: a left-to-right component flow with the stage vocabulary above, grouped into three lanes — Google Cloud managed services (Monitoring, Pub/Sub), the Sentinel agent on Cloud Run (investigate → diagnose with Gemini 2.5 Flash → two-gate policy), and outcomes showing **all three actions** (Cloud Run traffic rollback / Slack escalation / a lighter noop-observe branch, revision 11). Include the shop service as the monitored target and label the trust boundary (sentinel: authenticated-only ingress, least-privilege service account). Text in English (diagram is shared between the English repository and the Japanese entry; Proto Pedia norms accept English diagrams).
- [ ] **Step 2.** Wrap the SVG in a minimal HTML file with explicit pixel dimensions, then export PNG via `msedge --headless=new --screenshot=<png-path> --window-size=<w>,<h> <html-path>`, width ≥1600 pixels for legibility (revision 6). Named fallback if the headless flags misbehave on this machine: a headed-browser screenshot taken by the human, documented as a human step. The SVG source is committed regardless.
- [ ] **Step 3. Verify:** PNG opens and is legible (read the image back); SVG parses (open in Edge or an XML parse).
- [ ] **Step 4.** Add the between-takes operational comment to `deploy/demo.sh` next to `reset()` (revision 10): stray 5xx responses or retried Pub/Sub messages can trigger spurious rollbacks between takes, and shop fault state is in-memory per instance — always run `reset` and `restore` between takes.

### Phase 2: Video shooting script (Japanese)

**Files:** create `docs/submission/video-script.md`.

- [ ] **Step 1.** Pre-flight checklist section, in order (revisions 2, 4, 5): recording shell is **Git Bash** and all four demo-driver subcommands have been exercised in Git Bash; one-time instance pinning `gcloud run services update shop --min-instances=1 --max-instances=1 --region asia-northeast1 --project sentinel-sre-2026` (revert after the session) plus one warm-up request to `/`; `deploy/demo.sh reset` then `restore`; confirm `/checkout` returns 200 (never `/health` — revision 3); Slack channel visible; terminal font size; `gcloud` authenticated; screen layout (terminal left, Slack right, browser tab with shop); **one full non-recorded rehearsal** (`reset → restore → beat1 → recovery proof → reset → restore → beat2 → reset`) before the kept take.
- [ ] **Step 2.** Timed narration table (columns: time, on-screen action, narration in Japanese) covering: hook (~20 s, the problem: 深夜のアラート対応 and the risk of blind auto-remediation); beat 1 (~65 s, revision 12: `deploy/demo.sh beat1`, watch the Slack `[AUTONOMOUS ROLLBACK]` message land — rollback and report complete in roughly the same ~12 seconds measured as time-to-revision-change in the live trial (revision 8) — then run the recovery proof `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'` showing 500 before and 200 after (revision 1)); beat 2 (~55 s, revision 12: `deploy/demo.sh beat2`, watch `[ESCALATION]` with reason `root cause 'pii_exposure' is sensitive`, emphasize the deterministic gate refusing autonomy); evidence + close (~30 s: scorecard 10/10 with zero unsafe actions, continuous-integration eval gate, 5/5 live trial, README).
- [ ] **Step 3.** Presenter warnings section (revision 3): the `beat1` terminal echo prints "shop /health flips 200 -> 404" — explain on paper that the 404 is an environment artifact (the rollback-target revision predates the `/health` route) and instruct the presenter to ignore the line on camera and never to curl `/health`.
- [ ] **Step 4.** Failure-recovery section: what to do if a beat misbehaves on camera (`reset`, `restore`, re-inject; the between-takes gotcha now also documented in `deploy/demo.sh` per revision 10).
- [ ] **Step 5. Verify:** every quoted command, URL, log line, and Slack string in the script matches the verified strings in Global Constraints; the file opens with the Japanese freshness header (revision 9); narration timing sums to ≤ 3 minutes 10 seconds.

### Phase 3: Proto Pedia entry text (Japanese)

**Files:** create `docs/submission/protopedia.md`.

- [ ] **Step 1.** Draft every required field: 作品タイトル; 概要 (2-3 sentences); ストーリー ①課題と背景 (alert fatigue, the danger of naive auto-remediation, "the value is knowing when NOT to act"), ②想定ユーザー (small teams running services on Cloud Run without a dedicated site-reliability-engineering rotation), ③プロダクトの特徴 (two-gate safety design, measured zero-unsafe eval gate in continuous integration, 5/5 live rollback trial, least-privilege deployment); システム構成 supplementary text (one paragraph naming the diagram stages); 開発素材 (Python, FastAPI, Pydantic, Gemini 2.5 Flash / Vertex AI, google-genai, Cloud Run, Cloud Logging, Cloud Monitoring, Pub/Sub, Secret Manager, GitHub Actions, pytest, pyright, ruff); タグ (`findy_hackathon` plus discretionary tags); 関連URL (GitHub repository, shop service URL); video URL placeholder.
- [ ] **Step 2.** A short "submission-form answers" section for the final Google Form: GitHub URL, deployed URL (shop, with the one-sentence security-posture explanation of the authenticated-only sentinel service), Proto Pedia URL placeholder.
- [ ] **Step 3. Verify:** field-by-field check against the official requirements table (source: the official hackathon page supplied by the user on 2026-07-03, revision 7); all facts consistent with the README and scorecards; the file opens with the Japanese freshness header (revision 9). A human step remains at entry-creation time: confirm the live Proto Pedia form fields match, because the live form was not fetchable during planning.

### Phase 4: Review, commit, pull request

- [ ] **Step 1.** Branch `V1-sentinel/feature/submission-kit` off `V1-sentinel/develop`.
- [ ] **Step 2.** Task review of all three artifacts (facts, Japanese quality, field completeness).
- [ ] **Step 3.** Verification commands (pytest, ruff, pyright) before push, per the standing rule; commit; push; pull request to `V1-sentinel/develop`; merge on green continuous integration.

## Plan 7 Done-When

- `docs/submission/` contains the reviewed video script (Japanese, timed, all strings verified), the architecture diagram (SVG + legible PNG), and the Proto Pedia entry text (Japanese, every required field drafted).
- The remaining human steps are exactly: record, upload video, paste into Proto Pedia, fill the Google Form.
- The pull request is merged into `V1-sentinel/develop` with green continuous integration.
