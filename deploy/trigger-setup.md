# Sentinel deployment & event trigger

Reproducible setup for the live demo on GCP project `sentinel-sre-2026`
(project number `71088340431`), region `asia-northeast1`.

Event flow:

```
shop 5xx  ->  Monitoring alert policy  ->  Pub/Sub notification channel
          ->  topic sentinel-alerts     ->  push subscription (OIDC)
          ->  sentinel /pubsub/push      ->  investigate -> diagnose -> gate
          ->  rollback shop revision + Slack report
```

## 1. Services

- **shop** (victim, public): `gcloud run deploy shop --source . --region asia-northeast1 --allow-unauthenticated`
- **sentinel** (agent, authenticated-only), running as the scoped agent SA, webhook from Secret Manager:

```bash
gcloud run deploy sentinel --source . --region asia-northeast1 \
  --service-account sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --set-env-vars APP_TARGET=sentinel.main:create_app_from_env,GOOGLE_CLOUD_PROJECT=sentinel-sre-2026,GOOGLE_CLOUD_REGION=asia-northeast1 \
  --set-secrets SLACK_WEBHOOK_URL=sentinel-slack-webhook:latest
```

## 2. Scoped agent service account (`sentinel-agent`)

Least privilege: read telemetry, call Gemini, shift traffic on shop only.

```bash
gcloud iam service-accounts create sentinel-agent --display-name="Sentinel SRE agent"

# project-level read + Gemini
for r in roles/logging.viewer roles/monitoring.viewer roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding sentinel-sre-2026 \
    --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" --role="$r"
done

# traffic control on shop ONLY, plus the two grants a Cloud Run traffic update needs:
gcloud run services add-iam-policy-binding shop --region asia-northeast1 \
  --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" --role="roles/run.developer"
# poll the traffic-update long-running operation (operations are location-scoped,
# so the service-scoped run.developer grant above does NOT cover run.operations.get;
# without this, operation.result() in the traffic shifter fails with 403):
gcloud projects add-iam-policy-binding sentinel-sre-2026 \
  --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" --role="roles/run.viewer"
# read the image being routed:
gcloud artifacts repositories add-iam-policy-binding cloud-run-source-deploy --location=asia-northeast1 \
  --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" --role="roles/artifactregistry.reader"
# act as shop's runtime SA (shop runs as the default compute SA):
gcloud iam service-accounts add-iam-policy-binding 71088340431-compute@developer.gserviceaccount.com \
  --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" --role="roles/iam.serviceAccountUser"
```

## 3. Secret (Slack webhook)

```bash
printf '%s' "$SLACK_WEBHOOK_URL" | gcloud secrets create sentinel-slack-webhook --data-file=-
gcloud secrets add-iam-policy-binding sentinel-slack-webhook \
  --member="serviceAccount:sentinel-agent@sentinel-sre-2026.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 4. Pub/Sub topic + authenticated push subscription

```bash
gcloud pubsub topics create sentinel-alerts

gcloud iam service-accounts create sentinel-invoker --display-name="Pub/Sub push -> sentinel invoker"
gcloud run services add-iam-policy-binding sentinel --region asia-northeast1 \
  --member="serviceAccount:sentinel-invoker@sentinel-sre-2026.iam.gserviceaccount.com" --role="roles/run.invoker"
# let the Pub/Sub service agent mint OIDC tokens for the invoker SA:
gcloud beta services identity create --service=pubsub.googleapis.com
gcloud iam service-accounts add-iam-policy-binding sentinel-invoker@sentinel-sre-2026.iam.gserviceaccount.com \
  --member="serviceAccount:service-71088340431@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

gcloud pubsub subscriptions create sentinel-alerts-push \
  --topic=sentinel-alerts \
  --push-endpoint="https://sentinel-71088340431.asia-northeast1.run.app/pubsub/push" \
  --push-auth-service-account=sentinel-invoker@sentinel-sre-2026.iam.gserviceaccount.com \
  --ack-deadline=60
```

## 5. Monitoring alert policy -> Pub/Sub notification channel

```bash
# notification channel targeting the topic
gcloud beta monitoring channels create --type=pubsub --display-name="Sentinel Pub/Sub" \
  --channel-labels="topic=projects/sentinel-sre-2026/topics/sentinel-alerts"
# allow Monitoring to publish to the topic (the notification SA is created on channel create):
gcloud pubsub topics add-iam-policy-binding sentinel-alerts \
  --member="serviceAccount:service-71088340431@gcp-sa-monitoring-notification.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
# the alert policy (references the channel id in the JSON):
gcloud alpha monitoring policies create --policy-from-file=deploy/alert-policy.json
```

See `deploy/alert-policy.json` for the shop 5xx condition. The notification-channel
id in that file (`notificationChannels/13395857036823536516`) is environment-specific;
regenerate it if recreating the channel.

## Demo

Inject a fault and generate 5xx; the alert fires and the agent rolls back autonomously:

```bash
curl -X POST "$SHOP_URL/admin/inject" -H 'Content-Type: application/json' -d '{"fault":"checkout_error","fail_count":100}'
for i in $(seq 1 20); do curl -s -o /dev/null -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'; done
```

For a fast (no-wait) demo, publish a synthetic alert directly to the topic instead:

```bash
gcloud pubsub topics publish sentinel-alerts \
  --message='{"incident":{"resource":{"labels":{"service_name":"shop"}},"condition_name":"shop_error_rate_high","started_at":0,"state":"open"}}'
```
