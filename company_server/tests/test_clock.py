"""Tests for the CompanyClock time engine."""

from datetime import datetime, timedelta

from company_server.clock import CompanyClock


def test_now_advances_at_acceleration():
    clock = CompanyClock(acceleration=10.0, virtual_start=datetime(2026, 1, 5, 9, 0, 0))
    # Virtual time should be close to virtual_start right after creation
    vt = clock.now()
    assert vt.year == 2026
    assert vt.month == 1
    assert vt.day == 5


def test_acceleration_multiplies_elapsed():
    start = datetime(2026, 6, 1, 12, 0, 0)
    clock = CompanyClock(acceleration=10.0, virtual_start=start)
    # Manually set real_start to simulate elapsed time
    clock.real_start = datetime.now() - timedelta(seconds=360)  # 6 real minutes
    vt = clock.now()
    # 360 real seconds * 10x = 3600 virtual seconds = 1 virtual hour
    expected = start + timedelta(hours=1)
    diff = abs((vt - expected).total_seconds())
    assert diff < 5  # Allow small timing margin


def test_business_hours_weekday_9_to_17():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 12, 0, 0))  # Monday noon
    clock.real_start = datetime.now()  # Effectively now = virtual_start
    assert clock.is_business_hours() is True


def test_not_business_hours_weekend():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 3, 12, 0, 0))  # Saturday noon
    clock.real_start = datetime.now()
    assert clock.is_business_hours() is False


def test_not_business_hours_evening():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 20, 0, 0))  # Monday 8pm
    clock.real_start = datetime.now()
    assert clock.is_business_hours() is False


def test_activity_multiplier_peak():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 12, 0, 0))  # Monday noon
    clock.real_start = datetime.now()
    assert clock.activity_multiplier() == 1.0


def test_activity_multiplier_evening():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 19, 0, 0))  # Monday 7pm
    clock.real_start = datetime.now()
    assert clock.activity_multiplier() == 0.3


def test_activity_multiplier_night():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 3, 0, 0))  # Monday 3am
    clock.real_start = datetime.now()
    assert clock.activity_multiplier() == 0.1


def test_activity_multiplier_weekend():
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 3, 12, 0, 0))  # Saturday
    clock.real_start = datetime.now()
    assert clock.activity_multiplier() == 0.05
