# Notifier — Docker 環境構築ガイド

## 概要

notifier をローカルの Docker 環境で起動・開発するための手順書です。　
.

### サービス構成

| サービス | イメージ | ポート | 説明 |
|---|---|---|---|
| `app` | python:3.13-slim | 8080 → 8000 | Notifier API (FastAPI + Uvicorn) |
| `notifier-db` | postgres:18-alpine | 内部のみ | PostgreSQL データベース |


## 前提条件

- Docker Engine
- Docker Compose 

---

## クイックスタート

```bash
# プロジェクトルートから実行
cd docker

# ビルド＆起動（初回はイメージビルドが走ります）
docker compose up --build

# バックグラウンド起動
docker compose up --build -d

# ログ確認
docker compose logs -f app
```

起動後、以下の URL でアクセスできます:

| URL | 説明 |
|---|---|
| http://localhost:8080/health | ヘルスチェック |
| http://localhost:8080/readiness | レディネスチェック（DB接続確認） |
| http://localhost:8080/docs | OpenAPI ドキュメント (Swagger UI) |
| http://localhost:8080/redoc | OpenAPI ドキュメント (ReDoc) |

---

## ディレクトリ構成

```
docker/
├── Dockerfile           # 本番用マルチステージビルド
├── Dockerfile.dev       # 開発用（ホットリロード対応）
├── docker-compose.yml   # 開発環境定義
├── requirements.txt     # Python 依存パッケージ
├── requirements-dev.txt # 開発用追加パッケージ
└── README.md            # 本ドキュメント
```

---

## Dockerfile の使い分け

### `Dockerfile` — 本番用

- マルチステージビルド（builder → final）で軽量イメージを生成
- 非 root ユーザー（`appuser:1000`）で実行

```bash
# 本番用ビルド
docker build -f docker/Dockerfile -t notifier-api:latest .
```

### `Dockerfile.dev` — 開発用

- `requirements-dev.txt`（pytest, faker 等）もインストール
- `--reload` によるホットリロード対応

```bash
# 開発用ビルド
docker build -f docker/Dockerfile.dev -t notifier-api:dev .
```

---

## データベース

### 初回起動時

`docker compose up` で PostgreSQL が自動的に起動し、ヘルスチェック通過後にアプリケーションが開始されます。

### DB接続情報（開発環境デフォルト）

| 項目 | 値 |
|---|---|
| ホスト | `notifier-db`（コンテナ間）|
| ポート | `5432` |
| データベース名 | `fastapi_db` |
| ユーザー | `postgres` |
| パスワード | `postgres` |

### マイグレーション

Alembic を使用してデータベーススキーマを管理しています。

```bash
# アプリコンテナに入る
docker compose exec app bash

# マイグレーション実行
cd /app
alembic -c migrations/alembic.ini upgrade head

# マイグレーション履歴確認
alembic -c migrations/alembic.ini history

# 新しいマイグレーション作成
alembic -c migrations/alembic.ini revision --autogenerate -m "add_new_table"
```

### データベースのリセット

```bash
# ボリュームごと削除して再作成
docker compose down -v
docker compose up --build
```

---

## 環境変数

`docker-compose.yml` で設定されている主要な環境変数です。
`${変数名:-デフォルト値}` の形式で、シェル環境変数での上書きが可能です。

### アプリケーション設定

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `ENVIRONMENT` | `DEVELOP` | 実行環境（`DEVELOP` / `PRODUCTION`） |
| `DEBUG` | `False` | デバッグモード |
| `LOG_LEVEL` | `INFO` | ログレベル |

### セキュリティ設定

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `SECRET_KEY` | `dev-only-secret-key-...` | JWT署名キー（本番では必ず変更） |
| `CORS_ORIGINS` | `http://localhost:3000` | CORS許可オリジン |
| `X_NOTIFICATION_API_KEY` | `dev-notification-api-key` | API キー |

### L3 認証設定

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `L3_BASE_URL` | `https://dev-auth.example.com` | L3 の URL（トークン検証・認可判定 API の接続先） |
| `L3_INTROSPECT_ENDPOINT` | `/auth/token/introspect` | トークン検証エンドポイント |
| `L3_API_KEY` | `dev-l3-api-key` | L3 API キー |
| `L3_CLIENT_ID` | `dev-client-id` | L3 クライアント ID |
| `L3_CLIENT_SECRET` | `dev-client-secret` | L3 クライアントシークレット |

### 認可サービス設定（L3 認可判定API）

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `AUTHZ_ENABLED` | `false` | 認可チェック有効/無効 |
| `AUTHZ_STORE_ID` | `01KFY9RF3HQM...` | Notifier の API 実行権限を登録した L3 の認可ストア ID |
| `L3_AUTHZ_EVALUATION_ENDPOINT` | `/authz/stores/{store_id}/access/v1/evaluation` | L3 の認可判定 API（AuthZEN）のパス |

認可確認は L3 の認可判定 API を経由して行います（接続先・API キーは `L3_BASE_URL`・`L3_API_KEY` を使用）。`L3_API_KEY` のレルムが、`AUTHZ_STORE_ID` の認可ストアに紐付けられている必要があります。

### データベース設定

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `POSTGRES_HOST` | `notifier-db` | DB ホスト |
| `POSTGRES_PORT` | `5432` | DB ポート |
| `POSTGRES_DB` | `fastapi_db` | DB 名 |
| `POSTGRES_USER` | `postgres` | DB ユーザー |
| `POSTGRES_PASSWORD` | `postgres` | DB パスワード |
| `DB_CONNECT_TIMEOUT` | `10` | 接続タイムアウト（秒） |
| `DB_POOL_TIMEOUT` | `10` | プールタイムアウト（秒） |

### ログ設定

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `LOG_JSON_FORMAT` | `false` | JSON 形式ログ（本番向け） |
| `LOG_FILE_ENABLED` | `false` | ファイル出力 |
| `LOG_COLORIZE` | `true` | カラーログ |
| `APP_NAME` | `notifier-api` | アプリケーション名 |
| `SQLALCHEMY_LOG_LEVEL` | `ERROR` | SQLAlchemy ログレベル |
| `UVICORN_LOG_LEVEL` | `debug` | Uvicorn ログレベル |

---

## ODS スタック統合

ODS スタックの他サービス（L3 等）と連携して動かす場合の手順です。

### 共有ネットワークへの参加

`docker-compose.yml` の default ネットワークは共有ネットワーク（デフォルト名: `shared-network`）に接続されます。
同一ネットワークに参加している他サービスとは、コンテナ名で相互通信できます。

ネットワーク名は `SHARED_NETWORK_NAME` で変更できます。スタック側が `shared-network-ods` を使用している場合:

```bash
SHARED_NETWORK_NAME=shared-network-ods docker compose up --build -d
```

スタック側で作成済みのネットワークに参加する際、ラベル不一致で compose がエラーになる場合は、
`docker/docker-compose.override.yml` を作成して external 指定してください:

```yaml
networks:
  default:
    name: shared-network-ods
    external: true
```

### ポート競合

| ホストポート | 使用サービス | 備考 |
|---|---|---|
| 8080 | notifier (app) | OpenFGA の HTTP デフォルト (8080) と競合し得る |
| 8081 / 3000 | OpenFGA (gRPC / Playground) | OpenFGA をホスト公開している場合 |

notifier のホストポートは `NOTIFIER_PORT` で変更できます:

```bash
NOTIFIER_PORT=18080 docker compose up -d
# → http://localhost:18080/health
```

`notifier-db` はホストにポート公開していない（コンテナ間通信のみ）ため、ホストや他サービスの
PostgreSQL (5432) とは競合しません。デバッグ等でホスト公開する場合は `"15432:5432"` のように
5432 以外を割り当ててください。

### PostgreSQL 18 (PG18) の注意点

- `postgres:18` イメージは PGDATA が `/var/lib/postgresql/18/docker` に変更されたため、ボリュームは `/var/lib/postgresql` にマウントしてください（`/var/lib/postgresql/data` ではデータが永続化されません。本 compose は対応済み）。
- PostgreSQL 17 以前で作成した既存ボリュームでは起動できません（`database files are incompatible with server`）。`docker compose down -v` で再作成してください。

---

## 外部サービスとの連携

### L3 認可判定 API

notifier では認可チェック（`AUTHZ_ENABLED: false`）がデフォルトで無効です。

---

## テスト実行

```bash
# プロジェクトルートから実行

# unit テストのみ（DB不要）
docker compose -f docker/docker-compose.yml exec app pytest test/unit -v

# 開発用イメージでテスト実行
docker build -f docker/Dockerfile.dev -t notifier-api:dev .
docker run --rm notifier-api:dev pytest test/unit -v --cov=app --cov-report=term-missing
```

---

## ボリュームマウント（開発時）

`docker-compose.yml` では以下のディレクトリがマウントされ、ホットリロードが有効です:

| ホスト側 | コンテナ側 | 用途 |
|---|---|---|
| `../app` | `/app/app` | アプリケーションコード |
| `../migrations` | `/app/migrations` | Alembic マイグレーション |

ソースコードを編集すると、Uvicorn が自動的にリロードします。

---
