"""共通レスポンスヘッダ定義（OpenAPIドキュメント用）"""

# OpenAPIドキュメントに表示するレスポンスヘッダ定義
# 実際のヘッダ値はミドルウェア(CommonSecurityHeadersMiddleware, TrackingMiddleware)で設定
COMMON_RESPONSE_HEADERS = {
    "Cache-Control": {
        "description": "キャッシュ制御指示",
        "schema": {"type": "string", "example": "no-cache, no-store, must-revalidate"},
    },
    "X-TrackingId": {
        "description": "リクエストトラッキング用UUID",
        "schema": {"type": "string", "example": "550e8400-e29b-41d4-a716-446655440000"},
    },
    "Content-Security-Policy": {
        "description": "XSS対策",
        "schema": {"type": "string", "example": "default-src 'self'"},
    },
    "X-Content-Type-Options": {
        "description": "MIMEスニッフィング防止",
        "schema": {"type": "string", "example": "nosniff"},
    },
    "Strict-Transport-Security": {
        "description": "HTTPS強制",
        "schema": {"type": "string", "example": "max-age=63072000; includeSubDomains"},
    },
}

# GETエンドポイント用の追加ヘッダ（リソース取得時のキャッシュ制御）
GET_RESPONSE_HEADERS = {
    "ETag": {
        "description": "レスポンス内容のバージョン識別子（弱いETag）",
        "schema": {"type": "string", "example": 'W/"3f2a9c...e1b0"'},
    },
}

# 個別リソース取得（パスパラメータあり）用の追加ヘッダ
GET_RESOURCE_RESPONSE_HEADERS = {
    "Last-Modified": {
        "description": "リソースの最終更新日時",
        "schema": {"type": "string", "example": "Wed, 30 Jul 2025 01:00:00 GMT"},
    },
}

# GETエンドポイント用の条件付きリクエストヘッダ
GET_REQUEST_PARAMETERS = [
    {
        "name": "If-None-Match",
        "in": "header",
        "required": False,
        "description": "前回取得時の ETag。現在の ETag と一致する場合は 304 Not Modified を返す",
        "schema": {"type": "string"},
    },
]

# 個別リソース取得（パスパラメータあり）用の条件付きリクエストヘッダ
GET_RESOURCE_REQUEST_PARAMETERS = [
    {
        "name": "If-Modified-Since",
        "in": "header",
        "required": False,
        "description": "前回取得時の Last-Modified。以降に更新がない場合は 304 Not Modified を返す（If-None-Match 指定時は無視）",
        "schema": {"type": "string"},
    },
]

# 条件付きリクエストの条件に一致した場合のレスポンス
NOT_MODIFIED_RESPONSE = {
    "description": "未更新（If-None-Match / If-Modified-Since の条件に一致。ボディなし）",
}
