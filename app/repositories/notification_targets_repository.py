"""
データベースリポジトリ(3層アーキテクチャ対応版)

各モデルに対するCRUD操作を提供するリポジトリパターン実装
ログ機能、エラーハンドリングを含む

重要: Repository層ではcommit/rollbackを行いません
      トランザクション管理はService層の責務です
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import (
    IntegrityError, 
    SQLAlchemyError,
    NoResultFound
)
from sqlalchemy import and_, or_, func

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
    ConfirmationStatus
)

from . import BaseRepository

# ============================================================================
# 通知先リストリポジトリ
# ============================================================================

class NotificationTargetListRepository(BaseRepository):
    """
    通知先リストの操作を管理するリポジトリ
    
    注意: このリポジトリはcommit/rollbackを行いません
         Service層でトランザクション管理を行ってください
    """
    
    @log_execution_time(logger, 'debug')
    def create(
        self,
        target_list_id: str,
        name: str,
        owner_id: str,
        target_ids: Optional[List[str]] = None
    ) -> NotificationTargetList:
        """
        通知先リストを作成(commitはService層で実施)
        
        Args:
            target_list_id: 通知先リストID
            name: 通知先リスト名称
            owner_id: リスト所有者ID
            target_ids: 通知受信者IDのリスト(オプション)
        
        Returns:
            作成された通知先リスト(未commit)
        
        Raises:
            SQLAlchemyError: データベースエラー時
        """
        try:
            logger.info(
                "Creating notification target list",
                extra={
                    'target_list_id': target_list_id,
                    'list_name': name,
                    'owner_id': owner_id,
                    'target_count': len(target_ids) if target_ids else 0
                }
            )
            
            # 通知先リストの作成
            target_list = NotificationTargetList(
                target_list_id=target_list_id,
                name=name,
                owner_id=owner_id
            )
            
            self.db.add(target_list)
            
            # 通知受信者を追加
            if target_ids:
                for target_id in target_ids:
                    target_member = TargetIds(
                        target_list_id=target_list_id,
                        target_id=target_id
                    )
                    self.db.add(target_member)
            
            # flush()でIDを取得(commitはしない)
            self.db.flush()
            
            logger.info(
                "Notification target list created (not committed)",
                extra={'target_list': target_list}
            )
            
            return target_list
            
        except SQLAlchemyError as e:
            self._log_error(e, 'create_notification_target_list')
            raise

    @log_execution_time(logger, 'debug')
    def get_members(self, target_list_id: str) -> List[str]:
        """
        通知先リストのメンバーIDリストを取得（単一リスト）
        
        Args:
            target_list_id: 通知先リストID
        
        Returns:
            通知受信者IDのリスト
        """
        try:
            logger.debug(
                "Getting members of notification target list",
                extra={'target_list_id': target_list_id}
            )
            
            members = self.db.query(TargetIds.target_id).filter(
                TargetIds.target_list_id == target_list_id
            ).all()
            
            target_ids = [member[0] for member in members]
            
            logger.debug(
                "Retrieved target list members",
                extra={
                    'target_list_id': target_list_id,
                    'count': len(target_ids)
                }
            )
            
            return target_ids
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_target_list_members')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_members_from_multiple_lists(self, target_list_ids: List[str]) -> List[str]:
        """
        複数の通知先リストのメンバーIDリストを取得（重複除去）
        
        Args:
            target_list_ids: 通知先リストIDのリスト
        
        Returns:
            通知受信者IDのリスト（重複なし）
        """
        try:
            logger.debug(
                "Getting members from multiple notification target lists",
                extra={
                    'target_list_ids': target_list_ids,
                    'list_count': len(target_list_ids)
                }
            )
            
            if not target_list_ids:
                return []
            
            # IN句を使って複数のリストから一度にメンバーを取得
            members = self.db.query(TargetIds.target_id).filter(
                TargetIds.target_list_id.in_(target_list_ids)
            ).distinct().all()  # ✅ distinct()で重複除去
            
            target_ids = [member[0] for member in members]
            
            logger.debug(
                "Retrieved target list members from multiple lists",
                extra={
                    'target_list_ids': target_list_ids,
                    'total_count': len(target_ids)
                }
            )
            
            return target_ids
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_members_from_multiple_lists')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_id(
        self,
        target_list_id: str,
        include_members: bool = True
    ) -> Optional[NotificationTargetList]:
        """
        IDで通知先リストを取得
        
        Args:
            target_list_id: 通知先リストID
            include_members: メンバー情報も取得するか
        
        Returns:
            通知先リスト(存在しない場合はNone)
        """
        try:
            logger.debug(
                "Getting notification target list by ID",
                extra={'target_list_id': target_list_id}
            )
            
            query = self.db.query(NotificationTargetList)
            
            if include_members:
                query = query.options(joinedload(NotificationTargetList.target_ids))
            
            target_list = query.filter(
                NotificationTargetList.target_list_id == target_list_id
            ).first()

            if target_list:
                try:
                    members = getattr(target_list, "target_ids", None)
                    if members is None:
                        logger.info("Found target_list but target_ids is None", extra={"target_list_id": str(target_list.target_list_id)})
                    else:
                        # リスト長と先頭3件だけを表示
                        member_ids = [m.target_id for m in members]
                        logger.info(
                            "Found target_list with members",
                            extra={
                                "target_list_id": str(target_list.target_list_id),
                                "target_ids_count": len(member_ids),
                                "sample_target_ids": member_ids[:3]
                            }
                        )
                except Exception:
                    # 安全策: 何か例外が出ても repr を残す
                    logger.exception("Failed reading target_ids for logging", extra={"target_list": repr(target_list)})
            else:
                logger.info("Notification target list not found", extra={"target_list_id": target_list_id})
            
            if target_list:
                logger.info(
                    "Notification target list found",
                    extra={'target_list': target_list}
                )
            else:
                logger.info(
                    "Notification target list not found",
                    extra={'target_list_id': target_list_id}
                )
            
            return target_list
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_target_list')
            raise

    @log_execution_time(logger, 'debug')
    def get_all_list(
        self,
        skip: int = 0,
        limit: int = 1000
    ) -> List[NotificationTargetList]:
        """
        通知先リストをすべて取得
        
        Args:
            owner_id: リスト所有者ID
            skip: スキップする件数
            limit: 取得する最大件数
        
        Returns:
            通知先リストのリスト
        """
        try:
            logger.debug(
                "Getting notification target lists all",
                extra={
                    'skip': skip,
                    'limit': limit
                }
            )
            
            target_lists = self.db.query(NotificationTargetList).order_by(
                NotificationTargetList.created_at.desc()
            ).offset(skip).limit(limit).all()
            
            logger.debug(
                "Retrieved notification target lists",
                extra={
                    'count': len(target_lists)
                }
            )
            
            return target_lists
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_target_lists_by_owner')
            raise
    
    @log_execution_time(logger, 'debug')
    def get_by_owner(
        self,
        owner_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[NotificationTargetList]:
        """
        所有者IDで通知先リストを取得
        
        Args:
            owner_id: リスト所有者ID
            skip: スキップする件数
            limit: 取得する最大件数
        
        Returns:
            通知先リストのリスト
        """
        try:
            logger.debug(
                "Getting notification target lists by owner",
                extra={
                    'owner_id': owner_id,
                    'skip': skip,
                    'limit': limit
                }
            )
            
            target_lists = self.db.query(NotificationTargetList).filter(
                NotificationTargetList.owner_id == owner_id
            ).order_by(
                NotificationTargetList.created_at.desc()
            ).offset(skip).limit(limit).all()
            
            logger.debug(
                "Retrieved notification target lists",
                extra={
                    'owner_id': owner_id,
                    'count': len(target_lists)
                }
            )
            
            return target_lists
            
        except SQLAlchemyError as e:
            self._log_error(e, 'get_notification_target_lists_by_owner')
            raise
    
    @log_execution_time(logger, 'debug')
    def update(
        self,
        target_list_id: str,
        name: Optional[str] = None,
        owner_id: Optional[str] = None,
        target_ids: Optional[List[str]] = None
    ) -> Optional[NotificationTargetList]:
        """
        通知先リストを更新(commitはService層で実施)

        Args:
            target_list_id: 通知先リストID
            name: 新しいリスト名称
            owner_id: 新しい所有者ID
            target_ids: 新しい通知受信者IDリスト

        Returns:
            更新された通知先リスト(存在しない場合はNone)
        """
        try:
            logger.info(
                "Updating notification target list",
                extra={'target_list_id': target_list_id}
            )

            target_list = self.get_by_id(target_list_id)

            if not target_list:
                logger.warning(
                    "Cannot update: notification target list not found",
                    extra={'target_list_id': target_list_id}
                )
                return None

            if name is not None:
                target_list.name = name

            if owner_id is not None:
                target_list.owner_id = owner_id

            # target_idsの更新（既存を削除して新規作成）
            if target_ids is not None:
                # 既存のtarget_idsを削除
                self.db.query(TargetIds).filter(
                    TargetIds.target_list_id == target_list_id
                ).delete()

                # 新しいtarget_idsを追加
                for tid in target_ids:
                    target_member = TargetIds(
                        target_list_id=target_list_id,
                        target_id=tid
                    )
                    self.db.add(target_member)

            target_list.updated_at = datetime.utcnow()

            self.db.flush()

            # リレーションを再読み込み
            self.db.refresh(target_list)

            logger.info(
                "Notification target list updated (not committed)",
                extra={'target_list_id': target_list_id}
            )

            return target_list

        except SQLAlchemyError as e:
            self._log_error(e, 'update_notification_target_list')
            raise
    
    @log_execution_time(logger, 'debug')
    def delete(self, target_list_id: str) -> bool:
        """
        通知先リストを削除(commitはService層で実施)
        
        Args:
            target_list_id: 通知先リストID
        
        Returns:
            削除対象が存在した場合True、存在しない場合False
        """
        try:
            logger.info(
                "Deleting notification target list",
                extra={'target_list_id': target_list_id}
            )
            
            target_list = self.get_by_id(target_list_id)
            
            if not target_list:
                logger.warning(
                    "Cannot delete: notification target list not found",
                    extra={'target_list_id': target_list_id}
                )
                return False
            
            self.db.delete(target_list)
            self.db.flush()
            
            logger.info(
                "Notification target list deleted (not committed)",
                extra={'target_list_id': target_list_id}
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'delete_notification_target_list')
            raise
    
    @log_execution_time(logger, 'debug')
    def add_member(self, target_list_id: str, target_id: str) -> bool:
        """
        通知先リストにメンバーを追加(commitはService層で実施)
        
        Args:
            target_list_id: 通知先リストID
            target_id: 追加する通知受信者ID
        
        Returns:
            追加成功時True
        """
        try:
            logger.info(
                "Adding member to notification target list",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            # 既に存在するかチェック
            existing = self.db.query(TargetIds).filter(
                and_(
                    TargetIds.target_list_id == target_list_id,
                    TargetIds.target_id == target_id
                )
            ).first()
            
            if existing:
                logger.info(
                    "Member already exists in target list",
                    extra={
                        'target_list_id': target_list_id,
                        'target_id': target_id
                    }
                )
                return True
            
            member = TargetIds(
                target_list_id=target_list_id,
                target_id=target_id
            )
            
            self.db.add(member)
            self.db.flush()
            
            logger.info(
                "Member added (not committed)",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'add_member_to_target_list')
            raise
    
    @log_execution_time(logger, 'debug')
    def remove_member(self, target_list_id: str, target_id: str) -> bool:
        """
        通知先リストからメンバーを削除(commitはService層で実施)
        
        Args:
            target_list_id: 通知先リストID
            target_id: 削除する通知受信者ID
        
        Returns:
            削除成功時True
        """
        try:
            logger.info(
                "Removing member from notification target list",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            member = self.db.query(TargetIds).filter(
                and_(
                    TargetIds.target_list_id == target_list_id,
                    TargetIds.target_id == target_id
                )
            ).first()
            
            if not member:
                logger.warning(
                    "Member not found in target list",
                    extra={
                        'target_list_id': target_list_id,
                        'target_id': target_id
                    }
                )
                return False
            
            self.db.delete(member)
            self.db.flush()
            
            logger.info(
                "Member removed (not committed)",
                extra={
                    'target_list_id': target_list_id,
                    'target_id': target_id
                }
            )
            
            return True
            
        except SQLAlchemyError as e:
            self._log_error(e, 'remove_member_from_target_list')
            raise
    
# ============================================================================
# ファクトリー関数
# ============================================================================

def get_notification_target_list_repository(db: Session) -> NotificationTargetListRepository:
    """通知先リストリポジトリを取得"""
    return NotificationTargetListRepository(db)
