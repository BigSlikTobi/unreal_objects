"""Tests for CompanyScheduler interval computation and case creation."""

from datetime import datetime
from unittest.mock import MagicMock

from company_server.clock import CompanyClock
from company_server.config import CompanyConfig
from company_server.scheduler import CompanyScheduler
from company_server.state import CompanyState
from company_server.webhooks import WebhookDispatcher


def _make_scheduler(acceleration=10.0, base_rate=5.0, virtual_start=None):
    config = CompanyConfig(
        acceleration=acceleration,
        base_cases_per_hour=base_rate,
        ai_api_key="",
    )
    clock = CompanyClock(
        acceleration=acceleration,
        virtual_start=virtual_start or datetime(2026, 1, 5, 12, 0, 0),
    )
    clock.real_start = datetime.now()
    state = CompanyState()
    webhook = WebhookDispatcher()
    return CompanyScheduler(config=config, state=state, clock=clock, webhook=webhook, use_ai=False)


def test_interval_peak_hours():
    scheduler = _make_scheduler(acceleration=10.0, base_rate=5.0)
    # During peak (multiplier=1.0): 3600 / (5 * 10 * 1.0) = 72 seconds
    interval = scheduler._compute_interval()
    # Allow jitter range: 72 +/- 20%
    assert 50 < interval < 95


def test_interval_night():
    scheduler = _make_scheduler(
        acceleration=10.0, base_rate=5.0,
        virtual_start=datetime(2026, 1, 5, 3, 0, 0),  # 3am Monday
    )
    # Night multiplier=0.1: 3600 / (5 * 10 * 0.1) = 720 seconds
    interval = scheduler._compute_interval()
    assert 550 < interval < 900


def test_interval_weekend():
    scheduler = _make_scheduler(
        acceleration=10.0, base_rate=5.0,
        virtual_start=datetime(2026, 1, 3, 12, 0, 0),  # Saturday
    )
    # Weekend multiplier=0.05: 3600 / (5 * 10 * 0.05) = 1440 seconds
    interval = scheduler._compute_interval()
    assert 1100 < interval < 1800


def test_no_ai_uses_deterministic():
    scheduler = _make_scheduler()
    assert scheduler.ai_generator is None


def test_stop():
    scheduler = _make_scheduler()
    scheduler._running = True
    scheduler.stop()
    assert scheduler._running is False
