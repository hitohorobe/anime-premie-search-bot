# agent.md

このファイルはAIエージェント（Claude Code等）がこのリポジトリで作業する際の前提知識をまとめたものです。

## プロジェクト概要

アニメの「先行上映会」「先行配信」イベント情報（開催日時・場所・予約開始/終了・予約サイトリンク）を自動収集し、以下のチャネルへ配信するシステムです。

- RSSフィード（`public/feed.xml`）
- 静的Webサイト（`public/index.html`、GitHub Pagesで公開）
- X (Twitter)
- Bluesky
- Google カレンダー（専用の公開カレンダー）

情報源は アニメイトタイムズ (animatetimes.com)。RSSフィードが提供されていないため、ニュース一覧ページ（`/anime/?p=N`、新しい順でページネーションされている）を必要な分だけページ送りしながら取得し、記事詳細ページをスクレイピングして本文をLLM（Claude）に渡して構造化データ（日時・会場・予約期間など）を抽出する。一覧ページ上で既知のIDしか見つからなくなった時点でページ送りを停止する。抽出後、全セッションが終了済みのイベントは配信対象から除外する。

記事から取れる `reservation.ticket_url`（予約サイトのURL）については、未終了イベント全件を対象に毎回のパイプライン実行時にそのページ自体も再クロールし、LLMで予約開始/終了日時と現在の受付状況（`available`/`not_yet_open`/`closed`/`sold_out`）を補足抽出して `reservation` を最新化する（`pipeline.py` の `_refresh_ticket_reservations`）。チケットページはl-tike/eplusなど多様な構造のため汎用フェッチャー（`sources/ticket_page.py`）でテキストを抽出するのみで、サイト固有の解析はしない。取得・抽出に失敗した場合は既存の予約情報を変更せずスキップする。

サイト（`public/index.html`）は収集した全イベントを削除せず保持し続ける設計で、表示側でページネーション（1ページ20件）と開催日でのfrom/to絞り込みを行う。並び順は未終了イベントが開催が近い順、終了済みイベントはその後ろに開催が新しい順で続く（`publishers/site.py` の `_order_events`）。全イベントはJSONとして`index.html`に埋め込まれ、`public/site.js`（クライアントサイドJS、ビルド時に`templates/site/site.js`からコピーされる）がフィルタ・ページネーション・カード描画を行う。サーバー側（Jinja2）はイベントの一覧描画自体は行わない。

実行は2つのGitHub Actionsワークフローに分かれている。常駐サーバーは持たない。永続データは外部DBを使わず `data/events.json` をGitで管理し、重複投稿防止とチャネル別の投稿済み状態を追跡する。

- 収集パイプライン（`pipeline.run_collect` / `aggregator-run` / `.github/workflows/run.yml`、2時間ごとのcron）: スクレイピング・LLM抽出・チケットページ再チェック・永続化・RSS/静的サイト生成・Googleカレンダー更新。
- SNS投稿パイプライン（`pipeline.run_publish_sns` / `aggregator-publish-sns` / `.github/workflows/publish-sns.yml`）: スクレイピングは行わず `data/events.json` の既存イベントだけを対象にX/Blueskyへ投稿する。収集パイプライン完了後に`workflow_run`で自動的に起動する（収集が失敗した回はスキップ）。投稿は取り消せない操作なので、意図的に収集パイプラインから分離してある。

詳細な設計意図・データモデル・各コンポーネントの設計根拠は `/home/super/.claude/plans/sns-bot-rss-google-streamed-allen.md`（プランファイル）に記載されている。大きな変更を加える前にそちらも参照すること。

## 構成案（ディレクトリ構成）

```
pyproject.toml / uv.lock      # uvで依存管理（venv/pipは使わない）
src/aggregator/
  config.py                   # 環境変数からのConfig読み込み
  models.py                   # Event/Session/ReservationWindow等のpydanticモデル
  sources/
    base.py                   # SourceScraper抽象基底クラス（list_articles/fetch_article）
    animatetimes.py           # animatetimes.com実装（v1で唯一のソース）
    ticket_page.py            # 予約サイトページの汎用フェッチャー（サイト非依存、テキスト抽出のみ）
  extraction/
    prompts.py                # LLM抽出用システムプロンプト・JSON Schema（記事用・チケットページ用の両方）
    llm_extractor.py          # 記事本文/チケットページ本文 -> Claude API -> Event/ReservationWindow候補（失敗時はNoneを返しスキップ）
  storage/
    repository.py             # data/events.json の読み書き・dedupe・publish_status管理
  publishers/
    base.py                   # Publisher抽象基底クラス
    rss.py / site.py          # RSS・静的サイト生成（feedgen / Jinja2）。run_collect側。site.pyは_order_events（並び順）+JSON埋め込み+site.jsコピーも担う
    gcal.py                   # Googleカレンダー連携。run_collect側
    twitter.py / bluesky.py   # X/Bluesky投稿（未投稿のものだけ処理）。run_publish_sns側
  pipeline.py                  # run_collect（scrape -> extract -> persist -> RSS/site/gcal）と run_publish_sns（X/Bluesky投稿のみ）の2つのエントリポイント。各段は他段の失敗から独立
  cli.py                       # `uv run aggregator-run`（main）/ `uv run aggregator-publish-sns`（main_sns）のエントリポイント
data/events.json               # イベントDB（Git管理、重複投稿防止の主キー）。両パイプラインが読み書きする
templates/site/                # base.html（CSS含む）/ index.html（Jinja2、JSON埋め込み+フィルタUIの骨組みのみ）/ site.js（クライアントサイドのフィルタ・ページネーション・カード描画、ビルド時にpublic/へそのままコピー）
public/                        # 生成物（feed.xml, index.html, site.js）。GitHub Pagesの公開対象
tests/                         # pytest。fixtures/にスクレイパー用の合成HTML
.github/workflows/
  run.yml                      # 収集パイプライン。2時間ごとのcron + workflow_dispatch
  publish-sns.yml              # SNS投稿パイプライン。run.yml完了後にworkflow_runで自動起動 + workflow_dispatch
```

## 拡張のポイント

- 新しい情報源サイトを追加する場合は `sources/base.py` の `SourceScraper` を実装し、`pipeline.py` の `sources` リストに追加する。
- 新しい配信先チャネルを追加する場合は `publishers/base.py` の `Publisher` を実装し、用途に応じて `pipeline.py` の `_build_collect_publishers`（RSS/site/gcal系、収集時に毎回実行）または `_build_sns_publishers`（SNS系、別パイプラインから実行）に条件付きで追加する。
- イベントのフィールドを増やす場合は `models.py` のpydanticモデルと `extraction/prompts.py` のJSON Schemaを両方更新する（抽出結果はスキーマでバリデーションされるため）。サイト表示にも反映したい場合は `templates/site/site.js` のカード描画処理（`renderSession` / `renderReservation`）も併せて更新する（Jinja2側にはイベント一覧の描画ロジックは無い）。

## よく使うコマンド

```bash
uv sync                       # 依存関係のインストール
uv run pytest                 # テスト実行
uv run pytest -q              # 簡潔な出力でテスト実行
uv run aggregator-run --dry-run          # 収集: スクレイピング+LLM抽出のみ確認（保存・投稿はしない）
uv run aggregator-run                    # 収集: 本実行（data/events.json保存 + RSS/サイト/カレンダーへ公開）
uv run aggregator-publish-sns --dry-run  # SNS投稿: 対象確認のみ（投稿/保存はしない）
uv run aggregator-publish-sns            # SNS投稿: 本実行（X/Blueskyへ投稿、publish_status保存）
uv run aggregator-run --log-level DEBUG  # ログレベル変更
```

## 環境変数（GitHub Secrets）

| 変数名 | 用途 | 使われるワークフロー |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLMによるイベント情報抽出（未設定時は新規記事の抽出をスキップ） | `run.yml` |
| `LLM_MODEL` | 抽出に使うモデル（デフォルト `claude-haiku-4-5`） | `run.yml` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` / `GCAL_CALENDAR_ID` | Googleカレンダー連携（未設定時はスキップ） | `run.yml` |
| `X_API_KEY` / `X_API_SECRET` / `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | X投稿（未設定時はXへの投稿をスキップ） | `publish-sns.yml` |
| `BLUESKY_HANDLE` / `BLUESKY_APP_PASSWORD` | Bluesky投稿（未設定時はスキップ） | `publish-sns.yml` |

RSS生成・静的サイト生成は常に実行される（認証情報不要）。

## 注意事項

- `data/events.json` の `id` フィールド（`{source_site}-{記事ID}`）が重複投稿防止の主キー。スキーマを壊す変更（IDの生成方法変更など）は既存データの再投稿事故につながるため要注意。
- `publish_status` は各チャネルへの投稿成功直後に更新・保存すること（パイプライン中断時の二重投稿を防ぐため）。新しいPublisherを実装する際もこの原則を守る。
- `run_publish_sns` は `run_collect` がコミットした最新の `data/events.json` を前提にしている。`publish-sns.yml` は `workflow_run` で収集完了後にのみ起動するため、2つのパイプラインが同時に同じファイルへコミットすることは想定していない。
- ニュース一覧ページのURL/HTML構造はサイト都合で変わる可能性がある。スクレイパーが新着記事を取得できなくなった場合は `sources/animatetimes.py` のセレクタを見直す。
