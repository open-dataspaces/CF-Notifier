"""
サービス層（ビジネスロジック層）

3層アーキテクチャにおけるService層の実装
- ビジネスロジックの実装
- トランザクション管理（commit/rollback）
- 複数のRepository操作の調整
- ログ機能統合
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import uuid

# ログ設定のインポート
from app.core.logging import get_logger, log_execution_time
from app.core.custom_exceptions import RecordNotFoundError, OptimisticLockError
from app.utils.helpers import to_naive_utc
logger = get_logger(__name__)


# モデルのインポート
from app.models.notifications_model import (
    NotificationTargetList,
    NotificationType,
    Notification,
    NotificationConfirmed,
    NotificationDataConfirmed,
    NotificationStatus,
    ConfirmationStatus
)

# リポジトリのインポート
from app.repositories.notification_targets_repository import (
    NotificationTargetListRepository
)

from app.repositories.notifications_repository import (
    NotificationTypeRepository,
    NotificationRepository,
    NotificationConfirmedRepository,
    NotificationDataConfirmedRepository
)

from . import BaseService

# ============================================================================
# 通知種別サービス
# ============================================================================

class NotificationTypeService(BaseService):
    """通知種別のビジネスロジックを管理するサービス"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.repository = NotificationTypeRepository(db)
    
    @log_execution_time(logger, 'info')
    def create_notification_type(
        self,
        type_code: str,
        type_name: str
    ) -> NotificationType:
        """
        通知種別を作成
        
        Args:
            type_code: 通知種別コード
            type_name: 通知種別名
        
        Returns:
            作成された通知種別
        """
        try:
            # バリデーション
            if not type_code or not type_code.strip():
                raise ValueError("Type code cannot be empty")
            if not type_name or not type_name.strip():
                raise ValueError("Type name cannot be empty")
            
            # IDの生成
            # type_id = f"type_{uuid.uuid4().hex[:12]}"
            type_id = uuid.uuid4() 
            
            logger.info(
                "Creating notification type",
                extra={
                    'type_id': type_id,
                    'type_code': type_code,
                    'type_name': type_name
                }
            )
            
            notification_type = self.repository.create(
                type_id=type_id,
                type_code=type_code,
                type_name=type_name
            )
            
            self.commit()
            
            logger.info(
                "Notification type created successfully",
                extra={'type_id': type_id}
            )
            
            return notification_type
            
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except IntegrityError as e:
            self.rollback()
            logger.error("Failed to create notification type", exc_info=True)
            raise
        except Exception as e:
            self.rollback()
            logger.error("Unexpected error creating notification type", exc_info=True)
            raise
    
    def get_notification_type(self, type_id: str) -> Optional[NotificationType]:
        """通知種別を取得"""
        return self.repository.get_by_id(type_id)
    
    def get_notification_type_by_code(self, type_code: str) -> Optional[NotificationType]:
        """コードで通知種別を取得"""
        return self.repository.get_by_code(type_code)
    
    def get_all_notification_types(self) -> List[NotificationType]:
        """すべての通知種別を取得"""
        return self.repository.get_all()


# ============================================================================
# 通知サービス
# ============================================================================

class NotificationService(BaseService):
    """
    通知のビジネスロジックを管理するサービス
    
    複雑なビジネスロジックとトランザクション管理を担当
    """
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.notification_repo = NotificationRepository(db)
        self.confirmed_repo = NotificationConfirmedRepository(db)
        self.data_confirmed_repo = NotificationDataConfirmedRepository(db)
        self.target_list_repo = NotificationTargetListRepository(db)
        self.type_repo = NotificationTypeRepository(db)
    
    @log_execution_time(logger, 'info')
    def create_notification(
        self,
        owner_id: str,
        type_code: str,
        type_name: str,
        title: str,
        content: str,
        target_ids: Optional[List[str]] = None,
        target_list_ids: Optional[List[str]] = None,
        data_id: Optional[str] = None,
        initialize_confirmation: bool = True,
        commit: bool = True
    ) -> Notification:
        """
        通知を作成（確認状態も自動初期化）
        
        Args:
            owner_id: 所有者ID（APIを実行した提供者のoperator_id）
            type_code: 通知種別コード
            type_name: 通知種別名
            title: 通知タイトル
            content: 通知内容
            target_ids: 通知受信者IDリスト
            target_list_ids: 通知先リストIDのリスト（複数指定可）
            data_id: データID
            initialize_confirmation: 確認状態を初期化するか
            commit: Falseの場合はcommitしない
        
        Returns:
            作成された通知
        """
        try:
            # バリデーション
            if not owner_id or not owner_id.strip():
                raise ValueError("Owner ID (operator_id) cannot be empty")
            if not type_code or not type_code.strip():
                raise ValueError("Type code cannot be empty")
            if not type_name or not type_name.strip():
                raise ValueError("Type name cannot be empty")
            if not title or not title.strip():
                raise ValueError("Title cannot be empty")
            if not content or not content.strip():
                raise ValueError("Content cannot be empty")
            if not target_ids and not target_list_ids:
                raise ValueError("Either target_ids or target_list_ids must be specified")
            
            # 通知種別の取得または作成
            notification_type = self.type_repo.get_by_code(type_code)

            if not notification_type:
                # type_nameの一意制約チェック（異なるtype_codeで同じtype_nameが既に存在しないか）
                existing_by_name = self.type_repo.get_by_name(type_name)
                if existing_by_name:
                    raise ValueError(
                        f"type_name '{type_name}' is already used by type_code '{existing_by_name.type_code}'"
                    )

                # 通知種別が存在しない場合は新規作成
                type_id = uuid.uuid4()

                logger.info(
                    "Creating new notification type",
                    extra={
                        'type_id': type_id,
                        'type_code': type_code,
                        'type_name': type_name
                    }
                )

                notification_type = self.type_repo.create(
                    type_id=type_id,
                    type_code=type_code,
                    type_name=type_name
                )
            else:
                # type_code/type_nameの整合性チェック
                if notification_type.type_name != type_name:
                    raise ValueError(
                        f"type_code '{type_code}' is already registered with type_name '{notification_type.type_name}', "
                        f"but received type_name '{type_name}'"
                    )

                logger.debug(
                    "Using existing notification type",
                    extra={
                        'type_id': notification_type.type_id,
                        'type_code': type_code
                    }
                )
            
            # 通知先の取得
            owned_target_list_ids = []
            list_member_ids = []
            
            if target_list_ids:
                # 複数の通知先リストからメンバーを取得
                logger.info(
                    "Getting members from multiple target lists",
                    extra={
                        'target_list_ids': target_list_ids,
                        'list_count': len(target_list_ids)
                    }
                )
                
                owned_target_list_ids = self.target_list_repo.get_owned_ids(target_list_ids, owner_id)
                list_member_ids = self.target_list_repo.get_members_from_multiple_lists(owned_target_list_ids)
                
                if not list_member_ids:
                    raise ValueError(f"All target lists are empty: {target_list_ids}")
            
            # 重複を除去（target_idsとtarget_list_idsの両方が指定される場合に備えて）
            all_target_ids = list(dict.fromkeys(list(target_ids or []) + list_member_ids))
            
            # IDの生成
            notification_id = uuid.uuid4()
            
            logger.info(
                "Creating notification",
                extra={
                    'notification_id': notification_id,
                    'type_id': notification_type.type_id,
                    'type_code': type_code,
                    'title': title,
                    'target_count': len(all_target_ids),
                    'target_list_count': len(target_list_ids) if target_list_ids else 0
                }
            )
            
            # 通知の作成
            notification = self.notification_repo.create(
                notification_id=notification_id,
                type_id=notification_type.type_id,
                owner_id=owner_id,
                title=title,
                content=content,
                target_ids=target_ids,
                target_list_ids=owned_target_list_ids,
                status='enabled',
                data_id=data_id
            )
            
            # 確認状態の初期化
            if initialize_confirmation:
                for target_id in all_target_ids:
                    self.confirmed_repo.create_or_update(
                        notification_id=notification_id,
                        target_id=target_id,
                        status='unconfirmed'
                    )
            
            # トランザクションコミット
            if commit:
                self.commit()
            
            logger.info(
                "Notification created successfully with confirmations",
                extra={
                    'notification_id': notification_id,
                    'type_code': type_code,
                    'confirmation_count': len(all_target_ids)
                }
            )
            

            response = {
                "notification_id": notification.notification_id,
                "type_code": type_code,
                "type_name": type_name,
                "title": title,
                "content": content,
                "target_ids": target_ids or [],
                "target_list_ids": owned_target_list_ids,
                "data_id": data_id
            }
            return response
            
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to create notification", exc_info=True)
            raise
    
    @log_execution_time(logger, 'info')
    def get_notification(
        self,
        notification_id: str,
        include_relations: bool = False
    ) -> Optional[Notification]:
        """
        通知を取得
        
        Args:
            notification_id: 通知ID
            include_relations: リレーション情報も取得するか
        
        Returns:
            通知
        """
        return self.notification_repo.get_by_id(notification_id, include_relations)

    @log_execution_time(logger, 'info')
    def get_notification_for_operator(
        self,
        notification_id: str,
        operator_id: Optional[str]
    ) -> Optional[Tuple[Notification, bool]]:
        """
        通知を取得（通知の所有者または受信者のみ）

        Args:
            notification_id: 通知ID
            operator_id: APIを実行したoperator_id

        Returns:
            (通知, 所有者かどうか)。存在しない場合、所有者でも受信者でもない場合はNone
        """
        if not operator_id:
            return None

        notification = self.notification_repo.get_by_id(notification_id, include_relations=True)
        if notification is None:
            return None

        if notification.owner_id == operator_id:
            return notification, True

        if any(c.target_id == operator_id for c in notification.confirmations):
            return notification, False

        return None
    
    @log_execution_time(logger, 'info')
    def get_user_notifications(
        self,
        user_id: str,
        status: Optional[NotificationStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Notification]:
        """
        ユーザーへの通知を取得
        
        Args:
            user_id: ユーザーID
            status: フィルタするステータス
            skip: スキップする件数
            limit: 取得する最大件数
        
        Returns:
            通知のリスト
        """
        return self.notification_repo.get_by_target_id(user_id, status, skip, limit)
    
    @log_execution_time(logger, 'info')
    def get_unread_notifications(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        ユーザーの未読通知を取得
        
        Args:
            user_id: ユーザーID
            skip: スキップする件数
            limit: 取得する最大件数
        
        Returns:
            通知と確認状態の辞書リスト
        """
        notifications = self.notification_repo.get_by_target_id(
            user_id,
            'enabled',
            skip,
            limit
        )
        
        result = []
        for notification in notifications:
            confirmation = self.confirmed_repo.get(notification.notification_id, user_id)
            if not confirmation or confirmation.status == 'unconfirmed':
                result.append({
                    'notification': notification,
                    'is_read': False,
                    'confirmation_status': confirmation.status if confirmation else None
                })
        
        return result
        
    @log_execution_time(logger, 'info')
    def update_notification(
        self,
        notification_id: str,
        owner_id: Optional[str],
        expected_updated_at: datetime,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[NotificationStatus] = None,
        commit: bool = True
    ) -> Optional[Notification]:
        """
        通知を更新
        
        Args:
            notification_id: 通知ID
            owner_id: 所有者ID（APIを実行したoperator_id）
            expected_updated_at: クライアントが取得時に保持していた更新日時
            title: 新しいタイトル
            content: 新しい内容
            status: 新しいステータス
            commit: Falseの場合はcommitしない
        
        Returns:
            更新された通知
        """
        try:
            # バリデーション
            if title is not None and (not title or not title.strip()):
                raise ValueError("Title cannot be empty")
            if content is not None and (not content or not content.strip()):
                raise ValueError("Content cannot be empty")
            
            logger.info(
                "Updating notification",
                extra={'notification_id': notification_id}
            )
            
            expected_updated_at = to_naive_utc(expected_updated_at)
            notification = self.notification_repo.update(
                notification_id,
                owner_id,
                expected_updated_at,
                title,
                content,
                status
            )
            
            if notification is None:
                current = self.notification_repo.get_owned_by(notification_id, owner_id)
                if current is None:
                    raise RecordNotFoundError("Notification", notification_id)
                raise OptimisticLockError(
                    f"Notification({notification_id})",
                    expected_updated_at.isoformat(),
                    current.updated_at.isoformat()
                )
            
            if commit:
                self.commit()
            logger.info(
                "Notification updated successfully",
                extra={'notification_id': notification_id}
            )
            
            return notification
            
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except (RecordNotFoundError, OptimisticLockError):
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to update notification", exc_info=True)
            raise
    
    @log_execution_time(logger, 'info')
    def delete_notification(self, notification_id: str, owner_id: Optional[str], commit: bool = True) -> bool:
        """
        通知を削除（論理削除）
        
        Args:
            notification_id: 通知ID
            owner_id: 所有者ID（APIを実行したoperator_id）
            commit: Falseの場合はcommitしない
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Deleting notification",
                extra={'notification_id': notification_id}
            )
            
            result = self.notification_repo.delete(notification_id, owner_id)
            
            if not result:
                raise RecordNotFoundError("Notification", notification_id)
            
            if commit:
                self.commit()
            logger.info(
                "Notification deleted successfully",
                extra={'notification_id': notification_id}
            )
            
            return result
            
        except RecordNotFoundError:
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to delete notification", exc_info=True)
            raise

    @log_execution_time(logger, 'info')
    def bulk_create_notifications(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        複数の通知を一括登録

        Args:
            items: create_notification の引数（commit 以外）の辞書リスト

        Returns:
            登録結果のリスト（リクエストと同じ順序）
        """
        try:
            results = []
            for index, item in enumerate(items):
                try:
                    results.append(self.create_notification(**item, commit=False))
                except ValueError as e:
                    raise ValueError(f"notifications[{index}]: {e}") from e
            self.commit()
            logger.info("Notifications bulk created", extra={'count': len(results)})
            return results
        except Exception:
            self.rollback()
            raise

    @log_execution_time(logger, 'info')
    def bulk_update_notifications(self, items: List[Dict[str, Any]]) -> List[Notification]:
        """
        複数の通知を一括更新

        Args:
            items: update_notification の引数（commit 以外）の辞書リスト

        Returns:
            更新後の通知リスト（リクエストと同じ順序）
        """
        try:
            results = [None] * len(items)
            # notification_id の順に更新する（結果はリクエストの順序で返す）
            for index in sorted(range(len(items)), key=lambda i: items[i]['notification_id']):
                try:
                    results[index] = self.update_notification(**items[index], commit=False)
                except ValueError as e:
                    raise ValueError(f"notifications[{index}]: {e}") from e
            self.commit()
            logger.info("Notifications bulk updated", extra={'count': len(results)})
            return results
        except Exception:
            self.rollback()
            raise

    @log_execution_time(logger, 'info')
    def bulk_delete_notifications(self, notification_ids: List[str], owner_id: Optional[str]) -> int:
        """
        複数の通知を一括削除（論理削除）

        Args:
            notification_ids: 通知IDのリスト
            owner_id: 所有者ID（APIを実行したoperator_id）

        Returns:
            削除件数
        """
        try:
            # notification_id の順に削除する
            for notification_id in sorted(notification_ids):
                self.delete_notification(notification_id, owner_id, commit=False)
            self.commit()
            logger.info("Notifications bulk deleted", extra={'count': len(notification_ids)})
            return len(notification_ids)
        except Exception:
            self.rollback()
            raise

    @log_execution_time(logger, 'info')
    def mark_notification_as_read(
        self,
        notification_id: str,
        user_id: str
    ) -> NotificationConfirmed:
        """
        通知を既読にする
        
        Args:
            notification_id: 通知ID
            user_id: ユーザーID
        
        Returns:
            更新された確認状態
        """
        try:
            logger.info(
                "Marking notification as read",
                extra={
                    'notification_id': notification_id,
                    'user_id': user_id
                }
            )
            
            # Check if notification exists
            notification = self.notification_repo.get_by_id(notification_id)
            if notification is None:
                raise RecordNotFoundError("Notification", notification_id)

            if self.confirmed_repo.get(notification_id, user_id) is None:
                raise RecordNotFoundError("Notification", notification_id)
            
            confirmation = self.confirmed_repo.create_or_update(
                notification_id=notification_id,
                target_id=user_id,
                status='confirmed'
            )
            
            self.commit()
            
            logger.info(
                "Notification marked as read",
                extra={
                    'notification_id': notification_id,
                    'user_id': user_id
                }
            )
            
            return confirmation
            
        except RecordNotFoundError:
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to mark notification as read", exc_info=True)
            raise


    @log_execution_time(logger, 'info')
    def mark_data_as_received(
        self,
        notification_id: str,
        user_id: str,
        data_id: Optional[str] = None
    ) -> NotificationDataConfirmed:
        """
        データ受領状態を更新（受領済みにする）

        Args:
            notification_id: 通知ID
            user_id: ユーザーID
            data_id: データID（ログ出力用）

        Returns:
            更新されたデータ受領状態
        """
        try:
            logger.info(
                "Marking data as received",
                extra={
                    'notification_id': notification_id,
                    'user_id': user_id,
                    'data_id': data_id
                }
            )

            # Check if notification exists
            notification = self.notification_repo.get_by_id(notification_id)
            if notification is None:
                raise RecordNotFoundError("Notification", notification_id)

            if self.confirmed_repo.get(notification_id, user_id) is None:
                raise RecordNotFoundError("Notification", notification_id)

            # データ受領状態を作成または更新
            data_confirmation = self.data_confirmed_repo.create_or_update(
                notification_id=notification_id,
                target_id=user_id,
                status='confirmed'
            )

            # トランザクションコミット
            self.commit()

            logger.info(
                "Data marked as received",
                extra={
                    'notification_id': notification_id,
                    'user_id': user_id,
                    'data_id': data_id
                }
            )

            return data_confirmation

        except RecordNotFoundError:
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to mark data as received", extra={'data_id': data_id}, exc_info=True)
            raise


# ============================================================================
# ファクトリー関数
# ============================================================================

def get_notification_type_service(db: Session) -> NotificationTypeService:
    """通知種別サービスを取得"""
    return NotificationTypeService(db)


def get_notification_service(db: Session) -> NotificationService:
    """通知サービスを取得"""
    return NotificationService(db)
