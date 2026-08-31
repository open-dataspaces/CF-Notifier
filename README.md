# Notifierサービス

## 概要

本サービスは、Open Data Spaces(ODS)の共通機能（Common Functionalities）の一つとして動作し、
提供者からのデータ配信の通知機能を提供するAPIサーバです。

### 主要機能

- **通知先リスト管理**: 通知先リストの作成・更新・取得・削除
- **通知管理**: 通知の作成・更新・取得・削除
- **通知確認**: ユーザーによる通知の既読確認
- **データ受信確認**: データ受信状態の更新


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
│   │   └── authz_client.py       # OpenFGA認可クライアント
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

