from datetime import UTC, datetime
from itertools import count


_COUNTERS: dict[str, count] = {}


def _next(prefix: str) -> int:
    if prefix not in _COUNTERS:
        _COUNTERS[prefix] = count(1)
    return next(_COUNTERS[prefix])


def generate_id(prefix: str, ts: datetime | None = None) -> str:
    timestamp = ts or datetime.now(UTC)
    return f"{prefix}-{timestamp:%Y%m%d}-{_next(prefix):04d}"
