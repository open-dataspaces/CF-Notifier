"""条件付きリクエスト（ETag / Last-Modified）ミドルウェア"""
import hashlib
from email.utils import parsedate_to_datetime
from typing import Callable, Awaitable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


class ConditionalRequestMiddleware(BaseHTTPMiddleware):
    """GETの200応答にETagを付与し、条件付きリクエストの条件に一致する場合は304を返す"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        if (
            request.method != "GET"
            or response.status_code != 200
            or not request.url.path.startswith(settings.API_V1_PREFIX)
        ):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = f'W/"{hashlib.sha256(body).hexdigest()}"'

        if _is_not_modified(request, etag, response.headers.get("last-modified")):
            not_modified = Response(status_code=304)
            not_modified.raw_headers = [
                (k, v) for k, v in response.raw_headers
                if k not in (b"content-length", b"content-type")
            ]
            not_modified.headers["ETag"] = etag
            return not_modified

        new_response = Response(content=body, status_code=response.status_code)
        new_response.raw_headers = list(response.raw_headers)
        new_response.headers["ETag"] = etag
        return new_response


def _is_not_modified(request: Request, etag: str, last_modified: Optional[str]) -> bool:
    """条件付きリクエストの条件に一致し、304 を返すべきか判定する（RFC 9110 13.1.2, 13.1.3）"""
    if_none_match = request.headers.get("if-none-match")
    if if_none_match is not None:
        # If-None-Match は弱い比較（W/ を無視）で判定し、If-Modified-Since より優先する
        if if_none_match.strip() == "*":
            return True
        candidates = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
        return etag.removeprefix("W/") in candidates

    if_modified_since = request.headers.get("if-modified-since")
    if if_modified_since and last_modified:
        try:
            return parsedate_to_datetime(last_modified) <= parsedate_to_datetime(if_modified_since)
        except (TypeError, ValueError):
            # 日付の形式が不正な場合は条件を無視する
            return False

    return False
