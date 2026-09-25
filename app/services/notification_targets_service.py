"""
サービス層（ビジネスロジック層）

3層アーキテクチャにおけるService層の実装
- ビジネスロジックの実装
- トランザクション管理（commit/rollback）
- 複数のRepository操作の調整
- ログ機能統合
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import uuid

# ログ設定のインポート
from app.core.logging import get_logger, log_execution_time
from app.core.custom_exceptions import RecordNotFoundError, OptimisticLockError
from app.utils.helpers import to_naive_utc
logger = get_logger(__name__)

# スキーマのインポート
from app.schemas.notification_targets_schema import (
    NotificationTargetCreateRequest,
    NotificationTargetUpdateRequest,
    NotificationTargetResponse,
    NotificationTargetListResponse
)

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
    NotificationTargetListRepository,
)

from . import BaseService

# ============================================================================
# 通知先リストサービス
# ============================================================================

class NotificationTargetListService(BaseService):
    """
    通知先リストのビジネスロジックを管理するサービス
    
    トランザクション管理とビジネスルールの実装
    """
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.repository = NotificationTargetListRepository(db)
    
    @log_execution_time(logger, 'info')
    def create_target_list(
        self,
        name: str,
        owner_id: str,
        target_ids: Optional[List[str]] = None
    ) -> NotificationTargetList:
        """
        通知先リストを作成
        
        Args:
            name: 通知先リスト名称
            owner_id: リスト所有者ID
            target_ids: 通知受信者IDのリスト
        
        Returns:
            作成された通知先リスト
        
        Raises:
            ValueError: バリデーションエラー
            IntegrityError: 一意制約違反
        """
        try:
            # バリデーション
            if not name or not name.strip():
                raise ValueError("List name cannot be empty")
            
            if not owner_id or not owner_id.strip():
                raise ValueError("Owner ID cannot be empty")
            
            # IDの生成
            target_list_id = f"{uuid.uuid4()}"
            
            logger.info(
                "Creating target list",
                extra={
                    'target_list_id': target_list_id,
                    'list_name': name,
                    'owner_id': owner_id,
                    'member_count': len(target_ids) if target_ids else 0,
                    'target_ids': target_ids
                }
            )
            
            # Repository層でデータ作成
            target_list = self.repository.create(
                target_list_id=target_list_id,
                name=name,
                owner_id=owner_id,
                target_ids=target_ids
            )
            
            # トランザクションコミット
            self.commit()
            
            logger.info(
                "Target list created successfully",
                extra={'target_list_id': target_list_id}
            )

            target_list_dict = {
                'target_list_id': target_list.target_list_id,
                'name': target_list.name,
                'owner_id': target_list.owner_id,
                
                'created_at': target_list.created_at.isoformat() if target_list.created_at else None,
                'updated_at': target_list.updated_at.isoformat() if target_list.updated_at else None,
                'target_ids': target_ids
            }
            
            logger.info(
                "Target list created successfully and details are logged",
                target_list_id=target_list_id,
                # 辞書としてログに出力
                target_list_details=target_list_dict 
            )

            # データ取得して返却
            return target_list_dict
            
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except IntegrityError as e:
            self.rollback()
            logger.error("Failed to create target list", exc_info=True)
            raise
        except Exception as e:
            self.rollback()
            logger.error("Unexpected error creating target list", exc_info=True)
            raise
    @log_execution_time(logger, 'info')
    def get_all_target_list(
        self,
        skip: int = 0,
        limit: int = 1000
    ) -> List[dict]:
        """
        全ての通知先リストを取得

        Args:
            skip: スキップする件数
            limit: 取得する最大件数

        Returns:
            通知先リストのリスト
        """
        target_lists = self.repository.get_all_list(skip, limit)

        return [
            {
                "target_list_id": str(tl.target_list_id),
                "name": tl.name,
                "owner_id": tl.owner_id,
                "updated_at": tl.updated_at.isoformat(),
                "target_ids": [m.target_id for m in tl.target_ids] if tl.target_ids else []
            }
            for tl in target_lists
        ]

    @log_execution_time(logger, 'info')
    def get_target_list(
        self,
        target_list_id: str,
        include_members: bool = False
    ) -> Optional[NotificationTargetList]:
        """
        通知先リストを取得
        
        Args:
            target_list_id: 通知先リストID
            include_members: メンバー情報も取得するか
        
        Returns:
            通知先リスト
        """
        target_list = self.repository.get_by_id(target_list_id, include_members)

        if target_list == None:
            return None
        
        response = {
            "target_list_id": str(target_list.target_list_id),
            "name": target_list.name,
            "owner_id": target_list.owner_id,
            "created_at": target_list.created_at.isoformat(),
            "updated_at": target_list.updated_at.isoformat(),
            "target_ids": [m.target_id for m in target_list.target_ids] or []
        }
        return response
    
    @log_execution_time(logger, 'info')
    def get_user_target_lists(
        self,
        owner_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """
        ユーザーの通知先リストを取得

        Args:
            owner_id: リスト所有者ID
            skip: スキップする件数
            limit: 取得する最大件数

        Returns:
            通知先リストのリスト
        """
        target_lists = self.repository.get_by_owner(owner_id, skip, limit)

        return [
            {
                "target_list_id": str(tl.target_list_id),
                "name": tl.name,
                "owner_id": tl.owner_id,
                "updated_at": tl.updated_at.isoformat(),
                "target_ids": [m.target_id for m in tl.target_ids] if tl.target_ids else []
            }
            for tl in target_lists
        ]
    
    @log_execution_time(logger, 'info')
    def update_target_list(
        self,
        target_list_id: str,
        expected_updated_at: datetime,
        name: Optional[str] = None,
        owner_id: Optional[str] = None,
        target_ids: Optional[List[str]] = None
    ) -> Optional[NotificationTargetList]:
        """
        通知先リストを更新

        Args:
            target_list_id: 通知先リストID
            expected_updated_at: クライアントが取得時に保持していた更新日時
            name: 新しいリスト名称
            owner_id: 新しい所有者ID
            target_ids: 新しい通知受信者IDリスト

        Returns:
            更新された通知先リスト
        """
        try:
            # バリデーション
            if name is not None and (not name or not name.strip()):
                raise ValueError("List name cannot be empty")

            if owner_id is not None and (not owner_id or not owner_id.strip()):
                raise ValueError("Owner ID cannot be empty")

            logger.info(
                "Updating target list",
                extra={'target_list_id': target_list_id}
            )

            expected_updated_at = to_naive_utc(expected_updated_at)
            target_list = self.repository.update(
                target_list_id,
                expected_updated_at,
                name=name,
                owner_id=owner_id,
                target_ids=target_ids
            )

            if target_list is None:
                current = self.repository.get_by_id(target_list_id)
                if current is None:
                    raise RecordNotFoundError("NotificationTargetList", target_list_id)
                raise OptimisticLockError(
                    f"NotificationTargetList({target_list_id})",
                    expected_updated_at.isoformat(),
                    current.updated_at.isoformat()
                )

            self.commit()
            logger.info(
                "Target list updated successfully",
                extra={'target_list_id': target_list_id}
            )

            response = {
                "target_list_id": str(target_list.target_list_id),
                "name": target_list.name,
                "owner_id": target_list.owner_id,
                "created_at": target_list.created_at.isoformat(),
                "updated_at": target_list.updated_at.isoformat(),
                "target_ids": [m.target_id for m in target_list.target_ids] or []
            }
            return response

        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except (RecordNotFoundError, OptimisticLockError):
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to update target list", exc_info=True)
            raise
    
    @log_execution_time(logger, 'info')
    def delete_target_list(self, target_list_id: str) -> bool:
        """
        通知先リストを削除
        
        Args:
            target_list_id: 通知先リストID
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Deleting target list",
                extra={'target_list_id': target_list_id}
            )
            
            result = self.repository.delete(target_list_id)
            
            if not result:
                raise RecordNotFoundError("NotificationTargetList", target_list_id)
            
            self.commit()
            logger.info(
                "Target list deleted successfully",
                extra={'target_list_id': target_list_id}
            )
            
            return result
            
        except RecordNotFoundError:
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to delete target list", exc_info=True)
            raise
    
    @log_execution_time(logger, 'info')
    def add_member_to_list(
        self,
        target_list_id: str,
        target_id: str
    ) -> bool:
        """
        通知先リストにメンバーを追加
        
        Args:
            target_list_id: 通知先リストID
            target_id: 追加する通知受信者ID
        
        Returns:
            追加成功時True
        """
        try:
            # バリデーション
            if not target_id or not target_id.strip():
                raise ValueError("Target ID cannot be empty")
            
            logger.info(
                "Adding member to target list",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            result = self.repository.add_member(target_list_id, target_id)
            
            if result:
                self.commit()
                logger.info("Member added successfully")
            
            return result
            
        except ValueError as e:
            logger.warning(f"Validation error: {e}")
            raise
        except Exception as e:
            self.rollback()
            logger.error("Failed to add member", exc_info=True)
            raise
    
    @log_execution_time(logger, 'info')
    def remove_member_from_list(
        self,
        target_list_id: str,
        target_id: str
    ) -> bool:
        """
        通知先リストからメンバーを削除
        
        Args:
            target_list_id: 通知先リストID
            target_id: 削除する通知受信者ID
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Removing member from target list",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            result = self.repository.remove_member(target_list_id, target_id)
            
            if result:
                self.commit()
                logger.info("Member removed successfully")
            
            return result
            
        except Exception as e:
            self.rollback()
            logger.error("Failed to remove member", exc_info=True)
            raise
    
    def get_list_members(self, target_list_id: str) -> List[str]:
        """
        通知先リストのメンバーIDリストを取得
        
        Args:
            target_list_id: 通知先リストID
        
        Returns:
            通知受信者IDのリスト
        """
        return self.repository.get_members(target_list_id)


# ============================================================================
# ファクトリー関数
# ============================================================================

def get_notification_target_list_service(db: Session) -> NotificationTargetListService:
    """通知先リストサービスを取得"""
    return NotificationTargetListService(db)

