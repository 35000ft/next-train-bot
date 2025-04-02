from datetime import datetime, timedelta, timezone


def get_offset_from_str(offset_str):
    if not offset_str:
        return 0
    # 解析偏移字符串，例如 "+08:00" 或 "-05:00"
    hours, minutes = map(int, offset_str.split(':'))
    return hours * 60 + minutes


def get_now(timeoffset: int = None) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=timeoffset)
