"""Accelerated virtual time engine for the living company."""

from datetime import datetime, timedelta


class CompanyClock:
    """Tracks virtual company time at an accelerated rate.

    Default 10x: 1 real second = 10 virtual seconds.
    """

    def __init__(
        self,
        acceleration: float = 10.0,
        virtual_start: datetime | None = None,
    ):
        self.acceleration = acceleration
        self.real_start = datetime.now()
        self.virtual_start = virtual_start or datetime(2026, 1, 5, 9, 0, 0)

    def now(self) -> datetime:
        elapsed = datetime.now() - self.real_start
        virtual_elapsed = timedelta(seconds=elapsed.total_seconds() * self.acceleration)
        return self.virtual_start + virtual_elapsed

    def is_business_hours(self) -> bool:
        vt = self.now()
        weekday = vt.weekday()  # 0=Mon, 6=Sun
        if weekday >= 5:
            return False
        return 9 <= vt.hour < 17

    def activity_multiplier(self) -> float:
        vt = self.now()
        weekday = vt.weekday()
        hour = vt.hour

        if weekday >= 5:
            return 0.05

        if 9 <= hour < 17:
            return 1.0
        elif 17 <= hour < 22:
            return 0.3
        else:
            return 0.1
