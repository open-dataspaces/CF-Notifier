from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Enum, Text, CheckConstraint, Table
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PostgreSQL_UUID, ENUM as PostgreSQL_ENUM
from sqlalchemy.orm import relationship
import enum
import uuid
from app.models.base import Base

# ---------------------------------
# Enumクラス（API仕様に合わせる）
# ---------------------------------
class NotificationStatus(str, enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DELETED = "deleted"

class ConfirmationStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    DELETED = "deleted"

# ---------------------------------
# 中間テーブル（NotificationとNotificationTargetListの多対多）
# ---------------------------------
notification_target_list_map = Table(
    "notification_target_list_map",
    Base.metadata,
    Column("notification_id", PostgreSQL_UUID(as_uuid=True), ForeignKey("notification.notification_id", ondelete="CASCADE"), primary_key=True),
    Column("target_list_id", PostgreSQL_UUID(as_uuid=True), ForeignKey("notification_target_list.target_list_id", ondelete="CASCADE"), primary_key=True)
)

# ---------------------------------
# 通知種別
# ---------------------------------
class NotificationType(Base):
    __tablename__ = "notification_type"
    type_id = Column(PostgreSQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_code = Column(String(100), nullable=False, unique=True)
    type_name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    notifications = relationship("Notification", back_populates="notification_type")

# ---------------------------------
# 通知先リスト
# ---------------------------------
class NotificationTargetList(Base):
    __tablename__ = "notification_target_list"
    target_list_id = Column(PostgreSQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    owner_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    target_ids = relationship("TargetIds", back_populates="target_list", cascade="all, delete-orphan")
    notifications = relationship("Notification", secondary=notification_target_list_map, back_populates="target_lists")

# ---------------------------------
# 通知先リストの受信者
# ---------------------------------
class TargetIds(Base):
    __tablename__ = "target_ids"
    target_list_id = Column(PostgreSQL_UUID(as_uuid=True), ForeignKey("notification_target_list.target_list_id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(String(255), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    target_list = relationship("NotificationTargetList", back_populates="target_ids")

# ---------------------------------
# 通知情報
# ---------------------------------
class Notification(Base):
    __tablename__ = "notification"
    notification_id = Column(PostgreSQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_id = Column(PostgreSQL_UUID(as_uuid=True), ForeignKey("notification_type.type_id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    target_ids = Column(ARRAY(String(255)), nullable=True, comment="通知受信者IDリスト")
    status = Column(PostgreSQL_ENUM('enabled', 'disabled', 'deleted', name='notificationstatus', create_type=False), nullable=False, default='enabled')
    data_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    notification_type = relationship("NotificationType", back_populates="notifications")
    target_lists = relationship("NotificationTargetList", secondary=notification_target_list_map, back_populates="notifications")
    confirmations = relationship("NotificationConfirmed", back_populates="notification", cascade="all, delete-orphan")
    data_confirmations = relationship("NotificationDataConfirmed", back_populates="notification", cascade="all, delete-orphan")

    @property
    def type_code(self):
        """通知種別コード（notification_typeリレーション経由）"""
        return self.notification_type.type_code if self.notification_type else None

    @property
    def type_name(self):
        """通知種別名（notification_typeリレーション経由）"""
        return self.notification_type.type_name if self.notification_type else None

    __table_args__ = (
        CheckConstraint("array_length(target_ids, 1) > 0 OR target_ids IS NULL", name="check_target_ids_non_empty"),
    )

# ---------------------------------
# 通知確認状態
# ---------------------------------
class NotificationConfirmed(Base):
    __tablename__ = "notification_confirmed"
    notification_id = Column(PostgreSQL_UUID(as_uuid=True), ForeignKey("notification.notification_id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(String(255), primary_key=True)
    status = Column(PostgreSQL_ENUM('confirmed', 'unconfirmed', 'deleted', name='confirmationstatus', create_type=False), nullable=False, default='unconfirmed')
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    notification = relationship("Notification", back_populates="confirmations")

# ---------------------------------
# データ受信状態
# ---------------------------------
class NotificationDataConfirmed(Base):
    __tablename__ = "notification_data_confirmed"
    notification_id = Column(PostgreSQL_UUID(as_uuid=True), ForeignKey("notification.notification_id", ondelete="CASCADE"), primary_key=True)
    target_id = Column(String(255), primary_key=True)
    status = Column(PostgreSQL_ENUM('confirmed', 'unconfirmed', 'deleted', name='confirmationstatus', create_type=False), nullable=False, default='unconfirmed')
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    notification = relationship("Notification", back_populates="data_confirmations")