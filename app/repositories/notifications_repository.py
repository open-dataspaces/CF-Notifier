"""
データベースリポジトリ(3層アーキテクチャ対応版)

各モデルに対するCRUD操作を提供するリポジトリパターン実装
ログ機能、エラーハンドリングを含む

重要: Repository層ではcommit/rollbackを行いません
      トランザクション管理はService層の責務です
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import uuid
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import (
    IntegrityError, 
    SQLAlchemyError,
    NoResultFound
)
from sqlalchemy import and_, or_, func, update as sa_update

# ログ設定のインポート
from app.core.logging import get_logger, log_execution_time
logger = get_logger(__name__)

# モデルのインポート
from app.models.notifications_model import (
    NotificationTargetList,
    TargetIds,
    NotificationType,
    Notification,
    NotificationConfirmed,
    NotificationDataConfirmed,
    NotificationStatus,
    ConfirmationStatus,
    notification_target_list_map,
)

from . import BaseRepository

# ============================================================================
# 通知種別リポジトリ
# ============================================================================

class NotificationTypeRepository(BaseRepository):
    """通知種別の操作を管理するリポジトリ"""
    
    @log_execution_time(logger, 'debug')
    def create(
        self,
        type_id: str,
        type_code: str,
        type_name: str
    ) -> NotificationType:
        """
        通知種別を作成(commitはService層で実施)
        
        Args:
            type_id: 通知種別ID
            type_code: 通知種別コード
            type_name: 通知種別名
        
        Returns:
            作成された通知種別(未commit)
        """
        try:
            logger.info(
                "Creating notification type",
                extra={
                    'type_id': type_id,
                    'type_code': type_code,
                    'type_name': type_name
                }
            )
            
            notification_type = NotificationType(
                type_id=type_id,
                type_code=type_code,
                type_name=type_name
            )
            
            self.db.add(notification_type)
            self.db.flush()
            
            logger.info(
                "Notification type created (not committed)",
                extra={'type_id': type_id}
            )
            
            return notification_type
            
        except SQLAlchemyError as e:
            self._log_error(e, 'create_notification_type')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_id(self, type_id: str) -> Optional[NotificationType]:
        """
        IDで通知種別を取得
        
        Args:
            type_id: 通知種別ID
        
        Returns:
            通知種別(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting notification type by ID",
                extra={'type_id': type_id}
            )
            
            notification_type = self.db.query(NotificationType).filter(
                NotificationType.type_id == type_id
            ).first()
            
            if notification_type:
                logger.debug("Notification type found", extra={'type_id': type_id})
            else:
                logger.debug("Notification type not found", extra={'type_id': type_id})
            
            return notification_type
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_type')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_code(self, type_code: str) -> Optional[NotificationType]:
        """
        コードで通知種別を取得
        
        Args:
            type_code: 通知種別コード
        
        Returns:
            通知種別(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting notification type by code",
                extra={'type_code': type_code}
            )
            
            notification_type = self.db.query(NotificationType).filter(
                NotificationType.type_code == type_code
            ).first()
            
            if notification_type:
                logger.debug("Notification type found", extra={'type_code': type_code})
            else:
                logger.debug("Notification type not found", extra={'type_code': type_code})
            
            return notification_type
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_type_by_code')
            raise

    @log_execution_time(logger, 'debug')
    def get_by_name(self, type_name: str) -> Optional[NotificationType]:
        """
        名前で通知種別を取得

        Args:
            type_name: 通知種別名

        Returns:
            通知種別(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting notification type by name",
                extra={'type_name': type_name}
            )

            notification_type = self.db.query(NotificationType).filter(
                NotificationType.type_name == type_name
            ).first()

            if notification_type:
                logger.debug("Notification type found", extra={'type_name': type_name})
            else:
                logger.debug("Notification type not found", extra={'type_name': type_name})

            return notification_type

        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_type_by_name')
            raise

    @log_execution_time(logger, 'debug')
    def get_all(self) -> List[NotificationType]:
        """
        すべての通知種別を取得
        
        Returns:
            通知種別のリスト
        """
        try:
            logger.debug("Getting all notification types")
            
            notification_types = self.db.query(NotificationType).order_by(
                NotificationType.type_code
            ).all()
            
            logger.debug(
                "Retrieved notification types",
                extra={'count': len(notification_types)}
            )
            
            return notification_types
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_all_notification_types')
            raise
    
    @log_execution_time(logger, 'debug')
    def update(
        self,
        type_id: str,
        type_code: Optional[str] = None,
        type_name: Optional[str] = None
    ) -> Optional[NotificationType]:
        """
        通知種別を更新(commitはService層で実施)
        
        Args:
            type_id: 通知種別ID
            type_code: 新しい通知種別コード
            type_name: 新しい通知種別名
        
        Returns:
            更新された通知種別(存在しない場合はNone)
        """
        try:
            logger.info(
                "Updating notification type",
                extra={'type_id': type_id}
            )
            
            notification_type = self.get_by_id(type_id)
            
            if not notification_type:
                logger.warning(
                    "Cannot update: notification type not found",
                    extra={'type_id': type_id}
                )
                return None
            
            if type_code is not None:
                notification_type.type_code = type_code
            if type_name is not None:
                notification_type.type_name = type_name
            
            notification_type.updated_at = datetime.utcnow()
            
            self.db.flush()
            
            logger.info(
                "Notification type updated (not committed)",
                extra={'type_id': type_id}
            )
            
            return notification_type
            
        except SQLAlchemyError as e:
            self._log_error(e, 'update_notification_type')
            raise
    
    @log_execution_time(logger, 'debug')
    def delete(self, type_id: str) -> bool:
        """
        通知種別を削除(commitはService層で実施)
        
        Args:
            type_id: 通知種別ID
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Deleting notification type",
                extra={'type_id': type_id}
            )
            
            notification_type = self.get_by_id(type_id)
            
            if not notification_type:
                logger.warning(
                    "Cannot delete: notification type not found",
                    extra={'type_id': type_id}
                )
                return False
            
            self.db.delete(notification_type)
            self.db.flush()
            
            logger.info(
                "Notification type deleted (not committed)",
                extra={'type_id': type_id}
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'delete_notification_type')
            raise


# ============================================================================
# 通知情報リポジトリ
# ============================================================================


class NotificationRepository(BaseRepository):
    """通知情報の操作を管理するリポジトリ"""

    @log_execution_time(logger, 'debug')
    def create(
        self,
        notification_id: uuid.UUID,
        type_id: uuid.UUID,
        title: str,
        content: str,
        target_ids: Optional[List[str]] = None,
        target_list_ids: Optional[List[str]] = None,
        status: str = 'enabled',
        data_id: Optional[str] = None
    ) -> Notification:
        try:
            logger.info("Creating notification", extra={
                'notification_id': str(notification_id),
                'type_id': str(type_id),
                'title': title,
                'target_count': len(target_ids) if target_ids else 0,
                'target_list_ids': target_list_ids,
                'status': status
            })

            # ✅ target_idsを文字列化
            if target_ids:
                target_ids = [str(t) for t in target_ids]

            # ✅ data_idも文字列化
            if data_id and isinstance(data_id, uuid.UUID):
                data_id = str(data_id)

            notification = Notification(
                notification_id=notification_id,
                type_id=type_id,
                title=title,
                content=content,
                target_ids=target_ids,
                status=status,
                data_id=data_id
            )

            self.db.add(notification)

            # ✅ target_list_idsがある場合、中間テーブル経由で関連付け
            if target_list_ids:
                # Handle both UUID objects and strings
                uuid_list_ids = [
                    t if isinstance(t, uuid.UUID) else uuid.UUID(str(t))
                    for t in target_list_ids
                ]
                target_lists = (
                    self.db.query(NotificationTargetList)
                    .filter(NotificationTargetList.target_list_id.in_(uuid_list_ids))
                    .all()
                )
                for tl in target_lists:
                    notification.target_lists.append(tl)

            self.db.flush()
            logger.info("Notification created (not committed)", extra={'notification_id': str(notification_id)})
            return notification

        except SQLAlchemyError as e:
            self._log_error(e, 'create_notification')
            raise

    @log_execution_time(logger, 'debug')
    def get_by_id(
        self,
        notification_id: uuid.UUID,
        include_relations: bool = False,
        include_deleted: bool = False
    ) -> Optional[Notification]:
        try:
            query = self.db.query(Notification)
            if include_relations:
                query = query.options(
                    joinedload(Notification.notification_type),
                    joinedload(Notification.target_lists),
                    joinedload(Notification.confirmations),
                    joinedload(Notification.data_confirmations)
                )
            query = query.filter(Notification.notification_id == notification_id)
            if not include_deleted:
                query = query.filter(Notification.status != NotificationStatus.DELETED.value)
            return query.first()
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification')
            raise

    @log_execution_time(logger, 'debug')
    def get_by_target_id(self, target_id: str, status: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Notification]:
        try:
            # ✅ target_list_id参照を削除し、中間テーブルJOINに変更
            query = self.db.query(Notification).options(
                joinedload(Notification.notification_type)
            ).filter(
                or_(
                    Notification.target_ids.contains([target_id]),
                    Notification.notification_id.in_(
                        self.db.query(notification_target_list_map.c.notification_id)
                        .join(TargetIds, TargetIds.target_list_id == notification_target_list_map.c.target_list_id)
                        .filter(TargetIds.target_id == target_id)
                    )
                )
            )
            query = query.filter(Notification.status != NotificationStatus.DELETED.value)
            if status:
                query = query.filter(Notification.status == status)
            return query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notifications_by_target_id')
            raise

    
    @log_execution_time(logger, 'debug')
    def get_by_type(
        self,
        type_id: str,
        status: Optional[NotificationStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Notification]:
        """
        通知種別IDで通知を取得
        
        Args:
            type_id: 通知種別ID
            status: フィルタするステータス
            skip: スキップする件数
            limit: 取得する最大件数
        
        Returns:
            通知のリスト
        """
        try:
            logger.debug(
                "Getting notifications by type",
                extra={
                    'type_id': type_id,
                    'status': status if status else None,
                    'skip': skip,
                    'limit': limit
                }
            )
            
            query = self.db.query(Notification).filter(
                Notification.type_id == type_id
            )
            
            query = query.filter(Notification.status != NotificationStatus.DELETED.value)
            if status:
                query = query.filter(Notification.status == status)

            notifications = query.order_by(
                Notification.created_at.desc()
            ).offset(skip).limit(limit).all()

            logger.debug(
                "Retrieved notifications",
                extra={
                    'type_id': type_id,
                    'count': len(notifications)
                }
            )

            return notifications

        except SQLAlchemyError as e:
            self._log_error(e, 'get_notifications_by_type')
            raise
    
    @log_execution_time(logger, 'debug')
    def update(
        self,
        notification_id: str,
        expected_updated_at: datetime,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[NotificationStatus] = None
    ) -> Optional[Notification]:
        """
        通知を更新(commitはService層で実施)
        
        Args:
            notification_id: 通知ID
            expected_updated_at: クライアントが取得時に保持していた更新日時
            title: 新しいタイトル
            content: 新しい内容
            status: 新しいステータス
        
        Returns:
            更新された通知(存在しない、または更新日時が一致しない場合はNone)
        """
        try:
            logger.info(
                "Updating notification",
                extra={'notification_id': notification_id}
            )
            
            values = {'updated_at': datetime.utcnow()}
            if title is not None:
                values['title'] = title
            if content is not None:
                values['content'] = content
            if status is not None:
                values['status'] = status

            result = self.db.execute(
                sa_update(Notification)
                .where(
                    Notification.notification_id == notification_id,
                    Notification.status != NotificationStatus.DELETED.value,
                    Notification.updated_at == expected_updated_at
                )
                .values(**values)
                .execution_options(synchronize_session='fetch')
            )

            if result.rowcount == 0:
                logger.warning(
                    "Cannot update: notification not found or updated_at mismatch",
                    extra={'notification_id': notification_id}
                )
                return None
            
            # status を deleted に更新した場合も更新後の通知を返す
            notification = self.get_by_id(notification_id, include_relations=True, include_deleted=True)

            logger.info(
                "Notification updated (not committed)",
                extra={'notification_id': notification_id}
            )
            
            return notification
            
        except SQLAlchemyError as e:
            self._log_error(e, 'update_notification')
            raise
    
    @log_execution_time(logger, 'debug')
    def delete(self, notification_id: str) -> bool:
        """
        通知を削除(論理削除:ステータスをDELETEDに変更)
        commitはService層で実施
        
        Args:
            notification_id: 通知ID
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Deleting notification (soft delete)",
                extra={'notification_id': notification_id}
            )
            
            notification = self.get_by_id(notification_id)
            
            if not notification:
                logger.warning(
                    "Cannot delete: notification not found",
                    extra={'notification_id': notification_id}
                )
                return False
            
            notification.status = 'deleted'
            notification.updated_at = datetime.utcnow()
            
            self.db.flush()
            
            logger.info(
                "Notification deleted (soft delete, not committed)",
                extra={'notification_id': notification_id}
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'delete_notification')
            raise
    
    @log_execution_time(logger, 'debug')
    def hard_delete(self, notification_id: str) -> bool:
        """
        通知を物理削除(commitはService層で実施)
        
        Args:
            notification_id: 通知ID
        
        Returns:
            削除成功時True
        """
        try:
            logger.warning(
                "Hard deleting notification",
                extra={'notification_id': notification_id}
            )
            
            notification = self.get_by_id(notification_id)
            
            if not notification:
                logger.warning(
                    "Cannot delete: notification not found",
                    extra={'notification_id': notification_id}
                )
                return False
            
            self.db.delete(notification)
            self.db.flush()
            
            logger.warning(
                "Notification hard deleted (not committed)",
                extra={'notification_id': notification_id}
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'hard_delete_notification')
            raise


# ============================================================================
# 通知確認済み状態リポジトリ
# ============================================================================

class NotificationConfirmedRepository(BaseRepository):
    """通知確認済み状態の操作を管理するリポジトリ"""
    
    @log_execution_time(logger, 'debug')
    def create_or_update(
        self,
        notification_id: str,
        target_id: str,
        status: str
    ) -> NotificationConfirmed:
        """
        通知確認状態を作成または更新(commitはService層で実施)
        
        Args:
            notification_id: 通知ID
            target_id: 通知受信者ID
            status: 確認状態
        
        Returns:
            通知確認状態(未commit)
        """
        try:
            logger.info(
                "Creating or updating notification confirmation",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id,
                    'status': status
                }
            )
            
            # 既存のレコードを取得
            confirmation = self.db.query(NotificationConfirmed).filter(
                and_(
                    NotificationConfirmed.notification_id == notification_id,
                    NotificationConfirmed.target_id == target_id
                )
            ).first()
            
            if confirmation:
                # 更新
                confirmation.status = status
                confirmation.updated_at = datetime.utcnow()
                logger.info("Updated existing confirmation")
            else:
                # 新規作成
                confirmation = NotificationConfirmed(
                    notification_id=notification_id,
                    target_id=target_id,
                    status=status
                )
                self.db.add(confirmation)
                logger.info("Created new confirmation")
            
            self.db.flush()
            
            logger.info(
                "Notification confirmation saved (not committed)",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id
                }
            )
            
            return confirmation
            
        except SQLAlchemyError as e:
            self._log_error(e, 'create_or_update_notification_confirmation')
            raise
    
    @log_execution_time(logger, 'debug')
    def get(
        self,
        notification_id: str,
        target_id: str
    ) -> Optional[NotificationConfirmed]:
        """
        通知確認状態を取得
        
        Args:
            notification_id: 通知ID
            target_id: 通知受信者ID
        
        Returns:
            通知確認状態(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting notification confirmation",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id
                }
            )
            
            confirmation = self.db.query(NotificationConfirmed).filter(
                and_(
                    NotificationConfirmed.notification_id == notification_id,
                    NotificationConfirmed.target_id == target_id
                )
            ).first()
            
            if confirmation:
                logger.debug("Notification confirmation found")
            else:
                logger.debug("Notification confirmation not found")
            
            return confirmation
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_confirmation')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_notification(
        self,
        notification_id: str
    ) -> List[NotificationConfirmed]:
        """
        通知IDで確認状態を取得
        
        Args:
            notification_id: 通知ID
        
        Returns:
            通知確認状態のリスト
        """
        try:
            logger.debug(
                "Getting confirmation states for notification",
                extra={'notification_id': notification_id}
            )
            
            confirmations = self.db.query(NotificationConfirmed).filter(
                NotificationConfirmed.notification_id == notification_id
            ).all()
            
            logger.debug(
                "Retrieved confirmation states",
                extra={
                    'notification_id': notification_id,
                    'count': len(confirmations)
                }
            )
            
            return confirmations
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_confirmations_by_notification')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_target(
        self,
        target_id: str,
        status: Optional[str] = None
    ) -> List[NotificationConfirmed]:
        """
        通知受信者IDで確認状態を取得
        
        Args:
            target_id: 通知受信者ID
            status: フィルタする確認状態
        
        Returns:
            通知確認状態のリスト
        """
        try:
            logger.debug(
                "Getting confirmation states for target",
                extra={
                    'target_id': target_id,
                    'status': status if status else None
                }
            )
            
            query = self.db.query(NotificationConfirmed).filter(
                NotificationConfirmed.target_id == target_id
            )
            
            if status:
                query = query.filter(NotificationConfirmed.status == status)
            
            confirmations = query.all()
            
            logger.debug(
                "Retrieved confirmation states",
                extra={
                    'target_id': target_id,
                    'count': len(confirmations)
                }
            )
            
            return confirmations
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_confirmations_by_target')
            raise


# ============================================================================
# データ受信済み状態リポジトリ
# ============================================================================

class NotificationDataConfirmedRepository(BaseRepository):
    """データ受信済み状態の操作を管理するリポジトリ"""
    
    @log_execution_time(logger, 'debug')
    def create_or_update(
        self,
        notification_id: str,
        target_id: str,
        status: str
    ) -> NotificationDataConfirmed:
        """
        データ受信状態を作成または更新(commitはService層で実施)
        
        Args:
            notification_id: 通知ID
            target_id: 通知受信者ID
            status: 受信状態
        
        Returns:
            データ受信状態(未commit)
        """
        try:
            logger.info(
                "Creating or updating data confirmation",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id,
                    'status': status
                }
            )


            # 既存のレコードを取得
            data_confirmation = self.db.query(NotificationDataConfirmed).filter(
                and_(
                    NotificationDataConfirmed.notification_id == notification_id,
                    NotificationDataConfirmed.target_id == target_id
                )
            ).first()
            
            if data_confirmation:
                # 更新
                data_confirmation.status = status
                data_confirmation.updated_at = datetime.utcnow()
                logger.info("Updated existing data confirmation")
            else:
                # 新規作成
                data_confirmation = NotificationDataConfirmed(
                    notification_id=notification_id,
                    target_id=target_id,
                    status=status
                )
                self.db.add(data_confirmation)
                logger.info("Created new data confirmation")
            
            self.db.flush()
            
            logger.info(
                "Data confirmation saved (not committed)",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id
                }
            )
            
            return data_confirmation
            
        except SQLAlchemyError as e:
            self._log_error(e, 'create_or_update_data_confirmation')
            raise
    
    @log_execution_time(logger, 'debug')
    def get(
        self,
        notification_id: str,
        target_id: str
    ) -> Optional[NotificationDataConfirmed]:
        """
        データ受信状態を取得
        
        Args:
            notification_id: 通知ID
            target_id: 通知受信者ID
        
        Returns:
            データ受信状態(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting data confirmation",
                extra={
                    'notification_id': notification_id,
                    'target_id': target_id
                }
            )
            
            data_confirmation = self.db.query(NotificationDataConfirmed).filter(
                and_(
                    NotificationDataConfirmed.notification_id == notification_id,
                    NotificationDataConfirmed.target_id == target_id
                )
            ).first()
            
            if data_confirmation:
                logger.debug("Data confirmation found")
            else:
                logger.debug("Data confirmation not found")
            
            return data_confirmation
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_data_confirmation')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_notification(
        self,
        notification_id: str
    ) -> List[NotificationDataConfirmed]:
        """
        通知IDでデータ受信状態を取得
        
        Args:
            notification_id: 通知ID
        
        Returns:
            データ受信状態のリスト
        """
        try:
            logger.debug(
                "Getting data confirmation states for notification",
                extra={'notification_id': notification_id}
            )
            
            data_confirmations = self.db.query(NotificationDataConfirmed).filter(
                NotificationDataConfirmed.notification_id == notification_id
            ).all()
            
            logger.debug(
                "Retrieved data confirmation states",
                extra={
                    'notification_id': notification_id,
                    'count': len(data_confirmations)
                }
            )
            
            return data_confirmations
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_data_confirmations_by_notification')
            raise


# ============================================================================
# ファクトリー関数
# ============================================================================

def get_notification_type_repository(db: Session) -> NotificationTypeRepository:
    """通知種別リポジトリを取得"""
    return NotificationTypeRepository(db)


def get_notification_repository(db: Session) -> NotificationRepository:
    """通知リポジトリを取得"""
    return NotificationRepository(db)


def get_notification_confirmed_repository(db: Session) -> NotificationConfirmedRepository:
    """通知確認済み状態リポジトリを取得"""
    return NotificationConfirmedRepository(db)


def get_notification_data_confirmed_repository(db: Session) -> NotificationDataConfirmedRepository:
    """データ受信済み状態リポジトリを取得"""
    return NotificationDataConfirmedRepository(db)