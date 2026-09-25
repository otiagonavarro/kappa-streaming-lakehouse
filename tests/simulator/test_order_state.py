import pytest
from simulator.domain.errors import (
    InvalidTransition,  # pyright: ignore[reportMissingImports]
)
from simulator.domain.order_state import (  # pyright: ignore[reportMissingImports]
    OrderStatus,
    ensure_transition,
)

VALID = [
    (OrderStatus.CREATED, OrderStatus.PAID),
    (OrderStatus.CREATED, OrderStatus.CANCELLED),
    (OrderStatus.PAID, OrderStatus.SHIPPED),
    (OrderStatus.PAID, OrderStatus.CANCELLED),
    (OrderStatus.SHIPPED, OrderStatus.DELIVERED),
    (OrderStatus.DELIVERED, OrderStatus.REFUNDED),
]


@pytest.mark.parametrize(("current", "target"), VALID)
def test_valid_transitions_are_allowed(current, target):
    ensure_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [(c, t) for c in OrderStatus for t in OrderStatus if (c, t) not in VALID],
)
def test_every_other_transition_is_rejected(current, target):
    with pytest.raises(InvalidTransition):
        ensure_transition(current, target)


def test_terminal_states_have_no_exit():
    for terminal in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
        for target in OrderStatus:
            with pytest.raises(InvalidTransition):
                ensure_transition(terminal, target)


def test_accepts_raw_status_strings_from_the_database():
    ensure_transition("created", "paid")
    with pytest.raises(InvalidTransition):
        ensure_transition("delivered", "cancelled")
