import time
from datetime import datetime, timedelta, timezone


def get_offset_from_str(offset_str):
    if not offset_str:
        return 0
    # 解析偏移字符串，例如 "+08:00" 或 "-05:00"
    hours, minutes = map(int, offset_str.split(':'))
    return hours * 60 + minutes


def get_now(timeoffset: int = None) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=timeoffset)


def end_of_date_timestamp(_date: datetime) -> float:
    # 设置时间为当天的 23:59:59
    _date = _date.replace(tzinfo=None)
    end_of_day_local = _date.replace(hour=23, minute=59, second=59, microsecond=999)
    end_of_day_utc = end_of_day_local.astimezone(timezone.utc).timestamp()
    return end_of_day_utc


def parse_date(_date_str: str) -> datetime:
    """
    解析日期字符串，支持格式：250103, 2025-01-03, 2025/01/03
    :param _date_str: 日期字符串
    :return: datetime对象
    :raises ValueError: 当字符串不匹配任何支持的格式时抛出
    """
    formats = [
        "%Y-%m-%d",  # 匹配例如2025-01-03
        "%Y/%m/%d",  # 匹配例如2025/01/03
        "%y%m%d",  # 匹配例如250103（解析为2025-01-03）
    ]
    for fmt in formats:
        try:
            return datetime.strptime(_date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期字符串：'{_date_str}'，不支持该格式。")
