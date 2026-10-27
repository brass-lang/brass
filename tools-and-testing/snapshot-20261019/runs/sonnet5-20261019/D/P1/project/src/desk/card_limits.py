"""Per-holder card limits, and who went over theirs in a period."""
from .checks import finance_staff
from .errors import Failure, FailureCode
from .host import Store
from .ids import MONEY_MAX, Badge, Money, Period
from .records import CardLimit, CardStatus
from .registry import Registry


def set_card_limit(store: Store, reg: Registry, finance_badge: Badge, badge: Badge, limit: Money) -> None:
    finance_staff(store, finance_badge)
    holder = store.staff(badge)
    if not 0 <= limit <= MONEY_MAX:
        raise Failure(FailureCode.INVALID_INPUT, "a card limit is 0 to 1,000,000,000 cents")
    reg.save_card_limit(CardLimit(holder.badge, limit))


def over_limit(reg: Registry, period: Period) -> list[Badge]:
    spent: dict[Badge, int] = {}                   # insertion order is first appearance
    for t in reg.txns_for(period):
        if t.status is not CardStatus.DISPUTED:
            spent[t.badge] = spent.get(t.badge, 0) + t.amount
    over = []
    for badge, amount in spent.items():
        try:
            limit = reg.card_limit(badge).limit
        except Failure as f:
            if f.code is not FailureCode.NOT_FOUND:        # no limit set: never over
                raise
            continue
        if amount > limit:
            over.append(badge)
    return over
