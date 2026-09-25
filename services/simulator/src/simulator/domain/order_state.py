"""Order lifecycle: created → paid → shipped → delivered, with cancel/refund branches."""
from enum import Enum

from .errors import InvalidTransition


class OrderStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}

# Column stamped when an order enters each status (created_at is set on insert).
TIMESTAMP_COLUMN: dict[OrderStatus, str] = {
    OrderStatus.PAID: "paid_at",
    OrderStatus.SHIPPED: "shipped_at",
    OrderStatus.DELIVERED: "delivered_at",
    OrderStatus.CANCELLED: "cancelled_at",
    OrderStatus.REFUNDED: "refunded_at",
}


def ensure_transition(current: OrderStatus | str, target: OrderStatus | str) -> None:
    current, target = OrderStatus(current), OrderStatus(target)
    if target not in _TRANSITIONS[current]:
        raise InvalidTransition(f"order cannot go from {current.value} to {target.value}")
