# anime-premie-search-bot

アニメの先行上映会・先行配信イベント情報を収集し、RSS / 静的サイト（GitHub Pages） / X / Bluesky / Google カレンダーへ配信する自動収集・配信ツールです。

- 情報源: アニメイトタイムズ（`src/aggregator/sources/animatetimes.py`、RSSが無いためスクレイピング + LLM抽出）
- 実行: 2つのGitHub Actionsワークフローに分かれている
  - 収集パイプライン（`.github/workflows/run.yml`、2時間ごとのcron）: スクレイピング・LLM抽出・チケットページ再チェック・RSS/静的サイト生成・Googleカレンダー更新
  - SNS投稿パイプライン（`.github/workflows/publish-sns.yml`）: 収集パイプライン完了後に`workflow_run`で自動的に起動し、X/Blueskyへの投稿のみ行う
- データ保存: `data/events.json` をGitで管理（重複投稿防止・チャネル別投稿済み状態を追跡）。両パイプラインがこのファイルを読み書きするが、SNS投稿は収集完了後にのみ走るため競合しない

詳細な設計は `/home/super/.claude/plans/sns-bot-rss-google-streamed-allen.md`（プランファイル）を参照してください。

## ローカルでの開発

```bash
uv sync
cp .env.example .env   # .envにANTHROPIC_API_KEYを記入する（後述）
uv run pytest
uv run aggregator-run --dry-run          # スクレイピング+抽出のみ確認（投稿/保存なし）
uv run aggregator-run                    # 収集パイプライン実行（data/events.json保存 + public/ビルド + RSS/サイト/カレンダーへ公開）
uv run aggregator-publish-sns --dry-run  # SNS投稿対象の確認のみ（投稿/保存なし）
uv run aggregator-publish-sns            # SNS投稿パイプライン実行（data/events.jsonの既存イベントのみ対象、X/Blueskyへ投稿）
```

`aggregator-publish-sns` はスクレイピング・LLM抽出を行わず、`aggregator-run` が保存した `data/events.json` の内容だけを対象にX/Blueskyへ投稿します。本番では `aggregator-run` の完了後に自動的に呼ばれる想定です（後述のGitHub Actions参照）。

`.env` ファイル（リポジトリ直下、gitignore済み）にAPIキーを書いておけば `uv run aggregator-run` 実行時に自動で読み込まれます（`python-dotenv`使用）。シェルで直接 `export ANTHROPIC_API_KEY=...` する方法でも構いません。

ローカルで「ページ収集とビルドだけ試したい」場合は、`ANTHROPIC_API_KEY` だけ `.env` に設定すれば十分です（X/Bluesky/Google Calendarの認証情報は未設定なら自動でスキップされ、RSS/静的サイト生成は常に実行されます）。`--dry-run` を付けると `data/events.json` の保存や各チャネルへの投稿も行わず、スクレイピングとLLM抽出の結果だけを確認できます。`--dry-run` を外すと `public/index.html` ・ `public/feed.xml` の実ビルドと `data/events.json` への保存まで行われます。

animatetimesの一覧ページ（`/anime/?p=N`）は既知の記事IDしか見つからなくなった時点で自動的に巡回を止めますが、安全のため最大ページ数の上限（デフォルト30ページ）があります。`--max-pages N` オプション（または `ANIMATETIMES_MAX_PAGES` 環境変数）で上限を変更できます。

```bash
uv run aggregator-run --dry-run --max-pages 3
```

## 必要な環境変数 / GitHub Secrets

| 変数名 | 用途 | 使われるワークフロー |
|---|---|---|
| `ANTHROPIC_API_KEY` | 記事本文・チケットページからのイベント情報抽出（Claude API） | `run.yml`（収集） |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Calendar 連携用サービスアカウントの認証情報（JSON文字列をそのまま） | `run.yml`（収集） |
| `GCAL_CALENDAR_ID` | イベントを登録する先のGoogleカレンダーID | `run.yml`（収集） |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | X (Twitter) への投稿 | `publish-sns.yml` |
| `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` | Bluesky への投稿 | `publish-sns.yml` |

未設定のチャネルはパイプライン側で自動的にスキップされます（RSSと静的サイト生成のみ必須）。

## Google カレンダーの初期セットアップ（一度だけ手動で実施）

1. Google Cloud Consoleで新しいプロジェクト（または既存プロジェクト）にサービスアカウントを作成し、JSONキーをダウンロードする
2. Google Calendarで新規カレンダーを作成する（例: 「アニメ先行上映・先行配信情報」）
3. そのカレンダーの「設定と共有」から、サービスアカウントのメールアドレスを「予定の変更権限」で共有に追加する
4. カレンダーを公開設定にし、公開URL（embed / iCalリンク）を控える
5. カレンダー設定画面の「カレンダーの統合」からカレンダーIDを取得する
6. ダウンロードしたJSONキーの内容を `GOOGLE_SERVICE_ACCOUNT_JSON`、カレンダーIDを `GCAL_CALENDAR_ID` としてGitHub Secretsに登録する

## 静的サイト（ページネーション・期間絞り込み）

`public/index.html` は収集した全イベントを削除せずに保持し続けます（古いイベントもサイト上に残ります）。表示側では:

- 開催が近い順（未終了イベント）→ 開催が新しい順（終了済みイベント）に並びます。
- 全イベントをJSONとして`index.html`内に埋め込み、`public/site.js`（クライアントサイドJavaScript）がページネーション（1ページ20件）と開催日でのfrom/to絞り込みを行います。JavaScriptを無効にしている場合は一覧が表示されません（その場合は`public/feed.xml`のRSSフィードを利用してください）。
- イベントの表示項目を増やす場合は、Jinja2テンプレート（`templates/site/index.html`）だけでなく`templates/site/site.js`のレンダリング処理も合わせて更新する必要があります。

## GitHub Pages

`.github/workflows/run.yml` が `public/` ディレクトリをビルドし、GitHub Pagesにデプロイします。リポジトリの Settings > Pages で Source を「GitHub Actions」に設定してください。

## ワークフローの関係

`run.yml`（収集）が完了すると、`publish-sns.yml` が `workflow_run` トリガーで自動的に起動し、`data/events.json` の中身を見てX/Blueskyへの未投稿イベントだけを投稿します。収集が失敗した回（`conclusion != success`）はSNS投稿をスキップします。`publish-sns.yml` は `workflow_dispatch` でも手動実行できます。
