from calendar import monthrange
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def local_today(now: datetime | None = None) -> date:
    return (now or utc_now()).astimezone(SAO_PAULO).date()


def anniversary(anchor: date, index: int) -> date:
    if index < 0:
        raise ValueError("O índice do ciclo não pode ser negativo.")
    total_months = anchor.year * 12 + anchor.month - 1 + index
    year, month_zero = divmod(total_months, 12)
    month = month_zero + 1
    return date(year, month, min(anchor.day, monthrange(year, month)[1]))


def boundaries(anchor: date, index: int) -> tuple[datetime, datetime]:
    return tuple(
        datetime.combine(
            anniversary(anchor, i), datetime.min.time(), SAO_PAULO
        ).astimezone(timezone.utc)
        for i in (index, index + 1)
    )
