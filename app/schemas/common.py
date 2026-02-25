from typing import Optional
from pydantic import Field,ConfigDict
from fastapi import Header

from app.schemas.base import BaseSchema, TimestampSchema

class CommonRequestHeaders(BaseSchema):
    """
    共通リクエストヘッダーをPydanticモデルとして定義
    FastAPIが自動的にエイリアス(例: 'User-Agent')からマッピングします
    """
    user_agent: str = Header(..., alias="User-Agent", description="User-Agent",convert_underscores=False)
    x_tracking_id: str = Header(..., alias="X-TrackingId", description="X-TrackingId",convert_underscores=False)
    accept_language: str = Header("ja-JP", alias="Accept-Language", description="Accept-Language",convert_underscores=False)
    x_notifier_api_key: str = Header(..., alias="x-notifier-api-key", description="x-notifier-api-key",convert_underscores=False)
    
    # Pydantic v2 の設定 (populate_by_name=True が重要)
    model_config = ConfigDict(
        populate_by_name=True, # エイリアス名(camelCase)でもフィールド名(snake_case)でも初期化を許可
        # スキーマ生成時やシリアライズ時にaliasを優先させる設定
        by_alias=True
    )

class ErrorResponse(BaseSchema):
    type: str
    title: str
    detail: str
    status: int
    instance: str
