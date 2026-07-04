# Sentinel デモ動画 撮影台本（約3分 / ナレーション日本語）

> 本書の内容は 2026-07-03 時点のコミット ac7fe55 を基準に検証済み。引用しているコマンド・ログ行・Slack メッセージはすべてソースコードと照合済みです。

## 0. 撮影前チェックリスト（順番どおりに実施）

1. **シェルは Git Bash を使う。** `deploy/demo.sh` は bash 専用（`seq` / `date -u` / `curl` を使用）。撮影前に 4 つのサブコマンド（`reset` / `restore` / `beat1` / `beat2`）がすべて Git Bash で動くことを一度確認しておく。
2. **shop を単一インスタンスに固定する（撮影中のみ）。** shop の障害状態はインスタンスごとのメモリ内にあるため、スケールアウトしていると 5xx が薄まる。
   ```
   gcloud run services update shop --min-instances=1 --max-instances=1 \
     --region asia-northeast1 --project sentinel-sre-2026
   ```
   ウォームアップとして `curl -s https://shop-71088340431.asia-northeast1.run.app/ > /dev/null` を 1 回実行。**撮影後は必ず元に戻す**（`--min-instances=0 --max-instances=100` 相当のデフォルトへ）。
3. `./deploy/demo.sh reset` → `./deploy/demo.sh restore` を実行し、たまったアラートを破棄して最新リビジョンに戻す。
4. `/checkout` が 200 を返すことを確認する（**`/health` は使わない** — 後述の注意 2 を参照）:
   ```
   curl -s -o /dev/null -w '%{http_code}\n' -X POST \
     "https://shop-71088340431.asia-northeast1.run.app/checkout" \
     -H 'Content-Type: application/json' -d '{}'
   ```
5. Slack の通知チャンネルを画面に表示。`gcloud` の認証を確認。ターミナルのフォントを拡大（録画で読めるサイズ）。
6. 画面レイアウト: 左にターミナル、右に Slack、ブラウザタブに shop。
7. **本番テイクの前に、録画なしで通し稽古を 1 回行う**: `reset → restore → beat1 → 復旧確認 curl → reset → restore → beat2 → reset`。

> **本番テイクは `./deploy/record-take.sh` 一発で進行できる。** テイク駆動スクリプトがすべてのコマンドを画面上で実行し、実イベント（checkout の 500→200、エスカレーション判断ログ）を待機し、各ナレーション行の読み上げ位置を画面に表示する。撮影者は録画開始・ナレーション読み上げ・Enter キーだけを担当する（2026-07-04 に無人検証済み）。

## 1. ナレーション進行表（合計 約2分50秒）

| 時間 | 画面上の操作 | ナレーション（日本語） |
|---|---|---|
| 0:00–0:20 | タイトル / README を一瞬表示 | 深夜、サービスの 5xx アラートで起こされる。眠い頭でログを漁り、直近のデプロイを疑い、ロールバックを打つ——この一連の対応を安全に任せられる AI エージェントを作りました。Sentinel です。Sentinel の価値はロールバックの実行ではなく、「いつ動いて、いつ動かないか」の判断にあります。 |
| 0:20–0:40 | `./deploy/demo.sh beat1` を実行 | まずは、よくあるコード起因の障害です。デモ用の shop サービスにチェックアウト障害を注入し、5xx を発生させ、アラートを発報します。 |
| 0:40–1:05 | Slack に `[AUTONOMOUS ROLLBACK] Sentinel acted.` が届くのを見せる | アラートは Pub/Sub 経由で Sentinel に届きます。Sentinel は Cloud Logging のログとリビジョン履歴を調査し、Gemini で根本原因を診断——Slack に自律ロールバックの報告が届きました。診断は code_regression。トラフィックは前のリビジョンへ切り替わっています。リビジョン切り替えからこの報告までは、実測でおおむね 12 秒です。 |
| 1:05–1:25 | 復旧確認コマンドを実行し `200` を見せる:<br>`curl -s -o /dev/null -w '%{http_code}\n' -X POST "https://shop-71088340431.asia-northeast1.run.app/checkout" -H 'Content-Type: application/json' -d '{}'` | 実際に checkout を叩いて確かめます。障害中は 500 でしたが——いまは 200。ユーザー影響は解消しました。ここまで人間は一切操作していません。 |
| 1:25–1:45 | `./deploy/demo.sh reset` → `./deploy/demo.sh restore` → `./deploy/demo.sh beat2` を実行 | 次が本題です。今度は性質の違う障害——個人情報がログに漏えいする PII 障害を注入します。同じアラート、同じパイプラインです。 |
| 1:45–2:20 | Slack に `[ESCALATION] Sentinel needs a human.`（reason: `escalated by policy gate: root cause 'pii_exposure' is sensitive`）が届くのを見せる | しかし今度は、Sentinel はロールバックしません。Slack に届いたのはエスカレーションです。理由の欄には「escalated by policy gate — root cause 'pii_exposure' is sensitive」。個人情報や セキュリティ起因の障害は、LLM の確信度がどれだけ高くても、決定論的なポリシーゲートが自律行動を禁止し、人間に引き継ぎます。この抑制はプロンプトではなく、コードで強制されています。 |
| 2:20–2:50 | scorecard（10/10・unsafe 0）、GitHub Actions の eval gate、`scorecards/v0.3.1-live-trial.md`（5/5）を順に表示 | 安全性は「主張」ではなく「測定」です。10 種類の障害シナリオによる評価で、根本原因・アクションともに 10/10、危険な自律行動はゼロ。この評価は CI で毎プッシュ実行され、危険な自律行動が 1 件でもあれば CI が失敗します。ライブ試験でも 5 回中 5 回、自律ロールバックに成功。「動くとき」と「動かないとき」を知っている自律 SRE エージェント、Sentinel でした。 |

## 2. 撮影者向け注意（カメラに映る前に読む）

1. **`beat1` のターミナル出力は `/checkout flips 500 -> 200` を案内する**（2026-07-03 のコミットで `/health` への言及を除去済み）。ナレーションもこの `/checkout` シグナルに合わせる。
2. **カメラの前で `/health` を curl しない。** ロールバック先の旧リビジョンは `/health` ルート追加前のビルドのため 404 が返り、デモが壊れたように見える。復旧確認は必ず `/checkout`（500 → 200）で行う。
3. Slack 報告の実測レイテンシは計測していない。実測されたのは「リビジョン切り替えまで約 12 秒」（`scorecards/v0.3.1-live-trial.md`）であり、Slack 報告はロールバック実行直後に送信されるため「おおむね同じ約 12 秒」と表現する。

## 3. 撮影中にビートが失敗したとき

- まず `./deploy/demo.sh reset`（たまったアラートを破棄）→ `./deploy/demo.sh restore`（最新リビジョンへ復帰・障害クリア）。そのうえで該当ビートを再実行する。
- テイク間には必ず `reset` + `restore` を挟む。放置すると、残留 5xx や Pub/Sub の再送メッセージが**テイク外の勝手なロールバック**を引き起こす（この注意は `deploy/demo.sh` の `reset()` 直上にもコメントとして記載済み）。
- shop の障害状態はインスタンスのメモリ内にあるため、インスタンスが入れ替わると障害が勝手に消えることがある。チェックリスト手順 2 の単一インスタンス固定を確認する。
- Gemini の診断は非決定的で、まれに code_regression を正しく診断したままエスカレーションを選ぶことがある。beat1 でロールバックしなかった場合は `reset` → `restore` 後に再テイクする（v0.3.1 のライブ試験では 5/5 成功）。
- **ロールバック後も `/checkout` が 500 を返し続ける場合:** ロールバック先リビジョンの温存インスタンスが、以前のテイクで注入した障害をメモリ内に保持していることがある（`restore` の clear は最新リビジョンにしか届かない）。トラフィックがロールバック先に載っている状態で `curl -s -X POST "$SHOP_URL/admin/clear" -H 'Content-Type: application/json' -d '{}'` を実行して障害を消してから、`reset` → `restore` で再テイクする（2026-07-04 のリハーサルで実際に発生・解消済み）。

## 4. 撮影後

1. インスタンス固定を解除する（チェックリスト手順 2 の逆操作）。
2. `./deploy/demo.sh restore` で最新リビジョンに戻し、`reset` でアラートを空にする。
3. 動画を YouTube または Vimeo に限定公開でアップロードし、URL を Proto Pedia エントリ（`docs/submission/protopedia.md` の動画欄）に転記する。
