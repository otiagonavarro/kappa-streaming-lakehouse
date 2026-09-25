import random
from dataclasses import replace

import pytest
from conftest import fetch_one
from simulator.config import SimConfig
from simulator.usecases import orders, payments, shipments
from simulator.workers.progress import advance_orders

# Every delay is one simulated day = 1 s; tests backdate timestamps instead of sleeping.
BASE = SimConfig(
    seconds_per_day=1.0,
    pay_after_days=1.0,
    ship_after_days=1.0,
    deliver_after_days=1.0,
    refund_after_days=1.0,
    refund_window_days=30.0,
    payment_decline_rate=0.0,
    cancel_rate=0.0,
    refund_rate=0.0,
)


def backdate(conn, table, column, order_id, seconds=3600):
    conn.execute(
        f"UPDATE {table} SET {column} = {column} - make_interval(secs => %s) WHERE order_id = %s",
        (seconds, order_id),
    )


def status(conn, order_id):
    return fetch_one(conn, "SELECT status FROM orders WHERE order_id = %s", order_id)[0]


@pytest.fixture
def order(conn, make_customer, make_product):
    product = make_product(stock=5)
    return orders.place_order(conn, make_customer(), {product: 2}), product


def test_orders_wait_for_their_delay(conn, order):
    order_id, _ = order
    advance_orders(conn, BASE, random.Random(0))
    assert status(conn, order_id) == "created"


def test_happy_path_advances_one_stage_per_elapsed_delay(conn, order):
    order_id, _ = order
    rng = random.Random(0)

    backdate(conn, "orders", "created_at", order_id)
    advance_orders(conn, BASE, rng)
    assert status(conn, order_id) == "paid"

    backdate(conn, "orders", "paid_at", order_id)
    advance_orders(conn, BASE, rng)
    assert status(conn, order_id) == "shipped"

    backdate(conn, "orders", "shipped_at", order_id)
    advance_orders(conn, BASE, rng)
    assert status(conn, order_id) == "delivered"


def test_declined_payment_retries_once_per_delay_then_cancels(conn, order):
    order_id, product = order
    cfg = replace(BASE, payment_decline_rate=1.0, max_payment_attempts=3)
    backdate(conn, "orders", "created_at", order_id)

    for expected_attempts in (1, 2):
        advance_orders(conn, cfg, random.Random(0))
        assert payments.attempts(conn, order_id) == expected_attempts
        assert status(conn, order_id) == "created"
        backdate(conn, "payments", "created_at", order_id)

    advance_orders(conn, cfg, random.Random(0))
    assert payments.attempts(conn, order_id) == 3
    assert status(conn, order_id) == "cancelled"
    assert fetch_one(conn, "SELECT quantity FROM inventory WHERE product_id = %s", product)[0] == 5


def test_cancel_before_shipping_is_decided_per_order(conn, order):
    order_id, _ = order
    payments.pay_order(conn, order_id, "pix")
    backdate(conn, "orders", "paid_at", order_id)

    advance_orders(conn, replace(BASE, cancel_rate=1.0), random.Random(0))
    assert status(conn, order_id) == "cancelled"


def test_refund_only_within_the_window(conn, make_customer, make_product):
    product = make_product(stock=5)
    customer = make_customer()
    ids = []
    for _ in range(2):
        order_id = orders.place_order(conn, customer, {product: 1})
        payments.pay_order(conn, order_id, "pix")
        shipments.ship_order(conn, order_id, "Correios")
        shipments.deliver_order(conn, order_id)
        ids.append(order_id)
    in_window, too_old = ids
    backdate(conn, "orders", "delivered_at", in_window, seconds=5)
    backdate(conn, "orders", "delivered_at", too_old, seconds=3600)

    advance_orders(conn, replace(BASE, refund_rate=1.0), random.Random(0))

    assert status(conn, in_window) == "refunded"
    assert status(conn, too_old) == "delivered"


def test_locked_orders_are_skipped_by_concurrent_workers(conn, second_conn, order):
    order_id, _ = order
    backdate(conn, "orders", "created_at", order_id)

    with second_conn.transaction():
        second_conn.execute("SELECT 1 FROM orders WHERE order_id = %s FOR UPDATE", (order_id,))
        counts = advance_orders(conn, BASE, random.Random(0))
        assert sum(counts.values()) == 0

    assert status(conn, order_id) == "created"


def test_a_fresh_worker_resumes_from_database_state(second_conn, conn, order):
    """No in-memory state: a worker on a new connection (e.g. after a restart) picks up pending orders."""
    order_id, _ = order
    backdate(conn, "orders", "created_at", order_id)

    counts = advance_orders(second_conn, BASE, random.Random(0))

    assert counts["paid"] == 1
    assert status(conn, order_id) == "paid"
