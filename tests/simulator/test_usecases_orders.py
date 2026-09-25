import uuid
from decimal import Decimal

import pytest
from conftest import fetch_one
from simulator.domain.errors import (  # pyright: ignore[reportMissingImports]
    DomainError,
    InvalidTransition,
    OutOfStock,
    ProductUnavailable,
)
from simulator.usecases import (  # pyright: ignore[reportMissingImports]
    catalog,
    customers,
    orders,
    payments,
    shipments,
)


def stock(conn, product_id):
    return fetch_one(conn, "SELECT quantity FROM inventory WHERE product_id = %s", product_id)[0]


def status(conn, order_id):
    return fetch_one(conn, "SELECT status FROM orders WHERE order_id = %s", order_id)[0]


@pytest.fixture
def shop(make_customer, make_product):
    return {
        "customer": make_customer(),
        "a": make_product(price="10.00", stock=5),
        "b": make_product(price="2.50", stock=5),
    }


def test_place_order_writes_items_total_and_decrements_stock(conn, shop):
    session_id = uuid.uuid4()
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 2, shop["b"]: 3}, session_id=session_id)

    assert fetch_one(conn, "SELECT status, total, session_id FROM orders WHERE order_id = %s", order_id) == (
        "created",
        Decimal("27.50"),
        session_id,
    )
    items = conn.execute(
        "SELECT quantity, unit_price, line_total FROM order_items WHERE order_id = %s ORDER BY line_total", (order_id,)
    ).fetchall()
    assert items == [(3, Decimal("2.50"), Decimal("7.50")), (2, Decimal("10.00"), Decimal("20.00"))]
    assert (stock(conn, shop["a"]), stock(conn, shop["b"])) == (3, 2)


def test_place_order_is_atomic_on_stockout(conn, shop):
    with pytest.raises(OutOfStock):
        orders.place_order(conn, shop["customer"], {shop["a"]: 1, shop["b"]: 6})

    assert fetch_one(conn, "SELECT count(*) FROM orders")[0] == 0
    assert fetch_one(conn, "SELECT count(*) FROM order_items")[0] == 0
    assert (stock(conn, shop["a"]), stock(conn, shop["b"])) == (5, 5)


def test_place_order_rejects_discontinued_product(conn, shop):
    catalog.discontinue_product(conn, shop["a"])
    with pytest.raises(ProductUnavailable):
        orders.place_order(conn, shop["customer"], {shop["a"]: 1})


def test_place_order_rejects_empty_cart_and_deleted_customer(conn, shop):
    with pytest.raises(DomainError):
        orders.place_order(conn, shop["customer"], {})
    conn.execute("UPDATE customers SET status = 'deleted' WHERE customer_id = %s", (shop["customer"],))
    with pytest.raises(DomainError):
        orders.place_order(conn, shop["customer"], {shop["a"]: 1})


@pytest.mark.parametrize("pay_first", [False, True])
def test_cancel_restocks_before_shipping(conn, shop, pay_first):
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 2})
    if pay_first:
        payments.pay_order(conn, order_id, "pix")

    orders.cancel_order(conn, order_id)

    assert status(conn, order_id) == "cancelled"
    assert fetch_one(conn, "SELECT cancelled_at IS NOT NULL FROM orders WHERE order_id = %s", order_id) == (True,)
    assert stock(conn, shop["a"]) == 5


def test_cannot_cancel_after_shipping(conn, shop):
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 1})
    payments.pay_order(conn, order_id, "pix")
    shipments.ship_order(conn, order_id, "Correios")
    with pytest.raises(InvalidTransition):
        orders.cancel_order(conn, order_id)


def test_full_lifecycle_and_refund_does_not_restock(conn, shop):
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 2})
    payments.pay_order(conn, order_id, "credit_card")
    shipments.ship_order(conn, order_id, "Correios")
    shipments.deliver_order(conn, order_id)
    orders.refund_order(conn, order_id)

    row = fetch_one(
        conn,
        "SELECT status, paid_at <= shipped_at, shipped_at <= delivered_at, refunded_at IS NOT NULL "
        "FROM orders WHERE order_id = %s",
        order_id,
    )
    assert row == ("refunded", True, True, True)
    assert fetch_one(conn, "SELECT delivered_at IS NOT NULL FROM shipments WHERE order_id = %s", order_id) == (True,)
    assert stock(conn, shop["a"]) == 3


def test_declined_payment_keeps_order_created_and_counts_attempts(conn, shop):
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 1})

    payments.fail_payment(conn, order_id, "credit_card")
    assert status(conn, order_id) == "created"

    payments.pay_order(conn, order_id, "pix")
    rows = conn.execute(
        "SELECT attempt, status, amount FROM payments WHERE order_id = %s ORDER BY attempt", (order_id,)
    ).fetchall()
    assert rows == [(1, "declined", Decimal("10.00")), (2, "approved", Decimal("10.00"))]
    assert status(conn, order_id) == "paid"


def test_cannot_pay_twice_or_ship_unpaid(conn, shop):
    order_id = orders.place_order(conn, shop["customer"], {shop["a"]: 1})
    with pytest.raises(InvalidTransition):
        shipments.ship_order(conn, order_id, "Correios")
    payments.pay_order(conn, order_id, "pix")
    with pytest.raises(InvalidTransition):
        payments.pay_order(conn, order_id, "pix")


def test_checkout_blocks_a_concurrent_erasure_of_the_same_customer(conn, second_conn, shop):
    """place_order holds a share lock on the customer, so forget_customer cannot slip in between
    the status check and the order insert."""
    import psycopg

    with conn.transaction():
        orders.place_order(conn, shop["customer"], {shop["a"]: 1})
        second_conn.execute("SET lock_timeout = '200ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            customers.forget_customer(second_conn, shop["customer"])
