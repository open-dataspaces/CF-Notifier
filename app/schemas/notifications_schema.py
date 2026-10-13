"""Notifications Schemas"""
from datetime import datetime
from enum import Enum
from uuid import UUID
from typing import List, Optional
from pydantic import AliasChoices, ConfigDict, Field, field_validator
from pydantic_core import core_schema
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue

from app.schemas.base import BaseSchema, TimestampSchema


def _validate_uuid_format(value: str, field_name: str) -> None:
    """UUID形式の文字列かチェックする共通バリデーション"""
    try:
        UUID(value.strip())
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name}: UUID形式で指定してください")


class NotificationType(str, Enum):
    INFO = "TBD1"
    WARNING = "TBD2"

class NotificationStatus(str, Enum):
    DELETED = "deleted"
    NO_READ = "not_received"
    READ = "received"

class NotifStatus(str, Enum):
    """通知ステータス（詳細説明版）"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    DELETED = "deleted"

    @classmethod 
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """OpenAPIスキーマにenum値の詳細説明を追加"""
        json_schema = handler(core_schema)
        json_schema.update({
            "description": "通知の状態を表すステータス",
            "x-enum-descriptions": {
                "enabled": "有効 - 通知が配信される状態", 
                "disabled": "無効 - 通知が配信されない状態",
                "deleted": "削除済み - 論理削除された状態"
            }
        })
        return json_schema

class DataReceiveStatus(str, Enum):
    NO_RECEIVE = "not_received"
    RECEIVED = "received"
    # CONFIRMED = "confirmed"

# --- 新しい確認済み受信者モデル ---
class ConfirmedTarget(BaseSchema):
    target_id: str = Field(..., description="受信者ID")
    status: NotificationStatus = Field(..., description="通知確認状態（received: 確認済, not_received: 未確認, deleted: 削除済）")
    updated_at: datetime = Field(..., description="更新日時")

    @field_validator('status', mode='before')
    @classmethod
    def convert_db_status(cls, v):
        mapping = {'confirmed': 'received', 'unconfirmed': 'not_received'}
        if isinstance(v, str):
            v = mapping.get(v, v)
        return v

# --- データ済み受信者モデル ---
class DataConfirmTarget(BaseSchema):
    target_id: str = Field(..., description="受信者ID")
    status: DataReceiveStatus = Field(..., description="データ受領状態（received: 確認済, not_received: 未確認）")
    updated_at: datetime = Field(..., description="更新日時")

    @field_validator('status', mode='before')
    @classmethod
    def convert_db_status(cls, v):
        mapping = {'confirmed': 'received', 'unconfirmed': 'not_received'}
        if isinstance(v, str):
            v = mapping.get(v, v)
        return v

# ---------------
# 通知関連
# ---------------
class NotificationBase(BaseSchema):
    #type: NotificationType = Field(..., description="通知種別")
    type_code: Optional[str] = Field(default=None, description="通知種別コード")
    type_name: Optional[str] = Field(default=None, description="通知種別名")
    title: str = Field(..., description="通知タイトル")
    content: str = Field(..., description="通知内容")
    #target_user_id: UUID = Field(..., description="通知先ユーザID")
    target_ids: List[str] = Field(default_factory=list, description="通知受信者IDのリスト")
    target_list_ids: List[UUID] = Field(default_factory=list, description="通知先リストID")
    data_id: Optional[UUID] = Field(None, description="データID")

# 通知登録 リクエスト
class NotificationCreate(NotificationBase):
    """通知作成時に使うスキーマ"""
    type_code: str = Field(..., min_length=1, max_length=100, description="通知種別コード")
    type_name: str = Field(..., min_length=1, max_length=255, description="通知種別名")
    title: str = Field(..., min_length=1, max_length=500, description="通知タイトル")
    content: str = Field(..., min_length=1, description="通知内容")

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("type_code")
    @classmethod
    def validate_type_code(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("type_name")
    @classmethod
    def validate_type_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("target_ids")
    @classmethod
    def validate_target_ids(cls, v: List[str]) -> List[str]:
        for i, tid in enumerate(v):
            if not tid or not tid.strip():
                raise ValueError(f"target_ids[{i}]: 空の値は許可されていません")
            _validate_uuid_format(tid, f"target_ids[{i}]")
        return v

# 通知登録 レスポンス
class NotificationCreateResponse(NotificationBase):
    notification_id: UUID = Field(..., description="通知ID")

# 通知状態取得
class Notification(NotificationBase):
    notification_id: UUID = Field(..., description="通知ID")
    status: NotifStatus = Field(..., description="ステータス（enabled: 有効, disabled: 無効, deleted: 削除済み）")
    notification_confirmed_targets: List[ConfirmedTarget] = Field(
        default_factory=list,
        validation_alias=AliasChoices("notification_confirmed_targets", "confirmations"),
        description="通知受信者の詳細リスト（ID・ステータス（received: 確認済, not_received: 未確認, deleted: 削除済）・確認時刻）"
    )
    data_confirmed_targets: List[DataConfirmTarget] = Field(
        default_factory=list,
        validation_alias=AliasChoices("data_confirmed_targets", "data_confirmations"),
        description="データ受信者の詳細リスト（ID・ステータス（received: 確認済, not_received: 未確認）・確認時刻）"
    )
    created_at: datetime = Field(..., description="通知登録日時")
    updated_at: datetime = Field(..., description="通知更新日時")

    class Config:
        from_attributes = True

# 通知状態確認
class SelfNotification(BaseSchema):
    notification_id: UUID = Field(..., description="通知ID")
    type_code: Optional[str] = Field(default=None, description="通知種別コード")
    type_name: Optional[str] = Field(default=None, description="通知種別名")
    title: str = Field(..., description="通知タイトル")
    content: str = Field(..., description="通知内容")
    # target_user_ids: List[UUID] = Field(..., description="通知先ユーザIDのリスト")
    # target_list_id: Optional[UUID] = Field(None, description="通知先リストID")
    data_id: Optional[str] = Field(None, description="データID")

class SelfNotificationListResponse(BaseSchema):
    """通知状態確認リストレスポンス"""
    notifications: List[SelfNotification] = Field(..., description="通知リスト")

# 通知更新
class NotificationUpdate(NotificationBase):
    """通知更新時にクライアントが送信するスキーマ（未指定項目は変更しない）"""
    notification_id: UUID = Field(..., description="通知ID")
    status: NotifStatus = Field(..., description="ステータス（enabled: 有効, disabled: 無効, deleted: 削除済み）")
    title: str = Field(..., min_length=1, max_length=500, description="通知タイトル")
    content: str = Field(..., min_length=1, description="通知内容")
    updated_at: datetime = Field(..., description="更新日時（楽観的排他制御用。取得時の updated_at をそのまま指定し、不一致の場合は409）")

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        return v

    @field_validator("target_ids")
    @classmethod
    def validate_target_ids(cls, v: List[str]) -> List[str]:
        for i, tid in enumerate(v):
            if not tid or not tid.strip():
                raise ValueError(f"target_ids[{i}]: 空の値は許可されていません")
            _validate_uuid_format(tid, f"target_ids[{i}]")
        return v

# ---------------
# 通知一括処理
# ---------------
BULK_MAX_ITEMS = 100


def _validate_unique_ids(ids: List[UUID], field_name: str) -> None:
    """一括処理で同じ通知IDが重複指定されていないかチェックする"""
    if len(set(ids)) != len(ids):
        raise ValueError(f"{field_name}: 同じ通知IDが重複して指定されています")


class NotificationBulkCreateRequest(BaseSchema):
    """通知一括登録 リクエスト"""
    notifications: List[NotificationCreate] = Field(
        ..., min_length=1, max_length=BULK_MAX_ITEMS,
        description=f"登録する通知のリスト（1～{BULK_MAX_ITEMS}件）"
    )

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )


class NotificationBulkCreateResponse(BaseSchema):
    """通知一括登録 レスポンス"""
    notifications: List[NotificationCreateResponse] = Field(..., description="登録した通知のリスト（リクエストと同じ順序）")


class NotificationBulkUpdateRequest(BaseSchema):
    """通知一括更新 リクエスト"""
    notifications: List[NotificationUpdate] = Field(
        ..., min_length=1, max_length=BULK_MAX_ITEMS,
        description=f"更新する通知のリスト（1～{BULK_MAX_ITEMS}件）。各要素の notification_id で更新対象を指定する"
    )

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("notifications")
    @classmethod
    def validate_unique_notification_ids(cls, v: List[NotificationUpdate]) -> List[NotificationUpdate]:
        _validate_unique_ids([n.notification_id for n in v], "notifications")
        return v


class NotificationBulkUpdateResponse(BaseSchema):
    """通知一括更新 レスポンス"""
    notifications: List[Notification] = Field(..., description="更新後の通知のリスト（リクエストと同じ順序）")


class NotificationBulkDeleteRequest(BaseSchema):
    """通知一括削除 リクエスト"""
    notification_ids: List[UUID] = Field(
        ..., min_length=1, max_length=BULK_MAX_ITEMS,
        description=f"削除する通知IDのリスト（1～{BULK_MAX_ITEMS}件）"
    )

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("notification_ids")
    @classmethod
    def validate_unique_notification_ids(cls, v: List[UUID]) -> List[UUID]:
        _validate_unique_ids(v, "notification_ids")
        return v


class NotifUpdateSuccessResponse(BaseSchema):
    # status: NotificationStatus = Field(..., description="通知確認状態")
    updated_at: datetime = Field(..., description="更新日時")

class DataUpdateSuccessResponse(BaseSchema):
    # status: DataReceiveStatus = Field(..., description="データ受領状態")
    updated_at: datetime = Field(..., description="更新日時")