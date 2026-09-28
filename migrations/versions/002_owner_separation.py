"""Owner separation - 通知の所有者（提供者）による分離

Revision ID: 002_owner_separation
Revises: 001_initial
Create Date: 2026-09-28

- notification に所有者ID（owner_id）を追加し、既存データを補完する
- owner_id にインデックスを追加する
- 通知と通知先リストの所有者が一致することを、複合外部キーで保証する
- 受信者IDを直接指定した分の通知確認状態を補完する

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_owner_separation'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # Notification: 所有者ID
    # ===========================================
    op.add_column(
        'notification',
        sa.Column('owner_id', sa.String(255), nullable=True, comment='所有者ID（通知を登録した提供者のoperator_id）'),
    )

    # 既存の通知は、通知先リスト経由で登録されたものだけ、リストの所有者で補完する
    op.execute("""
        UPDATE notification n
        SET owner_id = sub.owner_id
        FROM (
            SELECT m.notification_id, MIN(l.owner_id) AS owner_id
            FROM notification_target_list_map m
            JOIN notification_target_list l ON l.target_list_id = m.target_list_id
            GROUP BY m.notification_id
            HAVING COUNT(DISTINCT l.owner_id) = 1
        ) sub
        WHERE n.notification_id = sub.notification_id
    """)

    op.create_check_constraint(
        'ck_notification_owner_id_not_null', 'notification', 'owner_id IS NOT NULL',
        postgresql_not_valid=True,
    )

    # ===========================================
    # Indexes
    # ===========================================
    op.create_index('ix_notification_owner_id', 'notification', ['owner_id'])
    op.create_index('ix_notification_target_list_owner_id', 'notification_target_list', ['owner_id'])

    # ===========================================
    # 通知と通知先リストの所有者一致（複合外部キー）
    # ===========================================
    op.create_unique_constraint('uq_notification_id_owner_id', 'notification', ['notification_id', 'owner_id'])
    op.create_unique_constraint(
        'uq_notification_target_list_id_owner_id', 'notification_target_list', ['target_list_id', 'owner_id']
    )

    op.add_column(
        'notification_target_list_map',
        sa.Column('owner_id', sa.String(255), nullable=True, comment='所有者ID（通知と通知先リストで同一）'),
    )
    op.execute("""
        UPDATE notification_target_list_map m
        SET owner_id = n.owner_id
        FROM notification n
        WHERE n.notification_id = m.notification_id
    """)
    op.create_check_constraint(
        'ck_notification_target_list_map_owner_id_not_null', 'notification_target_list_map', 'owner_id IS NOT NULL',
        postgresql_not_valid=True,
    )
    op.create_foreign_key(
        'fk_map_notification_owner', 'notification_target_list_map', 'notification',
        ['notification_id', 'owner_id'], ['notification_id', 'owner_id'], ondelete='CASCADE',
    )
    op.create_foreign_key(
        'fk_map_target_list_owner', 'notification_target_list_map', 'notification_target_list',
        ['target_list_id', 'owner_id'], ['target_list_id', 'owner_id'], ondelete='CASCADE',
    )

    # ===========================================
    # 送信時点の受信者の固定
    # ===========================================
    op.execute("""
        INSERT INTO notification_confirmed (notification_id, target_id, status, created_at, updated_at)
        SELECT n.notification_id, t.target_id, 'unconfirmed'::confirmationstatus, n.created_at, n.created_at
        FROM notification n
        CROSS JOIN LATERAL unnest(n.target_ids) AS t(target_id)
        ON CONFLICT (notification_id, target_id) DO NOTHING
    """)


def downgrade() -> None:
    """
    所有者IDと関連する制約・インデックスを削除する。
    補完した通知確認状態は削除しない。
    """
    op.drop_constraint('fk_map_target_list_owner', 'notification_target_list_map', type_='foreignkey')
    op.drop_constraint('fk_map_notification_owner', 'notification_target_list_map', type_='foreignkey')
    op.drop_constraint('ck_notification_target_list_map_owner_id_not_null', 'notification_target_list_map', type_='check')
    op.drop_column('notification_target_list_map', 'owner_id')

    op.drop_constraint('uq_notification_target_list_id_owner_id', 'notification_target_list', type_='unique')
    op.drop_constraint('uq_notification_id_owner_id', 'notification', type_='unique')

    op.drop_index('ix_notification_target_list_owner_id', table_name='notification_target_list')
    op.drop_index('ix_notification_owner_id', table_name='notification')

    op.drop_constraint('ck_notification_owner_id_not_null', 'notification', type_='check')
    op.drop_column('notification', 'owner_id')
