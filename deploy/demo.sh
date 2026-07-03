#!/usr/bin/env bash
# Sentinel live demo driver.
#
#   ./deploy/demo.sh beat1    routine code regression  -> AUTONOMOUS ROLLBACK
#   ./deploy/demo.sh beat2    sensitive PII exposure   -> REFUSE + ESCALATE (gate-enforced)
#   ./deploy/demo.sh restore  put shop back on the latest revision, clear faults
#   ./deploy/demo.sh reset    drop any queued alerts (clean slate between runs)
#
# Beats trigger via the fast synthetic-alert path (publish to the topic) for stage
# reliability; the real Monitoring alert policy runs the identical loop from a live
# SLO breach (see deploy/alert-policy.json), just with a few minutes of ingestion lag.
#
# Env overrides: PROJECT, REGION, SHOP_URL, TOPIC, SUBSCRIPTION, GCLOUD.
set -euo pipefail

PROJECT="${PROJECT:-sentinel-sre-2026}"
REGION="${REGION:-asia-northeast1}"
TOPIC="${TOPIC:-sentinel-alerts}"
SUBSCRIPTION="${SUBSCRIPTION:-sentinel-alerts-push}"
SHOP_URL="${SHOP_URL:-https://shop-71088340431.asia-northeast1.run.app}"
GCLOUD="${GCLOUD:-gcloud}"

_alert() {
  "$GCLOUD" pubsub topics publish "$TOPIC" --project "$PROJECT" \
    --message='{"incident":{"resource":{"labels":{"service_name":"shop"}},"condition_name":"shop_error_rate_high","started_at":0,"state":"open"}}' >/dev/null
  echo "  -> published alert to $TOPIC (agent will wake, investigate, and decide)"
}
_inject()  { curl -s -o /dev/null -X POST "$SHOP_URL/admin/inject" -H 'Content-Type: application/json' -d "{\"fault\":\"$1\",\"fail_count\":100}"; }
_clear()   { curl -s -o /dev/null -X POST "$SHOP_URL/admin/clear"  -H 'Content-Type: application/json' -d '{}'; }
_health()  { curl -s -o /dev/null -w '%{http_code}' "$SHOP_URL/health"; }

beat1() {
  echo "BEAT 1  routine code regression -> autonomous rollback"
  _clear; _inject checkout_error
  echo "  injecting checkout errors and generating 5xx traffic..."
  for i in $(seq 1 20); do curl -s -o /dev/null -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'; done
  _alert
  echo "  WATCH: Slack gets [AUTONOMOUS ROLLBACK]; shop /health flips 200 -> 404 (traffic moved to the previous revision)."
}

beat2() {
  echo "BEAT 2  sensitive PII exposure -> refuse + escalate"
  _clear; _inject pii_leak
  echo "  injecting a PII leak and generating exposures via /export..."
  for i in $(seq 1 40); do curl -s -o /dev/null "$SHOP_URL/export?user_id=u-$i"; done
  _alert
  echo "  WATCH: Slack gets [ESCALATION] pii_exposure; shop is NOT touched. The deterministic gate forbids acting on sensitive incidents."
}

restore() {
  echo "RESTORE  traffic -> latest revision, clear faults"
  "$GCLOUD" run services update-traffic shop --to-latest --region "$REGION" --project "$PROJECT" --quiet >/dev/null
  _clear
  echo "  shop /health = $(_health)"
}

# Between takes/runs: stray 5xx or retried Pub/Sub messages can trigger spurious
# rollbacks, and shop fault state is in-memory per instance -- always reset + restore.
reset() {
  echo "RESET  dropping any queued alerts"
  "$GCLOUD" pubsub subscriptions seek "$SUBSCRIPTION" --time="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --project "$PROJECT" >/dev/null
  echo "  subscription backlog cleared"
}

case "${1:-}" in
  beat1) beat1 ;;
  beat2) beat2 ;;
  restore) restore ;;
  reset) reset ;;
  *) echo "usage: $0 {beat1|beat2|restore|reset}"; exit 1 ;;
esac
