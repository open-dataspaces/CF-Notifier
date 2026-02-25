"""Initial tables - Notification関連テーブルのみ

Revision ID: 001_initial
Revises:
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # ENUM Types
    # ===========================================
    notification_status = postgresql.ENUM(
        'enabled', 'disabled', 'deleted',
        name='notificationstatus',
        create_type=False
    )
    confirmation_status = postgresql.ENUM(
        'confirmed', 'unconfirmed', 'deleted',
        name='confirmationstatus',
        create_type=False
    )

    # Create ENUM types
    op.execute("CREATE TYPE notificationstatus AS ENUM ('enabled', 'disabled', 'deleted')")
    op.execute("CREATE TYPE confirmationstatus AS ENUM ('confirmed', 'unconfirmed', 'deleted')")

    # ===========================================
    # Notification Type Table
    # ===========================================
    op.create_table(
        'notification_type',
        sa.Column('type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type_code', sa.String(100), nullable=False),
        sa.Column('type_name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('type_id'),
        sa.UniqueConstraint('type_code'),
        sa.UniqueConstraint('type_name'),
    )

    # ===========================================
    # Notification Target List Table
    # ===========================================
    op.create_table(
        'notification_target_list',
        sa.Column('target_list_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('target_list_id'),
    )

    # ===========================================
    # Target IDs Table
    # ===========================================
    op.create_table(
        'target_ids',
        sa.Column('target_list_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('target_list_id', 'target_id'),
        sa.ForeignKeyConstraint(['target_list_id'], ['notification_target_list.target_list_id'], ondelete='CASCADE'),
    )

    # ===========================================
    # Notification Table
    # ===========================================
    op.create_table(
        'notification',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('target_ids', postgresql.ARRAY(sa.String(255)), nullable=True, comment='通知受信者IDリスト'),
        sa.Column('status', postgresql.ENUM('enabled', 'disabled', 'deleted', name='notificationstatus', create_type=False), nullable=False),
        sa.Column('data_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('notification_id'),
        sa.ForeignKeyConstraint(['type_id'], ['notification_type.type_id']),
        sa.CheckConstraint('array_length(target_ids, 1) > 0 OR target_ids IS NULL', name='check_target_ids_non_empty'),
    )

    # Notification Indexes
    op.create_index('ix_notification_type_id', 'notification', ['type_id'])

    # ===========================================
    # Notification Target List Map Table (Many-to-Many)
    # ===========================================
    op.create_table(
        'notification_target_list_map',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_list_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('notification_id', 'target_list_id'),
        sa.ForeignKeyConstraint(['notification_id'], ['notification.notification_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_list_id'], ['notification_target_list.target_list_id'], ondelete='CASCADE'),
    )

    # ===========================================
    # Notification Confirmed Table
    # ===========================================
    op.create_table(
        'notification_confirmed',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(255), nullable=False),
        sa.Column('status', postgresql.ENUM('confirmed', 'unconfirmed', 'deleted', name='confirmationstatus', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('notification_id', 'target_id'),
        sa.ForeignKeyConstraint(['notification_id'], ['notification.notification_id'], ondelete='CASCADE'),
    )

    # ===========================================
    # Notification Data Confirmed Table
    # ===========================================
    op.create_table(
        'notification_data_confirmed',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', sa.String(255), nullable=False),
        sa.Column('status', postgresql.ENUM('confirmed', 'unconfirmed', 'deleted', name='confirmationstatus', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('notification_id', 'target_id'),
        sa.ForeignKeyConstraint(['notification_id'], ['notification.notification_id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    """
    WARNING: このダウングレードは全てのテーブルとデータを削除します。
    本番環境での実行は推奨されません。

    実行する場合は環境変数 ALLOW_DESTRUCTIVE_MIGRATION=true を設定してください。
    """
    import os

    # 本番環境での安全チェック
    allow_destructive = os.environ.get('ALLOW_DESTRUCTIVE_MIGRATION', 'false').lower() == 'true'
    environment = os.environ.get('ENVIRONMENT', 'PRODUCTION')

    if environment == 'PRODUCTION' and not allow_destructive:
        raise RuntimeError(
            "DANGER: Downgrade of initial migration will DELETE ALL DATA. "
            "This operation is blocked in PRODUCTION. "
            "If you really want to proceed, set ALLOW_DESTRUCTIVE_MIGRATION=true"
        )

    # Drop tables in reverse order (due to foreign key dependencies)
    op.drop_table('notification_data_confirmed')
    op.drop_table('notification_confirmed')
    op.drop_table('notification_target_list_map')
    op.drop_index('ix_notification_type_id', table_name='notification')
    op.drop_table('notification')
    op.drop_table('target_ids')
    op.drop_table('notification_target_list')
    op.drop_table('notification_type')

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS confirmationstatus')
    op.execute('DROP TYPE IF EXISTS notificationstatus')
