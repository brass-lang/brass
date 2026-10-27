from dataclasses import dataclass
from typing import Sequence

from .ids import Category, Money

MAX_LINES = 50


@dataclass(frozen=True)
class Line:
    category: Category
    amount: Money
    description: str
    receipt: bool


@dataclass(frozen=True)
class Policy:
    limit: Money
    receipt_over: Money
    budgeted: bool


POLICIES = {
    Category.FEED: Policy(200_000, 2_500, True),
    Category.VETERINARY: Policy(500_000, 2_500, True),
    Category.CONTAINMENT: Policy(1_000_000, 5_000, True),
    Category.EQUIPMENT: Policy(300_000, 2_500, True),
    Category.TRAVEL: Policy(150_000, 2_500, True),
    Category.OTHER: Policy(50_000, 2_500, True),
}


def policy_for(category: Category) -> Policy:
    return POLICIES[category]


def line_valid(line: Line) -> bool:
    policy = policy_for(line.category)
    return line.amount <= policy.limit and (line.amount <= policy.receipt_over or line.receipt)


def all_valid(lines: Sequence[Line]) -> bool:
    return 1 <= len(lines) <= MAX_LINES and all(line_valid(l) for l in lines)


def total(lines: Sequence[Line]) -> int:
    return sum(l.amount for l in lines)


def budgeted_total(lines: Sequence[Line]) -> int:
    return sum(l.amount for l in lines if policy_for(l.category).budgeted)
