from datetime import datetime
import pytz


def create_timezone(offset_str):
    if not offset_str:
        return pytz.timezone('UTC')
    # 解析偏移字符串，例如 "+08:00" 或 "-05:00"
    hours, minutes = map(int, offset_str.split(':'))
    total_offset = hours * 60 + minutes
    return pytz.FixedOffset(total_offset)


def get_now(timezone: str = None) -> datetime:
    return datetime.now(create_timezone(timezone))
