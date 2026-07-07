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
DEMO_BRANCH="${DEMO_BRANCH:-V1-sentinel/exp-red-ci-demo}"
ACTIONS_URL="${ACTIONS_URL:-https://github.com/taishi-dev/sentinel-sre-agent/actions}"

# Any abnormal exit (set -e abort, Ctrl-C) must not leave shop mid-fault:
# restore traffic + clear faults + drop queued alerts before exiting.
cleanup_on_abort() {
  ec=$?
  if [ "$ec" -ne 0 ]; then
    echo "ABORT (exit $ec) — shop を復旧して終了します" >&2
    ./deploy/demo.sh restore || true
    ./deploy/demo.sh reset || true
    if [ "${BEAT3_PUSHED:-}" = "1" ]; then
      git push origin --delete "$DEMO_BRANCH" 2>/dev/null || true
    fi
  fi
  exit "$ec"
}
trap cleanup_on_abort EXIT

cue()  { printf '\n\033[1;36m════ %s ════\033[0m\n' "$*"; }
say() {
  # Presenter-only reading prompts. Hidden during the real take (the off-screen
  # transcript is keyed to the banner cues); PROMPTS=1 shows them for rehearsal.
  if [ "${PROMPTS:-}" = "1" ]; then printf '\033[1;33m読む: %s\033[0m\n' "$*"; fi
}
cls()  { clear 2>/dev/null || printf '\033c'; }
pause() {
  # `|| true`: EOF on stdin must never abort a live take. The prompt is dim and
  # minimal so it stays unobtrusive on camera.
  if [ "${AUTO:-}" = "1" ]; then sleep 2; else read -r -p $'\n\033[2m[Enter]\033[0m ' || true; fi
}
run() {  # print the command like a typed prompt, then execute it
  printf '\n\033[1;32m$ %s\033[0m\n' "$*"
  sleep 1
  "$@"
}
checkout_code() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 8 -X POST "$SHOP_URL/checkout" \
    -H 'Content-Type: application/json' -d '{}'
}
latest_decision() {
  "$GCLOUD" run services logs read sentinel --region "$REGION" --project "$PROJECT" \
    --limit 50 2>/dev/null | grep "sentinel decision" | tail -1
}

# ---- preflight (before the recorder starts) --------------------------------
cls
cue "準備チェック（録画前）"
./deploy/demo.sh reset
./deploy/demo.sh restore
code="$(checkout_code || echo 000)"
echo "checkout preflight: $code"
if [ "$code" != "200" ]; then
  echo "ABORT: /checkout が 200 ではない。/admin/clear を実行してやり直す。" >&2
  exit 1
fi
baseline_decision="$(latest_decision || true)"
cls
cue "録画を開始してから Enter（この画面から本番）"
pause

# ---- 0:00 hook --------------------------------------------------------------
cls
printf '\n\033[1m  Sentinel — an autonomous SRE agent that knows when NOT to act\n'
printf '  DevOps × AI Agent Hackathon 2026\033[0m\n'
say "フック（0:00-0:20 の行）を読む"
pause

# ---- 0:20 beat 1 ------------------------------------------------------------
cue "BEAT 1  コード起因の障害 → 自律ロールバック"
say "0:20-0:40 の行を読みながら待つ"
run ./deploy/demo.sh beat1
printf '\n障害発生中の checkout（500 が出る）:\n'
run curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'
say "0:40-1:05 の行を読む — Slack に [AUTONOMOUS ROLLBACK] が届くのを待つ（実測 20〜25 秒）"
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
run curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 -X POST "$SHOP_URL/checkout" -H 'Content-Type: application/json' -d '{}'
say "1:05-1:25 の行を読む（障害中は500、いまは200）"
pause

# ---- 1:25 beat 2 ------------------------------------------------------------
cue "BEAT 2  PII 漏えい → 拒否してエスカレーション"
say "1:25-1:45 の行を読みながら待つ"
run ./deploy/demo.sh reset
run ./deploy/demo.sh restore
run ./deploy/demo.sh beat2
say "1:45-2:20 の行を読む — Slack に [ESCALATION] が届くのを待つ（実測 20〜25 秒）"
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

# ---- Beat 3: prove the eval gate bites (opt-in via BEAT3=1) -----------------
if [ "${BEAT3:-}" = "1" ]; then
  cue "BEAT 3  ゲートは飾りではない — 危険な自律行動で CI を赤にする"
  say "Beat 3 の行を読みながらプッシュする"
  run git push origin "$DEMO_BRANCH"
  BEAT3_PUSHED=1
  printf '\nGitHub Actions を開く: %s\n' "$ACTIONS_URL"
  printf 'eval gate ジョブを開く（unit ジョブも赤になるが、狙いは eval gate）。\n'
  printf 'eval gate のログが EVAL GATE FAILED: 1 unsafe autonomous action(s) になるのを待つ\n'
  say "eval gate ジョブを開き、EVAL GATE FAILED の行を指す"
  pause
fi

# ---- cleanup ------------------------------------------------------------------
printf '\n\033[2m（録画を停止してから Enter — 後片付けが走る）\033[0m\n'
pause
run ./deploy/demo.sh restore
run ./deploy/demo.sh reset
if [ "${BEAT3_PUSHED:-}" = "1" ]; then
  git push origin --delete "$DEMO_BRANCH" 2>/dev/null || true
fi
echo
echo "完了。checkout: $(checkout_code)（200 なら正常）"
