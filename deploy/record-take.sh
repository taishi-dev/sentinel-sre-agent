#!/usr/bin/env bash
# Self-driving take driver for the submission video (docs/submission/video-script.md).
#
# The presenter starts the screen recorder, runs this script, reads the narration
# aloud, and presses Enter to advance. The script runs every command visibly,
# waits on real events (checkout 500->200, escalation in the agent log), and
# never lets the take run ahead of the presenter.
#
#   ./deploy/record-take.sh          interactive take (Enter-paced)
#   AUTO=1 ./deploy/record-take.sh   unattended validation run (short sleeps)
set -euo pipefail

PROJECT="${PROJECT:-sentinel-sre-2026}"
REGION="${REGION:-asia-northeast1}"
SHOP_URL="${SHOP_URL:-https://shop-71088340431.asia-northeast1.run.app}"
GCLOUD="${GCLOUD:-gcloud}"

cue()  { printf '\n\033[1;36m════ %s ════\033[0m\n' "$*"; }
say()  { printf '\033[1;33m読む: %s\033[0m\n' "$*"; }
pause() {
  if [ "${AUTO:-}" = "1" ]; then sleep 2; else read -r -p $'\n   [Enter で次へ]\n'; fi
}
run() {  # print the command like a typed prompt, then execute it
  printf '\n\033[1;32m$ %s\033[0m\n' "$*"
  sleep 1
  "$@"
}
checkout_code() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "$SHOP_URL/checkout" \
    -H 'Content-Type: application/json' -d '{}'
}
latest_decision() {
  "$GCLOUD" run services logs read sentinel --region "$REGION" --project "$PROJECT" \
    --limit 20 2>/dev/null | grep "sentinel decision" | tail -1
}

# ---- preflight (before the recorder starts) --------------------------------
clear
cue "準備チェック（録画前）"
./deploy/demo.sh reset
./deploy/demo.sh restore
code="$(checkout_code)"
echo "checkout preflight: $code"
if [ "$code" != "200" ]; then
  echo "ABORT: /checkout が 200 ではない。/admin/clear を実行してやり直す。" >&2
  exit 1
fi
baseline_decision="$(latest_decision || true)"
clear
cue "録画を開始してから Enter（この画面から本番）"
pause

# ---- 0:00 hook --------------------------------------------------------------
clear
printf '\n\033[1m  Sentinel — an autonomous SRE agent that knows when NOT to act\n'
printf '  DevOps × AI Agent Hackathon 2026\033[0m\n'
say "フック（0:00-0:20 の行）を読む"
pause

# ---- 0:20 beat 1 ------------------------------------------------------------
cue "BEAT 1  コード起因の障害 → 自律ロールバック"
say "0:20-0:40 の行を読みながら待つ"
run ./deploy/demo.sh beat1
printf '\n障害発生中の checkout（500 が出る）:\n'
run bash -c "curl -s -o /dev/null -w '%{http_code}\n' -X POST '$SHOP_URL/checkout' -H 'Content-Type: application/json' -d '{}'"
say "0:40-1:05 の行を読む — Slack に [AUTONOMOUS ROLLBACK] が届くのを待つ（約25秒）"
printf 'ロールバック完了を待機中 '
recovered=""
for _ in $(seq 1 30); do
  sleep 4
  printf '.'
  if [ "$(checkout_code)" = "200" ]; then recovered=1; break; fi
done
echo
if [ -z "$recovered" ]; then
  echo "ABORT: 90秒待ってもロールバックしない。reset/restore して再テイク。" >&2
  exit 1
fi
cue "ロールバック完了 — 復旧を実演"
printf '復旧後の checkout（200 が出る）:\n'
run bash -c "curl -s -o /dev/null -w '%{http_code}\n' -X POST '$SHOP_URL/checkout' -H 'Content-Type: application/json' -d '{}'"
say "1:05-1:25 の行を読む（障害中は500、いまは200）"
pause

# ---- 1:25 beat 2 ------------------------------------------------------------
cue "BEAT 2  PII 漏えい → 拒否してエスカレーション"
say "1:25-1:45 の行を読みながら待つ"
run ./deploy/demo.sh reset
run ./deploy/demo.sh restore
run ./deploy/demo.sh beat2
say "1:45-2:20 の行を読む — Slack に [ESCALATION] が届くのを待つ（約25秒）"
printf 'エスカレーション判断を待機中 '
decision=""
for _ in $(seq 1 30); do
  sleep 4
  printf '.'
  d="$(latest_decision || true)"
  if [ -n "$d" ] && [ "$d" != "$baseline_decision" ] && printf '%s' "$d" | grep -q "pii_exposure"; then
    decision="$d"
    break
  fi
done
echo
if [ -z "$decision" ]; then
  echo "ABORT: 90秒待ってもエスカレーション判断が出ない。reset/restore して再テイク。" >&2
  exit 1
fi
cue "エージェントの判断ログ（shop は無傷）"
printf '%s\n' "$decision"
pause

# ---- 2:20 close --------------------------------------------------------------
cue "クロージング — ブラウザでスコアカード / CI / ライブ試験を見せる"
say "2:20-2:50 の行を読む → 読み終わったら Enter"
pause

# ---- cleanup ------------------------------------------------------------------
cue "録画を停止してから Enter（後片付けが走る）"
pause
run ./deploy/demo.sh restore
run ./deploy/demo.sh reset
echo
echo "完了。checkout: $(checkout_code)（200 なら正常）"
