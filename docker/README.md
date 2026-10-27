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

### 既存環境への 002（所有者の分離）の適用

マイグレーション `002_owner_separation` は、通知に所有者ID（`owner_id`）を追加し、既存の通知には次のとおり所有者を補完します。

| 既存の通知 | 補完結果 |
|---|---|
| 通知先リストを指定して登録した通知（リストの所有者が 1 人） | リストの所有者で補完する |
| 受信者IDを直接指定して登録した通知（通知先リストの指定なし） | 補完されず、所有者なし（NULL）のまま |
| 所有者の異なる複数の通知先リストを指定して登録した通知 | 補完されず、所有者なし（NULL）のまま |

所有者なしの通知は、どの提供者からも詳細取得・更新・削除ができません（404）。受信者による一覧取得・詳細取得・通知確認・データ受領状態の更新は従来どおり行えます。所有者なしのままで問題がなければ、追加の作業は不要です。

該当する通知を所有者が更新・削除できるようにする必要がある場合は、マイグレーションの適用後に、次の SQL で所有者を手動で設定してください。

```sql
-- 所有者なしの通知と、その通知が指定している通知先リストの所有者を確認する
SELECT n.notification_id, n.title, n.created_at, array_agg(l.owner_id) AS list_owner_ids
FROM notification n
LEFT JOIN notification_target_list_map m ON m.notification_id = n.notification_id
LEFT JOIN notification_target_list l ON l.target_list_id = m.target_list_id
WHERE n.owner_id IS NULL
GROUP BY n.notification_id, n.title, n.created_at
ORDER BY n.created_at;
```

```sql
-- 通知の所有者を設定する（'<notification_id>' と '<owner_id>' を置き換えて、通知ごとに実行する）
BEGIN;
-- 設定する所有者以外が所有する通知先リストとの関連付けを外す（通知と通知先リストの所有者は一致している必要がある）
-- 受信者は通知の登録時点で確定しているため、関連付けを外しても受信者には届いたままになる
DELETE FROM notification_target_list_map m
USING notification_target_list l
WHERE m.notification_id = '<notification_id>' AND l.target_list_id = m.target_list_id AND l.owner_id <> '<owner_id>';
UPDATE notification SET owner_id = '<owner_id>' WHERE notification_id = '<notification_id>' AND owner_id IS NULL;
UPDATE notification_target_list_map SET owner_id = '<owner_id>' WHERE notification_id = '<notification_id>' AND owner_id IS NULL;
COMMIT;
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
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | CORS許可オリジン（カンマ区切りまたは JSON 配列）。1.0.0 の `ALLOWED_HOSTS` も経過措置として読み込む（両方設定した場合は `CORS_ALLOWED_ORIGINS` を優先） |
| `X_NOTIFICATION_API_KEY` | `dev-notification-api-key` | API キー |
| `OPERATOR_ID_VERIFICATION_ENABLED` | `false` | 通知先リストの登録・更新で、リクエストボディの `owner_id` がアクセストークンの `operator_id` と一致するかを検証する（不一致は 403）。`false` の場合は検証せず、他の提供者の `owner_id` を指定した通知先リストを登録・更新できるため、**本番環境では必ず `true` にすること**。`ENVIRONMENT=DEVELOP` では設定にかかわらず検証しない |

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

notifier では認可チェック（`AUTHZ_ENABLED: false`）がデフォルトで無効です。有効にすると、各 API の実行前に L3 の認可判定 API（AuthZEN）へ「`user:{operator_id}` が `api_endpoint:{エンドポイント名}` に対して `can_access` の関係を持つか」を問い合わせ、許可されていない場合は 403 を返します（認可の考え方は [基本設計](../docs/basic_design.md) の「5.2 認可機能」を参照）。

#### 認可を有効にする手順

1. **notifier の環境変数を設定する**

   | 変数名 | 設定内容 |
   |---|---|
   | `AUTHZ_ENABLED` | `true` |
   | `L3_BASE_URL` | L3 の URL（トークン検証と共通） |
   | `L3_API_KEY` | notifier に発行された L3 の API キー（トークン検証と共通） |
   | `AUTHZ_STORE_ID` | notifier の API 実行権限を登録した L3 の認可ストア ID |

2. **L3 側で認可ストアと認可モデルを登録する**

   notifier 用の認可ストアを作成し、次の型と関係を持つ認可モデルを登録します。

   - 型 `user`（利用者。ID はアクセストークンの `operator_id`）
   - 型 `api_endpoint`（notifier の API。関係 `can_access` を `user` に対して定義する）

3. **各 API の実行権限（タプル）を登録する**

   利用者（`operator_id`）ごとに、実行を許可する API のタプル `user:{operator_id}` `can_access` `api_endpoint:{エンドポイント名}` を L3 の認可タプル登録 API（`POST /authz/stores/{store_id}/write`）で登録します。エンドポイント名は、コード中の名前（`notifications:post` など）の `:` を `-` に置き換えたものです。

   | エンドポイント名 | 対象 API |
   |---|---|
   | `api_endpoint:notification-targets-post` | POST /api/v1/notification-targets（通知先リスト登録） |
   | `api_endpoint:notification-targets-get-all` | GET /api/v1/notification-targets（通知先リスト一覧取得） |
   | `api_endpoint:notification-targets-get` | GET /api/v1/notification-targets/{target_list_id}（通知先リスト取得） |
   | `api_endpoint:notification-targets-put` | PUT /api/v1/notification-targets/{target_list_id}（通知先リスト更新） |
   | `api_endpoint:notification-targets-delete` | DELETE /api/v1/notification-targets/{target_list_id}（通知先リスト削除） |
   | `api_endpoint:notifications-post` | POST /api/v1/notifications（通知登録）、POST /api/v1/notifications/bulk（通知一括登録） |
   | `api_endpoint:notifications-get` | GET /api/v1/notifications（通知一覧取得） |
   | `api_endpoint:notifications-get-id` | GET /api/v1/notifications/{notification_id}（通知取得） |
   | `api_endpoint:notifications-put` | PUT /api/v1/notifications/{notification_id}（通知更新）、PUT /api/v1/notifications/bulk（通知一括更新） |
   | `api_endpoint:notifications-delete` | DELETE /api/v1/notifications/{notification_id}（通知削除）、POST /api/v1/notifications/bulk-delete（通知一括削除） |
   | `api_endpoint:notifications-receive-put` | PUT /api/v1/notifications/{notification_id}/receive（通知確認状態更新） |
   | `api_endpoint:notifications-data-receive-put` | PUT /api/v1/notifications/{notification_id}/data/{data_id}/receive（データ受領状態更新） |

4. **L3 の API キーのレルムと認可ストアを紐付ける**

   認可判定には、`L3_API_KEY` のレルムが `AUTHZ_STORE_ID` の認可ストアに紐付けられている必要があります。紐付けが登録されていることを確認してください。

認可を有効にした状態で API を呼び出し、権限を登録した利用者は 2xx、登録していない利用者は 403 になることを確認してください。

---

## ボリュームマウント（開発時）

`docker-compose.yml` では以下のディレクトリがマウントされ、ホットリロードが有効です:

| ホスト側 | コンテナ側 | 用途 |
|---|---|---|
| `../app` | `/app/app` | アプリケーションコード |
| `../migrations` | `/app/migrations` | Alembic マイグレーション |

ソースコードを編集すると、Uvicorn が自動的にリロードします。

---
