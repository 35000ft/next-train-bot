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
