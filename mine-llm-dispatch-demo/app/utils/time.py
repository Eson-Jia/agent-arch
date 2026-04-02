from datetime import datetime
from zoneinfo import ZoneInfo


def now_ts(timezone_name: str = "Asia/Shanghai") -> datetime:
    return datetime.now(ZoneInfo(timezone_name))
