"""Helper Functions"""
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Any, Dict
import re


def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def camel_to_snake(camel_str: str) -> str:
    """Convert camelCase to snake_case"""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_str).lower()


def remove_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove None values from dictionary"""
    return {k: v for k, v in data.items() if v is not None}


def to_naive_utc(dt: datetime) -> datetime:
    """Convert datetime to naive UTC datetime"""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_utc_z(dt: datetime) -> str:
    """Format datetime as UTC ISO 8601 with microseconds and a trailing Z"""
    # タイムゾーンなしの値は DB に格納した UTC の日時なので、UTC として扱う。
    # 楽観的排他制御で取得時の値をそのまま比較できるよう、マイクロ秒は常に 6 桁で出力する
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def to_http_date(dt: datetime) -> str:
    """Format datetime as HTTP-date"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt.astimezone(timezone.utc), usegmt=True)
