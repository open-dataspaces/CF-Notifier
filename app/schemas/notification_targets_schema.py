"""Notification Targets Schemas"""
from datetime import datetime
from typing import Optional, List
from pydantic import Field, ConfigDict, field_validator
from uuid import UUID
from app.schemas.base import BaseSchema, TimestampSchema

# --------------------------
# 通知先リスト スキーマ
# --------------------------

def _validate_uuid_format(value: str, field_name: str) -> None:
    """UUID形式の文字列かチェックする共通バリデーション"""
    try:
        UUID(value.strip())
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name}: UUID形式で指定してください")


class NotificationTargetBase(BaseSchema):
    # target_list_id: List[str] = Field(..., description="通知先リストID")
    target_list_id: UUID = Field(..., description="通知先リストID")
    name: str = Field(..., description="通知先リスト名")
    owner_id: str = Field(..., description="リスト所有者ID")
    target_ids: List[str] = Field(..., description="通知受信者IDリスト")


class NotificationTargetCreateRequest(BaseSchema):
    """通知先リスト作成時に使うスキーマ"""
    name: str = Field(..., min_length=1, max_length=255, description="通知先リスト名")
    owner_id: str = Field(..., min_length=1, max_length=255, description="リスト所有者ID")
    target_ids: List[str] = Field(..., min_length=1, description="通知受信者IDリスト")

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        if v.strip().isdigit():
            raise ValueError("数字のみの名前は許可されていません")
        return v

    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        _validate_uuid_format(v, "owner_id")
        return v

    @field_validator("target_ids")
    @classmethod
    def validate_target_ids(cls, v: List[str]) -> List[str]:
        for i, tid in enumerate(v):
            if not tid or not tid.strip():
                raise ValueError(f"target_ids[{i}]: 空の値は許可されていません")
            _validate_uuid_format(tid, f"target_ids[{i}]")
        return v


class NotificationTargetUpdateRequest(BaseSchema):
    """通知先リスト更新時に使うスキーマ"""
    name: str = Field(..., min_length=1, max_length=255, description="通知先リスト名")
    owner_id: str = Field(..., min_length=1, max_length=255, description="リスト所有者ID")
    target_ids: List[str] = Field(..., min_length=1, description="通知受信者IDリスト")
    updated_at: datetime = Field(..., description="更新日時（楽観的排他制御用。取得時の updated_at をそのまま指定し、不一致の場合は409）")

    model_config = ConfigDict(
        extra="forbid",  # 未定義フィールドを即座に拒否
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        if v.strip().isdigit():
            raise ValueError("数字のみの名前は許可されていません")
        return v

    @field_validator("owner_id")
    @classmethod
    def validate_owner_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("空白のみの値は許可されていません")
        _validate_uuid_format(v, "owner_id")
        return v

    @field_validator("target_ids")
    @classmethod
    def validate_target_ids(cls, v: List[str]) -> List[str]:
        for i, tid in enumerate(v):
            if not tid or not tid.strip():
                raise ValueError(f"target_ids[{i}]: 空の値は許可されていません")
            _validate_uuid_format(tid, f"target_ids[{i}]")
        return v


class NotificationTargetResponse(NotificationTargetBase):
    """作成・取得時に返却するスキーマ"""
    updated_at: datetime = Field(..., description="更新日時")

    model_config = ConfigDict(from_attributes=True)


class NotificationTargetListResponse(BaseSchema):

    notification_targets: List[NotificationTargetResponse] = Field(
        ..., description="通知先リスト一覧"
    )
