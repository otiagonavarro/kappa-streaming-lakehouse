"""Order use cases and the shared status-transition helper."""
from decimal import Decimal

import psycopg  # pyright: ignore[reportMissingImports]

from ..domain.errors import DomainError, NotFound, OutOfStock, ProductUnavailable
from ..domain.order_state import TIMESTAMP_COLUMN, OrderStatus, ensure_transition


def place_order(conn: psycopg.Connection, customer_id, items: dict, *, session_id=None):
    """Create an order with its items and reserve stock, atomically.

    `items` maps product_id → quantity. Inventory rows are locked in a stable
    order so concurrent checkouts cannot deadlock.
    """
    if not items or any(qty <= 0 for qty in items.values()):
        raise DomainError("an order needs at least one item with positive quantity")

    with conn.transaction():
        order_id = _create_order_and_reserve_stock(conn, customer_id, items, session_id)
    return order_id


def _create_order_and_reserve_stock(conn, customer_id, items, session_id):
    customer = conn.execute("SELECT status FROM customers WHERE customer_id = %s", (customer_id,)).fetchone()
    if customer is None:
        raise NotFound(f"customer {customer_id}")
    if customer[0] != "active":
        raise DomainError(f"customer {customer_id} is {customer[0]}")

    lines = []
    for product_id in sorted(items, key=str):
        row = conn.execute(
            "SELECT p.price, p.status, i.quantity FROM products p JOIN inventory i USING (product_id) "
            "WHERE p.product_id = %s FOR UPDATE OF i",
            (product_id,),
        ).fetchone()
        if row is None:
            raise NotFound(f"product {product_id}")
        price, product_status, in_stock = row
        if product_status != "active":
            raise ProductUnavailable(f"product {product_id} is {product_status}")
        if in_stock < items[product_id]:
            raise OutOfStock(f"product {product_id}: {in_stock} in stock, {items[product_id]} requested")
        lines.append((product_id, items[product_id], price, price * items[product_id]))

    total = sum((line_total for *_, line_total in lines), Decimal(0))
    (result,) = conn.execute(
        "INSERT INTO orders (customer_id, session_id, total) VALUES (%s, %s, %s) RETURNING order_id",
        (customer_id, session_id, total),
    ).fetchone()
    for product_id, quantity, unit_price, line_total in lines:
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total) "
            "VALUES (%s, %s, %s, %s, %s)",
            (result, product_id, quantity, unit_price, line_total),
        )
        conn.execute(
            "UPDATE inventory SET quantity = quantity - %s, updated_at = now() WHERE product_id = %s",
            (quantity, product_id),
        )
    return result


def cancel_order(conn: psycopg.Connection, order_id):
    """Cancel before shipping and return the reserved stock."""
    with conn.transaction():
        transition(conn, order_id, OrderStatus.CANCELLED)
        conn.execute(
            "UPDATE inventory i SET quantity = i.quantity + oi.quantity, updated_at = now() "
            "FROM order_items oi WHERE oi.order_id = %s AND i.product_id = oi.product_id",
            (order_id,),
        )


def refund_order(conn: psycopg.Connection, order_id):
    """Refund after delivery. Goods are not restocked."""
    with conn.transaction():
        transition(conn, order_id, OrderStatus.REFUNDED)


def transition(conn: psycopg.Connection, order_id, target: OrderStatus) -> Decimal:
    """Lock the order, validate the move and stamp the status timestamp. Returns the order total.

    Must run inside the caller's transaction.
    """
    row = conn.execute("SELECT status, total FROM orders WHERE order_id = %s FOR UPDATE", (order_id,)).fetchone()
    if row is None:
        raise NotFound(f"order {order_id}")
    current, total = row
    ensure_transition(current, target)
    column = TIMESTAMP_COLUMN[target]
    conn.execute(
        f"UPDATE orders SET status = %s, {column} = now(), updated_at = now() WHERE order_id = %s",
        (target.value, order_id),
    )
    return total
