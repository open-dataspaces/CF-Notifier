"""Notifications Endpoints"""
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.custom_exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    OptimisticLockError,
    ResourceConflictError,
    DatabaseError,
)
from app.core.logging import get_logger, set_request_id
from app.core.security import verify_access_token, verify_request_headers
from app.core.security import require_permission
from app.db.session import get_db
from app.schemas.common import ErrorResponse
from app.schemas.notifications_schema import (
    NotificationCreate,
    NotificationCreateResponse,
    Notification,
    NotificationUpdate,
    NotificationBulkCreateRequest,
    NotificationBulkCreateResponse,
    NotificationBulkUpdateRequest,
    NotificationBulkUpdateResponse,
    NotificationBulkDeleteRequest,
    SelfNotificationListResponse,
    DataUpdateSuccessResponse,
    NotifUpdateSuccessResponse,
)
from app.utils.helpers import to_http_date
from app.services.notifications_service import get_notification_service

logger = get_logger(__name__)

router = APIRouter()

# ========================================
# 通知関連エンドポイント
# ========================================

@router.post(
    "/notifications",
    response_model=NotificationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="通知登録API",
    description="通知内容を新規登録します。",
    responses={
        status.HTTP_201_CREATED: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def create_notification(
    request: NotificationCreate,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:post")),
    db: Session = Depends(get_db),
) -> NotificationCreateResponse:
    """
    通知を作成

    - **type_code**: 通知種別コード（必須）例: "INFO", "WARNING", "ERROR"
    - **type_name**: 通知種別名（必須）例: "情報通知", "警告通知", "エラー通知"
    - **title**: 通知タイトル（必須）
    - **content**: 通知内容（必須）
    - **target_ids**: 通知受信者IDリスト（target_list_idsと排他）
    - **target_list_ids**: 通知先リストIDのリスト（複数指定可、target_idsと排他）
    - **data_id**: データID（オプション）
    """
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received create notification request",
        endpoint="/api/v1/notifications",
        method="POST",
        type_code=request.type_code,
        title=request.title,
        target_count=len(request.target_ids) if request.target_ids else 0
    )

    try:
        service = get_notification_service(db)
        result = service.create_notification(
            type_code=request.type_code,
            type_name=request.type_name,
            title=request.title,
            content=request.content,
            target_ids=request.target_ids,
            target_list_ids=request.target_list_ids,
            data_id=request.data_id,
            initialize_confirmation=True
        )

        logger.info(
            "Notification created successfully",
            notification_id=str(result.get('notification_id') if isinstance(result, dict) else result.notification_id),
            status_code=201
        )

        return result

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except (DuplicateRecordError, ResourceConflictError) as e:
        logger.warning(
            "Request failed - resource conflict",
            error=str(e),
            status_code=409
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ========================================
# 通知一括処理エンドポイント
# ========================================

@router.post(
    "/notifications/bulk",
    response_model=NotificationBulkCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="通知一括登録API",
    description="複数の通知を一括で登録します。1件でも失敗した場合は全件を登録しません。",
    responses={
        status.HTTP_201_CREATED: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def bulk_create_notifications(
    request: NotificationBulkCreateRequest,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:post")),
    db: Session = Depends(get_db),
) -> NotificationBulkCreateResponse:
    """
    通知を一括登録

    - **notifications**: 登録する通知のリスト（各要素は通知登録APIのリクエストと同じ形式）
    """
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received bulk create notifications request",
        endpoint="/api/v1/notifications/bulk",
        method="POST",
        count=len(request.notifications)
    )

    try:
        service = get_notification_service(db)
        results = service.bulk_create_notifications([
            {
                "type_code": n.type_code,
                "type_name": n.type_name,
                "title": n.title,
                "content": n.content,
                "target_ids": n.target_ids,
                "target_list_ids": n.target_list_ids,
                "data_id": n.data_id,
                "initialize_confirmation": True,
            }
            for n in request.notifications
        ])

        logger.info(
            "Notifications bulk created successfully",
            count=len(results),
            status_code=201
        )

        return NotificationBulkCreateResponse(notifications=results)

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except (DuplicateRecordError, ResourceConflictError) as e:
        logger.warning(
            "Request failed - resource conflict",
            error=str(e),
            status_code=409
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put(
    "/notifications/bulk",
    response_model=NotificationBulkUpdateResponse,
    summary="通知一括更新API",
    description="複数の通知を一括で更新します。1件でも失敗した場合は全件を更新しません。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー（updated_at が最新でない場合を含む）", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def bulk_update_notifications(
    request: NotificationBulkUpdateRequest,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:put")),
    db: Session = Depends(get_db),
) -> NotificationBulkUpdateResponse:
    """
    通知を一括更新

    - **notifications**: 更新する通知のリスト（各要素は通知更新APIのリクエストと同じ形式。notification_id で対象を指定）
    """
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received bulk update notifications request",
        endpoint="/api/v1/notifications/bulk",
        method="PUT",
        count=len(request.notifications)
    )

    try:
        service = get_notification_service(db)
        results = service.bulk_update_notifications([
            {
                "notification_id": n.notification_id,
                "expected_updated_at": n.updated_at,
                "title": n.title,
                "content": n.content,
                "status": n.status.value if n.status else None,
            }
            for n in request.notifications
        ])

        logger.info(
            "Notifications bulk updated successfully",
            count=len(results),
            status_code=200
        )

        return NotificationBulkUpdateResponse(notifications=results)

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except (OptimisticLockError, ResourceConflictError) as e:
        logger.warning(
            "Request failed - resource conflict",
            error=str(e),
            status_code=409
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/notifications/bulk-delete",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="通知一括削除API",
    description="複数の通知を一括で削除します。1件でも失敗した場合は全件を削除しません。",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def bulk_delete_notifications(
    request: NotificationBulkDeleteRequest,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:delete")),
    db: Session = Depends(get_db),
):
    """
    通知を一括削除

    - **notification_ids**: 削除する通知IDのリスト
    """
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received bulk delete notifications request",
        endpoint="/api/v1/notifications/bulk-delete",
        method="POST",
        count=len(request.notification_ids)
    )

    try:
        service = get_notification_service(db)
        service.bulk_delete_notifications(request.notification_ids)

        logger.info(
            "Notifications bulk deleted successfully",
            count=len(request.notification_ids),
            status_code=204
        )

        return None

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get(
    "/notifications",
    response_model=SelfNotificationListResponse,
    summary="通知一覧取得API",
    description="自身宛の通知一覧を取得します。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def list_notifications(
    response: Response,
    notification_status: Optional[str] = Query(None, alias="status", description="通知ステータスでフィルタ"),
    skip: int = Query(0, ge=0, description="スキップ件数"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数上限"),
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:get")),
    db: Session = Depends(get_db),
) -> SelfNotificationListResponse:
    """自身宛の通知一覧を取得"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    user_id = credential.get("operator_id")

    logger.info(
        "Received list notifications request",
        endpoint="/api/v1/notifications",
        method="GET",
        user_id=user_id,
        status_filter=notification_status,
        skip=skip,
        limit=limit
    )

    try:
        service = get_notification_service(db)
        notifications = service.get_user_notifications(
            user_id=user_id,
            status=notification_status,
            skip=skip,
            limit=limit
        )

        if notifications is None:
            notifications = []

        logger.info(
            "Notifications retrieved successfully",
            total=len(notifications) if isinstance(notifications, list) else 0,
            status_code=200
        )

        # SelfNotificationListResponseに変換
        return SelfNotificationListResponse(notifications=notifications)

    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get(
    "/notifications/{notification_id}",
    response_model=Notification,
    summary="通知詳細取得API",
    description="指定した通知の詳細を取得します。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def get_notification(
    notification_id: UUID,
    response: Response,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:get-id")),
    db: Session = Depends(get_db),
) -> Notification:
    """通知詳細を取得"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received get notification request",
        endpoint=f"/api/v1/notifications/{notification_id}",
        method="GET",
        notification_id=str(notification_id)
    )

    try:
        service = get_notification_service(db)
        result = service.get_notification(
            notification_id=notification_id,
            include_relations=True
        )

        if result is None:
            logger.warning(
                "Request failed - resource not found",
                notification_id=str(notification_id),
                status_code=404
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification not found: {notification_id}"
            )

        response.headers["Last-Modified"] = to_http_date(max(
            [result.updated_at]
            + [c.updated_at for c in result.confirmations]
            + [c.updated_at for c in result.data_confirmations]
        ))

        logger.info(
            "Notification retrieved successfully",
            notification_id=str(notification_id),
            status_code=200
        )

        return result

    except HTTPException:
        raise
    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            notification_id=str(notification_id),
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            notification_id=str(notification_id),
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            notification_id=str(notification_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put(
    "/notifications/{notification_id}",
    response_model=Notification,
    summary="通知更新API",
    description="指定した通知内容を更新します。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー（updated_at が最新でない場合を含む）", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def update_notification(
    notification_id: UUID,
    request: NotificationUpdate,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:put")),
    db: Session = Depends(get_db),
) -> Notification:
    """通知を更新"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received update notification request",
        endpoint=f"/api/v1/notifications/{notification_id}",
        method="PUT",
        notification_id=str(notification_id)
    )

    try:
        service = get_notification_service(db)
        result = service.update_notification(
            notification_id=notification_id,
            expected_updated_at=request.updated_at,
            title=request.title,
            content=request.content,
            status=request.status.value if request.status else None
        )

        logger.info(
            "Notification updated successfully",
            notification_id=str(notification_id),
            status_code=200
        )

        return result

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            notification_id=str(notification_id),
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except (OptimisticLockError, ResourceConflictError) as e:
        logger.warning(
            "Request failed - resource conflict",
            notification_id=str(notification_id),
            error=str(e),
            status_code=409
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            notification_id=str(notification_id),
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            notification_id=str(notification_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.delete(
    "/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="通知削除API",
    description="指定した通知を削除します。",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def delete_notification(
    notification_id: UUID,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:delete")),
    db: Session = Depends(get_db),
):
    """通知を削除"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received delete notification request",
        endpoint=f"/api/v1/notifications/{notification_id}",
        method="DELETE",
        notification_id=str(notification_id)
    )

    try:
        service = get_notification_service(db)
        service.delete_notification(notification_id=notification_id)

        logger.info(
            "Notification deleted successfully",
            notification_id=str(notification_id),
            status_code=204
        )

        return None

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            notification_id=str(notification_id),
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            notification_id=str(notification_id),
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            notification_id=str(notification_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ========================================
# 通知確認状態更新エンドポイント
# ========================================

@router.put(
    "/notifications/{notification_id}/receive",
    response_model=NotifUpdateSuccessResponse,
    summary="通知確認状態更新API",
    description="通知の確認状態を更新します（通知確認時に実行）。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def confirm_notification(
    notification_id: UUID,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:receive-put")),
    db: Session = Depends(get_db),
) -> NotifUpdateSuccessResponse:
    """通知確認状態を更新"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    # 認証情報からオペレータIDを取得
    user_id = credential.get("operator_id")

    logger.info(
        "Received confirm notification request",
        endpoint=f"/api/v1/notifications/{notification_id}/receive",
        method="PUT",
        notification_id=str(notification_id),
        user_id=user_id
    )

    try:
        service = get_notification_service(db)
        confirmation = service.mark_notification_as_read(
            notification_id=notification_id,
            user_id=user_id
        )

        logger.info(
            "Notification confirmed successfully",
            notification_id=str(notification_id),
            user_id=user_id,
            status_code=200
        )

        return NotifUpdateSuccessResponse(updated_at=confirmation.updated_at)

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            notification_id=str(notification_id),
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            notification_id=str(notification_id),
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            notification_id=str(notification_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# ========================================
# データ受領状態更新エンドポイント
# ========================================

@router.put(
    "/notifications/{notification_id}/data/{data_id}/receive",
    response_model=DataUpdateSuccessResponse,
    summary="データ受領状態更新API",
    description="データの受領状態を更新します（データ受領時に実行）。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def receive_notification_data(
    notification_id: UUID,
    data_id: UUID,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notifications:data-receive-put")),
    db: Session = Depends(get_db),
) -> DataUpdateSuccessResponse:
    """データ受領状態を更新"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    # 認証情報からオペレータIDを取得
    user_id = credential.get("operator_id")

    logger.info(
        "Received data receive request",
        endpoint=f"/api/v1/notifications/{notification_id}/data/{data_id}/receive",
        method="PUT",
        notification_id=str(notification_id),
        data_id=str(data_id),
        user_id=user_id
    )

    try:
        service = get_notification_service(db)
        confirmation = service.mark_data_as_received(
            notification_id=str(notification_id),
            user_id=user_id,
            data_id=str(data_id)
        )

        logger.info(
            "Data received successfully",
            notification_id=str(notification_id),
            data_id=str(data_id),
            user_id=user_id,
            status_code=200
        )

        return DataUpdateSuccessResponse(updated_at=confirmation.updated_at)

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            notification_id=str(notification_id),
            data_id=str(data_id),
            error=str(e),
            status_code=404
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DatabaseError as e:
        logger.error(
            "Request failed - database error",
            notification_id=str(notification_id),
            data_id=str(data_id),
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred"
        )
    except ValueError as e:
        logger.warning(
            "Request failed - validation error",
            error=str(e),
            status_code=400
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Request failed - unexpected error",
            notification_id=str(notification_id),
            data_id=str(data_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
