"""Payment use cases. Every attempt is a row; only an approved one moves the order to paid."""
import psycopg  # pyright: ignore[reportMissingImports]

from ..domain.errors import InvalidTransition, NotFound
from ..domain.order_state import OrderStatus
from .orders import transition


def pay_order(conn: psycopg.Connection, order_id, method: str):
    with conn.transaction():
        total = transition(conn, order_id, OrderStatus.PAID)
        return _record_attempt(conn, order_id, method, total, "approved")


def fail_payment(conn: psycopg.Connection, order_id, method: str):
    with conn.transaction():
        row = conn.execute("SELECT status, total FROM orders WHERE order_id = %s FOR UPDATE", (order_id,)).fetchone()
        if row is None:
            raise NotFound(f"order {order_id}")
        if row[0] != OrderStatus.CREATED.value:
            raise InvalidTransition(f"cannot attempt payment on a {row[0]} order")
        return _record_attempt(conn, order_id, method, row[1], "declined")


def attempts(conn: psycopg.Connection, order_id) -> int:
    return conn.execute("SELECT count(*) FROM payments WHERE order_id = %s", (order_id,)).fetchone()[0]


def _record_attempt(conn, order_id, method: str, amount, status: str):
    (payment_id,) = conn.execute(
        "INSERT INTO payments (order_id, attempt, method, amount, status) "
        "VALUES (%s, (SELECT count(*) + 1 FROM payments WHERE order_id = %s), %s, %s, %s) RETURNING payment_id",
        (order_id, order_id, method, amount, status),
    ).fetchone()
    return payment_id
