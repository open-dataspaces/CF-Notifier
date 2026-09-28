"""Notification Targets Endpoints"""
from datetime import datetime
from typing import List
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
from app.schemas.notification_targets_schema import (
    NotificationTargetCreateRequest,
    NotificationTargetUpdateRequest,
    NotificationTargetResponse,
    NotificationTargetListResponse,
)
from app.services.notification_targets_service import get_notification_target_list_service
from app.utils.helpers import to_http_date

logger = get_logger(__name__)

router = APIRouter()

# ========================================
# 通知先リスト関連エンドポイント
# ========================================

@router.post(
    "/notification-targets",
    response_model=NotificationTargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="通知先リスト作成API",
    description="通知先リストを新規作成します。",
    responses={
        status.HTTP_201_CREATED: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"description": "リソース競合エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def create_notification_target(
    request: NotificationTargetCreateRequest,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notification-targets:post")),
    db: Session = Depends(get_db),
) -> NotificationTargetResponse:
    """通知先リストを作成"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received create notification target request",
        endpoint="/api/v1/notification-targets",
        method="POST",
        target_name=request.name,
        owner_id=request.owner_id,
        target_count=len(request.target_ids) if request.target_ids else 0
    )

    try:
        service = get_notification_target_list_service(db)
        result = service.create_target_list(
            name=request.name,
            owner_id=request.owner_id,
            target_ids=request.target_ids
        )

        logger.info(
            "Notification target created successfully",
            target_list_id=str(result.get('target_list_id') if isinstance(result, dict) else result.target_list_id),
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


@router.get(
    "/notification-targets",
    response_model=NotificationTargetListResponse,
    summary="通知先リスト一覧取得API",
    description="通知先リスト一覧を取得します。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def list_notification_targets(
    response: Response,
    skip: int = Query(0, ge=0, description="スキップ件数"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数上限"),
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notification-targets:get-all")),
    db: Session = Depends(get_db),
) -> NotificationTargetListResponse:
    """通知先リスト一覧を取得"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    owner_id = credential.get("operator_id")

    logger.info(
        "Received list notification targets request",
        endpoint="/api/v1/notification-targets",
        method="GET",
        skip=skip,
        limit=limit,
        owner_id=owner_id
    )

    try:
        service = get_notification_target_list_service(db)
        target_lists = service.get_user_target_lists(
            owner_id=owner_id,
            skip=skip,
            limit=limit
        )

        if target_lists is None:
            target_lists = []

        logger.info(
            "Notification targets retrieved successfully",
            total=len(target_lists),
            status_code=200
        )

        return NotificationTargetListResponse(notification_targets=target_lists)

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
    "/notification-targets/{target_list_id}",
    response_model=NotificationTargetResponse,
    summary="通知先リスト取得API",
    description="指定した通知先リストを取得します。",
    responses={
        status.HTTP_200_OK: {"description": "成功"},
        status.HTTP_400_BAD_REQUEST: {"description": "パラメータエラー", "model": ErrorResponse},
        status.HTTP_401_UNAUTHORIZED: {"description": "認証エラー", "model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"description": "認可エラー", "model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"description": "該当データなし", "model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "サーバエラー", "model": ErrorResponse},
    },
)
async def get_notification_target(
    target_list_id: UUID,
    response: Response,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notification-targets:get")),
    db: Session = Depends(get_db),
) -> NotificationTargetResponse:
    """通知先リストを取得"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received get notification target request",
        endpoint=f"/api/v1/notification-targets/{target_list_id}",
        method="GET",
        target_list_id=str(target_list_id)
    )

    try:
        service = get_notification_target_list_service(db)
        result = service.get_target_list(
            target_list_id=target_list_id,
            include_members=True
        )

        if result is None:
            logger.warning(
                "Request failed - resource not found",
                target_list_id=str(target_list_id),
                status_code=404
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification target list not found: {target_list_id}"
            )

        response.headers["Last-Modified"] = to_http_date(datetime.fromisoformat(result["updated_at"]))

        logger.info(
            "Notification target retrieved successfully",
            target_list_id=str(target_list_id),
            status_code=200
        )

        return result

    except HTTPException:
        raise
    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
    "/notification-targets/{target_list_id}",
    response_model=NotificationTargetResponse,
    summary="通知先リスト更新API",
    description="指定した通知先リストを更新します。",
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
async def update_notification_target(
    target_list_id: UUID,
    request: NotificationTargetUpdateRequest,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notification-targets:put")),
    db: Session = Depends(get_db),
) -> NotificationTargetResponse:
    """通知先リストを更新"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received update notification target request",
        endpoint=f"/api/v1/notification-targets/{target_list_id}",
        method="PUT",
        target_list_id=str(target_list_id),
        target_name=request.name,
        owner_id=request.owner_id,
        target_count=len(request.target_ids) if request.target_ids else 0
    )

    try:
        service = get_notification_target_list_service(db)
        result = service.update_target_list(
            target_list_id=target_list_id,
            expected_updated_at=request.updated_at,
            name=request.name,
            owner_id=request.owner_id,
            target_ids=request.target_ids
        )

        logger.info(
            "Notification target updated successfully",
            target_list_id=str(target_list_id),
            status_code=200
        )

        return result

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
    "/notification-targets/{target_list_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="通知先リスト削除API",
    description="指定した通知先リストを削除します。",
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
async def delete_notification_target(
    target_list_id: UUID,
    headers: dict = Depends(verify_request_headers),
    credential: dict = Depends(verify_access_token),
    _: None = Depends(require_permission("notification-targets:delete")),
    db: Session = Depends(get_db),
):
    """通知先リストを削除"""
    request_id = headers.get('x_tracking_id') or str(uuid4())
    set_request_id(request_id)

    logger.info(
        "Received delete notification target request",
        endpoint=f"/api/v1/notification-targets/{target_list_id}",
        method="DELETE",
        target_list_id=str(target_list_id)
    )

    try:
        service = get_notification_target_list_service(db)
        service.delete_target_list(target_list_id=target_list_id)

        logger.info(
            "Notification target deleted successfully",
            target_list_id=str(target_list_id),
            status_code=204
        )

        return None

    except RecordNotFoundError as e:
        logger.warning(
            "Request failed - resource not found",
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
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
            target_list_id=str(target_list_id),
            error_type=type(e).__name__,
            error=str(e),
            status_code=500,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
