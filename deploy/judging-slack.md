# Judging Slack — live reproduction for evaluators

Purpose: let a judge trigger a fault on the public `shop` service and watch Sentinel's
autonomous-rollback / refuse-and-escalate message arrive in real time. Sentinel's headline
behavior (the safety judgment) is delivered to Slack, so a dedicated public judging workspace
removes any doubt that the Slack surface only exists "on faith" in the demo video.

This is a **config/deploy change only** — no code change. The Slack webhook lives in Secret
Manager as `sentinel-slack-webhook` and is injected into the `sentinel` service via
`--set-secrets SLACK_WEBHOOK_URL=sentinel-slack-webhook:latest` (see `trigger-setup.md`).

> Never commit the webhook URL. It is a secret and belongs only in Secret Manager.
> The workspace invite link is public and is published in `docs/submission/protopedia.md`.

## Part A — Create the judging Slack (browser)

1. New workspace at <https://slack.com/create> — e.g. "Sentinel Judging". A throwaway
   workspace keeps the real one private.
2. Create a channel, e.g. `#incidents`.
3. Add an Incoming Webhook: <https://api.slack.com/apps> -> Create New App -> From scratch ->
   select the judging workspace -> Incoming Webhooks -> toggle On -> Add New Webhook to
   Workspace -> pick `#incidents` -> copy the `https://hooks.slack.com/services/...` URL.
4. Public invite link: workspace menu -> Invite people -> Create a shareable invite link ->
   set no expiry / high max uses. If greyed out: Admin -> Settings & administration ->
   Workspace settings -> enable shareable invite links.

## Part B — Re-point Sentinel to the judging channel

`:latest` is resolved at instance startup. Add a new secret version, then force one new
revision so it takes effect deterministically (no image rebuild needed).

```bash
# 1. add the judging webhook as a new secret version
printf '%s' "PASTE_JUDGING_WEBHOOK_URL_HERE" \
  | gcloud secrets versions add sentinel-slack-webhook --data-file=- --project sentinel-sre-2026

# 2. roll a new sentinel revision pointing at :latest (fast — no --source rebuild)
gcloud run services update sentinel --region asia-northeast1 --project sentinel-sre-2026 \
  --update-secrets SLACK_WEBHOOK_URL=sentinel-slack-webhook:latest
```

## Part C — Verify before relying on it

```bash
bash deploy/demo.sh    # injects a fault into shop; watch #incidents for Sentinel's message
```

## Part D — Publish the invite link

Add the public invite link to `docs/submission/protopedia.md` under the `関連URL` section.

## After judging (optional revert)

To point back at the original private channel, add that channel's webhook as a new secret
version and repeat Part B step 2:

```bash
printf '%s' "ORIGINAL_WEBHOOK_URL" \
  | gcloud secrets versions add sentinel-slack-webhook --data-file=- --project sentinel-sre-2026
gcloud run services update sentinel --region asia-northeast1 --project sentinel-sre-2026 \
  --update-secrets SLACK_WEBHOOK_URL=sentinel-slack-webhook:latest
```
