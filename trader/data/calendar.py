# trader/data/calendar.py
from __future__ import annotations
from datetime import datetime, timedelta

def trading_days(start: datetime, end: datetime) -> list[datetime]:
    """주말 제외 일별 시퀀스. (휴장일은 Phase 1 stub — 후속 exchange-calendars로 대체)"""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5: out.append(d)
        d += timedelta(days=1)
    return out
