# anime-premie-search-bot

アニメの先行上映会・先行配信イベント情報を収集し、RSS、静的サイト（GitHub Pages）、X、Bluesky、Googleカレンダーへ配信する自動収集ツール。

## 環境構築

必要なもの: Python 3.11+、uv

```bash
uv sync
cp .env.example .env  # ANTHROPIC_API_KEY を記入
```

## コマンド

```bash
uv run pytest
uv run aggregator-run --dry-run          # 収集: 確認のみ（保存・投稿なし）
uv run aggregator-run                    # 収集: 本実行
uv run aggregator-publish-sns --dry-run  # SNS投稿: 確認のみ
uv run aggregator-publish-sns            # SNS投稿: 本実行
```

最大巡回ページ数は `--max-pages N`（または `ANIMATETIMES_MAX_PAGES` 環境変数）で変更できる（デフォルト30）。

## 環境変数

GitHub Secretsに登録する。未設定のチャネルは自動スキップ。`ANTHROPIC_API_KEY` だけ設定すればRSSと静的サイト生成は動く。

収集ワークフロー（`run.yml`）:
- `ANTHROPIC_API_KEY` — Claude APIキー（記事・チケットページからの情報抽出）
- `GOOGLE_SERVICE_ACCOUNT_JSON` — サービスアカウントのJSONキー文字列
- `GCAL_CALENDAR_ID` — 登録先のGoogleカレンダーID

SNS投稿ワークフロー（`publish-sns.yml`）:
- `X_API_KEY`、`X_API_SECRET`、`X_ACCESS_TOKEN`、`X_ACCESS_TOKEN_SECRET`
- `BLUESKY_HANDLE`、`BLUESKY_APP_PASSWORD`

## Googleカレンダーの初期設定

一度だけ手動で実施。

1. Google Cloud Consoleでサービスアカウントを作成し、JSONキーをダウンロード
2. Google Calendarで専用カレンダーを新規作成
3. カレンダーの「設定と共有」でサービスアカウントのメールを「予定の変更権限」で追加
4. カレンダーIDを取得（「カレンダーの統合」から確認できる）
5. JSONキー文字列を `GOOGLE_SERVICE_ACCOUNT_JSON`、カレンダーIDを `GCAL_CALENDAR_ID` としてGitHub Secretsに登録

## GitHub Pages

Settings > Pages で Source を「GitHub Actions」に設定する。

## 仕様

### ワークフロー

収集（`run.yml`、2時間ごとcron）はスクレイピング・LLM抽出・チケットページ確認・RSS生成・サイト生成・Googleカレンダー更新を行う。SNS投稿（`publish-sns.yml`）は収集完了後に自動起動し、収集失敗時はスキップ。`workflow_dispatch` で手動実行も可。

`data/events.json` をGitで管理し、重複投稿防止とチャネル別の投稿済み状態を追跡する。

### サイト

- 全イベントを保持し続ける
- 表示順: 未終了イベントを開催が近い順、終了済みをその後ろに開催が新しい順
- 1ページ20件のページネーション、開催日でのfrom/to絞り込み
- JavaScript無効では一覧が表示されない（RSSフィードを利用）
- 表示項目を追加する場合は `templates/site/index.html` と `templates/site/site.js` の両方を更新
