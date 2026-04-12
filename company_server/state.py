"""In-memory company state: customers, orders, and support cases."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from support_company.models import CaseStatus, SupportCase


def _id() -> str:
    return str(uuid.uuid4())


class Customer(BaseModel):
    id: str = Field(default_factory=_id)
    name: str
    email: str
    tier: str = "basic"
    account_age_days: int = 365
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Order(BaseModel):
    id: str = Field(default_factory=_id)
    customer_id: str
    total: float
    status: str = "delivered"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


FIRST_NAMES = [
    "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
    "Ivy", "Jack", "Karen", "Leo", "Mia", "Noah", "Olivia", "Paul",
    "Quinn", "Rachel", "Sam", "Tina",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
]
TIERS = ["basic", "basic", "basic", "premium", "premium", "enterprise"]


class CompanyState:
    def __init__(self, max_cases: int = 5000):
        self.customers: dict[str, Customer] = {}
        self.orders: dict[str, Order] = {}
        self.cases: dict[str, SupportCase] = {}
        self.max_cases = max_cases

    def seed_customers(self, count: int = 20, seed: int = 42) -> None:
        rng = random.Random(seed)
        for _ in range(count):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            tier = rng.choice(TIERS)
            age = rng.randint(30, 2000)
            c = Customer(
                name=f"{first} {last}",
                email=f"{first.lower()}.{last.lower()}@example.com",
                tier=tier,
                account_age_days=age,
            )
            self.customers[c.id] = c

    def seed_orders(self, count: int = 50, seed: int = 42) -> None:
        rng = random.Random(seed)
        customer_ids = list(self.customers.keys())
        if not customer_ids:
            return
        for _ in range(count):
            cid = rng.choice(customer_ids)
            total = round(rng.uniform(15, 2500), 2)
            status = rng.choice(["delivered", "delivered", "shipped", "processing", "returned"])
            days_ago = rng.randint(1, 365)
            o = Order(
                customer_id=cid,
                total=total,
                status=status,
                created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            )
            self.orders[o.id] = o

    def add_case(self, case: SupportCase) -> SupportCase:
        self.cases[case.case_id] = case
        self._evict_if_needed()
        return case

    def _evict_if_needed(self) -> None:
        if len(self.cases) <= self.max_cases:
            return
        resolved = [
            cid for cid, c in self.cases.items()
            if c.status == CaseStatus.RESOLVED
        ]
        for cid in resolved:
            del self.cases[cid]
            if len(self.cases) <= self.max_cases:
                return
        # If still over limit after removing all resolved, drop oldest entries
        while len(self.cases) > self.max_cases:
            oldest_key = next(iter(self.cases))
            del self.cases[oldest_key]

    def get_open_cases(self) -> list[SupportCase]:
        return [c for c in self.cases.values() if c.status == CaseStatus.OPEN]

    def get_assigned_cases(self) -> list[SupportCase]:
        return [c for c in self.cases.values() if c.status == CaseStatus.ASSIGNED]

    def assign_case(self, case_id: str, bot_id: str) -> SupportCase | None:
        case = self.cases.get(case_id)
        if case and case.status == CaseStatus.OPEN:
            case.assigned_to = bot_id
            case.status = CaseStatus.ASSIGNED
            return case
        return None

    def resolve_case(self, case_id: str, resolution: str) -> SupportCase | None:
        case = self.cases.get(case_id)
        if case and case.status == CaseStatus.ASSIGNED:
            case.resolution = resolution
            case.status = CaseStatus.RESOLVED
            return case
        return None

    def get_customer_history(self, customer_id: str) -> dict:
        customer = self.customers.get(customer_id)
        if not customer:
            return {}

        customer_orders = [o for o in self.orders.values() if o.customer_id == customer_id]
        customer_cases = [c for c in self.cases.values() if c.customer_id == customer_id]

        return {
            "name": customer.name,
            "tier": customer.tier,
            "account_age_days": customer.account_age_days,
            "total_orders": len(customer_orders),
            "total_order_value": sum(o.total for o in customer_orders),
            "previous_cases": len(customer_cases),
        }

    def stats(self) -> dict:
        return {
            "total_customers": len(self.customers),
            "total_orders": len(self.orders),
            "total_cases": len(self.cases),
            "open_cases": len(self.get_open_cases()),
            "assigned_cases": len(self.get_assigned_cases()),
            "resolved_cases": len([c for c in self.cases.values() if c.status == CaseStatus.RESOLVED]),
        }
