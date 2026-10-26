# Notifierサービス

## 概要

本サービスは、Open Data Spaces(ODS)の共通機能（Common Functionalities）の一つとして動作し、
提供者からのデータ配信の通知機能を提供するAPIサーバです。

### 主要機能

- **通知先リスト管理**: 通知先リストの作成・更新・取得・削除
- **通知管理**: 通知の作成・更新・取得・削除（複数通知の一括登録・一括更新・一括削除を含む）
- **通知確認**: ユーザーによる通知の既読確認
- **データ受信確認**: データ受信状態の更新

### 通知の配信方式

本サービスは **Pull 型** で通知を配信します。

- 通知受信者のサービスアプリは、L2 Transaction を介して通知一覧取得 API（`GET /api/v1/notifications`）を定期的に呼び出し（ポーリング）、自身宛の通知を取得します。
- WebSocket、Server-Sent Events、Webhook などによる Push 型の配信は提供しません。

詳細は [基本設計](docs/basic_design.md) の「2.3 通知の配信方式」を参照してください。

#### ポーリング時の推奨事項

ポーリングで通知を取得する場合は、次の方法で Notifier とデータベースの負荷、通信量を抑えてください。

- **条件付きリクエストを使う**: 通知一覧取得 API の応答には `ETag` ヘッダが付きます。次回の取得時に `If-None-Match` ヘッダへ前回の `ETag` の値を指定すると、前回から変更がない場合は 304 Not Modified（ボディなし）が返り、通信量を抑えられます（詳細は [詳細設計](docs/detail_design.md) の「2.3 条件付きリクエスト仕様」を参照）。
- **取得する通知を絞り込む**: クエリパラメータ `status=enabled` で有効な通知だけを取得してください。応答の通知受信者の詳細リスト（`notification_confirmed_targets`）で自身の確認状態が `not_received` のものが未確認の通知です。処理した通知は通知確認状態更新 API（`PUT /api/v1/notifications/{notification_id}/receive`）で確認済みにしてください。
- **ポーリング間隔の目安**: 60 秒以上を推奨します。通知の即時性が必要な場合でも、条件付きリクエストと組み合わせたうえで、受信者の数に応じて間隔を調整してください。


## ディレクトリ構成

```
.
├── app/                          # アプリケーションコード
│   ├── main.py                   # FastAPIアプリケーションエントリーポイント
│   ├── api/v1/                   # APIエンドポイント
│   │   ├── router.py             # ルート登録
│   │   └── endpoints/            # 各エンドポイント実装
│   │       ├── notifications.py
│   │       ├── notification_targets.py
│   │       └── health.py
│   ├── models/                   # SQLAlchemy ORMモデル
│   ├── schemas/                  # Pydantic リクエスト/レスポンススキーマ
│   ├── repositories/             # データアクセス層（DBクエリ）
│   ├── services/                 # ビジネスロジック層
│   ├── clients/                  # 外部サービスHTTPクライアント
│   │   ├── l3_client.py          # L3認証クライアント
│   │   └── authz_client.py       # L3認可クライアント
│   ├── core/                     # コア機能
│   │   ├── config.py             # 環境変数ベースの設定
│   │   ├── security.py           # 認証・認可ユーティリティ
│   │   └── events.py             # 起動/終了イベントハンドラ
│   ├── middleware/               # カスタムミドルウェア
│   ├── db/                       # データベース設定
│   └── utils/                    # ユーティリティ関数
├── migrations/                   # Alembic DBマイグレーション
├── docker/                       # Docker設定
│   └── README.md                 # Docker環境構築ガイド（起動手順、環境変数、ODSスタック統合）
├── docs/                         # ドキュメント
│   ├── basic_design.md           # 基本設計書
│   ├── detail_design.md          # 詳細設計書
│   └── openapi/                  # OpenAPI仕様（openapi.json / openapi.html）
└── scripts/                      # ユーティリティスクリプト
    └── generate-openapi.sh       # OpenAPI仕様生成スクリプト
```

## 前提条件
- Docker / Docker Compose
- Python 3.11+（ローカル開発時）
- PostgreSQL 18

## クイックスタート

Docker Compose でローカル起動できます。

```bash
cd docker
docker compose up --build -d

# DBマイグレーション
docker compose exec app alembic -c migrations/alembic.ini upgrade head
```

起動後、http://localhost:8080/health （ヘルスチェック）、http://localhost:8080/docs （Swagger UI）でアクセスできます。

詳細な手順（環境変数、テスト実行、ODSスタックとの統合、PostgreSQL 18 の注意点など）は [Docker 環境構築ガイド](docker/README.md) を参照してください。

## バージョン 1.1.0 での変更

2026年4月以降に確認された不備の修正と機能の追加を行いました。変更の一覧は API ドキュメント（`/docs`）の変更履歴を参照してください。

### 互換性に影響する変更

1.0.0 から利用している場合は、次の点を確認してください。

- **更新 API の `updated_at` が必須になりました**: 通知更新 API・通知先リスト更新 API のリクエストボディに、取得時の `updated_at` をそのまま指定してください。最新の更新日時と一致しない場合は 409 Conflict を返します。
- **通知・通知先リストを所有者ごとに分離しました**: 通知の取得・更新・削除は、通知の所有者・受信者以外からは 404 を返します。通知先リストの登録・更新で `owner_id` がアクセストークンの `operator_id` と異なる場合は 403 を返します（`OPERATOR_ID_VERIFICATION_ENABLED=true` の場合）。
- **認可確認の設定項目を変更しました**: `AUTHZ_BASE_URL`・`AUTHZ_OPENFGA_STORE_ID`・`AUTHZ_OPENFGA_MODEL_ID` に代えて `L3_BASE_URL`・`L3_API_KEY`・`AUTHZ_STORE_ID` を使用します。認可確認は L3 の認可判定 API 経由で行います。
- **CORS の許可オリジンの設定名を変更しました**: `ALLOWED_HOSTS` に代えて `CORS_ALLOWED_ORIGINS` を使用してください。旧名も当面は読み込みます。
- **データベースのマイグレーション（002）の適用が必要です**: 通知に所有者ID を追加します。既存の通知のうち所有者を補完できないものの扱いと対処方法は、[Docker 環境構築ガイド](docker/README.md) の「既存環境への 002（所有者の分離）の適用」を参照してください。

## ドキュメント

| ドキュメント | 説明 |
|------------|------|
| [Docker 環境構築ガイド](docker/README.md) | ローカル起動手順、環境変数、ODSスタック統合 |
| [基本設計](docs/basic_design.md) | システムアーキテクチャ、全体構成 |
| [詳細設計](docs/detail_design.md) | 詳細シーケンス、データ設計|
| [OpenAPI仕様 (JSON)](docs/openapi/openapi.json) | API仕様（機械可読形式） |
| [OpenAPI仕様 (HTML)](docs/openapi/openapi.html) | API仕様（ブラウザ閲覧用） |

## ライセンス
- 本リポジトリはMITライセンスで提供されています。
- ソースコードおよび関連ドキュメントの著作権は、一般社団法人自動車・蓄電池トレーサビリティ推進センターに帰属します。  

## 免責事項
- 本リポジトリの内容は予告なく変更・削除する可能性があります。
- 本リポジトリの利用により生じた損失及び損害等について、いかなる責任も負わないものとします。

