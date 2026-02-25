"""API V1 Router"""
from fastapi import APIRouter

from app.api.v1.endpoints import notification_targets
from app.api.v1.endpoints import notifications

api_router = APIRouter()

# 通知先リスト
api_router.include_router(notification_targets.router, tags=["通知先リスト"])
# 通知
api_router.include_router(notifications.router, tags=["通知"])
