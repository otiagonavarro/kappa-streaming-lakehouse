"""Background workers that move orders through their lifecycle.

All progression state lives in Postgres, so a restarted simulator resumes where it
stopped. Each order is advanced in its own transaction, claimed with
FOR UPDATE SKIP LOCKED so concurrent workers never double-process an order.
Per-order decisions (cancel, refund) are a deterministic hash of the order id:
they do not depend on how often a worker polls.
"""
import random
from collections import Counter
from collections.abc import Callable

import psycopg  # pyright: ignore[reportMissingImports]

from ..config import SimConfig
from ..usecases import orders, payments, shipments

CARRIERS = ["Correios", "Jadlog", "Loggi", "Total Express"]
PAYMENT_METHODS = ["pix", "credit_card", "boleto"]
PAYMENT_WEIGHTS = [0.45, 0.45, 0.10]


def _bucket(salt: str) -> str:
    """SQL expression: a stable uniform value in [0, 1) per order and decision."""
    return f"(('x' || substr(md5(o.order_id::text || '{salt}'), 1, 8))::bit(32)::bigint / 4294967296.0)"


def advance_orders(conn: psycopg.Connection, cfg: SimConfig, rng: random.Random, batch: int = 50) -> Counter:
    counts: Counter = Counter()

    def pay_step(order_id, _bucket_value):
        tried = payments.attempts(conn, order_id)
        method = rng.choices(PAYMENT_METHODS, PAYMENT_WEIGHTS)[0]
        if rng.random() >= cfg.payment_decline_rate:
            payments.pay_order(conn, order_id, method)
            return "paid"
        payments.fail_payment(conn, order_id, method)
        if tried + 1 >= cfg.max_payment_attempts:
            orders.cancel_order(conn, order_id)
            return "cancelled"
        return "declined"

    def ship_step(order_id, cancel_bucket):
        if cancel_bucket < cfg.cancel_rate:
            orders.cancel_order(conn, order_id)
            return "cancelled"
        shipments.ship_order(conn, order_id, rng.choice(CARRIERS))
        return "shipped"

    def deliver_step(order_id, _bucket_value):
        shipments.deliver_order(conn, order_id)
        return "delivered"

    def refund_step(order_id, _bucket_value):
        orders.refund_order(conn, order_id)
        return "refunded"

    last_attempt = "coalesce((SELECT max(p.created_at) FROM payments p WHERE p.order_id = o.order_id), o.created_at)"
    stages = [
        ("created", f"{last_attempt} < now() - %(pay)s", "0", pay_step),
        ("paid", "o.paid_at < now() - %(ship)s", _bucket("cancel"), ship_step),
        ("shipped", "o.shipped_at < now() - %(deliver)s", "0", deliver_step),
        (
            "delivered",
            (
                "o.delivered_at < now() - %(refund)s AND o.delivered_at > now() - %(window)s "
                f"AND {_bucket('refund')} < %(refund_rate)s"
            ),
            "0",
            refund_step,
        ),
    ]
    params = {
        "pay": cfg.delay(cfg.pay_after_days),
        "ship": cfg.delay(cfg.ship_after_days),
        "deliver": cfg.delay(cfg.deliver_after_days),
        "refund": cfg.delay(cfg.refund_after_days),
        "window": cfg.delay(cfg.refund_window_days),
        "refund_rate": cfg.refund_rate,
    }
    for status, due, bucket_sql, step in stages:
        _drain(conn, status, due, bucket_sql, params, step, batch, counts)
    return counts


def _drain(conn, status, due, bucket_sql, params, step: Callable, batch: int, counts: Counter) -> None:
    query = (
        f"SELECT o.order_id, {bucket_sql} FROM orders o WHERE o.status = %(status)s AND {due} "
        "ORDER BY o.updated_at LIMIT 1 FOR UPDATE SKIP LOCKED"
    )
    for _ in range(batch):
        with conn.transaction():
            row = conn.execute(query, {**params, "status": status}).fetchone()
            if row is None:
                return
            counts[step(row[0], float(row[1]))] += 1
